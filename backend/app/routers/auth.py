from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from app.config import ACCESS_TOKEN_EXPIRE_MINUTES, SESSION_COOKIE_SECURE
from app.database import SessionDep
from app.models import LoginRequest, RegisterRequest, Roles, User, UserPublic
from app.services.auth import create_token, get_current_user, hash_password, verify_password

router = APIRouter(tags=["auth"])

SESSION_COOKIE_NAME = "session"


def set_session_cookie(response: Response, username: str, role: str) -> str:
    token = create_token(username, role)
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
    # username and password arrive as form data (OAuth2 standard), not JSON
    user = session.exec(select(User).where(User.username == form.username)).first()
    # same answer for unknown user and wrong password: it doesn't reveal which usernames exist
    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Wrong username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = set_session_cookie(response, user.username, user.role)
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

    set_session_cookie(response, user.username, user.role)
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
def read_me(user: Annotated[UserPublic, Depends(get_current_user)]):
    return user
