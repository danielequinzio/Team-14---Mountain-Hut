from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlmodel import select

from app.database import SessionDep, booking_transaction
from app.models import (
    Booking,
    BookingCreate,
    BookingRequirement,
    CurrentUser,
    Roles,
    Slot,
    SlotTable,
    Table,
    TableSeats,
)
from app.services.auth import require_role
from app.services.booking import (
    assign_tables,
    booking_response,
    find_slot,
    get_user,
)

from app.services.notification import build_confirmation, send_booking_confirmation
from app.models.booking import BookingDetails

router = APIRouter(prefix="/booking", tags=["booking"])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_booking(
    data: BookingCreate,
    session: SessionDep,
    user: Annotated[CurrentUser, Depends(require_role(Roles.HIKER))],
    background_tasks: BackgroundTasks,
):
    with booking_transaction(session):
        db_user = get_user(session, user.id)
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
        session.add_all(
            [
                BookingRequirement(
                    booking_id=booking.id,
                    allergies=requirement.allergies,
                    description=requirement.description,
                )
                for requirement in data.requirements
            ]
        )
        response = booking_response(session, booking)
        confirmation = build_confirmation(db_user, slot, booking)

    # fuori dal blocco: l'email parte solo dopo il commit
    background_tasks.add_task(send_booking_confirmation, confirmation)
    return response


@router.get("")
def get_my_bookings(
     session: SessionDep,
     user: Annotated[CurrentUser, Depends(require_role(Roles.HIKER))],
    ):
     db_user = get_user(session, user.id)

     bookings = session.exec(
        select(
            Booking.id,
            Booking.party_size,
            Slot.start_time,
            Slot.end_time,
            Table.number,
            BookingTable.seats_booked,
        )
        .join(Slot, Slot.id == Booking.slot_id)
        .join(BookingTable, BookingTable.booking_id == Booking.id)
        .join(
            SlotTable,
            (SlotTable.id == BookingTable.slot_table_id)
            & (SlotTable.slot_id == Slot.id),
        )
        .join(Table, Table.id == SlotTable.table_id)
        .where(Booking.user_id == db_user.id)
     ).all()

     # one row per (booking, table): group the rows by booking id
     result: dict[int, BookingDetails] = {}
     for booking_id, party_size, start_time, end_time, number, seats in bookings:
         if booking_id not in result:
             result[booking_id] = BookingDetails(
                 id=booking_id,
                 party_size=party_size,
                 slot_time_start=start_time.time(),
                 slot_time_end=end_time.time(),
                 tables=[],
             )
         result[booking_id].tables.append(TableSeats(number=number, seats=seats))

     return list(result.values())


# Not needed for now, but could be useful for a booking cancellation story:
# @router.patch("/{booking_id}")
# def update_booking(
#     booking_id: int,
#     data: BookingUpdate,
#     session: SessionDep,
#     user: Annotated[CurrentUser, Depends(require_role(Roles.HIKER))],
# ):
#     with booking_transaction(session):
#         db_user = get_user(session, user.id)
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