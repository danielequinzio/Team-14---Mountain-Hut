"""
Unit tests of the slot management endpoints (/slots) in app/routers/slot.py.

The route functions are called directly with a fake session, so no db and no http are involved.
"""
from datetime import date, datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from fastapi import HTTPException

from app.models import Slot, SlotCreate, SlotTable, SlotTablesAdd, CopySlotRequest
from app.routers.slot import (
    add_tables_to_slot,
    create_slot,
    get_configured_slot,
    list_configured_slots, copy_slot_tables,
    list_week_slots,
)


HUT_TIMEZONE = ZoneInfo("Europe/Rome")
USER = SimpleNamespace(id=5, role="warden")


class FakeSession:
    """Stands in for the db session.

    `slots` maps an id to the Slot that session.get returns.
    `results` are the rows of each session.exec call, consumed in order.
    """

    def __init__(self, slots=None, results=None):
        self.slots = slots or {}
        self.results = list(results or [])
        self.added = []
        self.commits = 0

    def get(self, model, identifier):
        return self.slots.get(identifier)

    def exec(self, query):
        rows = self.results.pop(0)
        return SimpleNamespace(all=lambda: rows)

    def add(self, obj):
        self.added.append(obj)

    def add_all(self, objs):
        self.added.extend(objs)

    def commit(self):
        self.commits += 1

    def refresh(self, obj):
        obj.id = 1


def make_slot(slot_id, day=1, hour=12):
    start = datetime(2030, 1, day, hour, 0, tzinfo=HUT_TIMEZONE)
    return Slot(id=slot_id, start_time=start, end_time=start.replace(hour=hour + 1), created_by=5)


def list_slots(session, date=None, from_date=None, to_date=None):
    # the query params must be passed explicitly: their defaults are Query objects, not None
    return list_configured_slots(session, USER, date=date, from_date=from_date, to_date=to_date)

def week_slots(session, date):
    # the query param must be passed explicitly: its default is a Query object
    return list_week_slots(session, USER, date=date)


# ---------- GET /slots ----------

def test_list_configured_slots_returns_all_without_filters():
    slots = [make_slot(1, day=1), make_slot(2, day=2), make_slot(3, day=3)]
    session = FakeSession(results=[slots])

    assert [s.id for s in list_slots(session)] == [1, 2, 3]


def test_list_configured_slots_filters_by_date():
    slots = [make_slot(1, day=1), make_slot(2, day=2), make_slot(3, day=2, hour=18)]
    session = FakeSession(results=[slots])

    result = list_slots(session, date=date(2030, 1, 2))

    assert [s.id for s in result] == [2, 3]


def test_list_configured_slots_filters_by_range_inclusive():
    slots = [make_slot(i, day=i) for i in range(1, 6)]
    session = FakeSession(results=[slots])

    result = list_slots(session, from_date=date(2030, 1, 2), to_date=date(2030, 1, 4))

    assert [s.id for s in result] == [2, 3, 4]


def test_list_configured_slots_only_from_date():
    slots = [make_slot(i, day=i) for i in range(1, 4)]
    session = FakeSession(results=[slots])

    assert [s.id for s in list_slots(session, from_date=date(2030, 1, 2))] == [2, 3]


def test_list_configured_slots_only_to_date():
    slots = [make_slot(i, day=i) for i in range(1, 4)]
    session = FakeSession(results=[slots])

    assert [s.id for s in list_slots(session, to_date=date(2030, 1, 2))] == [1, 2]


def test_list_configured_slots_uses_hut_timezone_for_the_date():
    # 23:30 UTC on Jan 1 is already Jan 2 in Rome
    start = datetime(2030, 1, 1, 23, 30, tzinfo=ZoneInfo("UTC"))
    slot = Slot(id=1, start_time=start, end_time=start, created_by=5)
    session = FakeSession(results=[[slot]])

    assert list_slots(session, date=date(2030, 1, 2)) == [slot]


def test_list_configured_slots_treats_naive_datetimes_as_hut_time():
    start = datetime(2030, 1, 1, 23, 30)
    slot = Slot(id=1, start_time=start, end_time=start, created_by=5)
    session = FakeSession(results=[[slot]])

    assert list_slots(session, date=date(2030, 1, 1)) == [slot]


def test_list_configured_slots_returns_empty_when_nothing_matches():
    session = FakeSession(results=[[make_slot(1, day=1)]])

    assert list_slots(session, date=date(2031, 1, 1)) == []


def test_list_configured_slots_rejects_inverted_range():
    session = FakeSession()

    with pytest.raises(HTTPException) as exc:
        list_slots(session, from_date=date(2030, 1, 5), to_date=date(2030, 1, 1))

    assert exc.value.status_code == 400
    assert exc.value.detail == "from_date must not be after to_date"


# ---------- GET /slots/{id} ----------

def test_get_configured_slot_returns_detail():
    slot = make_slot(7)
    session = FakeSession(slots={7: slot}, results=[[(11, 3, 6, 2)]])

    result = get_configured_slot(7, session, USER)

    assert result.id == 7
    assert result.created_by == 5
    assert result.tables[0].model_dump() == {
        "id": 11,
        "table_id": 3,
        "seats_booked": 2,
        "seats_free": 4,
    }


def test_get_configured_slot_raises_for_unknown_slot():
    with pytest.raises(HTTPException) as exc:
        get_configured_slot(99, FakeSession(), USER)

    assert exc.value.status_code == 404
    assert exc.value.detail == "Slot not found"


# ---------- GET /slots/week ----------

def test_list_week_slots_returns_monday_to_sunday_only():
    # Jan 7 2030 is a monday: the week is Jan 7 - Jan 13
    slots = [make_slot(day, day=day) for day in (6, 7, 10, 13, 14)]
    session = FakeSession(results=[slots])

    result = week_slots(session, date(2030, 1, 10))

    assert [s.id for s in result] == [7, 10, 13]


@pytest.mark.parametrize("day", [7, 10, 13], ids=["monday", "wednesday", "sunday"])
def test_list_week_slots_any_day_gives_the_same_week(day):
    slots = [make_slot(d, day=d) for d in (6, 7, 13, 14)]
    session = FakeSession(results=[slots])

    assert [s.id for s in week_slots(session, date(2030, 1, day))] == [7, 13]


def test_list_week_slots_week_across_two_years():
    # Jan 1 2030 is a tuesday: the week is Dec 31 2029 - Jan 6 2030
    def slot_on(slot_id, year, month, day):
        start = datetime(year, month, day, 12, 0, tzinfo=HUT_TIMEZONE)
        return Slot(id=slot_id, start_time=start, end_time=start.replace(hour=13), created_by=5)

    slots = [
        slot_on(1, 2029, 12, 30),
        slot_on(2, 2029, 12, 31),
        slot_on(3, 2030, 1, 6),
        slot_on(4, 2030, 1, 7),
    ]
    session = FakeSession(results=[slots])

    assert [s.id for s in week_slots(session, date(2030, 1, 1))] == [2, 3]


def test_list_week_slots_returns_empty_when_week_has_no_slots():
    session = FakeSession(results=[[make_slot(1, day=1)]])

    assert week_slots(session, date(2030, 1, 10)) == []


# ---------- POST /slots ----------

def test_create_slot_saves_slot_with_creator():
    start = datetime(2030, 1, 1, 12, 0, tzinfo=HUT_TIMEZONE)
    end = datetime(2030, 1, 1, 13, 0, tzinfo=HUT_TIMEZONE)
    session = FakeSession(results=[[]])  # no existing slots

    result = create_slot(SlotCreate(start_time=start, end_time=end), session, USER)

    assert session.added == [result]
    assert session.commits == 1
    assert result.id == 1
    assert result.start_time == start
    assert result.end_time == end
    assert result.created_by == USER.id


@pytest.mark.parametrize(
    ("start_hour", "start_minute", "end_hour", "end_minute"),
    [
        (12, 0, 13, 0),    # same interval
        (11, 30, 12, 30),  # ends inside the existing 12:00-13:00
        (12, 30, 13, 30),  # starts inside it
        (12, 15, 12, 45),  # inside it
        (11, 0, 14, 0),    # contains it
    ],
    ids=["same", "end-inside", "start-inside", "inside", "contains"],
)
def test_create_slot_rejects_overlapping_slot(start_hour, start_minute, end_hour, end_minute):
    start = datetime(2030, 1, 1, start_hour, start_minute, tzinfo=HUT_TIMEZONE)
    end = datetime(2030, 1, 1, end_hour, end_minute, tzinfo=HUT_TIMEZONE)
    session = FakeSession(results=[[make_slot(1)]])  # 12:00-13:00

    with pytest.raises(HTTPException) as exc:
        create_slot(SlotCreate(start_time=start, end_time=end), session, USER)

    assert exc.value.status_code == 409
    assert exc.value.detail == "The slot overlaps an existing slot"
    assert session.added == []
    assert session.commits == 0


@pytest.mark.parametrize(
    ("start_hour", "end_hour"),
    [(11, 12), (13, 14)],  # ends when the existing one starts / starts when it ends
    ids=["just-before", "just-after"],
)
def test_create_slot_accepts_back_to_back_slots(start_hour, end_hour):
    start = datetime(2030, 1, 1, start_hour, 0, tzinfo=HUT_TIMEZONE)
    end = datetime(2030, 1, 1, end_hour, 0, tzinfo=HUT_TIMEZONE)
    session = FakeSession(results=[[make_slot(1)]])  # 12:00-13:00

    result = create_slot(SlotCreate(start_time=start, end_time=end), session, USER)

    assert session.added == [result]


def test_create_slot_compares_stored_naive_times_as_hut_time():
    # sqlite gives back 12:00-13:00 without timezone: it is Rome time
    stored = Slot(id=1, start_time=datetime(2030, 1, 1, 12, 0),
                  end_time=datetime(2030, 1, 1, 13, 0), created_by=5)
    # 11:30 UTC is 12:30 in Rome (winter): inside the stored slot
    start = datetime(2030, 1, 1, 11, 30, tzinfo=ZoneInfo("UTC"))
    end = datetime(2030, 1, 1, 12, 30, tzinfo=ZoneInfo("UTC"))
    session = FakeSession(results=[[stored]])

    with pytest.raises(HTTPException) as exc:
        create_slot(SlotCreate(start_time=start, end_time=end), session, USER)

    assert exc.value.status_code == 409


def test_slot_create_rejects_end_before_start():
    start = datetime(2030, 1, 1, 12, 0)

    with pytest.raises(ValueError):
        SlotCreate(start_time=start, end_time=start.replace(hour=11))


def test_slot_create_rejects_end_equal_to_start():
    start = datetime(2030, 1, 1, 12, 0)

    with pytest.raises(ValueError):
        SlotCreate(start_time=start, end_time=start)


# ---------- POST /slots/{id}/tables ----------

def test_add_tables_to_slot_adds_each_table():
    tables = [SimpleNamespace(id=1), SimpleNamespace(id=2)]
    detail_rows = [(10, 1, 4, 0), (11, 2, 6, 0)]
    session = FakeSession(slots={7: make_slot(7)}, results=[tables, [], detail_rows])

    result = add_tables_to_slot(7, SlotTablesAdd(table_ids=[1, 2]), session, USER)

    assert session.commits == 1
    assert all(isinstance(row, SlotTable) for row in session.added)
    assert {(row.slot_id, row.table_id) for row in session.added} == {(7, 1), (7, 2)}
    assert [t.table_id for t in result.tables] == [1, 2]


def test_add_tables_to_slot_keeps_existing_other_tables():
    session = FakeSession(
        slots={7: make_slot(7)},
        results=[[SimpleNamespace(id=2)], [1], [(10, 1, 4, 0), (11, 2, 6, 0)]],
    )

    add_tables_to_slot(7, SlotTablesAdd(table_ids=[2]), session, USER)

    assert [(row.slot_id, row.table_id) for row in session.added] == [(7, 2)]


def test_add_tables_to_slot_raises_for_unknown_slot():
    session = FakeSession()

    with pytest.raises(HTTPException) as exc:
        add_tables_to_slot(99, SlotTablesAdd(table_ids=[1]), session, USER)

    assert exc.value.status_code == 404
    assert exc.value.detail == "Slot not found"
    assert session.added == []


def test_add_tables_to_slot_rejects_duplicate_ids():
    session = FakeSession(slots={7: make_slot(7)})

    with pytest.raises(HTTPException) as exc:
        add_tables_to_slot(7, SlotTablesAdd(table_ids=[1, 2, 1]), session, USER)

    assert exc.value.status_code == 400
    assert exc.value.detail == "A table cannot be added twice"
    assert session.added == []


def test_add_tables_to_slot_raises_for_unknown_table():
    # table 99 doesn't exist: the query finds only table 1
    session = FakeSession(slots={7: make_slot(7)}, results=[[SimpleNamespace(id=1)]])

    with pytest.raises(HTTPException) as exc:
        add_tables_to_slot(7, SlotTablesAdd(table_ids=[1, 99]), session, USER)

    assert exc.value.status_code == 404
    assert exc.value.detail == "One or more tables not found"
    assert session.added == []


def test_add_tables_to_slot_rejects_table_already_in_slot():
    session = FakeSession(
        slots={7: make_slot(7)},
        results=[[SimpleNamespace(id=1), SimpleNamespace(id=2)], [2]],
    )

    with pytest.raises(HTTPException) as exc:
        add_tables_to_slot(7, SlotTablesAdd(table_ids=[1, 2]), session, USER)

    assert exc.value.status_code == 409
    assert exc.value.detail == "A table is already assigned to this slot"
    assert session.added == []
    assert session.commits == 0


def test_slot_tables_add_requires_at_least_one_table():
    with pytest.raises(ValueError):
        SlotTablesAdd(table_ids=[])


def test_copy_slot_from_another_correct():
    # source = slot 2 (has tables 1, 2, 3), target = slot 1 (already has tables 4, 5, 6)
    session = FakeSession(
        slots={1: make_slot(1), 2: make_slot(2)},
        results=[
            # 1st query: select(SlotTable) of the source -> SlotTable objects
            [
                SlotTable(slot_id=2, table_id=1, occupied_seats=3),
                SlotTable(slot_id=2, table_id=2),
                SlotTable(slot_id=2, table_id=3),
            ],
            # 2nd query: select(SlotTable.table_id) of the target -> plain table ids
            [4, 5, 6],
            # 3rd query: get_slot_info(target) -> (slot_table_id, table_id, capacity, occupied_seats)
            [
                (20, 4, 4, 0), (21, 5, 4, 0), (22, 6, 4, 0),
                (23, 1, 6, 0), (24, 2, 6, 0), (25, 3, 6, 0),
            ],
        ],
    )

    result = copy_slot_tables(2, CopySlotRequest(target_slot_id=1), session, USER)

    # one new SlotTable per source table, all pointing at the target slot
    assert [(row.slot_id, row.table_id) for row in session.added] == [(1, 1), (1, 2), (1, 3)]
    # the bookings of the source are not copied
    assert all(row.occupied_seats == 0 for row in session.added)
    assert session.commits == 1
    # the response is the target slot with its old tables plus the copied ones
    assert result.id == 1
    assert sorted(t.table_id for t in result.tables) == [1, 2, 3, 4, 5, 6]


def test_copy_slot_from_another_empty_source():
    # source = slot 2 has no tables: nothing is copied
    session = FakeSession(
        slots={1: make_slot(1), 2: make_slot(2)},
        results=[[], [], []],
    )

    result = copy_slot_tables(2, CopySlotRequest(target_slot_id=1), session, USER)

    assert session.added == []
    assert result.id == 1
    assert result.tables == []


def test_copy_slot_from_another_same_id():
    # source and target are the same slot
    session = FakeSession(
        slots={1: make_slot(1), 2: make_slot(2)},
    )
    with pytest.raises(HTTPException) as exc:
        copy_slot_tables(1, CopySlotRequest(target_slot_id=1), session, USER)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Source and target slots must differ"


def test_copy_slot_from_another_source_id_not_found():
    # source = slot 1 doesn't exist
    session = FakeSession(
        slots={2: make_slot(2)},
    )
    with pytest.raises(HTTPException) as exc:
        copy_slot_tables(1, CopySlotRequest(target_slot_id=2), session, USER)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Source or target slot not found"


def test_copy_slot_from_another_target_id_not_found():
    # source = slot 2 exists, target = slot 1 doesn't
    session = FakeSession(
        slots={2: make_slot(2)},
    )
    with pytest.raises(HTTPException) as exc:
        copy_slot_tables(2, CopySlotRequest(target_slot_id=1), session, USER)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Source or target slot not found"


def test_copy_slot_from_another_same_table():
    # source = slot 1 (tables 1, 2, 3), target = slot 2 (already has tables 1, 2, 3)
    session = FakeSession(
        slots={1: make_slot(1), 2: make_slot(2)},
        results=[
            # 1st query: select(SlotTable) of the source -> SlotTable objects
            [
                SlotTable(slot_id=1, table_id=1),
                SlotTable(slot_id=1, table_id=2),
                SlotTable(slot_id=1, table_id=3),
            ],
            # 2nd query: select(SlotTable.table_id) of the target -> plain table ids
            [1, 2, 3],
        ],
    )
    with pytest.raises(HTTPException) as exc:
        copy_slot_tables(1, CopySlotRequest(target_slot_id=2), session, USER)
    assert exc.value.status_code == 409
    assert exc.value.detail == "A table is already assigned to the target slot"
    assert session.added == []
    assert session.commits == 0


def test_copy_slot_from_another_one_shared_table():
    # source = slot 1 (tables 1, 2, 3), target = slot 2 (tables 3, 7): only table 3 is shared
    session = FakeSession(
        slots={1: make_slot(1), 2: make_slot(2)},
        results=[
            [
                SlotTable(slot_id=1, table_id=1),
                SlotTable(slot_id=1, table_id=2),
                SlotTable(slot_id=1, table_id=3),
            ],
            [3, 7],
        ],
    )
    with pytest.raises(HTTPException) as exc:
        copy_slot_tables(1, CopySlotRequest(target_slot_id=2), session, USER)
    assert exc.value.status_code == 409
    assert session.added == []
    assert session.commits == 0


def test_copy_slot_request_requires_positive_target():
    with pytest.raises(ValueError):
        CopySlotRequest(target_slot_id=0)