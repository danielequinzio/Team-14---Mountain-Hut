from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func
from sqlmodel import select

from app.database import SessionDep
from app.models import BookingTable, Slot, SlotDetail, SlotTable, SlotTableInfo, Table

router = APIRouter(prefix="/slot", tags=["slot"])


@router.get("", response_model=list[Slot], status_code=200)
def get_slots(session: SessionDep):
    slots = session.exec(select(Slot)).all()
    return slots

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