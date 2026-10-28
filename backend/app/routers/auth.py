from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import select

from app.auth import create_token, get_current_user, verify_password
from app.database import SessionDep
from app.models import User, UserPublic

router = APIRouter(tags=["auth"])


@router.post("/token", status_code=200)
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], session: SessionDep):
    # username and password arrive as form data (OAuth2 standard), not JSON
    user = session.exec(select(User).where(User.username == form.username)).first()
    # same answer for unknown user and wrong password: it doesn't reveal which usernames exist
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Wrong username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {"access_token": create_token(user.username, user.role), "token_type": "bearer"}

@router.get("/users/me", response_model=UserPublic, status_code=200)
def read_me(user: Annotated[UserPublic, Depends(get_current_user)]):
    return user
