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

    # every table of the slot, with the seats already booked on it (0 if none)
    booked = func.coalesce(func.sum(BookingTable.seats_booked), 0)
    rows = session.exec(
        select(SlotTable, Table, booked)
        .join(Table, Table.id == SlotTable.table_id)
        .outerjoin(BookingTable, BookingTable.slot_table_id == SlotTable.id)
        .where(SlotTable.slot_id == id)
        .group_by(SlotTable.id, Table.id)
        .order_by(Table.number)
    ).all()

    tables = [SlotTableInfo(id=slot_table.id, table=table, seats_booked=seats_booked,
                            seats_free=table.capacity - seats_booked)
              for slot_table, table, seats_booked in rows]
    return SlotDetail(**slot.model_dump(), tables=tables)