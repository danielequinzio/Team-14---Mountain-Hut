import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Cookie, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from app.config import ACCESS_TOKEN_EXPIRE_MINUTES, PWD_RESET_EXPIRE_MINUTES, SESSION_COOKIE_SECURE
from app.database import SessionDep
from app.models import CurrentUser, LoginRequest, RegisterRequest, Roles, User, UserPublic, pwd_reset, ResetData, ResetPasswordRequest
from app.services.auth import create_token, get_current_user, hash_password, verify_password
from app.services.notification import send_pwd_reset


router = APIRouter(tags=["auth"])

SESSION_COOKIE_NAME = "session"


def set_session_cookie(response: Response, user: User) -> str:
    token = create_token(user.id, user.username, user.role)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=True,
        secure=SESSION_COOKIE_SECURE,
        samesite="lax",
    )
    return token


@router.post("/token", status_code=200)
def login_token(
    response: Response,
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: SessionDep,
):
    # username and password arrive as form data (OAuth2 standard), not JSON.
    # the OAuth2 form has no email field, so the email is sent as "username"
    email = form.username.lower()
    user = session.exec(select(User).where(User.email == email)).first()
    # same answer for unknown user and wrong password: it doesn't reveal which usernames exist
    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Wrong username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = set_session_cookie(response, user)
    return {"access_token": token, "token_type": "bearer"}


@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
def register(data: RegisterRequest, session: SessionDep):
    name = data.name.strip()
    surname = data.surname.strip()
    email = str(data.email).lower()
    if session.exec(select(User).where(User.email == email)).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    username = f"{name.lower()}.{surname.lower()}"
    user = User(
        username=username,
        name=name,
        surname=surname,
        email=email,
        mobile_number=data.mobile_number.strip(),
        notes=data.notes.strip() if data.notes else None,
        emergency_contact=data.emergency_contact.strip() if data.emergency_contact else None,
        password_hash=hash_password(data.password),
        role=Roles.HIKER,
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
    return user


@router.post("/login", response_model=UserPublic, status_code=status.HTTP_200_OK)
def login(data: LoginRequest, response: Response, session: SessionDep):
    email = str(data.email).lower()
    user = session.exec(select(User).where(User.email == email)).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Wrong email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    set_session_cookie(response, user)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
):
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        httponly=True,
        secure=SESSION_COOKIE_SECURE,
        samesite="lax",
    )

@router.get("/users/me", response_model=UserPublic, status_code=200)
def read_me(user: Annotated[CurrentUser, Depends(get_current_user)]):
    return user


@router.post("/auth/forgot-password", status_code= status.HTTP_201_CREATED)
def forgot_password(user_email: str, session: SessionDep, background_tasks: BackgroundTasks):
    email = user_email.lower()
    user = session.exec(select(User).where(User.email == email)).first()
    if user:
        token = secrets.token_urlsafe(16)  # 128 bits
        expire_at = datetime.now(timezone.utc) + timedelta(minutes=PWD_RESET_EXPIRE_MINUTES)
        reset = pwd_reset(
            user_id=user.id,
            token_hash=hashlib.sha256(token.encode()).hexdigest(),
            expire_at=expire_at,
        )
        session.add(reset)
        session.commit()

        # the plain token only goes in the email; the db keeps its hash
        background_tasks.add_task(send_pwd_reset, user.email, ResetData(token=token, expire_at=expire_at))


    # same answer whether the email exists or not: it doesn't reveal which emails are registered
    return {"detail": "If the email is registered, a reset link has been sent"}


@router.post("/auth/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(data: ResetPasswordRequest, session: SessionDep):
    # the db only has the hash, so the token received is hashed the same way to find its row
    token_hash = hashlib.sha256(data.token.encode()).hexdigest()
    reset = session.exec(select(pwd_reset).where(pwd_reset.token_hash == token_hash)).first()

    expire_at = reset.expire_at if reset else None
    if expire_at and expire_at.tzinfo is None:  # sqlite gives the datetime back without its timezone
        expire_at = expire_at.replace(tzinfo=timezone.utc)

    # one answer for unknown, used and expired tokens: the user has to ask for a new link anyway
    if not reset or reset.used or expire_at < datetime.now(timezone.utc):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired reset link")

    user = session.get(User, reset.user_id)
    if not user:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired reset link")

    user.password_hash = hash_password(data.new_password)
    # the password changed: every other link sent to this user stops working too
    other_resets = session.exec(
        select(pwd_reset).where(pwd_reset.user_id == user.id, pwd_reset.used == False)  # noqa: E712
    ).all()
    for row in other_resets:
        row.used = True
    reset.used = True
    session.add(user)
    session.commit()





