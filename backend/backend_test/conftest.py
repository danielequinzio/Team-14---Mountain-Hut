"""
Shared fixtures for every test in backend_test/ (pytest loads this file by itself).
"""
import os
import tempfile
from pathlib import Path

# must run before `app` is imported: app/config.py reads these when the engine is created.
# The tests use their own empty db, never backend/MountainHut.db, and no sample data
_TEST_DB = Path(tempfile.gettempdir()) / "mountain_hut_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB}"
os.environ["SEED_DATA"] = "false"

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel

from app.auth import get_current_user
from app.database import engine
from app.main import app
from app.models import Roles, UserPublic


@pytest.fixture(autouse=True)
def db():
    """Every test starts from empty tables, and the db is wiped after it."""
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    yield
    SQLModel.metadata.drop_all(engine)


@pytest.fixture
def session():
    """A db session, to insert the rows a test needs."""
    with Session(engine) as session:
        yield session


@pytest.fixture
def client():
    """Calls the api in-process. Not used as a context manager, so the startup seeding doesn't run."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def as_warden():
    """Every test runs as a logged-in warden, so the tests of the other routes don't need a token.

    The tests of the login itself remove this override (see integrationTest/test_integration_auth.py).
    """
    app.dependency_overrides[get_current_user] = lambda: UserPublic(username="test-warden", role=Roles.WARDEN)
    yield
    app.dependency_overrides.pop(get_current_user, None)