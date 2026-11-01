"""
Unit tests for POST /login, POST /token and POST /logout.

The real DB session is replaced with a MagicMock, so these tests never
touch the db. Run from the backend folder with:

    python -m pytest backend_test -v
"""
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.services.auth import hash_password
from app.database import get_session
from app.main import app
from app.models import Roles, User

PASSWORD = "password123"


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
def fake_user():
    """The user returned by the mocked query."""
    return User(id=1, username="anna.rossi", name="Anna", surname="Rossi",
                email="anna.rossi@mail.example", mobile_number="+39 333 345 6789",
                password_hash=hash_password(PASSWORD), role=Roles.HIKER)


# ---------- Tests: POST /login ----------

def test_login_success(client, mock_session, fake_user):
    mock_session.exec.return_value.first.return_value = fake_user

    response = client.post("/login", json={"email": "Anna.Rossi@Mail.Example", "password": PASSWORD})

    assert response.status_code == 200
    assert response.json() == {"username": "anna.rossi", "role": "Hiker"}
    assert "session" in response.cookies  # session cookie with the token
    assert "httponly" in response.headers["set-cookie"].lower()
    mock_session.exec.assert_called_once()


def test_login_wrong_password(client, mock_session, fake_user):
    mock_session.exec.return_value.first.return_value = fake_user

    response = client.post("/login", json={"email": fake_user.email, "password": "wrong-pass"})

    assert response.status_code == 401
    assert response.json() == {"detail": "Wrong email or password"}
    assert "session" not in response.cookies


def test_login_unknown_email(client, mock_session):
    mock_session.exec.return_value.first.return_value = None

    response = client.post("/login", json={"email": "nobody@mail.example", "password": PASSWORD})

    assert response.status_code == 401
    assert response.json() == {"detail": "Wrong email or password"}  # same answer as wrong password


@pytest.mark.parametrize("body", [
    {"password": PASSWORD},                               # missing email
    {"email": "anna.rossi@mail.example"},                 # missing password
    {"email": "not-an-email", "password": PASSWORD},      # invalid email
])
def test_login_invalid_body(client, mock_session, body):
    response = client.post("/login", json=body)

    assert response.status_code == 422  # FastAPI validation error
    mock_session.exec.assert_not_called()


# ---------- Tests: POST /token ----------

def test_token_success(client, mock_session, fake_user):
    mock_session.exec.return_value.first.return_value = fake_user

    response = client.post("/token", data={"username": "anna.rossi", "password": PASSWORD})

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"] == response.cookies["session"]  # same token in body and cookie


def test_token_wrong_credentials(client, mock_session, fake_user):
    mock_session.exec.return_value.first.return_value = fake_user

    response = client.post("/token", data={"username": "anna.rossi", "password": "wrong-pass"})

    assert response.status_code == 401
    assert response.json() == {"detail": "Wrong username or password"}


def test_token_missing_form_data(client, mock_session):
    response = client.post("/token")

    assert response.status_code == 422
    mock_session.exec.assert_not_called()


# ---------- Tests: POST /logout ----------

def test_logout_deletes_cookie(client):
    response = client.post("/logout")

    assert response.status_code == 204
    assert 'session=""' in response.headers["set-cookie"]
    assert "max-age=0" in response.headers["set-cookie"].lower()
