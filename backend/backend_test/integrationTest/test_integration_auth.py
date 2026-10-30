"""
Integration tests for login and registration: POST /register, POST /login,
POST /token, POST /logout, GET /users/me.

The routes run against the real test db created by conftest.py and the real
authentication (the as_warden override is removed). Run from the backend folder with:

    python -m pytest backend_test -v
"""
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from sqlmodel import select

from app.services.auth import ALGORITHM, get_current_user, hash_password
from app.config import SECRET_KEY
from app.main import app
from app.models import Roles, User

PASSWORD = "password123"

NEW_USER = {
    "name": "Mario",
    "surname": "Rossi",
    "email": "mario.rossi@mail.example",
    "mobile_number": "+39 333 111 2222",
    "password": PASSWORD,
}


# ---------- Fixtures ----------

@pytest.fixture(autouse=True)
def real_auth(as_warden):
    """Removes the as_warden override of conftest.py: these tests check the real login."""
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


# ---------- Tests: registration ----------

def test_register_saves_user(client, session):
    response = client.post("/register", json=NEW_USER)

    assert response.status_code == 201
    assert response.json() == {"username": "mario.rossi", "role": "Hiker"}
    saved = session.exec(select(User).where(User.email == NEW_USER["email"])).one()
    assert saved.username == "mario.rossi"
    assert saved.role == Roles.HIKER
    assert saved.password_hash != PASSWORD


def test_register_duplicate_email(client, session, user):
    response = client.post("/register", json={**NEW_USER, "email": user.email.upper()})

    assert response.status_code == 409
    assert len(session.exec(select(User)).all()) == 1  # nothing new saved


# ---------- Tests: login ----------

def test_login_success(client, user):
    response = client.post("/login", json={"email": user.email, "password": PASSWORD})

    assert response.status_code == 200
    assert response.json() == {"username": "anna.rossi", "role": "Hiker"}
    assert "session" in response.cookies


def test_login_wrong_password(client, user):
    response = client.post("/login", json={"email": user.email, "password": "wrong-pass"})

    assert response.status_code == 401


def test_token_success(client, user):
    response = client.post("/token", data={"username": user.username, "password": PASSWORD})

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"


# ---------- Tests: authenticated session ----------

def test_me_not_authenticated(client):
    response = client.get("/users/me")

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


def test_me_with_bearer_token(client, user):
    token = client.post("/token", data={"username": user.username, "password": PASSWORD}).json()["access_token"]
    client.cookies.clear()  # only the Authorization header is checked

    response = client.get("/users/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json() == {"username": "anna.rossi", "role": "Hiker"}


def test_me_with_invalid_token(client):
    response = client.get("/users/me", headers={"Authorization": "Bearer not-a-jwt"})

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or expired token"}


def test_me_with_expired_token(client):
    expired = jwt.encode({"sub": "anna.rossi", "role": "Hiker",
                          "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
                         SECRET_KEY, algorithm=ALGORITHM)

    response = client.get("/users/me", headers={"Authorization": f"Bearer {expired}"})

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or expired token"}


def test_register_login_me_logout_flow(client):
    assert client.post("/register", json=NEW_USER).status_code == 201
    assert client.post("/login", json={"email": NEW_USER["email"], "password": PASSWORD}).status_code == 200

    response = client.get("/users/me")  # the session cookie is sent by the client
    assert response.status_code == 200
    assert response.json() == {"username": "mario.rossi", "role": "Hiker"}

    assert client.post("/logout").status_code == 204
    assert client.get("/users/me").status_code == 401
