import secrets
from select import select
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.models import CurrentUser, UserPublic, UserBookingCreation, Guest

from app.services.user import EmployeeOrWarden

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Cookie, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from app.config import ACCESS_TOKEN_EXPIRE_MINUTES, PWD_RESET_EXPIRE_MINUTES, SESSION_COOKIE_SECURE
from app.database import SessionDep
from app.models import Booking, CurrentUser, LoginRequest, RegisterRequest, Roles, User, UserPublic, RegisterRequestEmployee
from app.services.auth import create_token, get_current_user, hash_password, verify_password
from app.services.notification import build_account_created, send_account_created, send_pwd_reset


router = APIRouter(tags=["user"])

@router.get("/users/me", response_model=UserPublic, status_code=200)
def read_me(user: Annotated[CurrentUser, Depends(get_current_user)]):
    return user

@router.get("/profileCheck", response_model=UserBookingCreation, status_code=200)
def check_hiker_existence(user: EmployeeOrWarden, session: SessionDep, email: str = Query()):
    # emails are stored lowercase, so normalize before comparing
    email = email.strip().lower()
    hiker = session.exec(
        select(User).where(User.email == email, User.role == Roles.HIKER)
    ).first()
    if not hiker:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "hiker not found")

    return hiker

@router.post("/registerHiker", response_model=UserBookingCreation, status_code=201)
def create_hiker_profile(user: EmployeeOrWarden,
                         session: SessionDep,
                         hiker: RegisterRequestEmployee,
                         background_tasks: BackgroundTasks):
    name = hiker.name.strip()
    surname = hiker.surname.strip()
    email = str(hiker.email).lower()
    if session.exec(select(User).where(User.email == email)).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    username = f"{name.lower()}.{surname.lower()}"
    # the plain password only goes in the email; the db keeps its hash
    password = secrets.token_urlsafe(8)
    user = User(
        username=username,
        name=name,
        surname=surname,
        email=email,
        mobile_number=hiker.mobile_number.strip(),
        notes=hiker.notes.strip() if hiker.notes else None,
        emergency_contact=hiker.emergency_contact.strip() if hiker.emergency_contact else None,
        password_hash=hash_password(password),
        role=Roles.HIKER,
        must_change_password=True,  # the password travelled by email: it must be changed at the first login
    )
    session.add(user)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        if session.exec(select(User).where(User.email == email)).first():
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Email already registered",
            )
        raise
    session.refresh(user)

    background_tasks.add_task(send_account_created, build_account_created(user, password))

    return user


@router.post("/registerGuest", response_model=UserBookingCreation, status_code=201)
def create_guest_profile(user: EmployeeOrWarden,
                         session: SessionDep,
                         guest: Guest):
    """Add a hiker without an account, only to put them in a booking: they can't log in."""
    name = guest.name.strip()
    surname = guest.surname.strip()

    guest_user = User(
        username=f"{name.lower()}.{surname.lower()}",
        name=name,
        surname=surname,
        email=None,
        mobile_number=guest.mobile_number.strip(),
        notes=None,
        emergency_contact=None,
        # a random password that is never sent to anyone: the guest has no way to log in
        password_hash=hash_password(secrets.token_urlsafe(32)),
        role=Roles.HIKER,
        is_guest=True,
    )
    session.add(guest_user)
    session.commit()
    session.refresh(guest_user)
    # no email at all: the guest gave none, so neither an account email nor booking confirmations are sent
    return guest_user


@router.delete("/guests/{guest_id}", status_code=204)
def remove_guest(user: EmployeeOrWarden, session: SessionDep, guest_id: int):
    """Remove a guest added by the staff. Only guests: hikers with an account and staff are never touched."""
    guest = session.get(User, guest_id)
    if not guest or not guest.is_guest:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "guest not found")

    # the bookings point to the guest: the staff must cancel them first
    if session.exec(select(Booking).where(Booking.user_id == guest_id)).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "guest still has bookings")

    session.delete(guest)
    session.commit()
    return Response(status_code=204)

