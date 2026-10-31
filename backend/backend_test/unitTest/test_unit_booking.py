from contextlib import nullcontext
from datetime import date, datetime, time, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest
from fastapi import HTTPException

from app.models import Booking, BookingCreate, BookingTable, Roles, Slot, SlotTable, Table, UserPublic
from app.routers.booking import create_booking
import app.services.booking as booking_service
from app.services.booking import (
    _distribute,
    _slot_datetime,
    allocate,
    assign_tables,
    booking_response,
    find_slot,
    get_free_seats,
    get_user,
    slot_start,
)


HUT_TIMEZONE = ZoneInfo("Europe/Rome")


def test_allocate_prefers_best_fit_single_table():
    assert allocate({1: 8, 2: 5, 3: 6}, 5) == [(2, 5)]


def test_allocate_splits_using_minimum_waste_and_deterministic_order():
    assert allocate({1: 3, 2: 4, 3: 4}, 7) == [(2, 4), (1, 3)]


@pytest.mark.parametrize("party_size", [0, -1])
def test_allocate_rejects_non_positive_party_size(party_size):
    with pytest.raises(ValueError, match="party_size must be > 0"):
        allocate({1: 4}, party_size)


def test_allocate_returns_none_when_capacity_is_insufficient():
    assert allocate({1: 2, 2: 0}, 3) is None


def test_allocate_skips_combinations_that_are_too_small():
    assert allocate({1: 2, 2: 2, 3: 5}, 6) == [(3, 5), (1, 1)]


def test_allocate_uses_three_tables_when_no_pair_is_large_enough():
    assert allocate({1: 2, 2: 2, 3: 2}, 5) == [(1, 2), (2, 2), (3, 1)]


def test_distribute_fills_largest_tables_first():
    assert _distribute((1, 2), {1: 2, 2: 5}, 4) == [(2, 4)]


def test_distribute_returns_partial_result_when_n_exceeds_capacity():
    assert _distribute((1, 2), {1: 2, 2: 3}, 10) == [(2, 3), (1, 2)]


def test_slot_start_and_slot_datetime_normalize_to_hut_timezone():
    naive = datetime(2030, 1, 1, 12, 0)
    slot = Slot(id=1, start_time=naive, end_time=naive, created_by=1)

    assert slot_start(slot).tzinfo == HUT_TIMEZONE
    assert _slot_datetime(date(2030, 1, 1), time(12, 0)).tzinfo == HUT_TIMEZONE


def test_get_user_returns_user():
    user = UserPublic(username="anna.rossi", role=Roles.HIKER)
    session = MagicMock()
    session.exec.return_value.first.return_value = user

    assert get_user(session, "anna.rossi") == user


def test_get_user_raises_when_user_does_not_exist():
    session = MagicMock()
    session.exec.return_value.first.return_value = None

    with pytest.raises(HTTPException) as exc:
        get_user(session, "missing")

    assert exc.value.status_code == 401


def test_find_slot_returns_matching_future_slot():
    start = datetime.now(HUT_TIMEZONE) + timedelta(hours=4)
    slot = Slot(id=1, start_time=start, end_time=start, created_by=1)
    session = MagicMock()
    session.exec.return_value.all.return_value = [slot]

    assert find_slot(session, start.date(), start.time()) is slot


def test_find_slot_raises_when_slot_is_missing_or_booking_is_closed():
    session = MagicMock()
    session.exec.return_value.all.return_value = []

    with pytest.raises(HTTPException) as missing:
        find_slot(session, date(2030, 1, 1), time(12, 0))
    assert missing.value.status_code == 404

    closed = datetime.now(HUT_TIMEZONE) + timedelta(hours=1)
    session.exec.return_value.all.return_value = [
        Slot(id=1, start_time=closed, end_time=closed, created_by=1)
    ]
    with pytest.raises(HTTPException) as too_late:
        find_slot(session, closed.date(), closed.time())
    assert too_late.value.status_code == 400


def test_booking_response_returns_assigned_tables():
    slot = Slot(
        id=2,
        start_time=datetime(2030, 1, 1, 12, 0, tzinfo=HUT_TIMEZONE),
        end_time=datetime(2030, 1, 1, 13, 30, tzinfo=HUT_TIMEZONE),
        created_by=1,
    )
    assignment = BookingTable(booking_id=8, slot_table_id=10, seats_booked=3)
    session = MagicMock()
    session.exec.return_value.all.return_value = [(assignment, 4)]
    session.get.return_value = slot

    result = booking_response(session, Booking(id=8, user_id=1, slot_id=2, party_size=3))

    assert result["id"] == 8
    assert result["tables"] == [{"number": 4, "seats": 3}]


def test_booking_response_raises_when_slot_is_missing():
    session = MagicMock()
    session.exec.return_value.all.return_value = []
    session.get.return_value = None

    with pytest.raises(HTTPException) as exc:
        booking_response(session, Booking(id=8, user_id=1, slot_id=2, party_size=3))

    assert exc.value.status_code == 500


def test_get_free_seats_returns_persisted_availability(monkeypatch):
    availability = [
        SimpleNamespace(number=1, free_seats=2),
        SimpleNamespace(number=2, free_seats=4),
    ]
    monkeypatch.setattr("app.services.booking._get_table_availability", lambda session, slot_id: availability)

    assert get_free_seats(MagicMock(), 5) == {1: 2, 2: 4}


def test_get_table_availability_clamps_negative_free_seats():
    slot_table = SlotTable(id=10, slot_id=2, table_id=3, occupied_seats=8)
    session = MagicMock()
    session.exec.return_value.all.return_value = [(slot_table, 4, 6)]

    availability = booking_service._get_table_availability(session, 2)

    assert availability[0].number == 4
    assert availability[0].capacity == 6
    assert availability[0].free_seats == 0


def test_allocate_from_availability_uses_table_numbers():
    availability = [
        booking_service.TableAvailability(
            number=4,
            slot_table=SlotTable(id=10, slot_id=2, table_id=3),
            capacity=6,
            free_seats=4,
        )
    ]

    assert booking_service._allocate_from_availability(availability, 3) == [(4, 3)]


def test_assign_tables_persists_booking_and_assignments():
    slot_table = SlotTable(id=10, slot_id=2, table_id=3, occupied_seats=1)
    availability = [
        SimpleNamespace(
            number=4,
            slot_table=slot_table,
            capacity=6,
            free_seats=5,
        )
    ]
    session = MagicMock()
    session.flush.side_effect = lambda: setattr(booking, "id", 20)
    booking = Booking(user_id=1, slot_id=2, party_size=3)
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        booking_service,
        "_get_table_availability",
        lambda current_session, slot_id: availability,
    )
    result = assign_tables(session, booking)
    monkeypatch.undo()

    assert booking.id == 20
    assert slot_table.occupied_seats == 4
    assert result[0].seats_booked == 3
    session.add.assert_called_once_with(booking)
    session.add_all.assert_called_once()


def test_assign_tables_returns_none_when_no_assignment_is_possible(monkeypatch):
    monkeypatch.setattr(booking_service, "_get_table_availability", lambda session, slot_id: [])
    session = MagicMock()
    booking = Booking(id=20, user_id=1, slot_id=2, party_size=3)

    assert assign_tables(session, booking) is None
    session.add.assert_not_called()
    session.add_all.assert_not_called()


def test_assign_tables_rejects_assignment_exceeding_capacity(monkeypatch):
    availability = [
        booking_service.TableAvailability(
            number=4,
            slot_table=SlotTable(id=10, slot_id=2, table_id=3, occupied_seats=5),
            capacity=6,
            free_seats=4,
        )
    ]
    monkeypatch.setattr(
        booking_service,
        "_get_table_availability",
        lambda session, slot_id: availability,
    )
    monkeypatch.setattr(
        booking_service,
        "_allocate_from_availability",
        lambda current_availability, party_size: [(4, 2)],
    )
    session = MagicMock()
    booking = Booking(id=20, user_id=1, slot_id=2, party_size=2)

    assert assign_tables(session, booking) is None
    session.add_all.assert_not_called()


def test_assign_tables_uses_existing_booking_id(monkeypatch):
    slot_table = SlotTable(id=10, slot_id=2, table_id=3, occupied_seats=1)
    availability = [
        booking_service.TableAvailability(
            number=4,
            slot_table=slot_table,
            capacity=6,
            free_seats=5,
        )
    ]
    monkeypatch.setattr(
        booking_service,
        "_get_table_availability",
        lambda session, slot_id: availability,
    )
    session = MagicMock()
    booking = Booking(id=20, user_id=1, slot_id=2, party_size=2)

    result = assign_tables(session, booking)

    assert result[0].booking_id == 20
    session.add.assert_not_called()
    session.add_all.assert_called_once()


def test_create_booking_returns_booking_response(monkeypatch):
    session = MagicMock()
    session.exec.return_value.first.return_value = None
    user = UserPublic(username="anna.rossi", role=Roles.HIKER)
    db_user = SimpleNamespace(id=3)
    slot = SimpleNamespace(id=9)
    response = {"id": 20}
    booking = None

    monkeypatch.setattr("app.routers.booking.booking_transaction", lambda session: nullcontext())
    monkeypatch.setattr("app.routers.booking.get_user", lambda session, username: db_user)
    monkeypatch.setattr("app.routers.booking.find_slot", lambda session, data_date, data_time: slot)
    monkeypatch.setattr("app.routers.booking.assign_tables", lambda session, value: [MagicMock()])

    def make_response(current_session, value):
        nonlocal booking
        booking = value
        return response

    monkeypatch.setattr("app.routers.booking.booking_response", make_response)

    result = create_booking(
        BookingCreate(date=date(2030, 1, 1), time=time(12, 0), party_size=3),
        session,
        user,
    )

    assert result == response
    assert booking.user_id == 3
    assert booking.slot_id == 9
    assert booking.party_size == 3


def test_create_booking_rejects_duplicate_booking(monkeypatch):
    session = MagicMock()
    session.exec.return_value.first.return_value = MagicMock()
    monkeypatch.setattr("app.routers.booking.booking_transaction", lambda session: nullcontext())
    monkeypatch.setattr("app.routers.booking.get_user", lambda session, username: SimpleNamespace(id=3))
    monkeypatch.setattr("app.routers.booking.find_slot", lambda session, data_date, data_time: SimpleNamespace(id=9))

    with pytest.raises(HTTPException) as exc:
        create_booking(
            BookingCreate(date=date(2030, 1, 1), time=time(12, 0), party_size=3),
            session,
            UserPublic(username="anna.rossi", role=Roles.HIKER),
        )

    assert exc.value.status_code == 409
    assert exc.value.detail == "A booking already exists for this slot"


def test_create_booking_rejects_when_tables_are_unavailable(monkeypatch):
    session = MagicMock()
    session.exec.return_value.first.return_value = None
    monkeypatch.setattr("app.routers.booking.booking_transaction", lambda session: nullcontext())
    monkeypatch.setattr("app.routers.booking.get_user", lambda session, username: SimpleNamespace(id=3))
    monkeypatch.setattr("app.routers.booking.find_slot", lambda session, data_date, data_time: SimpleNamespace(id=9))
    monkeypatch.setattr("app.routers.booking.assign_tables", lambda session, booking: None)

    with pytest.raises(HTTPException) as exc:
        create_booking(
            BookingCreate(date=date(2030, 1, 1), time=time(12, 0), party_size=3),
            session,
            UserPublic(username="anna.rossi", role=Roles.HIKER),
        )

    assert exc.value.status_code == 409
    assert exc.value.detail == "There are not enough seats for this party"
