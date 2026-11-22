"""Unit tests for forgot-password and reset-password."""

import hashlib
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

import app.routers.auth as auth_router
from app.database import get_session
from app.main import app
from app.models import Roles, User, pwd_reset
from app.services.auth import hash_password, verify_password


PASSWORD = "password123"
NEW_PASSWORD = "new-password456"


@pytest.fixture
def mock_session():
    session = MagicMock()
    session.exec.return_value.all.return_value = []
    return session


@pytest.fixture
def client(mock_session):
    app.dependency_overrides[get_session] = lambda: mock_session
    yield TestClient(app)
    app.dependency_overrides.pop(get_session, None)


@pytest.fixture
def fake_user():
    return User(
        id=1,
        username="anna.rossi",
        name="Anna",
        surname="Rossi",
        email="anna.rossi@mail.example",
        mobile_number="+39 333 345 6789",
        password_hash=hash_password(PASSWORD),
        role=Roles.HIKER,
        must_change_password=True,
    )


def test_forgot_password_unknown_email_returns_same_answer(client, mock_session):
    mock_session.exec.return_value.first.return_value = None

    response = client.post("/auth/forgot-password?user_email=Nobody@Mail.Example")

    assert response.status_code == 201
    assert response.json() == {"detail": "If the email is registered, a reset link has been sent"}
    mock_session.add.assert_not_called()
    mock_session.commit.assert_not_called()


def test_forgot_password_creates_hashed_reset_and_schedules_email(client, mock_session, fake_user, monkeypatch):
    mock_session.exec.return_value.first.return_value = fake_user
    sent = []
    monkeypatch.setattr(auth_router, "send_pwd_reset", lambda recipient, reset: sent.append((recipient, reset)))

    response = client.post("/auth/forgot-password?user_email=Anna.Rossi@Mail.Example")

    assert response.status_code == 201
    reset = mock_session.add.call_args.args[0]
    assert isinstance(reset, pwd_reset)
    assert reset.user_id == fake_user.id
    assert len(reset.token_hash) == 64
    mock_session.commit.assert_called_once()
    assert len(sent) == 1
    recipient, reset_data = sent[0]
    assert recipient == fake_user.email
    assert reset.token_hash == hashlib.sha256(reset_data.token.encode()).hexdigest()
    assert reset.expire_at == reset_data.expire_at


def test_reset_password_success(client, mock_session, fake_user):
    reset = pwd_reset(
        user_id=fake_user.id,
        token_hash=hashlib.sha256(b"valid-token").hexdigest(),
        expire_at=datetime.now(timezone.utc) + timedelta(minutes=30),
    )
    mock_session.exec.return_value.first.return_value = reset
    mock_session.get.return_value = fake_user

    response = client.post(
        "/auth/reset-password",
        json={"token": "valid-token", "new_password": NEW_PASSWORD},
    )

    assert response.status_code == 204
    assert verify_password(NEW_PASSWORD, fake_user.password_hash)
    assert not fake_user.must_change_password
    assert reset.used
    mock_session.commit.assert_called_once()


def test_reset_password_invalidates_all_pending_links(client, mock_session, fake_user):
    reset = pwd_reset(
        user_id=fake_user.id,
        token_hash=hashlib.sha256(b"valid-token").hexdigest(),
        expire_at=datetime.now(timezone.utc) + timedelta(minutes=30),
    )
    pending = [MagicMock(used=False), MagicMock(used=False)]
    mock_session.exec.return_value.first.return_value = reset
    mock_session.exec.return_value.all.return_value = pending
    mock_session.get.return_value = fake_user

    response = client.post(
        "/auth/reset-password",
        json={"token": "valid-token", "new_password": NEW_PASSWORD},
    )

    assert response.status_code == 204
    assert all(row.used for row in pending)
    assert reset.used


def test_reset_password_accepts_naive_sqlite_expiry(client, mock_session, fake_user):
    reset = pwd_reset(
        user_id=fake_user.id,
        token_hash=hashlib.sha256(b"valid-token").hexdigest(),
        expire_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=30),
    )
    mock_session.exec.return_value.first.return_value = reset
    mock_session.get.return_value = fake_user

    response = client.post(
        "/auth/reset-password",
        json={"token": "valid-token", "new_password": NEW_PASSWORD},
    )

    assert response.status_code == 204


@pytest.mark.parametrize("kind", ["unknown", "used", "expired", "missing-user"])
def test_reset_password_rejects_invalid_reset_states(client, mock_session, fake_user, kind):
    reset = None
    if kind == "used":
        reset = pwd_reset(
            user_id=fake_user.id,
            token_hash="hash",
            expire_at=datetime.now(timezone.utc) + timedelta(minutes=30),
            used=True,
        )
    elif kind == "expired":
        reset = pwd_reset(
            user_id=fake_user.id,
            token_hash="hash",
            expire_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
    elif kind == "missing-user":
        reset = pwd_reset(
            user_id=fake_user.id,
            token_hash="hash",
            expire_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        )

    mock_session.exec.return_value.first.return_value = reset
    mock_session.get.return_value = None if kind == "missing-user" else fake_user

    response = client.post(
        "/auth/reset-password",
        json={"token": "bad-token", "new_password": NEW_PASSWORD},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid or expired reset link"}
    mock_session.commit.assert_not_called()


@pytest.mark.parametrize("body", [
    {"new_password": NEW_PASSWORD},
    {"token": "token"},
    {"token": "", "new_password": NEW_PASSWORD},
    {"token": "token", "new_password": "short"},
])
def test_reset_password_invalid_body(client, mock_session, body):
    response = client.post("/auth/reset-password", json=body)

    assert response.status_code == 422
    mock_session.exec.assert_not_called()
