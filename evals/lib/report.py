"""Collect eval case outcomes and print a human-readable summary."""

from __future__ import annotations

import functools
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path


@dataclass
class EvalResult:
    category: str
    name: str
    passed: bool
    detail: str = ""


@dataclass
class EvalReport:
    results: list[EvalResult] = field(default_factory=list)

    def record(self, category: str, name: str, passed: bool, detail: str = "") -> None:
        self.results.append(EvalResult(category, name, passed, detail))

    def clear(self) -> None:
        self.results.clear()

    @property
    def passed_count(self) -> int:
        return sum(1 for result in self.results if result.passed)

    @property
    def total_count(self) -> int:
        return len(self.results)

    @property
    def all_passed(self) -> bool:
        return self.total_count > 0 and self.passed_count == self.total_count

    def categories(self) -> dict[str, list[EvalResult]]:
        grouped: dict[str, list[EvalResult]] = {}
        for result in self.results:
            grouped.setdefault(result.category, []).append(result)
        return grouped

    def to_dict(self) -> dict:
        generated_at = datetime.now(UTC).isoformat()
        return {
            "title": "Property Scout AI Evaluation Results",
            "generated_at": generated_at,
            "summary": {
                "passed": self.passed_count,
                "total": self.total_count,
                "status": "PASS" if self.all_passed else "FAIL",
            },
            "categories": [
                {
                    "name": category,
                    "passed": sum(1 for item in items if item.passed),
                    "total": len(items),
                    "cases": [asdict(item) for item in items],
                }
                for category, items in self.categories().items()
            ],
        }

    def to_markdown(self) -> str:
        payload = self.to_dict()
        lines = [
            f"# {payload['title']}",
            "",
            f"- **Generated:** {payload['generated_at']}",
            f"- **Overall:** {payload['summary']['passed']}/{payload['summary']['total']} {payload['summary']['status']}",
            "",
        ]
        for category in payload["categories"]:
            lines.append(f"## {category['name']}")
            lines.append("")
            lines.append(f"_{category['passed']}/{category['total']} passed_")
            lines.append("")
            for case in category["cases"]:
                mark = "PASS" if case["passed"] else "FAIL"
                lines.append(f"- [{mark}] {case['name']}")
                if not case["passed"] and case["detail"]:
                    lines.append(f"  - {case['detail']}")
            lines.append("")
        return "\n".join(lines).strip() + "\n"

    def print_summary(self) -> None:
        if not self.results:
            print("AI EVALUATION RESULTS\n\nNo eval cases recorded.")
            return

        print("AI EVALUATION RESULTS\n")
        for category, items in self.categories().items():
            print(category)
            for item in items:
                mark = "✓" if item.passed else "✗"
                print(f"{mark} {item.name}")
                if not item.passed and item.detail:
                    print(f"  → {item.detail}")
            print()

        print(f"Overall: {self.passed_count}/{self.total_count} PASS")


REPORT = EvalReport()


def clear_results() -> None:
    REPORT.clear()


def record(category: str, name: str, passed: bool, detail: str = "") -> None:
    REPORT.record(category, name, passed, detail)


def print_report() -> None:
    REPORT.print_summary()


def write_reports(
    output_dir: Path,
    *,
    formats: tuple[str, ...] = ("json", "md"),
    timestamped: bool = True,
) -> dict[str, Path]:
    """Write downloadable report files; returns paths keyed by format."""
    output_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

    if "json" in formats:
        latest = output_dir / "evals-report.json"
        latest.write_text(json.dumps(REPORT.to_dict(), indent=2) + "\n", encoding="utf-8")
        written["json"] = latest
        if timestamped:
            stamped = output_dir / f"evals-report-{stamp}.json"
            stamped.write_text(latest.read_text(encoding="utf-8"), encoding="utf-8")
            written["json_stamped"] = stamped

    if "md" in formats:
        latest = output_dir / "evals-report.md"
        latest.write_text(REPORT.to_markdown(), encoding="utf-8")
        written["md"] = latest
        if timestamped:
            stamped = output_dir / f"evals-report-{stamp}.md"
            stamped.write_text(latest.read_text(encoding="utf-8"), encoding="utf-8")
            written["md_stamped"] = stamped

    return written


def eval_case(category: str, name: str):
    """Decorator that records pass/fail for the eval summary report."""

    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                fn(*args, **kwargs)
                record(category, name, True)
            except AssertionError as exc:
                record(category, name, False, str(exc))
                raise

        return wrapper

    return decorator
