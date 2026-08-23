from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[3]
_API_ROOT = Path(__file__).resolve().parents[1]


def _env_file_paths() -> tuple[str, ...]:
    paths = [_REPO_ROOT / ".env", _API_ROOT / ".env", Path(".env")]
    resolved = tuple(str(path) for path in paths if path.is_file())
    return resolved or (".env",)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_env_file_paths(),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:3000"

    gemini_api_key: str = ""
    llm_model: str = "gemini-2.5-flash-native-audio-preview-12-2025"
    gemini_tts_model: str = "gemini-2.5-flash-preview-tts"
    gemini_voice: str = "Charon"
    llm_temperature: float = 0.2
    llm_confidence_threshold: float = 0.6

    # Optional n8n webhook for shortlist PDF email (Phase 7)
    n8n_webhook_url: str = ""

    # Empty → SQLite under data/property_scout.db
    # Vercel: postgresql+psycopg://USER:PASS@HOST/DB?sslmode=require
    database_url: str = ""

    # Redis for durable sessions on Vercel (empty → in-memory for local)
    redis_url: str = ""
    session_ttl_seconds: int = 60 * 60 * 24

    # overpass | static | live (live = overpass)
    osm_mode: str = "overpass"

    # Allow https://*.vercel.app Preview deployments
    cors_allow_vercel_previews: bool = False

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def cors_origin_regex(self) -> str | None:
        if self.cors_allow_vercel_previews:
            return r"https://.*\.vercel\.app"
        return None


@lru_cache
def get_settings() -> Settings:
    return Settings()
