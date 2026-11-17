"""
Integration tests for the forced password change of the accounts created by the staff.

POST /registerHiker emails a generated password and marks the user with
must_change_password: until POST /auth/change-password (or a reset link) is used,
every route protected by require_role answers 403. The routes run against the real
test db created by conftest.py and the real authentication. No email is sent:
send_account_created is replaced to catch the generated password. Run from the backend folder with:

    python -m pytest backend_test -v
"""
import hashlib
from datetime import datetime, timedelta, timezone

import pytest
from sqlmodel import select

from app.main import app
from app.models import Roles, User, pwd_reset
from app.routers import user as user_router
from app.services.auth import get_current_user, hash_password

NEW_PASSWORD = "new-password456"

HIKER = {
    "name": "Mario",
    "surname": "Rossi",
    "email": "mario.rossi@mail.example",
    "mobile_number": "+39 333 111 2222",
}


# ---------- Fixtures ----------

@pytest.fixture
def temp_password(client, monkeypatch):
    """Creates a hiker as the warden of conftest.py and returns the password that would be emailed."""
    sent = []
    monkeypatch.setattr(user_router, "send_account_created", sent.append)

    response = client.post("/registerHiker", json=HIKER)

    assert response.status_code == 201
    app.dependency_overrides.pop(get_current_user, None)  # from here on, the real login
    return sent[0].password


@pytest.fixture
def logged_client(client, temp_password):
    """The client after logging in with the emailed password."""
    response = client.post("/login", json={"email": HIKER["email"], "password": temp_password})
    assert response.status_code == 200
    return client


# ---------- Tests ----------

def test_created_hiker_must_change_password(session, temp_password):
    saved = session.exec(select(User).where(User.email == HIKER["email"])).one()

    assert saved.must_change_password is True


def test_self_registered_hiker_does_not(client, session):
    app.dependency_overrides.pop(get_current_user, None)
    client.post("/register", json={**HIKER, "password": "password123"})

    saved = session.exec(select(User).where(User.email == HIKER["email"])).one()
    assert saved.must_change_password is False


def test_login_tells_the_frontend(client, temp_password):
    response = client.post("/login", json={"email": HIKER["email"], "password": temp_password})

    assert response.status_code == 200
    assert response.json() == {"username": "mario.rossi", "role": "Hiker", "must_change_password": True}


def test_protected_routes_blocked_before_change(logged_client):
    response = logged_client.get("/booking")

    assert response.status_code == 403
    assert response.json() == {"detail": "Password change required"}


def test_users_me_still_answers_before_change(logged_client):
    response = logged_client.get("/users/me")

    assert response.status_code == 200
    assert response.json()["must_change_password"] is True


def test_change_password_unblocks_with_same_session(logged_client, session, temp_password):
    response = logged_client.post("/auth/change-password",
                                  json={"current_password": temp_password, "new_password": NEW_PASSWORD})

    assert response.status_code == 204
    saved = session.exec(select(User).where(User.email == HIKER["email"])).one()
    assert saved.must_change_password is False
    # the new cookie is used straight away: no need to log in again
    assert logged_client.get("/users/me").json()["must_change_password"] is False
    # 422 (empty body) instead of 403: require_role let the request through
    assert logged_client.post("/booking", json={}).status_code == 422


def test_flag_stays_off_at_next_login(logged_client, temp_password):
    logged_client.post("/auth/change-password",
                       json={"current_password": temp_password, "new_password": NEW_PASSWORD})
    logged_client.cookies.clear()

    response = logged_client.post("/login", json={"email": HIKER["email"], "password": NEW_PASSWORD})

    assert response.json()["must_change_password"] is False


def test_wrong_current_password_keeps_the_block(logged_client, session):
    response = logged_client.post("/auth/change-password",
                                  json={"current_password": "wrong-pass", "new_password": NEW_PASSWORD})

    assert response.status_code == 400
    saved = session.exec(select(User).where(User.email == HIKER["email"])).one()
    assert saved.must_change_password is True
    assert logged_client.get("/booking").status_code == 403


def test_reset_link_clears_the_flag(client, session):
    app.dependency_overrides.pop(get_current_user, None)
    user = User(username="anna.rossi", name="Anna", surname="Rossi",
                email="anna.rossi@mail.example", mobile_number="+39 333 345 6789",
                password_hash=hash_password("temp-pass1"), role=Roles.HIKER,
                must_change_password=True)
    session.add(user)
    session.commit()
    session.refresh(user)
    session.add(pwd_reset(user_id=user.id,
                          token_hash=hashlib.sha256(b"reset-token").hexdigest(),
                          expire_at=datetime.now(timezone.utc) + timedelta(minutes=30)))
    session.commit()

    response = client.post("/auth/reset-password", json={"token": "reset-token", "new_password": NEW_PASSWORD})

    assert response.status_code == 204
    session.refresh(user)
    assert user.must_change_password is False