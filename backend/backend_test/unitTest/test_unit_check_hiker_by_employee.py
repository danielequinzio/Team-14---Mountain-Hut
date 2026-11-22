"""
Unit tests for MH-07 "Reserve for a hiker": GET /profileCheck, the employee checks
the presence of a hiker.

The real DB session is replaced with a MagicMock, so these tests never touch the db. The logged-in user is the warden of conftest.py.
Run from the backend folder with:

    python -m pytest backend_test -v
"""
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.database import get_session
from app.main import app
from app.models import Roles, User

URL = "/profileCheck"


# ---------- Fixtures ----------

@pytest.fixture
def mock_session():
    """A fake Session: configure its return values inside each test."""
    return MagicMock()


@pytest.fixture
def client(mock_session):
    """TestClient whose get_session dependency yields the mock session."""
    app.dependency_overrides[get_session] = lambda: mock_session
    # not used as a context manager -> lifespan (create_all / seeding) doesn't run
    yield TestClient(app)
    app.dependency_overrides.pop(get_session, None)


@pytest.fixture
def hiker():
    """The hiker returned by the mocked query."""
    return User(id=7, username="anna.rossi", name="Anna", surname="Rossi",
                email="anna.rossi@mail.example", mobile_number="+39 333 345 6789",
                password_hash="hash", role=Roles.HIKER)


def query_values(mock_session) -> list:
    """The values the route put in the WHERE clause of its query."""
    statement = mock_session.exec.call_args.args[0]
    return list(statement.compile().params.values())



# ---------- Tests: check the presence of a hiker (GET /profileCheck) ----------

def test_employee_profile_check_returns_hiker(client, mock_session, hiker):
    mock_session.exec.return_value.first.return_value = hiker

    response = client.get(URL, params={"email": hiker.email})

    assert response.status_code == 200
    assert response.json() == {"id": 7, "email": "anna.rossi@mail.example", "role": "Hiker",
                               "is_guest": False}  # no hash


def test_employee_profile_check_normalizes_email_and_filters_hikers(client, mock_session, hiker):
    mock_session.exec.return_value.first.return_value = hiker

    client.get(URL, params={"email": "  Anna.Rossi@MAIL.Example "})

    assert query_values(mock_session) == ["anna.rossi@mail.example", Roles.HIKER]


def test_employee_profile_check_hiker_not_found(client, mock_session):
    mock_session.exec.return_value.first.return_value = None

    response = client.get(URL, params={"email": "nobody@mail.example"})

    assert response.status_code == 404
    assert response.json() == {"detail": "hiker not found"}


def test_employee_profile_check_without_email(client, mock_session):
    response = client.get(URL)

    assert response.status_code == 422  # FastAPI validation error
    mock_session.exec.assert_not_called()