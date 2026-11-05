"""
Unit tests for POST /register.

The real DB session is replaced with a MagicMock, so these tests never
touch the db. Run from the backend folder with:

    python -m pytest backend_test -v
"""
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.services.auth import verify_password
from app.database import get_session
from app.main import app
from app.models import Roles, User

VALID = {
    "name": "Mario",
    "surname": "Rossi",
    "email": "mario.rossi@mail.example",
    "mobile_number": "+39 333 111 2222",
    "password": "password123",
}


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


# ---------- Tests ----------

def test_register_created(client, mock_session):
    mock_session.exec.return_value.first.return_value = None  # email not registered yet

    response = client.post("/register", json={**VALID, "name": " Mario ", "email": "Mario.Rossi@Mail.Example",
                                               "notes": " vegetarian ", "emergency_contact": " +39 333 0 "})

    assert response.status_code == 201
    assert response.json() == {"username": "mario.rossi", "role": "Hiker"}  # no hash in the answer
    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()

    user = mock_session.add.call_args.args[0]  # the User saved by the route
    assert isinstance(user, User)
    assert user.name == "Mario"
    assert user.email == "mario.rossi@mail.example"
    assert user.notes == "vegetarian"
    assert user.emergency_contact == "+39 333 0"
    assert user.role == Roles.HIKER
    assert user.password_hash != VALID["password"]
    assert verify_password(VALID["password"], user.password_hash)


def test_register_optional_fields_empty(client, mock_session):
    mock_session.exec.return_value.first.return_value = None

    response = client.post("/register", json=VALID)

    assert response.status_code == 201
    user = mock_session.add.call_args.args[0]
    assert user.notes is None
    assert user.emergency_contact is None


def test_register_email_already_registered(client, mock_session):
    mock_session.exec.return_value.first.return_value = MagicMock()  # a user with that email exists

    response = client.post("/register", json=VALID)

    assert response.status_code == 409
    assert response.json() == {"detail": "Email already registered"}
    mock_session.add.assert_not_called()
    mock_session.commit.assert_not_called()


def test_register_integrity_error_duplicate_email(client, mock_session):
    # free at the first check, taken at commit time (two concurrent registrations)
    mock_session.exec.return_value.first.side_effect = [None, MagicMock()]
    mock_session.commit.side_effect = IntegrityError("INSERT", {}, Exception())

    response = client.post("/register", json=VALID)

    assert response.status_code == 409
    assert response.json() == {"detail": "Email already registered"}
    mock_session.rollback.assert_called_once()


def test_register_integrity_error_other(client, mock_session):
    # integrity error not caused by the email: the route re-raises it
    mock_session.exec.return_value.first.return_value = None
    mock_session.commit.side_effect = IntegrityError("INSERT", {}, Exception())

    with pytest.raises(IntegrityError):
        client.post("/register", json=VALID)
    mock_session.rollback.assert_called_once()


@pytest.mark.parametrize("field, value", [
    ("name", ""),
    ("surname", ""),
    ("mobile_number", ""),
    ("email", "not-an-email"),
    ("password", "short"),  # less than 8 characters
])
def test_register_invalid_field(client, mock_session, field, value):
    response = client.post("/register", json={**VALID, field: value})

    assert response.status_code == 422  # FastAPI validation error
    mock_session.exec.assert_not_called()


@pytest.mark.parametrize("field", ["name", "surname", "email", "mobile_number", "password"])
def test_register_missing_field(client, mock_session, field):
    body = {k: v for k, v in VALID.items() if k != field}

    response = client.post("/register", json=body)

    assert response.status_code == 422
    mock_session.exec.assert_not_called()
