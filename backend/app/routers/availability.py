from datetime import date, time

from fastapi import APIRouter, Query

from app.database import SessionDep
from app.models import AvailabilityResponse
from app.services.booking import check_availability

router = APIRouter(prefix="/availability", tags=["availability"])


@router.get("", response_model=AvailabilityResponse, status_code=200)
def get_availability(
    session: SessionDep,
    date: date = Query(),
    time: time = Query(),
    party_size: int = Query(gt=0),
):
    """Tell whether a party fits in the slot starting at date+time, without booking."""
    return check_availability(session, date, time, party_size)