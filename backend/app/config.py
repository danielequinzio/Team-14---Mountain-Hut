import os
from pathlib import Path

from dotenv import load_dotenv

# settings come from environment variables, with defaults for local development.
# backend/.env fills in the ones that aren't already set in the real environment
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

DB_PATH = Path(__file__).resolve().parent.parent / "OQM.db"  # backend/OQM.db

DATABASE_URL = os.getenv("DATABASE_URL") or f"sqlite:///{DB_PATH}"  # `or`: an empty value also means the default

# signs the login tokens: anyone who knows it can create valid tokens, so set a
# long random value in production (e.g. `python -c "import secrets; print(secrets.token_hex(32))"`)
SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-secret-key-change-me-in-production")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
# fill an empty db with sample data on startup. Parsed by hand: bool("False") would be True
DATA_SEED = os.getenv("SEED_DATA", "false").strip().lower() in ("1", "true", "yes")

DEFAULT_CORS_ORIGINS = (
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:8080",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:8080",
)
CORS_ORIGINS = tuple(
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", ",".join(DEFAULT_CORS_ORIGINS)).split(",")
    if origin.strip()
)
SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").strip().lower() in (
    "1",
    "true",
    "yes",
)