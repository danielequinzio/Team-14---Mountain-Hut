"""
Integration tests for POST /auth/change-password.

The route runs against the real test db created by conftest.py and the real
authentication (the as_warden override is removed): the user logs in with
POST /login and the session cookie is sent by the client.
No email is sent: the pending reset links are inserted straight into the db
instead of going through POST /auth/forgot-password. Run from the backend folder with:

    python -m pytest backend_test -v
"""
import hashlib
from datetime import datetime, timedelta, timezone

import pytest
from sqlmodel import select

from app.main import app
from app.models import Roles, User, pwd_reset
from app.services.auth import get_current_user, hash_password, verify_password

PASSWORD = "password123"
NEW_PASSWORD = "new-password456"
URL = "/auth/change-password"


# ---------- Fixtures ----------

@pytest.fixture(autouse=True)
def real_auth(as_warden):
    """Removes the as_warden override of conftest.py: these tests use the real login."""
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def user(session):
    """A hiker already saved in the test db."""
    user = User(username="anna.rossi", name="Anna", surname="Rossi",
                email="anna.rossi@mail.example", mobile_number="+39 333 345 6789",
                password_hash=hash_password(PASSWORD), role=Roles.HIKER)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@pytest.fixture
def logged_client(client, user):
    """The client after a successful login: it carries the session cookie."""
    response = client.post("/login", json={"email": user.email, "password": PASSWORD})
    assert response.status_code == 200
    return client


def add_reset_link(session, user, token: str) -> None:
    """Saves a valid, unused reset link for the user, as forgot-password would (without the email)."""
    session.add(pwd_reset(
        user_id=user.id,
        token_hash=hashlib.sha256(token.encode()).hexdigest(),
        expire_at=datetime.now(timezone.utc) + timedelta(minutes=30),
    ))
    session.commit()


# ---------- Tests ----------

def test_change_password_saves_new_hash(logged_client, session, user):
    response = logged_client.post(URL, json={"current_password": PASSWORD, "new_password": NEW_PASSWORD})

    assert response.status_code == 204
    session.refresh(user)
    assert verify_password(NEW_PASSWORD, user.password_hash)
    assert not verify_password(PASSWORD, user.password_hash)


def test_login_after_change_uses_new_password(logged_client, user):
    logged_client.post(URL, json={"current_password": PASSWORD, "new_password": NEW_PASSWORD})
    logged_client.cookies.clear()

    old = logged_client.post("/login", json={"email": user.email, "password": PASSWORD})
    new = logged_client.post("/login", json={"email": user.email, "password": NEW_PASSWORD})

    assert old.status_code == 401
    assert new.status_code == 200


def test_user_stays_logged_in_after_change(logged_client):
    logged_client.post(URL, json={"current_password": PASSWORD, "new_password": NEW_PASSWORD})

    response = logged_client.get("/users/me")

    assert response.status_code == 200
    assert response.json() == {"username": "anna.rossi", "role": "Hiker", "must_change_password": False}


def test_change_password_with_bearer_token(client, user):
    token = client.post("/token", data={"username": user.email, "password": PASSWORD}).json()["access_token"]
    client.cookies.clear()  # only the Authorization header is checked

    response = client.post(URL, json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
                           headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 204


def test_change_password_wrong_current_password(logged_client, session, user):
    response = logged_client.post(URL, json={"current_password": "wrong-pass", "new_password": NEW_PASSWORD})

    assert response.status_code == 400
    assert response.json() == {"detail": "Current password is wrong"}
    session.refresh(user)
    assert verify_password(PASSWORD, user.password_hash)  # unchanged


def test_change_password_too_short(logged_client, session, user):
    response = logged_client.post(URL, json={"current_password": PASSWORD, "new_password": "short"})

    assert response.status_code == 422
    session.refresh(user)
    assert verify_password(PASSWORD, user.password_hash)  # unchanged


def test_change_password_not_authenticated(client, session, user):
    response = client.post(URL, json={"current_password": PASSWORD, "new_password": NEW_PASSWORD})

    assert response.status_code == 401
    session.refresh(user)
    assert verify_password(PASSWORD, user.password_hash)  # unchanged


def test_change_password_invalidates_pending_reset_links(logged_client, session, user):
    add_reset_link(session, user, "pending-token-1")
    add_reset_link(session, user, "pending-token-2")

    response = logged_client.post(URL, json={"current_password": PASSWORD, "new_password": NEW_PASSWORD})

    assert response.status_code == 204
    session.expire_all()
    rows = session.exec(select(pwd_reset).where(pwd_reset.user_id == user.id)).all()
    assert len(rows) == 2
    assert all(row.used for row in rows)

    # an old link can no longer override the new password
    reset = logged_client.post("/auth/reset-password",
                               json={"token": "pending-token-1", "new_password": "hijack-pass789"})
    assert reset.status_code == 400
    session.refresh(user)
    assert verify_password(NEW_PASSWORD, user.password_hash)


def test_change_password_does_not_touch_other_users_links(logged_client, session):
    other = User(username="luca.bianchi", name="Luca", surname="Bianchi",
                 email="luca.bianchi@mail.example", mobile_number="+39 333 999 0000",
                 password_hash=hash_password(PASSWORD), role=Roles.HIKER)
    session.add(other)
    session.commit()
    session.refresh(other)
    add_reset_link(session, other, "other-user-token")

    response = logged_client.post(URL, json={"current_password": PASSWORD, "new_password": NEW_PASSWORD})

    assert response.status_code == 204
    session.expire_all()
    row = session.exec(select(pwd_reset).where(pwd_reset.user_id == other.id)).one()
    assert row.used is False