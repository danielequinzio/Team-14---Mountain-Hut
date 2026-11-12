import os
from pathlib import Path

from dotenv import load_dotenv

# settings come from environment variables, with defaults for local development.
# backend/.env fills in the ones that aren't already set in the real environment
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

DB_PATH = Path(__file__).resolve().parent.parent / "MountainHut.db"  # backend/OQM.db

DATABASE_URL = os.getenv("DATABASE_URL") or f"sqlite:///{DB_PATH}"  # `or`: an empty value also means the default

# signs the login tokens: anyone who knows it can create valid tokens, so set a
# long random value in production (e.g. `python -c "import secrets; print(secrets.token_hex(32))"`)
SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-secret-key-change-me-in-production")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
# how long a password reset link stays valid
PWD_RESET_EXPIRE_MINUTES = int(os.getenv("PWD_RESET_EXPIRE_MINUTES", "10"))
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


# confirmation emails. With SMTP_HOST empty nothing is sent: the app only logs it
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", "")

# where the frontend is served: links in emails (e.g. password reset) point here
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")