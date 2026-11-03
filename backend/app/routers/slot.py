from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from app.database import SessionDep
from app.models import Slot, SlotAvailability, SlotDetail, SlotTable, SlotTableInfo, Table

router = APIRouter(prefix="/slot", tags=["slot"])
HUT_TIMEZONE = ZoneInfo("Europe/Rome")


@router.get("", response_model=list[SlotAvailability], status_code=200)
def get_slots(session: SessionDep):
    rows = session.exec(
        select(Slot, Table.capacity, SlotTable.occupied_seats)
        .join(SlotTable, SlotTable.slot_id == Slot.id)
        .join(Table, Table.id == SlotTable.table_id)
    ).all()

    slots: dict[int, tuple[Slot, int]] = {}
    for slot, capacity, occupied_seats in rows:
        available_seats = max(capacity - occupied_seats, 0)
        if slot.id is not None:
            current, total_available = slots.get(slot.id, (slot, 0))
            slots[slot.id] = (current, total_available + available_seats)

    now = datetime.now(HUT_TIMEZONE)
    return [
        SlotAvailability(
            id=slot.id,
            date=_slot_start(slot).date(),
            time=_slot_start(slot).time(),
            available_seats=available_seats,
        )
        for slot, available_seats in slots.values()
        if available_seats > 0
        and now <= _slot_start(slot) - timedelta(hours=2)
    ]


def _slot_start(slot: Slot) -> datetime:
    if slot.start_time.tzinfo is None:
        return slot.start_time.replace(tzinfo=HUT_TIMEZONE)
    return slot.start_time.astimezone(HUT_TIMEZONE)

@router.get("/{id}", response_model=SlotDetail, status_code=200)
def get_slot_info(id: int, session: SessionDep):
    slot = session.get(Slot, id)
    if not slot:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Slot not found")

    rows = session.exec(
        select(SlotTable.id, Table.id, Table.capacity, SlotTable.occupied_seats)
        .where(Table.id == SlotTable.table_id, SlotTable.slot_id == slot.id)
    ).all()

    tables = []
    for slot_table_id, table_id, capacity, occupied_seats in rows:
        tables.append(
            SlotTableInfo(
                id=slot_table_id,
                table_id=table_id,
                seats_booked=occupied_seats,
                seats_free=capacity - occupied_seats,
            )
        )

    return SlotDetail(
            id=slot.id,
            tables=tables,
            start_time=slot.start_time,
            end_time=slot.end_time,
            created_by = slot.created_by
        )