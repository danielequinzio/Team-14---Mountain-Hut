from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Cookie, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pwdlib import PasswordHash

from app.config import ACCESS_TOKEN_EXPIRE_MINUTES, SECRET_KEY
from app.models import UserPublic

ALGORITHM = "HS256"

password_hash = PasswordHash.recommended()  # argon2

# reads the "Authorization: Bearer <token>" header, answers 401 if it's missing.
# tokenUrl is the login route, used by the "Authorize" button of /docs
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)


def hash_password(password: str) -> str:
    return password_hash.hash(password)

def verify_password(password: str, hashed: str) -> bool:
    return password_hash.verify(password, hashed)

def create_token(username: str, role: str) -> str:
    # sub = who the token belongs to, exp = when it stops being accepted
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": username, "role": role, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    session_token: str | None = Cookie(default=None, alias="session"),
    authorization_token: str | None = Depends(oauth2_scheme),
) -> UserPublic:
    # the token is signed, so its content can be trusted without a db query
    token = session_token or authorization_token
    if not token:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])  # also checks exp
        return UserPublic(username=payload["sub"], role=payload["role"])
    except (jwt.InvalidTokenError, KeyError):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

def require_role(*roles: str):
    # builds a dependency that lets in only logged-in users with one of the roles
    def checker(user: UserPublic = Depends(get_current_user)) -> UserPublic:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not enough permissions")
        return user
    return checker
