from pydantic import EmailStr
from sqlmodel import Field, SQLModel


class RegisterRequest(SQLModel):
    name: str = Field(min_length=1)
    surname: str = Field(min_length=1)
    email: EmailStr
    mobile_number: str = Field(min_length=1)
    notes: str | None = None
    emergency_contact: str | None = None
    password: str = Field(min_length=8)


class LoginRequest(SQLModel):
    email: EmailStr
    password: str
