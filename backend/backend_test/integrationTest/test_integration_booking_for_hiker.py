"""
Integration tests for MH-07 "Reserve for a hiker": POST /booking/hiker/{hiker_id}.

An employee or the warden books a table on behalf of a hiker (a phone call, a party at
the door): the hiker already has an account, or is a guest created with POST /registerGuest.
The route runs against the real test db created by conftest.py and the real login and
role checks (the as_warden override is removed). The confirmation email is captured
instead of sent. Run from the backend folder with:

    python -m pytest backend_test/integrationTest/test_integration_booking_for_hiker.py -v
"""
from datetime import date, datetime, time, timedelta
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest
from sqlmodel import select

import app.routers.booking as booking_router
import app.services.notification as notification
from app.main import app
from app.models import Booking, BookingRequirement, Roles, Slot, SlotTable, Table, User
from app.services.auth import hash_password

HUT_TZ = ZoneInfo("Europe/Rome")
LUNCH = time(12, 0)
TABLES = {1: 2, 2: 4, 3: 6}  # table number -> seats: 12 seats per slot
PASSWORD = "password123"


# ---------- Helpers ----------

def far_day() -> date:
    """5 days from now: well over the two hours before which a booking is accepted."""
    return datetime.now(HUT_TZ).date() + timedelta(days=5)


def at(day: date, start: time) -> datetime:
    return datetime.combine(day, start, HUT_TZ)


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
    response = client.post("/login", json={"email": user.email, "password": PASSWORD})
    assert response.status_code == 200
    return client


def payload(party_size=2, day=None, start=LUNCH, requirements=None) -> dict:
    return {"date": (day or far_day()).isoformat(), "time": start.isoformat(),
            "party_size": party_size, "requirements": requirements or []}


def book_for(client, hiker_id: int, **kwargs):
    return client.post(f"/booking/hiker/{hiker_id}", json=payload(**kwargs))


def stored_bookings(session) -> list[Booking]:
    session.expire_all()  # read what the api committed
    return list(session.exec(select(Booking).order_by(Booking.id)).all())


def total_occupied_seats(session, slot_id: int) -> int:
    session.expire_all()
    return sum(session.exec(select(SlotTable.occupied_seats).where(SlotTable.slot_id == slot_id)).all())


# ---------- Fixtures ----------

@pytest.fixture(autouse=True)
def real_auth(as_warden):
    """Removes the as_warden override of conftest.py: the real token and role checks run."""
    app.dependency_overrides.clear()


@pytest.fixture
def hiker(session) -> User:
    return add_user(session, "anna.rossi", Roles.HIKER)


@pytest.fixture
def employee(session) -> User:
    return add_user(session, "giulia.ferrero", Roles.EMPLOYEE)


@pytest.fixture
def as_employee(client, employee):
    return login(client, employee)


@pytest.fixture
def lunch(session) -> int:
    """A slot far enough away, offering all TABLES."""
    warden_id = add_user(session, "luca.bonetti", Roles.WARDEN).id
    tables = [Table(number=n, capacity=c, location="Main hall") for n, c in TABLES.items()]
    session.add_all(tables)
    session.flush()
    start = at(far_day(), LUNCH)
    slot = Slot(start_time=start, end_time=start + timedelta(minutes=90), created_by=warden_id)
    session.add(slot)
    session.flush()
    slot_id = slot.id
    session.add_all([SlotTable(slot_id=slot_id, table_id=table.id) for table in tables])
    session.commit()
    return slot_id


@pytest.fixture
def sent(monkeypatch) -> list:
    """Captures the confirmation emails handed to the background task."""
    emails = []
    monkeypatch.setattr(booking_router, "send_booking_confirmation", emails.append)
    return emails


# ---------- Tests: the booking is made for the hiker ----------

def test_employee_books_for_a_hiker(as_employee, session, hiker, employee, lunch, sent):
    response = book_for(as_employee, hiker.id, party_size=5,
                        requirements=[{"allergies": True, "description": "1 peanut allergy"}])

    assert response.status_code == 201
    body = response.json()
    assert (body["date"], body["time"], body["party_size"]) == (far_day().isoformat(), "12:00:00", 5)
    assert sum(table["seats"] for table in body["tables"]) == 5  # the same rules as MH-01
    [booking] = stored_bookings(session)
    assert (booking.user_id, booking.slot_id, booking.party_size) == (hiker.id, lunch, 5)  # the hiker's, not the employee's
    assert total_occupied_seats(session, lunch) == 5
    requirements = session.exec(select(BookingRequirement)).all()
    assert [(r.booking_id, r.allergies, r.description) for r in requirements] == [(booking.id, True, "1 peanut allergy")]


@pytest.mark.parametrize("role", [Roles.EMPLOYEE, Roles.WARDEN])
def test_employee_and_warden_can_book_for_a_hiker(client, session, hiker, lunch, sent, role):
    staff = add_user(session, "staff.member", role)
    login(client, staff)

    response = book_for(client, hiker.id)

    assert response.status_code == 201
    assert [b.user_id for b in stored_bookings(session)] == [hiker.id]


def test_confirmation_email_goes_to_the_hiker(as_employee, hiker, employee, lunch, sent):
    response = book_for(as_employee, hiker.id, party_size=3)

    [email] = sent
    assert email.recipient == hiker.email  # the hiker is told, not the employee
    assert email.recipient != employee.email
    assert (email.reference, email.party_size) == (f"BK-{response.json()['id']:06d}", 3)


def test_the_hiker_sees_the_booking_in_their_list(client, as_employee, session, hiker, lunch, sent):
    booking_id = book_for(as_employee, hiker.id, party_size=4).json()["id"]

    login(client, hiker)  # the hiker replaces the employee's session
    response = client.get("/booking")

    assert response.status_code == 200
    assert [(b["id"], b["party_size"]) for b in response.json()] == [(booking_id, 4)]


# ---------- Tests: a guest without an account ----------

def test_booking_for_a_guest_sends_no_email(client, as_employee, session, lunch, sent, monkeypatch):
    guest = client.post("/registerGuest", json={"name": "Marco", "surname": "Neri", "mobile_number": ""})
    assert guest.status_code == 201
    assert guest.json()["email"] is None

    response = book_for(as_employee, guest.json()["id"], party_size=4)

    assert response.status_code == 201
    [booking] = stored_bookings(session)
    assert booking.user_id == guest.json()["id"]
    [email] = sent
    assert email.recipient is None  # nobody to write to
    # the real sender skips it: no mail server is even contacted
    smtp_class = MagicMock()
    monkeypatch.setattr(notification.smtplib, "SMTP", smtp_class)
    monkeypatch.setattr(notification, "SMTP_HOST", "smtp.test")
    notification.send_booking_confirmation(email)
    smtp_class.assert_not_called()


# ---------- Tests: who can use the route ----------

def test_booking_for_a_hiker_without_logging_in_is_refused(client, session, hiker, lunch, sent):
    response = book_for(client, hiker.id)

    assert response.status_code == 401
    assert stored_bookings(session) == []
    assert sent == []


def test_a_hiker_cannot_book_for_another_hiker(client, session, hiker, lunch, sent):
    other = add_user(session, "paolo.bianchi", Roles.HIKER)
    login(client, other)

    response = book_for(client, hiker.id)

    assert response.status_code == 403
    assert stored_bookings(session) == []
    assert sent == []


# ---------- Tests: what the route refuses ----------

def test_unknown_hiker_is_not_found(as_employee, session, lunch, sent):
    response = book_for(as_employee, 9999)

    assert response.status_code == 404
    assert response.json() == {"detail": "Hiker not found"}
    assert stored_bookings(session) == []
    assert sent == []


def test_a_staff_member_is_not_a_hiker(as_employee, session, lunch, sent):
    warden = session.exec(select(User).where(User.role == Roles.WARDEN)).one()

    response = book_for(as_employee, warden.id)

    assert response.status_code == 404
    assert response.json() == {"detail": "Hiker not found"}
    assert stored_bookings(session) == []


def test_not_enough_seats_is_refused(as_employee, session, hiker, lunch, sent):
    response = book_for(as_employee, hiker.id, party_size=13)  # the slot has 12 seats

    assert response.status_code == 409
    assert response.json() == {"detail": "There are not enough seats for this party"}
    assert stored_bookings(session) == []
    assert total_occupied_seats(session, lunch) == 0
    assert sent == []


def test_the_hiker_cannot_have_two_bookings_for_the_same_slot(as_employee, session, hiker, lunch, sent):
    assert book_for(as_employee, hiker.id, party_size=2).status_code == 201

    response = book_for(as_employee, hiker.id, party_size=3)

    assert response.status_code == 409
    assert response.json() == {"detail": "A booking already exists for this slot"}
    assert len(stored_bookings(session)) == 1
    assert total_occupied_seats(session, lunch) == 2
    assert len(sent) == 1


def test_date_and_time_without_a_slot_are_refused(as_employee, session, hiker, lunch, sent):
    response = book_for(as_employee, hiker.id, start=time(15, 30))

    assert response.status_code == 400
    assert response.json() == {"detail": "Slot not available"}
    assert stored_bookings(session) == []


def test_a_slot_that_already_started_is_refused(as_employee, session, hiker, lunch, sent):
    # MH-07: an employee cannot book after the beginning of the slot
    started = (datetime.now(HUT_TZ) - timedelta(minutes=30)).replace(second=0, microsecond=0)
    warden = session.exec(select(User).where(User.role == Roles.WARDEN)).one()
    slot = Slot(start_time=started, end_time=started + timedelta(minutes=90), created_by=warden.id)
    session.add(slot)
    session.flush()
    session.add_all([SlotTable(slot_id=slot.id, table_id=table.id)
                     for table in session.exec(select(Table)).all()])
    session.commit()

    response = book_for(as_employee, hiker.id, day=started.date(), start=started.time())

    assert response.status_code == 400
    assert stored_bookings(session) == []
    assert sent == []


@pytest.mark.parametrize("party_size", [0, -2])
def test_party_size_must_be_positive(as_employee, session, hiker, lunch, sent, party_size):
    response = book_for(as_employee, hiker.id, party_size=party_size)

    assert response.status_code == 422
    assert stored_bookings(session) == []
