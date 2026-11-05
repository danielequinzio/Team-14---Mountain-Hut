"""
Integration tests for MH-01 "Book a table": POST /booking.

The route runs against the real test db created by conftest.py and the real
authentication (the as_warden override is removed: only hikers can book).
Each test inserts only the rows it needs. Run from the backend folder with:

    python -m pytest backend_test -v
"""
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlmodel import select

from app.main import app
from app.models import Booking, BookingTable, Roles, Slot, SlotTable, Table, User
from app.services.auth import hash_password

HUT_TZ = ZoneInfo("Europe/Rome")
URL = "/booking"
LUNCH = time(12, 0)
DINNER = time(19, 0)
TABLES = {1: 2, 2: 4, 3: 6}  # table number -> seats: 12 seats per slot
PASSWORD = "password123"

NOT_ENOUGH_SEATS = "There are not enough seats for this party"


# ---------- Helpers ----------

def tomorrow() -> date:
    return datetime.now(HUT_TZ).date() + timedelta(days=1)


def at(day: date, start: time) -> datetime:
    return datetime.combine(day, start, HUT_TZ)


def login(client, user: User):
    """Real login: the client keeps the session cookie for the next requests."""
    response = client.post("/login", json={"email": user.email, "password": PASSWORD})
    assert response.status_code == 200
    return client


def book(client, party_size, day=None, start=LUNCH):
    payload = {
        "date": (day or tomorrow()).isoformat(),
        "time": start.isoformat(),
        "party_size": party_size,
    }
    return client.post(URL, json=payload)


def add_user(session, username: str, role: Roles) -> User:
    name, surname = username.split(".")
    user = User(username=username, name=name.title(), surname=surname.title(),
                email=f"{username}@mail.example", mobile_number="+39 333 000 0000",
                password_hash=hash_password(PASSWORD), role=role)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def bookings(session) -> list[Booking]:
    session.expire_all()  # read what the api committed
    return session.exec(select(Booking)).all()


def occupied_seats(session, slot_id: int) -> dict[int, int]:
    """Occupied seats per table number of a slot, as stored in the db."""
    session.expire_all()
    rows = session.exec(
        select(Table.number, SlotTable.occupied_seats)
        .join(Table, Table.id == SlotTable.table_id)
        .where(SlotTable.slot_id == slot_id)
    ).all()
    return dict(rows)


def seats_by_table(response) -> dict[int, int]:
    return {table["number"]: table["seats"] for table in response.json()["tables"]}


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
    """Client logged in as the registered hiker."""
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
    """Tomorrow's 12:00 slot with all the tables free."""
    return add_slot(at(tomorrow(), LUNCH))


# ---------- Tests: authentication ----------

def test_anonymous_user_cannot_book(client):
    assert book(client, 2).status_code == 401


@pytest.mark.parametrize("role", [Roles.WARDEN, Roles.EMPLOYEE])
def test_staff_cannot_book(client, session, role):
    login(client, add_user(session, "giulia.ferrero", role))

    response = book(client, 2)

    assert response.status_code == 403
    assert response.json() == {"detail": "Not enough permissions"}


def test_session_of_deleted_hiker_is_rejected(as_hiker, session, hiker):
    # the session cookie is still valid, but its user id is no longer in the db
    session.delete(hiker)
    session.commit()

    response = book(as_hiker, 2)

    assert response.status_code == 401
    assert response.json() == {"detail": "User not found"}


# ---------- Tests: mandatory fields ----------

@pytest.mark.parametrize("missing", ["date", "time", "party_size"])
def test_missing_field_is_rejected(as_hiker, lunch, missing):
    payload = {"date": tomorrow().isoformat(), "time": "12:00:00", "party_size": 2}
    del payload[missing]

    assert as_hiker.post(URL, json=payload).status_code == 422


@pytest.mark.parametrize("party_size", [0, -1])
def test_party_size_must_be_positive(as_hiker, lunch, party_size):
    assert book(as_hiker, party_size).status_code == 422


# ---------- Tests: slot selection ----------

def test_time_not_matching_a_slot_start(as_hiker, lunch):
    response = book(as_hiker, 2, start=time(12, 30))

    assert response.status_code == 400
    assert response.json() == {"detail": "Slot not available"}


def test_date_without_slots(as_hiker, lunch):
    response = book(as_hiker, 2, day=tomorrow() + timedelta(days=1))

    assert response.status_code == 400
    assert response.json() == {"detail": "Slot not available"}


@pytest.mark.parametrize(
    "offset", [timedelta(hours=1), timedelta(days=-1)], ids=["within-2-hours", "past"]
)
def test_booking_closes_two_hours_before_the_slot(as_hiker, session, add_slot, offset):
    start = (datetime.now(HUT_TZ) + offset).replace(second=0, microsecond=0)
    add_slot(start)

    response = book(as_hiker, 2, day=start.date(), start=start.time())

    assert response.status_code == 400
    assert response.json() == {"detail": "Bookings are closed less than two hours before the slot"}
    assert bookings(session) == []


# ---------- Tests: table assignment ----------

def test_booking_is_returned_and_stored(as_hiker, session, hiker, lunch):
    response = book(as_hiker, 3)

    assert response.status_code == 201
    [booking] = bookings(session)
    assert (booking.user_id, booking.slot_id, booking.party_size) == (hiker.id, lunch, 3)
    assert response.json() == {
        "id": booking.id,
        "date": tomorrow().isoformat(),
        "time": "12:00:00",
        "party_size": 3,
        "tables": [{"number": 2, "seats": 3}],
    }
    [row] = session.exec(select(BookingTable)).all()
    assert (row.booking_id, row.seats_booked) == (booking.id, 3)
    assert occupied_seats(session, lunch) == {1: 0, 2: 3, 3: 0}


@pytest.mark.parametrize(("party_size", "expected"), [(2, {1: 2}), (3, {2: 3}), (5, {3: 5})])
def test_whole_party_at_the_smallest_table_that_fits(as_hiker, session, lunch, party_size, expected):
    response = book(as_hiker, party_size)

    assert response.status_code == 201
    assert seats_by_table(response) == expected
    assert occupied_seats(session, lunch) == {n: expected.get(n, 0) for n in TABLES}


def test_party_shares_a_table_with_other_guests(as_hiker, session, add_slot):
    slot = add_slot(at(tomorrow(), LUNCH), occupied={2: 3, 3: 2})  # free: 2, 1, 4

    response = book(as_hiker, 4)

    assert response.status_code == 201
    assert seats_by_table(response) == {3: 4}
    assert occupied_seats(session, slot) == {1: 0, 2: 3, 3: 6}


@pytest.mark.parametrize(
    ("party_size", "expected"),
    [(7, {3: 6, 1: 1}), (10, {3: 6, 2: 4}), (12, {3: 6, 2: 4, 1: 2})],
    ids=["fewest-seats", "two-tables", "all-tables"],
)
def test_party_is_split_over_the_fewest_tables(as_hiker, session, lunch, party_size, expected):
    response = book(as_hiker, party_size)

    assert response.status_code == 201
    assert seats_by_table(response) == expected
    assert occupied_seats(session, lunch) == {n: expected.get(n, 0) for n in TABLES}


@pytest.mark.parametrize(
    ("occupied", "party_size"),
    [({}, 13), ({3: 6}, 7)],
    ids=["over-slot-capacity", "seats-already-taken"],
)
def test_not_enough_seats_stores_nothing(as_hiker, session, add_slot, occupied, party_size):
    slot = add_slot(at(tomorrow(), LUNCH), occupied)

    response = book(as_hiker, party_size)

    assert response.status_code == 409
    assert response.json() == {"detail": NOT_ENOUGH_SEATS}
    assert bookings(session) == []
    assert occupied_seats(session, slot) == {n: occupied.get(n, 0) for n in TABLES}


def test_response_reports_table_numbers_on_any_slot(as_hiker, lunch, add_slot):
    # second slot: its slot_table ids (4..6) differ from the table ids (1..3)
    add_slot(at(tomorrow(), DINNER))

    response = book(as_hiker, 3, start=DINNER)

    assert response.status_code == 201
    assert seats_by_table(response) == {2: 3}


# ---------- Tests: one booking per slot ----------

def test_second_booking_on_the_same_slot_is_rejected(as_hiker, session, lunch):
    assert book(as_hiker, 2).status_code == 201

    response = book(as_hiker, 2)

    assert response.status_code == 409
    assert response.json() == {"detail": "A booking already exists for this slot"}
    assert len(bookings(session)) == 1
    assert occupied_seats(session, lunch) == {1: 2, 2: 0, 3: 0}


def test_same_hiker_can_book_another_slot(as_hiker, session, lunch, add_slot):
    add_slot(at(tomorrow(), DINNER))

    assert book(as_hiker, 2).status_code == 201
    assert book(as_hiker, 2, start=DINNER).status_code == 201
    assert len(bookings(session)) == 2