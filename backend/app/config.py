import os
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _path(name: str, default: str) -> Path:
    path = Path(os.getenv(name) or default)
    return path if path.is_absolute() else ROOT / path


class Settings:
    db_path = _path("SHIPYARD_DB_PATH", "database/shipyard.db")
    file_dir = _path("SHIPYARD_FILE_DIR", "storage/drawings")
    app_secret = os.getenv("APP_SECRET") or secrets.token_hex(32)
    token_ttl = int(os.getenv("TOKEN_TTL") or 28800)
    otp_token_ttl = int(os.getenv("OTP_TOKEN_TTL") or 300)
    weather_provider = os.getenv("WEATHER_PROVIDER", "")
    today = "2026-10-19"


settings = Settings()
