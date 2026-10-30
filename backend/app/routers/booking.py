from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select

from app.database import SessionDep, booking_transaction
from app.models import (
    Booking,
    BookingCreate,
    Roles,
    UserPublic,
)
from app.services.auth import require_role
from app.services.booking import (
    assign_tables,
    booking_response,
    find_slot,
    get_user,
)

router = APIRouter(prefix="/booking", tags=["booking"])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_booking(
    data: BookingCreate,
    session: SessionDep,
    user: Annotated[UserPublic, Depends(require_role(Roles.HIKER))],
):
    with booking_transaction(session):
        db_user = get_user(session, user.username)
        slot = find_slot(session, data.date, data.time)
        if session.exec(
            select(Booking).where(
                Booking.user_id == db_user.id,
                Booking.slot_id == slot.id,
            )
        ).first():
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "A booking already exists for this slot",
            )

        booking = Booking(
            user_id=db_user.id,
            slot_id=slot.id,
            party_size=data.party_size,
        )
        if assign_tables(session, booking) is None:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "There are not enough seats for this party",
            )
        return booking_response(session, booking)

# Probably not needed for the frontend at the moment, because this is sent via email
# @router.get("")
# def get_my_bookings(
#     session: SessionDep,
#     user: Annotated[UserPublic, Depends(require_role(Roles.HIKER))],
# ):
#     db_user = get_user(session, user.username)
#     bookings = session.exec(
#         select(Booking).where(Booking.user_id == db_user.id).order_by(Booking.slot_id)
#     ).all()
#     return [booking_response(session, booking) for booking in bookings]


# Not needed for now, but could be useful for a booking cancellation story:
# @router.patch("/{booking_id}")
# def update_booking(
#     booking_id: int,
#     data: BookingUpdate,
#     session: SessionDep,
#     user: Annotated[UserPublic, Depends(require_role(Roles.HIKER))],
# ):
#     with booking_transaction(session):
#         db_user = get_user(session, user.username)
#         booking = session.exec(
#             select(Booking).where(
#                 Booking.id == booking_id,
#                 Booking.user_id == db_user.id,
#             )
#         ).first()
#         if booking is None:
#             raise HTTPException(status.HTTP_404_NOT_FOUND, "Booking not found")
#
#         slot = session.get(Slot, booking.slot_id)
#         if slot is None:
#             raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Booking slot not found")
#         if datetime.now(HUT_TIMEZONE) > slot_start(slot) - timedelta(hours=2):
#             raise HTTPException(
#                 status.HTTP_400_BAD_REQUEST,
#                 "Bookings are closed less than two hours before the slot",
#             )
#
#         release_tables(session, booking)
#         booking.party_size = data.party_size
#         if assign_tables(session, booking) is None:
#             raise HTTPException(
#                 status.HTTP_409_CONFLICT,
#                 "There are not enough seats for this party",
#             )
#         return booking_response(session, booking)