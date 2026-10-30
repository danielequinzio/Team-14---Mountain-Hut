from datetime import date, datetime, time, timedelta
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlmodel import Session, select

from app.models import Booking, BookingTable, Slot, SlotTable, Table, User

from itertools import combinations

HUT_TIMEZONE = ZoneInfo("Europe/Rome")


@dataclass(frozen=True)
class TableAvailability:
    number: int
    slot_table: SlotTable
    capacity: int
    free_seats: int


def _slot_datetime(data_date: date, data_time: time) -> datetime:
    return datetime.combine(data_date, data_time, HUT_TIMEZONE)


def slot_start(slot: Slot) -> datetime:
    if slot.start_time.tzinfo is None:
        return slot.start_time.replace(tzinfo=HUT_TIMEZONE)
    return slot.start_time.astimezone(HUT_TIMEZONE)


def get_user(session: Session, username: str) -> User:
    user = session.exec(select(User).where(User.username == username)).first()
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    return user


def find_slot(session: Session, data_date: date, data_time: time) -> Slot:
    requested = _slot_datetime(data_date, data_time)
    slots = session.exec(select(Slot)).all()
    slot = next(
        (candidate for candidate in slots if slot_start(candidate) == requested),
        None,
    )
    if slot is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Slot not available")
    if datetime.now(HUT_TIMEZONE) > slot_start(slot) - timedelta(hours=2):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Bookings are closed less than two hours before the slot",
        )
    return slot


def booking_response(session: Session, booking: Booking) -> dict:
    assignments = session.exec(
        select(BookingTable, Table.number)
        .join(Table, Table.id == BookingTable.slot_table_id)
        .where(BookingTable.booking_id == booking.id)
    ).all()
    slot = session.get(Slot, booking.slot_id)
    if slot is None:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Booking slot not found",
        )
    return {
        "id": booking.id,
        "date": slot_start(slot).date(),
        "time": slot_start(slot).time(),
        "party_size": booking.party_size,
        "tables": [
            {"number": number, "seats": seats.seats_booked}
            for seats, number in assignments
        ],
    }


def allocate(free: dict[int, int], party_size: int) -> list[tuple[int, int]] | None:
    """
    free: {table_number: posti_liberi} per lo slot richiesto
    Ritorna [(table_id, posti_assegnati), ...] oppure None se non c'è posto.
    """
    if party_size <= 0:
        raise ValueError("party_size must be > 0")

    candidates = {t: f for t, f in free.items() if f > 0}
    if sum(candidates.values()) < party_size:
        return None

    # 1) un solo tavolo: best fit
    single = [(f, t) for t, f in candidates.items() if f >= party_size]
    if single:
        _, table_id = min(single)          # meno posti liberi, poi id più basso
        return [(table_id, party_size)]

    # 2) split: minimo numero di tavoli, poi minimo spreco
    tables = sorted(candidates)             # ordine deterministico
    for k in range(2, len(tables) + 1):
        best = None
        for combo in combinations(tables, k):
            total = sum(candidates[t] for t in combo)
            if total < party_size:
                continue
            key = (total - party_size, combo)   # spreco, poi tie-break su id
            if best is None or key < best:
                best = key
        if best is not None:
            return _distribute(best[1], candidates, party_size)
    return None


def _distribute(combo: tuple[int, ...], free: dict[int, int], n: int) -> list[tuple[int, int]]:
    """Riempie prima i tavoli con più posti liberi; l'ultimo prende il resto."""
    result, remaining = [], n
    for t in sorted(combo, key=lambda t: (-free[t], t)):
        take = min(free[t], remaining)
        result.append((t, take))
        remaining -= take
        if remaining == 0:
            break
    return result


def _get_table_availability(session: Session, slot_id: int) -> list[TableAvailability]:
    slot_tables = session.exec(
        select(SlotTable, Table.number, Table.capacity)
        .join(Table, Table.id == SlotTable.table_id)
        .where(SlotTable.slot_id == slot_id)
    ).all()

    return [
        TableAvailability(
            number=number,
            slot_table=slot_table,
            capacity=capacity,
            free_seats=max(capacity - slot_table.occupied_seats, 0),
        )
        for slot_table, number, capacity in slot_tables
    ]


def _allocate_from_availability(
    availability: list[TableAvailability], party_size: int
) -> list[tuple[int, int]] | None:
    return allocate(
        {table.number: table.free_seats for table in availability},
        party_size,
    )


def get_free_seats(session: Session, slot_id: int) -> dict[int, int]:
    """Return free seats by table number from the slot's persisted counters."""
    return {
        table.number: table.free_seats
        for table in _get_table_availability(session, slot_id)
    }

def assign_tables(session: Session, booking: Booking) -> list[BookingTable] | None:
    """Persist the table assignment for an existing booking.

    The booking must already have its ``slot_id`` and ``party_size`` set.  The
    caller owns the transaction; this function only flushes so that the
    generated booking id is available to the assignment rows.
    """
    availability = _get_table_availability(session, booking.slot_id)
    assignment = _allocate_from_availability(availability, booking.party_size)
    if assignment is None:
        return None

    table_by_number = {table.number: table for table in availability}

    for table_number, seats in assignment:
        table = table_by_number[table_number]
        if table.slot_table.occupied_seats + seats > table.capacity:
            return None

    if booking.id is None:
        session.add(booking)
        session.flush()

    rows = []

    for table_number, seats in assignment:
        slot_table = table_by_number[table_number].slot_table
        slot_table.occupied_seats += seats
        rows.append(
            BookingTable(
                booking_id=booking.id,
                slot_table_id=slot_table.id,
                seats_booked=seats,
            )
        )

    session.add_all(rows)
    session.flush()
    return rows


# Not needed for now, but could be useful for a booking cancellation story:
# def release_tables(session: Session, booking: Booking) -> None:
#     """Release the seats currently assigned to a booking."""
#     rows = session.exec(
#         select(BookingTable).where(BookingTable.booking_id == booking.id)
#     ).all()
#     if not rows:
#         return
#     slot_tables = {
#         row.id: row
#         for row in session.exec(
#             select(SlotTable).where(
#                 SlotTable.id.in_([assignment.slot_table_id for assignment in rows])
#             )
#         ).all()
#     }
#     for row in rows:
#         slot_tables[row.slot_table_id].occupied_seats -= row.seats_booked
#         session.delete(row)
#     session.flush()