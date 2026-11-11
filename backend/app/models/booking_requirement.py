from sqlmodel import Field, SQLModel


class BookingRequirement(SQLModel, table=True):
    __tablename__ = "booking_requirement"

    id: int | None = Field(default=None, primary_key=True)
    booking_id: int = Field(foreign_key="booking.id")
    allergies: bool = False
    description: str | None = None


class BookingRequirementCreate(SQLModel):
    allergies: bool = False
    description: str | None = None
