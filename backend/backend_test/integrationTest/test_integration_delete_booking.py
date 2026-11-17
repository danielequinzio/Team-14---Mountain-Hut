"""
Integration tests for "Cancel a booking": DELETE /booking/{booking_id}.

Run from the backend folder with:

    python -m pytest backend_test/integrationTest/test_integration_delete_booking.py -v
"""
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlmodel import select

from app.main import app
from app.models import Booking, BookingRequirement, BookingTable, Roles, Slot, SlotTable, Table, User
from app.services.auth import hash_password

HUT_TZ = ZoneInfo("Europe/Rome")
URL = "/booking"
LUNCH = time(12, 0)
DINNER = time(19, 0)
TABLES = {1: 2, 2: 4, 3: 6}  # table number -> seats: 12 seats per slot
PASSWORD = "password123"


# ---------- Helpers ----------

def far_day() -> date:
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


def book(client, party_size, start=LUNCH, requirements=None):
    payload = {"date": far_day().isoformat(), "time": start.isoformat(),
               "party_size": party_size, "requirements": requirements or []}
    return client.post(URL, json=payload)


def book_id(client, party_size, start=LUNCH, requirements=None) -> int:
    response = book(client, party_size, start, requirements)
    assert response.status_code == 201
    return response.json()["id"]


def cancel(client, booking_id: int):
    return client.delete(f"{URL}/{booking_id}")


def stored_bookings(session) -> list[int]:
    session.expire_all()  # read what the api committed
    return [booking.id for booking in session.exec(select(Booking).order_by(Booking.id)).all()]


def stored_requirements(session) -> list[tuple[int, str | None]]:
    session.expire_all()
    rows = session.exec(select(BookingRequirement).order_by(BookingRequirement.id)).all()
    return [(row.booking_id, row.description) for row in rows]


def stored_booking_tables(session) -> list[int]:
    session.expire_all()
    return [row.booking_id for row in session.exec(select(BookingTable)).all()]


def occupied_seats(session, slot_id: int) -> dict[int, int]:
    session.expire_all()
    rows = session.exec(
        select(Table.number, SlotTable.occupied_seats)
        .join(Table, Table.id == SlotTable.table_id)
        .where(SlotTable.slot_id == slot_id)
    ).all()
    return dict(rows)


# ---------- Fixtures ----------

@pytest.fixture(autouse=True)
def real_auth(as_warden):
    """Removes the as_warden override of conftest.py: the real token and role checks run."""
    app.dependency_overrides.clear()


@pytest.fixture
def hiker(session) -> User:
    return add_user(session, "anna.rossi", Roles.HIKER)


@pytest.fixture
def as_hiker(client, hiker):
    return login(client, hiker)


@pytest.fixture
def add_slot(session):
    """Factory: adds a slot offering all TABLES, optionally with seats already occupied."""
    warden_id = add_user(session, "luca.bonetti", Roles.WARDEN).id
    tables = [Table(number=n, capacity=c, location="Main hall") for n, c in TABLES.items()]
    session.add_all(tables)
    session.flush()
    table_ids = {table.number: table.id for table in tables}
    session.commit()

    def _add_slot(start: datetime, occupied: dict[int, int] | None = None) -> int:
        occupied = occupied or {}
        slot = Slot(start_time=start, end_time=start + timedelta(minutes=90), created_by=warden_id)
        session.add(slot)
        session.flush()
        slot_id = slot.id
        session.add_all([
            SlotTable(slot_id=slot_id, table_id=table_ids[n], occupied_seats=occupied.get(n, 0))
            for n in sorted(table_ids)
        ])
        session.commit()
        return slot_id

    return _add_slot


@pytest.fixture
def lunch(add_slot) -> int:
    return add_slot(at(far_day(), LUNCH))


@pytest.fixture
def dinner(add_slot) -> int:
    return add_slot(at(far_day(), DINNER))


# ---------- Tests: successful cancellation ----------

def test_cancel_removes_the_booking_and_frees_its_seats(as_hiker, session, lunch):
    booking_id = book_id(as_hiker, 5)

    response = cancel(as_hiker, booking_id)

    assert response.status_code == 204
    assert response.content == b""
    assert stored_bookings(session) == []
    assert stored_booking_tables(session) == []
    assert occupied_seats(session, lunch) == {1: 0, 2: 0, 3: 0}


def test_cancel_removes_the_requirements(as_hiker, session, lunch):
    booking_id = book_id(as_hiker, 2, requirements=[
        {"allergies": True, "description": "Nuts"},
        {"description": "Vegan"},
    ])

    assert cancel(as_hiker, booking_id).status_code == 204

    assert stored_requirements(session) == []


def test_cancel_leaves_the_other_bookings_untouched(as_hiker, session, lunch, dinner):
    lunch_id = book_id(as_hiker, 2, requirements=[{"description": "Vegan"}])
    dinner_id = book_id(as_hiker, 4, start=DINNER, requirements=[{"description": "Gluten free"}])

    assert cancel(as_hiker, lunch_id).status_code == 204

    assert stored_bookings(session) == [dinner_id]
    assert stored_requirements(session) == [(dinner_id, "Gluten free")]
    assert occupied_seats(session, lunch) == {1: 0, 2: 0, 3: 0}
    assert occupied_seats(session, dinner) == {1: 0, 2: 4, 3: 0}


def test_cancel_keeps_the_seats_occupied_by_others(as_hiker, session, add_slot):
    slot = add_slot(at(far_day(), LUNCH), occupied={2: 4, 3: 6})
    booking_id = book_id(as_hiker, 2)  # the last 2 seats, table 1

    assert cancel(as_hiker, booking_id).status_code == 204

    assert occupied_seats(session, slot) == {1: 0, 2: 4, 3: 6}


def test_freed_seats_can_be_booked_by_another_hiker(client, session, hiker, as_hiker, add_slot):
    add_slot(at(far_day(), LUNCH), occupied={3: 6})  # 6 free seats
    booking_id = book_id(as_hiker, 6)
    other = add_user(session, "paolo.bianchi", Roles.HIKER)
    login(client, other)
    assert book(client, 2).status_code == 409  # the slot is full

    login(client, hiker)
    assert cancel(client, booking_id).status_code == 204
    login(client, other)

    assert book(client, 2).status_code == 201


def test_booking_without_assigned_tables_is_cancelled(as_hiker, session, hiker, lunch):
    # nothing to release: release_tables returns early
    booking = Booking(user_id=hiker.id, slot_id=lunch, party_size=2)
    session.add(booking)
    session.commit()

    response = cancel(as_hiker, booking.id)

    assert response.status_code == 204
    assert stored_bookings(session) == []


def test_hiker_can_book_the_same_slot_again_after_cancelling(as_hiker, session, lunch):
    booking_id = book_id(as_hiker, 2)
    assert book(as_hiker, 2).status_code == 409  # one booking per slot

    assert cancel(as_hiker, booking_id).status_code == 204

    assert book(as_hiker, 2).status_code == 201


# ---------- Tests: refused cancellation (nothing deleted) ----------

def test_unknown_booking_is_not_found(as_hiker, session, lunch):
    booking_id = book_id(as_hiker, 2)

    response = cancel(as_hiker, booking_id + 1)

    assert response.status_code == 404
    assert response.json() == {"detail": "Booking not found"}
    assert stored_bookings(session) == [booking_id]


def test_booking_of_another_hiker_is_not_found(client, session, as_hiker, lunch):
    booking_id = book_id(as_hiker, 2, requirements=[{"description": "Vegan"}])
    login(client, add_user(session, "paolo.bianchi", Roles.HIKER))

    response = cancel(client, booking_id)

    assert response.status_code == 404
    assert response.json() == {"detail": "Booking not found"}
    assert stored_bookings(session) == [booking_id]
    assert stored_requirements(session) == [(booking_id, "Vegan")]
    assert occupied_seats(session, lunch) == {1: 2, 2: 0, 3: 0}


def test_cancelling_twice_is_not_found(as_hiker, lunch):
    booking_id = book_id(as_hiker, 2)
    assert cancel(as_hiker, booking_id).status_code == 204

    response = cancel(as_hiker, booking_id)

    assert response.status_code == 404
    assert response.json() == {"detail": "Booking not found"}


# ---------- Tests: authentication ----------

def test_anonymous_user_cannot_cancel(client, session, as_hiker, lunch):
    booking_id = book_id(as_hiker, 2)
    client.cookies.clear()

    response = cancel(client, booking_id)

    assert response.status_code == 401
    assert stored_bookings(session) == [booking_id]


@pytest.mark.parametrize("role", [Roles.WARDEN, Roles.EMPLOYEE])
def test_staff_cannot_cancel(client, session, as_hiker, lunch, role):
    booking_id = book_id(as_hiker, 2)
    login(client, add_user(session, "giulia.ferrero", role))

    response = cancel(client, booking_id)

    assert response.status_code == 403
    assert response.json() == {"detail": "Not enough permissions"}
    assert stored_bookings(session) == [booking_id]


def test_session_of_deleted_hiker_is_rejected(as_hiker, session, hiker):
    # the session cookie is still valid, but its user id is no longer in the db
    session.delete(hiker)
    session.commit()

    response = cancel(as_hiker, 1)

    assert response.status_code == 401
    assert response.json() == {"detail": "User not found"}