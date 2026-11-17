from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import select

from app.database import SessionDep
from app.models import (
    CopySlotRequest,
    CurrentUser,
    Roles,
    Slot,
    SlotAvailability,
    SlotCreate,
    SlotDetail,
    SlotTable,
    SlotTableInfo,
    SlotTablesAdd,
    Table,
)

from app.services.user import EmployeeOrWarden

router = APIRouter(prefix="/slot", tags=["slot"])
management_router = APIRouter(prefix="/slots", tags=["slot management"])
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




@management_router.get("", response_model=list[Slot], status_code=200)
def list_configured_slots(
    session: SessionDep,
    user: EmployeeOrWarden,
    date: date | None = Query(default=None),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
):
    if from_date and to_date and from_date > to_date:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "from_date must not be after to_date")

    slots = session.exec(select(Slot).order_by(Slot.start_time)).all()
    return [
        slot for slot in slots
        if (date is None or _slot_start(slot).date() == date)
        and (from_date is None or _slot_start(slot).date() >= from_date)
        and (to_date is None or _slot_start(slot).date() <= to_date)
    ]


@management_router.get("/{id}", response_model=SlotDetail, status_code=200)
def get_configured_slot(id: int, session: SessionDep, user: EmployeeOrWarden):
    return get_slot_info(id, session)


@management_router.post("", response_model=Slot, status_code=status.HTTP_201_CREATED)
def create_slot(
    data: SlotCreate,
    session: SessionDep,
    user: EmployeeOrWarden,
):
    slot = Slot(start_time=data.start_time, end_time=data.end_time, created_by=user.id)
    session.add(slot)
    session.commit()
    session.refresh(slot)
    return slot


@management_router.post("/{id}/tables", response_model=SlotDetail, status_code=200)
def add_tables_to_slot(
    id: int,
    data: SlotTablesAdd,
    session: SessionDep,
    user: EmployeeOrWarden,
):
    slot = session.get(Slot, id)
    if slot is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Slot not found")

    table_ids = set(data.table_ids)
    if len(table_ids) != len(data.table_ids):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "A table cannot be added twice")

    tables = session.exec(select(Table).where(Table.id.in_(table_ids))).all()
    if len(tables) != len(table_ids):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "One or more tables not found")

    existing = set(session.exec(select(SlotTable.table_id).where(SlotTable.slot_id == id)).all())
    if existing.intersection(table_ids):
        raise HTTPException(status.HTTP_409_CONFLICT, "A table is already assigned to this slot")


    session.add_all([SlotTable(slot_id=id, table_id=table_id) for table_id in table_ids])
    session.commit()
    return get_slot_info(id, session)


@management_router.post("/{id}/copy", response_model=SlotDetail, status_code=200)
def copy_slot_tables(
    id: int,
    data: CopySlotRequest,
    session: SessionDep,
    user: EmployeeOrWarden,
):
    source = session.get(Slot, id)
    target = session.get(Slot, data.target_slot_id)
    if source is None or target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Source or target slot not found")
    if source.id == target.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Source and target slots must differ")
    source_tables = session.exec(select(SlotTable).where(SlotTable.slot_id == source.id)).all()
    existing = set(session.exec(select(SlotTable.table_id).where(SlotTable.slot_id == target.id)).all())
    if existing.intersection({row.table_id for row in source_tables}):
        raise HTTPException(status.HTTP_409_CONFLICT, "A table is already assigned to the target slot")
    session.add_all([SlotTable(slot_id=target.id, table_id=row.table_id) for row in source_tables])
    session.commit()
    return get_slot_info(target.id, session)