from fastapi import APIRouter, Depends
from sqlmodel import select

from app.auth import require_role
from app.database import SessionDep
from app.models import Slot

router = APIRouter(prefix="/slot", tags=["slot"])


@router.get("", response_model=list[Slot], status_code=200)
def get_slots(session: SessionDep):
    slots = session.exec(select(Slot)).all()
    return slots