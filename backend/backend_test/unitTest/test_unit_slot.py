from datetime import datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from fastapi import HTTPException

from app.models import Slot
from app.routers.slot import get_slot_info, get_slots


HUT_TIMEZONE = ZoneInfo("Europe/Rome")


def test_get_slots_aggregates_available_seats_and_filters_closed_slots():
    future = datetime.now(HUT_TIMEZONE) + timedelta(hours=4)
    closed = datetime.now(HUT_TIMEZONE) + timedelta(hours=1)
    rows = [
        (Slot(id=1, start_time=future, end_time=future, created_by=1), 4, 1),
        (Slot(id=1, start_time=future, end_time=future, created_by=1), 2, 2),
        (Slot(id=2, start_time=closed, end_time=closed, created_by=1), 8, 0),
        (Slot(id=3, start_time=future, end_time=future, created_by=1), 2, 5),
    ]
    session = SimpleNamespace(exec=lambda query: SimpleNamespace(all=lambda: rows))

    result = get_slots(session)

    assert len(result) == 1
    assert result[0].id == 1
    assert result[0].available_seats == 3
    assert result[0].date == future.date()
    assert result[0].time == future.time()


def test_get_slots_handles_naive_datetimes():
    future = datetime.now() + timedelta(hours=4)
    slot = Slot(id=4, start_time=future, end_time=future, created_by=1)
    rows = [(slot, 4, 0)]
    session = SimpleNamespace(exec=lambda query: SimpleNamespace(all=lambda: rows))

    result = get_slots(session)

    assert len(result) == 1
    assert result[0].id == 4
    assert result[0].date == future.date()


def test_get_slots_ignores_rows_without_slot_id():
    future = datetime.now(HUT_TIMEZONE) + timedelta(hours=4)
    slot = Slot(start_time=future, end_time=future, created_by=1)
    rows = [(slot, 4, 0)]
    session = SimpleNamespace(exec=lambda query: SimpleNamespace(all=lambda: rows))

    assert get_slots(session) == []


def test_get_slot_info_returns_table_details():
    slot = Slot(
        id=7,
        start_time=datetime(2030, 1, 1, 12, 0, tzinfo=HUT_TIMEZONE),
        end_time=datetime(2030, 1, 1, 13, 30, tzinfo=HUT_TIMEZONE),
        created_by=4,
    )
    rows = [(11, 3, 6, 2), (12, 5, 4, 4)]
    session = SimpleNamespace(
        get=lambda model, identifier: slot,
        exec=lambda query: SimpleNamespace(all=lambda: rows),
    )

    result = get_slot_info(7, session)

    assert result.id == 7
    assert result.created_by == 4
    assert result.tables[0].model_dump() == {
        "id": 11,
        "table_id": 3,
        "seats_booked": 2,
        "seats_free": 4,
    }
    assert result.tables[1].seats_free == 0


def test_get_slot_info_raises_for_unknown_slot():
    session = SimpleNamespace(get=lambda model, identifier: None)

    with pytest.raises(HTTPException) as exc:
        get_slot_info(99, session)

    assert exc.value.status_code == 404
    assert exc.value.detail == "Slot not found"
