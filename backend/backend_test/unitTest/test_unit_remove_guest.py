"""
Unit tests for DELETE /guests/{guest_id}: the employee or the warden removes a guest
(a hiker without an account, added with POST /registerGuest).

The real DB session is replaced with a MagicMock, so these tests never touch the db.
The logged-in user is the warden of conftest.py; the role check is replaced per test when needed.
Run from the backend folder with:

    python -m pytest backend_test -v
"""
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.database import get_session
from app.main import app
from app.models import Booking, Roles, User, UserPublic
from app.services.auth import get_current_user


def url(guest_id) -> str:
    return f"/guests/{guest_id}"


# ---------- Fixtures ----------

@pytest.fixture
def mock_session():
    """A fake Session: configure its return values inside each test. By default the guest has no bookings."""
    session = MagicMock()
    session.exec.return_value.first.return_value = None
    return session


@pytest.fixture
def client(mock_session):
    """TestClient whose get_session dependency yields the mock session."""
    app.dependency_overrides[get_session] = lambda: mock_session
    # not used as a context manager -> lifespan (create_all / seeding) doesn't run
    yield TestClient(app)
    app.dependency_overrides.pop(get_session, None)


@pytest.fixture
def guest():
    return User(id=9, username="luigi.neri", name="Luigi", surname="Neri", email=None,
                mobile_number="+39 349 555 6666", password_hash="hash", role=Roles.HIKER, is_guest=True)


@pytest.fixture
def hiker():
    return User(id=7, username="anna.rossi", name="Anna", surname="Rossi", email="anna.rossi@mail.example",
                mobile_number="+39 333 345 6789", password_hash="hash", role=Roles.HIKER)


def query_values(mock_session) -> list:
    """The values the route put in the WHERE clause of its bookings query."""
    statement = mock_session.exec.call_args.args[0]
    return list(statement.compile().params.values())


# ---------- Tests ----------

@pytest.mark.parametrize("role", [Roles.WARDEN, Roles.EMPLOYEE])
def test_remove_guest_deletes_and_commits(client, mock_session, guest, role):
    app.dependency_overrides[get_current_user] = lambda: UserPublic(username="staff", role=role)
    mock_session.get.return_value = guest

    response = client.delete(url(guest.id))

    assert response.status_code == 204
    assert response.content == b""
    mock_session.get.assert_called_once_with(User, guest.id)
    mock_session.delete.assert_called_once_with(guest)
    mock_session.commit.assert_called_once()


def test_remove_guest_looks_for_the_guest_bookings(client, mock_session, guest):
    mock_session.get.return_value = guest

    client.delete(url(guest.id))

    assert query_values(mock_session) == [guest.id]


def test_remove_guest_forbidden_to_hikers(client, mock_session):
    app.dependency_overrides[get_current_user] = lambda: UserPublic(username="anna.rossi", role=Roles.HIKER)

    response = client.delete(url(9))

    assert response.status_code == 403
    assert response.json() == {"detail": "Not enough permissions"}
    mock_session.get.assert_not_called()
    mock_session.delete.assert_not_called()


def test_remove_guest_not_found(client, mock_session):
    mock_session.get.return_value = None

    response = client.delete(url(404))

    assert response.status_code == 404
    assert response.json() == {"detail": "guest not found"}
    mock_session.delete.assert_not_called()
    mock_session.commit.assert_not_called()


def test_remove_guest_refuses_a_hiker_with_an_account(client, mock_session, hiker):
    mock_session.get.return_value = hiker

    response = client.delete(url(hiker.id))

    assert response.status_code == 404
    assert response.json() == {"detail": "guest not found"}
    mock_session.delete.assert_not_called()
    mock_session.commit.assert_not_called()


def test_remove_guest_with_bookings_is_refused(client, mock_session, guest):
    mock_session.get.return_value = guest
    mock_session.exec.return_value.first.return_value = Booking(id=1, user_id=guest.id, slot_id=3, party_size=2)

    response = client.delete(url(guest.id))

    assert response.status_code == 409
    assert response.json() == {"detail": "guest still has bookings"}
    mock_session.delete.assert_not_called()
    mock_session.commit.assert_not_called()


def test_remove_guest_id_must_be_an_integer(client, mock_session):
    response = client.delete(url("abc"))

    assert response.status_code == 422  # FastAPI validation error
    mock_session.get.assert_not_called()
