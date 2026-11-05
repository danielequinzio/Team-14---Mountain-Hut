"""
Integration tests for GET /availability: can a party be seated in a slot?

The route runs against the real test db created by conftest.py and the real
authentication (the as_warden override is removed: the route is public).
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
URL = "/availability"
LUNCH = time(12, 0)
DINNER = time(19, 0)
TABLES = {1: 2, 2: 4, 3: 6}  # table number -> seats: 12 seats per slot

SLOT_NOT_AVAILABLE = "Slot not available"
BOOKINGS_CLOSED = "Bookings are closed less than two hours before the slot"


# ---------- Helpers ----------

def tomorrow() -> date:
    return datetime.now(HUT_TZ).date() + timedelta(days=1)


def at(day: date, start: time) -> datetime:
    return datetime.combine(day, start, HUT_TZ)


def check(client, party_size, day=None, start=LUNCH):
    params = {
        "date": (day or tomorrow()).isoformat(),
        "time": start.isoformat(),
        "party_size": party_size,
    }
    return client.get(URL, params=params)


def seats_by_table(response) -> dict[int, int]:
    return {table["number"]: table["seats"] for table in response.json()["tables"]}


def occupied_seats(session, slot_id: int) -> dict[int, int]:
    """Occupied seats per table number of a slot, as stored in the db."""
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
    """Removes the as_warden override of conftest.py: no user is logged in."""
    app.dependency_overrides.clear()


@pytest.fixture
def warden_id(session) -> int:
    user = User(username="luca.bonetti", name="Luca", surname="Bonetti",
                email="luca.bonetti@rifugio.example", mobile_number="+39 333 000 0000",
                password_hash=hash_password("password123"), role=Roles.WARDEN)
    session.add(user)
    session.commit()
    return user.id


@pytest.fixture
def table_ids(session) -> dict[int, int]:
    tables = [Table(number=n, capacity=c, location="Main hall") for n, c in TABLES.items()]
    session.add_all(tables)
    session.commit()
    return {table.number: table.id for table in tables}


@pytest.fixture
def add_slot(session, warden_id, table_ids):
    """Factory: adds a slot offering the given tables (all by default), optionally with seats occupied."""

    def _add_slot(start: datetime, occupied: dict[int, int] | None = None,
                  tables: list[int] | None = None) -> int:
        occupied = occupied or {}
        numbers = sorted(table_ids) if tables is None else tables
        slot = Slot(start_time=start, end_time=start + timedelta(minutes=90), created_by=warden_id)
        session.add(slot)
        session.flush()
        slot_id = slot.id
        session.add_all([
            SlotTable(slot_id=slot_id, table_id=table_ids[n], occupied_seats=occupied.get(n, 0))
            for n in numbers
        ])
        session.commit()
        return slot_id

    return _add_slot


@pytest.fixture
def lunch(add_slot) -> int:
    """Tomorrow's 12:00 slot with all the tables free."""
    return add_slot(at(tomorrow(), LUNCH))


# ---------- Tests: access ----------

def test_anonymous_user_can_check_availability(client, lunch):
    response = check(client, 2)

    assert response.status_code == 200
    assert response.json()["available"] is True


# ---------- Tests: available ----------

def test_small_party_gets_the_best_fitting_table(client, lunch):
    response = check(client, 2)

    assert response.status_code == 200
    assert response.json() == {"available": True, "tables": [{"number": 1, "seats": 2}]}


def test_party_gets_the_smallest_table_that_fits(client, lunch):
    response = check(client, 5)

    assert response.status_code == 200
    assert seats_by_table(response) == {3: 5}


def test_large_party_is_split_over_the_fewest_tables(client, lunch):
    response = check(client, 8)

    assert response.status_code == 200
    assert response.json()["available"] is True
    assert seats_by_table(response) == {1: 2, 3: 6}


def test_party_filling_every_seat_uses_all_tables(client, lunch):
    response = check(client, 12)

    assert response.status_code == 200
    assert seats_by_table(response) == {1: 2, 2: 4, 3: 6}


def test_occupied_seats_are_not_offered(client, add_slot):
    add_slot(at(tomorrow(), LUNCH), occupied={3: 6})

    response = check(client, 5)

    assert response.status_code == 200
    assert seats_by_table(response) == {2: 4, 1: 1}


def test_partially_occupied_table_can_still_be_used(client, add_slot):
    add_slot(at(tomorrow(), LUNCH), occupied={2: 1, 3: 6})

    response = check(client, 3)

    assert response.status_code == 200
    assert seats_by_table(response) == {2: 3}


def test_only_the_requested_slot_is_considered(client, add_slot):
    add_slot(at(tomorrow(), LUNCH), occupied={1: 2, 2: 4, 3: 6})  # full
    add_slot(at(tomorrow(), DINNER))

    assert check(client, 4, start=LUNCH).json()["available"] is False
    assert check(client, 4, start=DINNER).json()["available"] is True


# ---------- Tests: not available ----------

def test_party_larger_than_all_seats_is_not_available(client, lunch):
    response = check(client, 13)

    assert response.status_code == 200
    assert response.json() == {"available": False, "tables": []}


def test_full_slot_is_not_available(client, add_slot):
    add_slot(at(tomorrow(), LUNCH), occupied={1: 2, 2: 4, 3: 6})

    response = check(client, 1)

    assert response.status_code == 200
    assert response.json() == {"available": False, "tables": []}


def test_party_larger_than_the_free_seats_is_not_available(client, add_slot):
    add_slot(at(tomorrow(), LUNCH), occupied={2: 4, 3: 6})  # 2 seats left

    response = check(client, 3)

    assert response.status_code == 200
    assert response.json()["available"] is False


def test_slot_without_tables_is_not_available(client, add_slot):
    add_slot(at(tomorrow(), LUNCH), tables=[])

    response = check(client, 1)

    assert response.status_code == 200
    assert response.json() == {"available": False, "tables": []}


# ---------- Tests: read only ----------

def test_check_does_not_change_the_db(client, session, add_slot):
    slot_id = add_slot(at(tomorrow(), LUNCH), occupied={2: 1})

    response = check(client, 8)

    assert response.status_code == 200
    assert response.json()["available"] is True
    assert occupied_seats(session, slot_id) == {1: 0, 2: 1, 3: 0}
    session.expire_all()
    assert session.exec(select(Booking)).all() == []
    assert session.exec(select(BookingTable)).all() == []


def test_repeated_checks_give_the_same_answer(client, lunch):
    first = check(client, 8)
    second = check(client, 8)

    assert first.json() == second.json()


# ---------- Tests: slot errors ----------

def test_no_slot_at_that_time_is_rejected(client, lunch):
    response = check(client, 2, start=DINNER)

    assert response.status_code == 400
    assert response.json()["detail"] == SLOT_NOT_AVAILABLE


def test_no_slot_on_that_day_is_rejected(client, lunch):
    response = check(client, 2, day=tomorrow() + timedelta(days=1))

    assert response.status_code == 400
    assert response.json()["detail"] == SLOT_NOT_AVAILABLE


def test_slot_starting_in_less_than_two_hours_is_rejected(client, add_slot):
    start = (datetime.now(HUT_TZ) + timedelta(hours=1)).replace(second=0, microsecond=0)
    add_slot(start)

    response = check(client, 2, day=start.date(), start=start.time())

    assert response.status_code == 400
    assert response.json()["detail"] == BOOKINGS_CLOSED


def test_past_slot_is_rejected(client, add_slot):
    yesterday = tomorrow() - timedelta(days=2)
    add_slot(at(yesterday, LUNCH))

    response = check(client, 2, day=yesterday)

    assert response.status_code == 400
    assert response.json()["detail"] == BOOKINGS_CLOSED


# ---------- Tests: validation ----------

@pytest.mark.parametrize("party_size", [0, -1, "two"])
def test_invalid_party_size_is_rejected(client, lunch, party_size):
    response = check(client, party_size)

    assert response.status_code == 422


@pytest.mark.parametrize("missing", ["date", "time", "party_size"])
def test_missing_parameter_is_rejected(client, lunch, missing):
    params = {"date": tomorrow().isoformat(), "time": LUNCH.isoformat(), "party_size": 2}
    del params[missing]

    response = client.get(URL, params=params)

    assert response.status_code == 422


@pytest.mark.parametrize("field, value", [("date", "2026-13-01"), ("time", "25:00")])
def test_malformed_date_or_time_is_rejected(client, lunch, field, value):
    params = {"date": tomorrow().isoformat(), "time": LUNCH.isoformat(), "party_size": 2}
    params[field] = value

    response = client.get(URL, params=params)

    assert response.status_code == 422