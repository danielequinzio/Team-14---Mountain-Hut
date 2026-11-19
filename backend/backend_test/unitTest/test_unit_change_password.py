"""
Unit tests for POST /auth/change-password.

The real DB session is replaced with a MagicMock and the logged-in user is
injected through get_current_user, so these tests never touch the db.
The route sends no email. Run from the backend folder with:

    python -m pytest backend_test -v
"""
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.database import get_session
from app.main import app
from app.models import CurrentUser, Roles, User
from app.services.auth import get_current_user, hash_password, verify_password

PASSWORD = "password123"
NEW_PASSWORD = "new-password456"
URL = "/auth/change-password"


# ---------- Fixtures ----------

@pytest.fixture
def mock_session():
    """A fake Session: configure its return values inside each test."""
    session = MagicMock()
    session.exec.return_value.all.return_value = []  # no pending reset links by default
    return session


@pytest.fixture
def client(mock_session, as_warden):
    """TestClient with the mock session and a logged-in hiker (id=1)."""
    app.dependency_overrides[get_session] = lambda: mock_session
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=1, username="anna.rossi", role=Roles.HIKER
    )
    yield TestClient(app)
    app.dependency_overrides.pop(get_session, None)


@pytest.fixture
def fake_user():
    """The user returned by session.get."""
    return User(id=1, username="anna.rossi", name="Anna", surname="Rossi",
                email="anna.rossi@mail.example", mobile_number="+39 333 345 6789",
                password_hash=hash_password(PASSWORD), role=Roles.HIKER)


# ---------- Tests ----------

def test_change_password_success(client, mock_session, fake_user):
    mock_session.get.return_value = fake_user

    response = client.post(URL, json={"current_password": PASSWORD, "new_password": NEW_PASSWORD})

    assert response.status_code == 204
    assert response.content == b""
    mock_session.get.assert_called_once_with(User, 1)  # the id comes from the token
    assert verify_password(NEW_PASSWORD, fake_user.password_hash)
    assert not verify_password(PASSWORD, fake_user.password_hash)
    mock_session.commit.assert_called_once()


def test_change_password_invalidates_pending_reset_links(client, mock_session, fake_user):
    mock_session.get.return_value = fake_user
    pending = [MagicMock(used=False), MagicMock(used=False)]
    mock_session.exec.return_value.all.return_value = pending

    response = client.post(URL, json={"current_password": PASSWORD, "new_password": NEW_PASSWORD})

    assert response.status_code == 204
    assert all(row.used for row in pending)
    mock_session.commit.assert_called_once()


def test_change_password_wrong_current_password(client, mock_session, fake_user):
    mock_session.get.return_value = fake_user
    old_hash = fake_user.password_hash

    response = client.post(URL, json={"current_password": "wrong-pass", "new_password": NEW_PASSWORD})

    assert response.status_code == 400
    assert response.json() == {"detail": "Current password is wrong"}
    assert fake_user.password_hash == old_hash
    mock_session.commit.assert_not_called()


def test_change_password_user_not_in_db(client, mock_session):
    mock_session.get.return_value = None  # e.g. the account was deleted after login

    response = client.post(URL, json={"current_password": PASSWORD, "new_password": NEW_PASSWORD})

    assert response.status_code == 400
    assert response.json() == {"detail": "Current password is wrong"}
    mock_session.commit.assert_not_called()


@pytest.mark.parametrize("body", [
    {"new_password": NEW_PASSWORD},                          # missing current password
    {"current_password": PASSWORD},                          # missing new password
    {"current_password": "", "new_password": NEW_PASSWORD},  # empty current password
    {"current_password": PASSWORD, "new_password": "short"}, # new password under 8 chars
])
def test_change_password_invalid_body(client, mock_session, body):
    response = client.post(URL, json=body)

    assert response.status_code == 422  # FastAPI validation error
    mock_session.get.assert_not_called()
    mock_session.commit.assert_not_called()


def test_change_password_not_authenticated(client, mock_session):
    app.dependency_overrides.pop(get_current_user, None)  # real auth, no cookie or token

    response = client.post(URL, json={"current_password": PASSWORD, "new_password": NEW_PASSWORD})

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}
    mock_session.get.assert_not_called()