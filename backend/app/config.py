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