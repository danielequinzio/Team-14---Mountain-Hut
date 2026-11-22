"""
Integration tests for MH-07 "Reserve for a hiker": the employee checks and creates hikers.
  - GET  /profileCheck     check the presence of a hiker (by email)
  - POST /registerHiker    create a full hiker profile
  - POST /registerGuest    add a guest: a hiker without an account
  - DELETE /guests/{id}    remove a guest (refused while the guest has bookings)

The routes run against the real test db created by conftest.py and the real
authentication (the as_warden override is removed: the employee logs in for real).
Each test inserts only the rows it needs. The forced password change of the new hiker is
tested in test_integration_forced_password_change.py.
Run from the backend folder with:

    python -m pytest backend_test -v
"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.database import engine
from app.main import app
from app.models import Booking, Roles, Slot, User
from app.routers import user as user_router
from app.services.auth import hash_password

PASSWORD = "password123"
MISSING = object()

CHECK_URL = "/profileCheck"
HIKER_URL = "/registerHiker"
GUEST_URL = "/registerGuest"

HIKER = {
    "name": "Mario",
    "surname": "Rossi",
    "email": "mario.rossi@mail.example",
    "mobile_number": "+39 333 111 2222",
}

GUEST = {
    "name": "Luigi",
    "surname": "Neri",
    "mobile_number": "+39 349 555 6666",
}


# ---------- Helpers ----------

def add_user(session, username: str, role: Roles) -> User:
    name, surname = username.split(".")
    user = User(username=username, name=name.title(), surname=surname.title(),
                email=f"{username}@mail.example", mobile_number="+39 333 000 0000",
                password_hash=hash_password(PASSWORD), role=role)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def login(client, user: User):
    """Real login: the client keeps the session cookie for the next requests."""
    response = client.post("/login", json={"email": user.email, "password": PASSWORD})
    assert response.status_code == 200
    return client


def check(client, email: str):
    return client.get(CHECK_URL, params={"email": email})


def stored_hikers(session) -> list[User]:
    session.expire_all()  # read what the api committed
    return session.exec(select(User).where(User.role == Roles.HIKER, User.is_guest == False)).all()  # noqa: E712


def stored_guests(session) -> list[User]:
    session.expire_all()
    return session.exec(select(User).where(User.is_guest == True)).all()  # noqa: E712


# ---------- Fixtures ----------

@pytest.fixture(autouse=True)
def real_auth(as_warden):
    """Removes the as_warden override of conftest.py: the real token and role checks run."""
    app.dependency_overrides.clear()


@pytest.fixture
def employee(session) -> User:
    return add_user(session, "giulia.ferrero", Roles.EMPLOYEE)


@pytest.fixture
def as_employee(client, employee):
    return login(client, employee)


@pytest.fixture
def hiker(session) -> User:
    return add_user(session, "anna.rossi", Roles.HIKER)


@pytest.fixture
def sent_emails(monkeypatch) -> list:
    """Catches the account emails that /registerHiker hands to the background task."""
    sent = []
    monkeypatch.setattr(user_router, "send_account_created", sent.append)
    return sent


@pytest.fixture
def failing_commit(as_employee, monkeypatch):
    """Factory: the route's commit fails with IntegrityError, optionally because another
    request saved the same email between the route's check and its commit."""
    real_commit = Session.commit

    def _failing_commit(same_email_saved: bool):
        def commit(self):
            monkeypatch.setattr(Session, "commit", real_commit)  # only the route's commit fails
            if same_email_saved:
                with Session(engine) as other:
                    other.add(User(username="mario.rossi", name="Mario", surname="Rossi",
                                   email=HIKER["email"], mobile_number="+39 333 111 2222",
                                   password_hash="hash", role=Roles.HIKER))
                    other.commit()
            raise IntegrityError("INSERT", {}, Exception())

        monkeypatch.setattr(Session, "commit", commit)

    return _failing_commit


# ---------- Tests: check the presence of a hiker (GET /profileCheck) ----------

def test_employee_profile_check_needs_login(client, hiker):
    assert check(client, hiker.email).status_code == 401


def test_employee_profile_check_forbidden_to_hikers(client, hiker):
    response = check(login(client, hiker), hiker.email)

    assert response.status_code == 403
    assert response.json() == {"detail": "Not enough permissions"}


def test_employee_profile_check_finds_registered_hiker(as_employee, session, hiker):
    add_user(session, "paolo.bianchi", Roles.HIKER)  # another hiker: only the requested one comes back

    response = check(as_employee, hiker.email.upper())

    assert response.status_code == 200
    assert response.json() == {"id": hiker.id, "email": hiker.email, "role": "Hiker", "is_guest": False}


def test_employee_profile_check_unknown_email(as_employee, hiker):
    response = check(as_employee, "nobody@mail.example")

    assert response.status_code == 404
    assert response.json() == {"detail": "hiker not found"}


@pytest.mark.parametrize("role", [Roles.EMPLOYEE, Roles.WARDEN])
def test_employee_profile_check_ignores_staff_accounts(as_employee, session, role):
    staff = add_user(session, "luca.bonetti", role)

    assert check(as_employee, staff.email).status_code == 404


# ---------- Tests: create a hiker profile (POST /registerHiker) ----------

def test_employee_create_hiker_needs_login(client, session):
    assert client.post(HIKER_URL, json=HIKER).status_code == 401
    assert stored_hikers(session) == []


def test_employee_create_hiker_forbidden_to_hikers(client, session, hiker):
    response = login(client, hiker).post(HIKER_URL, json=HIKER)

    assert response.status_code == 403
    assert stored_hikers(session) == [hiker]  # only the logged-in hiker


def test_employee_creates_hiker_profile(as_employee, session, sent_emails):
    response = as_employee.post(HIKER_URL, json={**HIKER, "name": " Mario ", "email": "Mario.Rossi@Mail.Example",
                                                 "notes": " vegetarian ", "emergency_contact": " +39 333 0 "})

    assert response.status_code == 201
    [saved] = stored_hikers(session)
    assert response.json() == {"id": saved.id, "email": "mario.rossi@mail.example", "role": "Hiker",
                               "is_guest": False}
    assert (saved.username, saved.name, saved.surname) == ("mario.rossi", "Mario", "Rossi")
    assert (saved.notes, saved.emergency_contact) == ("vegetarian", "+39 333 0")
    [account] = sent_emails
    assert (account.recipient, account.username) == ("mario.rossi@mail.example", "mario.rossi")


def test_employee_create_hiker_without_optional_fields(as_employee, session, sent_emails):
    assert as_employee.post(HIKER_URL, json=HIKER).status_code == 201

    [saved] = stored_hikers(session)
    assert (saved.notes, saved.emergency_contact) == (None, None)


def test_employee_create_hiker_generates_different_passwords(as_employee, sent_emails):
    as_employee.post(HIKER_URL, json=HIKER)
    as_employee.post(HIKER_URL, json={**HIKER, "email": "mario.rossi.2@mail.example"})

    first, second = sent_emails
    assert first.password != second.password


def test_employee_create_hiker_email_already_registered(as_employee, session, sent_emails):
    as_employee.post(HIKER_URL, json=HIKER)

    response = as_employee.post(HIKER_URL, json={**HIKER, "email": HIKER["email"].upper()})

    assert response.status_code == 409
    assert response.json() == {"detail": "Email already registered"}
    assert len(stored_hikers(session)) == 1
    assert len(sent_emails) == 1  # no email for the rejected request


def test_employee_create_hiker_concurrent_same_email(as_employee, session, sent_emails, failing_commit):
    failing_commit(same_email_saved=True)

    response = as_employee.post(HIKER_URL, json=HIKER)

    assert response.status_code == 409
    assert response.json() == {"detail": "Email already registered"}
    assert len(stored_hikers(session)) == 1  # only the one of the other request
    assert sent_emails == []


def test_employee_create_hiker_other_integrity_error(as_employee, failing_commit):
    failing_commit(same_email_saved=False)

    with pytest.raises(IntegrityError):
        as_employee.post(HIKER_URL, json=HIKER)


@pytest.mark.parametrize("field, value", [
    ("name", ""),
    ("surname", ""),
    ("mobile_number", ""),
    ("email", "not-an-email"),
    ("email", MISSING),
])
def test_employee_create_hiker_invalid_field(as_employee, session, field, value):
    body = {k: v for k, v in HIKER.items() if k != field}
    if value is not MISSING:
        body[field] = value

    assert as_employee.post(HIKER_URL, json=body).status_code == 422
    assert stored_hikers(session) == []


# ---------- Tests: add a guest (POST /registerGuest) ----------

def test_employee_create_guest_needs_login(client, session):
    assert client.post(GUEST_URL, json=GUEST).status_code == 401
    assert stored_guests(session) == []


def test_employee_create_guest_forbidden_to_hikers(client, session, hiker):
    assert login(client, hiker).post(GUEST_URL, json=GUEST).status_code == 403
    assert stored_guests(session) == []


def test_employee_creates_guest(as_employee, session):
    response = as_employee.post(GUEST_URL, json={"name": " Luigi ", "surname": " Neri ",
                                                 "mobile_number": " +39 349 555 6666 "})

    assert response.status_code == 201
    [saved] = stored_guests(session)
    assert response.json() == {"id": saved.id, "email": None, "role": "Hiker", "is_guest": True}
    assert (saved.username, saved.name, saved.surname) == ("luigi.neri", "Luigi", "Neri")
    assert (saved.mobile_number, saved.role) == ("+39 349 555 6666", Roles.HIKER)


def test_employee_create_guests_without_email(as_employee, session):
    # the email is unique, but the missing emails (NULL) of the guests do not collide
    assert as_employee.post(GUEST_URL, json=GUEST).status_code == 201
    assert as_employee.post(GUEST_URL, json=GUEST).status_code == 201

    assert len(stored_guests(session)) == 2


@pytest.mark.parametrize("field", ["name", "surname", "mobile_number"])
def test_employee_create_guest_missing_field(as_employee, session, field):
    body = {k: v for k, v in GUEST.items() if k != field}

    assert as_employee.post(GUEST_URL, json=body).status_code == 422
    assert stored_guests(session) == []


# ---------- Tests: remove a guest (DELETE /guests/{guest_id}) ----------

def remove_guest_url(guest_id: int) -> str:
    return f"/guests/{guest_id}"


def add_guest(client) -> int:
    """Adds a guest through the api, as the staff does, and returns its id."""
    response = client.post(GUEST_URL, json=GUEST)
    assert response.status_code == 201
    return response.json()["id"]


def add_booking(session, user_id: int, staff_id: int) -> Booking:
    start = datetime(2030, 1, 1, 12, 0, tzinfo=timezone.utc)
    slot = Slot(start_time=start, end_time=start + timedelta(minutes=90), created_by=staff_id)
    session.add(slot)
    session.commit()
    booking = Booking(user_id=user_id, slot_id=slot.id, party_size=2)
    session.add(booking)
    session.commit()
    session.refresh(booking)
    return booking


def test_remove_guest_needs_login(client, session, as_employee):
    guest_id = add_guest(as_employee)
    client.cookies.clear()  # log out

    assert client.delete(remove_guest_url(guest_id)).status_code == 401
    assert [g.id for g in stored_guests(session)] == [guest_id]


def test_remove_guest_forbidden_to_hikers(client, session, as_employee, hiker):
    guest_id = add_guest(as_employee)
    client.cookies.clear()

    response = login(client, hiker).delete(remove_guest_url(guest_id))

    assert response.status_code == 403
    assert response.json() == {"detail": "Not enough permissions"}
    assert [g.id for g in stored_guests(session)] == [guest_id]


@pytest.mark.parametrize("role", [Roles.EMPLOYEE, Roles.WARDEN])
def test_staff_removes_a_guest(client, session, role):
    staff = add_user(session, "luca.bonetti", role)
    login(client, staff)
    guest_id = add_guest(client)
    other_id = add_guest(client)  # another guest: only the requested one goes

    response = client.delete(remove_guest_url(guest_id))

    assert response.status_code == 204
    assert [g.id for g in stored_guests(session)] == [other_id]


def test_remove_guest_twice_is_not_found(as_employee, session):
    guest_id = add_guest(as_employee)
    assert as_employee.delete(remove_guest_url(guest_id)).status_code == 204

    response = as_employee.delete(remove_guest_url(guest_id))

    assert response.status_code == 404
    assert response.json() == {"detail": "guest not found"}


def test_remove_guest_unknown_id(as_employee):
    response = as_employee.delete(remove_guest_url(999))

    assert response.status_code == 404
    assert response.json() == {"detail": "guest not found"}


def test_remove_guest_never_removes_a_hiker_with_an_account(as_employee, session, hiker):
    response = as_employee.delete(remove_guest_url(hiker.id))

    assert response.status_code == 404
    assert response.json() == {"detail": "guest not found"}
    assert stored_hikers(session) == [hiker]


def test_remove_guest_never_removes_staff(as_employee, session, employee):
    assert as_employee.delete(remove_guest_url(employee.id)).status_code == 404

    session.expire_all()
    assert session.get(User, employee.id) is not None


def test_remove_guest_with_bookings_is_refused(as_employee, session, employee):
    guest_id = add_guest(as_employee)
    booking = add_booking(session, guest_id, employee.id)

    response = as_employee.delete(remove_guest_url(guest_id))

    assert response.status_code == 409
    assert response.json() == {"detail": "guest still has bookings"}
    assert [g.id for g in stored_guests(session)] == [guest_id]
    assert session.get(Booking, booking.id) is not None
