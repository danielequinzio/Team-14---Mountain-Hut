"""
Integration tests of the slot management endpoints (/slots).

The routes run against the real test db created by conftest.py and the real
authentication (the as_warden override is removed: the user logs in for real).
Each test inserts only the rows it needs. Run from the backend folder with:

    python -m pytest backend_test -v
"""
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlmodel import select

from app.main import app
from app.models import Roles, Slot, SlotTable, Table, User
from app.services.auth import hash_password

HUT_TZ = ZoneInfo("Europe/Rome")
URL = "/slots"
PASSWORD = "password123"
DAY = date(2030, 1, 10)


# ---------- Helpers ----------

def at(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(day, time(hour, minute), HUT_TZ)


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


def add_table(session, number: int, capacity: int = 4) -> int:
    table = Table(number=number, capacity=capacity, location="Main hall")
    session.add(table)
    session.commit()
    return table.id


def slot_tables(session, slot_id: int) -> dict[int, int]:
    """table_id -> occupied seats of a slot, as stored in the db."""
    session.expire_all()  # read what the api committed
    rows = session.exec(
        select(SlotTable.table_id, SlotTable.occupied_seats).where(SlotTable.slot_id == slot_id)
    ).all()
    return dict(rows)


def slot_payload(start: datetime, minutes: int = 90) -> dict:
    return {"start_time": start.isoformat(), "end_time": (start + timedelta(minutes=minutes)).isoformat()}


# ---------- Fixtures ----------

@pytest.fixture(autouse=True)
def real_auth(as_warden):
    """Removes the as_warden override of conftest.py: the real token and role checks run."""
    app.dependency_overrides.clear()


@pytest.fixture
def warden(session) -> User:
    return add_user(session, "luca.bonetti", Roles.WARDEN)


@pytest.fixture
def as_warden_client(client, warden):
    return login(client, warden)


@pytest.fixture
def add_slot(session, warden):
    """Factory: adds a slot with the given tables, optionally with seats already occupied."""
    def _add_slot(start: datetime, table_ids=(), occupied: dict[int, int] | None = None) -> int:
        occupied = occupied or {}
        slot = Slot(start_time=start, end_time=start + timedelta(minutes=90), created_by=warden.id)
        session.add(slot)
        session.flush()
        session.add_all([
            SlotTable(slot_id=slot.id, table_id=t, occupied_seats=occupied.get(t, 0)) for t in table_ids
        ])
        session.commit()
        return slot.id

    return _add_slot


# ---------- Tests: authentication ----------

@pytest.mark.parametrize("method, path", [
    ("get", URL),
    ("get", f"{URL}/1"),
    ("post", URL),
    ("post", f"{URL}/1/tables"),
    ("post", f"{URL}/1/copy"),
])
def test_anonymous_user_is_rejected(client, method, path):
    assert getattr(client, method)(path).status_code == 401


def test_hiker_is_forbidden(client, session):
    login(client, add_user(session, "anna.rossi", Roles.HIKER))

    response = client.get(URL)

    assert response.status_code == 403
    assert response.json() == {"detail": "Not enough permissions"}


def test_employee_is_allowed(client, session):
    login(client, add_user(session, "giulia.ferrero", Roles.EMPLOYEE))

    assert client.get(URL).status_code == 200


# ---------- Tests: GET /slots ----------

def test_list_slots_empty(as_warden_client):
    response = as_warden_client.get(URL)

    assert response.status_code == 200
    assert response.json() == []


def test_list_slots_ordered_by_start(as_warden_client, add_slot):
    late = add_slot(at(DAY, 19))
    early = add_slot(at(DAY, 12))

    response = as_warden_client.get(URL)

    assert [s["id"] for s in response.json()] == [early, late]


def test_list_slots_by_date(as_warden_client, add_slot):
    add_slot(at(DAY - timedelta(days=1), 12))
    lunch = add_slot(at(DAY, 12))
    dinner = add_slot(at(DAY, 19))
    add_slot(at(DAY + timedelta(days=1), 12))

    response = as_warden_client.get(URL, params={"date": DAY.isoformat()})

    assert [s["id"] for s in response.json()] == [lunch, dinner]


def test_list_slots_by_range_inclusive(as_warden_client, add_slot):
    ids = [add_slot(at(DAY + timedelta(days=i), 12)) for i in range(5)]

    response = as_warden_client.get(URL, params={
        "from_date": (DAY + timedelta(days=1)).isoformat(),
        "to_date": (DAY + timedelta(days=3)).isoformat(),
    })

    assert [s["id"] for s in response.json()] == ids[1:4]


def test_list_slots_inverted_range(as_warden_client):
    response = as_warden_client.get(URL, params={
        "from_date": (DAY + timedelta(days=1)).isoformat(),
        "to_date": DAY.isoformat(),
    })

    assert response.status_code == 400
    assert response.json() == {"detail": "from_date must not be after to_date"}


def test_list_slots_invalid_date(as_warden_client):
    assert as_warden_client.get(URL, params={"date": "not-a-date"}).status_code == 422


# ---------- Tests: GET /slots/{id} ----------

def test_get_slot_with_tables(as_warden_client, session, add_slot, warden):
    small, big = add_table(session, 1, capacity=2), add_table(session, 2, capacity=6)
    slot_id = add_slot(at(DAY, 12), [small, big], occupied={big: 4})

    response = as_warden_client.get(f"{URL}/{slot_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == slot_id
    assert body["created_by"] == warden.id
    tables = {t["table_id"]: (t["seats_booked"], t["seats_free"]) for t in body["tables"]}
    assert tables == {small: (0, 2), big: (4, 2)}


def test_get_slot_not_found(as_warden_client):
    response = as_warden_client.get(f"{URL}/999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Slot not found"}


# ---------- Tests: POST /slots ----------

def test_create_slot(as_warden_client, session, warden):
    response = as_warden_client.post(URL, json=slot_payload(at(DAY, 12)))

    assert response.status_code == 201
    body = response.json()
    assert body["created_by"] == warden.id
    # the api answers in UTC ("...Z"): compare the instants, not the strings
    assert datetime.fromisoformat(body["start_time"]) == at(DAY, 12)
    assert datetime.fromisoformat(body["end_time"]) == at(DAY, 13, 30)
    session.expire_all()
    assert session.get(Slot, body["id"]) is not None


def test_created_slot_appears_in_list(as_warden_client):
    created = as_warden_client.post(URL, json=slot_payload(at(DAY, 12))).json()

    listed = as_warden_client.get(URL, params={"date": DAY.isoformat()}).json()

    assert [s["id"] for s in listed] == [created["id"]]


@pytest.mark.parametrize("minutes", [0, -30])
def test_create_slot_end_not_after_start(as_warden_client, session, minutes):
    response = as_warden_client.post(URL, json=slot_payload(at(DAY, 12), minutes))

    assert response.status_code == 422
    assert session.exec(select(Slot)).all() == []


@pytest.mark.parametrize("missing", ["start_time", "end_time"])
def test_create_slot_missing_field(as_warden_client, missing):
    payload = slot_payload(at(DAY, 12))
    del payload[missing]

    assert as_warden_client.post(URL, json=payload).status_code == 422


# ---------- Tests: POST /slots/{id}/tables ----------

def test_add_tables(as_warden_client, session, add_slot):
    t1, t2 = add_table(session, 1), add_table(session, 2)
    slot_id = add_slot(at(DAY, 12))

    response = as_warden_client.post(f"{URL}/{slot_id}/tables", json={"table_ids": [t1, t2]})

    assert response.status_code == 200
    assert sorted(t["table_id"] for t in response.json()["tables"]) == [t1, t2]
    assert slot_tables(session, slot_id) == {t1: 0, t2: 0}


def test_add_tables_keeps_existing(as_warden_client, session, add_slot):
    t1, t2 = add_table(session, 1), add_table(session, 2)
    slot_id = add_slot(at(DAY, 12), [t1], occupied={t1: 3})

    response = as_warden_client.post(f"{URL}/{slot_id}/tables", json={"table_ids": [t2]})

    assert response.status_code == 200
    assert slot_tables(session, slot_id) == {t1: 3, t2: 0}


def test_add_tables_slot_not_found(as_warden_client, session):
    t1 = add_table(session, 1)

    response = as_warden_client.post(f"{URL}/999/tables", json={"table_ids": [t1]})

    assert response.status_code == 404
    assert response.json() == {"detail": "Slot not found"}


def test_add_tables_duplicate_ids(as_warden_client, session, add_slot):
    t1 = add_table(session, 1)
    slot_id = add_slot(at(DAY, 12))

    response = as_warden_client.post(f"{URL}/{slot_id}/tables", json={"table_ids": [t1, t1]})

    assert response.status_code == 400
    assert response.json() == {"detail": "A table cannot be added twice"}
    assert slot_tables(session, slot_id) == {}


def test_add_tables_unknown_table(as_warden_client, session, add_slot):
    t1 = add_table(session, 1)
    slot_id = add_slot(at(DAY, 12))

    response = as_warden_client.post(f"{URL}/{slot_id}/tables", json={"table_ids": [t1, 999]})

    assert response.status_code == 404
    assert response.json() == {"detail": "One or more tables not found"}
    assert slot_tables(session, slot_id) == {}  # nothing added, not even the valid table


def test_add_tables_already_in_slot(as_warden_client, session, add_slot):
    t1, t2 = add_table(session, 1), add_table(session, 2)
    slot_id = add_slot(at(DAY, 12), [t1])

    response = as_warden_client.post(f"{URL}/{slot_id}/tables", json={"table_ids": [t1, t2]})

    assert response.status_code == 409
    assert response.json() == {"detail": "A table is already assigned to this slot"}
    assert slot_tables(session, slot_id) == {t1: 0}  # t2 was not added either


def test_add_tables_empty_list(as_warden_client, add_slot):
    slot_id = add_slot(at(DAY, 12))

    assert as_warden_client.post(f"{URL}/{slot_id}/tables", json={"table_ids": []}).status_code == 422


# ---------- Tests: POST /slots/{id}/copy ----------

def test_copy_tables(as_warden_client, session, add_slot):
    t1, t2, t3 = add_table(session, 1), add_table(session, 2), add_table(session, 3)
    source = add_slot(at(DAY, 12), [t1, t2], occupied={t1: 3})
    target = add_slot(at(DAY, 19), [t3])

    response = as_warden_client.post(f"{URL}/{source}/copy", json={"target_slot_id": target})

    assert response.status_code == 200
    assert response.json()["id"] == target
    assert sorted(t["table_id"] for t in response.json()["tables"]) == [t1, t2, t3]
    # the bookings are not copied, and the source is unchanged
    assert slot_tables(session, target) == {t1: 0, t2: 0, t3: 0}
    assert slot_tables(session, source) == {t1: 3, t2: 0}


def test_copy_into_newly_created_slot(as_warden_client, session, add_slot):
    # the real flow: create the new slot with POST /slots, then copy into it
    t1 = add_table(session, 1)
    source = add_slot(at(DAY, 12), [t1])
    target = as_warden_client.post(URL, json=slot_payload(at(DAY + timedelta(days=1), 12))).json()["id"]

    response = as_warden_client.post(f"{URL}/{source}/copy", json={"target_slot_id": target})

    assert response.status_code == 200
    assert slot_tables(session, target) == {t1: 0}


def test_copy_empty_source(as_warden_client, session, add_slot):
    source = add_slot(at(DAY, 12))
    target = add_slot(at(DAY, 19))

    response = as_warden_client.post(f"{URL}/{source}/copy", json={"target_slot_id": target})

    assert response.status_code == 200
    assert response.json()["tables"] == []


@pytest.mark.parametrize("missing", ["source", "target"])
def test_copy_slot_not_found(as_warden_client, add_slot, missing):
    existing = add_slot(at(DAY, 12))
    source, target = (999, existing) if missing == "source" else (existing, 999)

    response = as_warden_client.post(f"{URL}/{source}/copy", json={"target_slot_id": target})

    assert response.status_code == 404
    assert response.json() == {"detail": "Source or target slot not found"}


def test_copy_same_slot(as_warden_client, add_slot):
    slot_id = add_slot(at(DAY, 12))

    response = as_warden_client.post(f"{URL}/{slot_id}/copy", json={"target_slot_id": slot_id})

    assert response.status_code == 400
    assert response.json() == {"detail": "Source and target slots must differ"}


def test_copy_table_already_in_target(as_warden_client, session, add_slot):
    t1, t2, t3 = add_table(session, 1), add_table(session, 2), add_table(session, 3)
    source = add_slot(at(DAY, 12), [t1, t2])
    target = add_slot(at(DAY, 19), [t2, t3])

    response = as_warden_client.post(f"{URL}/{source}/copy", json={"target_slot_id": target})

    assert response.status_code == 409
    assert response.json() == {"detail": "A table is already assigned to the target slot"}
    assert slot_tables(session, target) == {t2: 0, t3: 0}  # t1 was not copied either


@pytest.mark.parametrize("target", [0, -1])
def test_copy_invalid_target_id(as_warden_client, add_slot, target):
    source = add_slot(at(DAY, 12))

    assert as_warden_client.post(f"{URL}/{source}/copy", json={"target_slot_id": target}).status_code == 422