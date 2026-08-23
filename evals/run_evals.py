#!/usr/bin/env python3
"""Run all Property Scout AI evaluation suites and print a summary report."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = REPO_ROOT / "apps" / "api"
EVALS_ROOT = REPO_ROOT / "evals"
DEFAULT_REPORT_DIR = EVALS_ROOT / "reports"

sys.path.insert(0, str(API_ROOT))
sys.path.insert(0, str(REPO_ROOT))

import pytest  # noqa: E402

from evals.lib.report import clear_results, write_reports  # noqa: E402


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Property Scout AI eval suites.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_REPORT_DIR,
        help=f"Directory for downloadable reports (default: {DEFAULT_REPORT_DIR})",
    )
    parser.add_argument(
        "--format",
        choices=("json", "md", "both"),
        default="both",
        help="Downloadable report format (default: both)",
    )
    parser.add_argument(
        "--no-timestamp",
        action="store_true",
        help="Skip writing timestamped report copies",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    clear_results()
    pytest_args = [
        str(EVALS_ROOT),
        "-q",
        "--tb=short",
        "-p",
        "no:warnings",
    ]
    exit_code = pytest.main(pytest_args)

    formats: tuple[str, ...]
    if args.format == "both":
        formats = ("json", "md")
    else:
        formats = (args.format,)

    written = write_reports(
        args.output_dir,
        formats=formats,
        timestamped=not args.no_timestamp,
    )
    if written:
        print("\nDownloadable reports:")
        for label, path in written.items():
            if label.endswith("_stamped"):
                continue
            print(f"  {path}")

    return int(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
