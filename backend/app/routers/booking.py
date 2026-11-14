from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlmodel import select

from app.database import SessionDep, booking_transaction
from app.models import (
    Booking,
    BookingCreate,
    BookingRequirement,
    BookingUpdate,
    CurrentUser,
    Roles,
    Slot,
)
from app.services.auth import require_role
from app.services.booking import (
    assign_tables,
    booking_response,
    ensure_change_allowed,
    find_slot,
    get_user,
    release_tables,
)

from app.services.notification import ( build_confirmation, send_booking_confirmation, send_booking_change, )

from app.models.booking_requirement import BookingRequirementCreate

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

# Probably not needed for the frontend at the moment, because this is sent via email
# @router.get("")
# def get_my_bookings(
#     session: SessionDep,
#     user: Annotated[CurrentUser, Depends(require_role(Roles.HIKER))],
# ):
#     db_user = get_user(session, user.id)
#     bookings = session.exec(
#         select(Booking).where(Booking.user_id == db_user.id).order_by(Booking.slot_id)
#     ).all()
#     return [booking_response(session, booking) for booking in bookings]


@router.patch("/{booking_id}")
def update_booking(
    booking_id: int,
    data: BookingUpdate,
    session: SessionDep,
    user: Annotated[CurrentUser, Depends(require_role(Roles.HIKER))],
    background_tasks: BackgroundTasks, 
):
    with booking_transaction(session):
        db_user = get_user(session, user.id)
        booking = session.exec(
            select(Booking).where(
                Booking.id == booking_id,
                Booking.user_id == db_user.id,
            )
        ).first()
        if booking is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Booking not found")

        original_slot = session.get(Slot, booking.slot_id)
        if original_slot is None:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                "Booking slot not found",
            )
        ensure_change_allowed(original_slot)

        if (data.date is None) != (data.time is None):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Date and time must be changed together",
            )

        new_slot = original_slot
        if data.date is not None and data.time is not None:
            new_slot = find_slot(session, data.date, data.time)
            ensure_change_allowed(new_slot)

        if new_slot.id != booking.slot_id and session.exec(
            select(Booking).where(
                Booking.user_id == db_user.id,
                Booking.slot_id == new_slot.id,
                Booking.id != booking.id,
            )
        ).first():
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "A booking already exists for this slot",
            )

        release_tables(session, booking)
        booking.slot_id = new_slot.id
        if data.party_size is not None:
            booking.party_size = data.party_size
        if assign_tables(session, booking) is None:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "There are not enough seats for this party",
            )

        if data.requirements is not None:
            old_requirements = session.exec(
                select(BookingRequirement).where(
                    BookingRequirement.booking_id == booking.id
                )
            ).all()
            for requirement in old_requirements:
                session.delete(requirement)
            session.flush()
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

         # MH-06: requirements shown in the email (the new ones, or the stored ones)
        requirements = data.requirements
        if requirements is None:
            requirements = [
                BookingRequirementCreate(allergies=r.allergies, description=r.description)
                for r in session.exec(
                    select(BookingRequirement).where(BookingRequirement.booking_id == booking.id)
                ).all()
            ]

        response = booking_response(session, booking)
        change = build_confirmation(db_user, new_slot, booking, requirements)
    # MH-06: outside the block, so the email leaves only after the commit
    background_tasks.add_task(send_booking_change, change)
    return response