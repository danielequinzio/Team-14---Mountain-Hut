# re-export every model, so the rest of the code can write `from app.models import Booking`
from app.models.auth import LoginRequest, RegisterRequest, ResetPasswordRequest, RegisterRequestEmployee
from app.models.booking import (
    AvailabilityResponse,
    Booking,
    BookingCreate,
    BookingTable,
    BookingUpdate,
    TableSeats,
)
from app.models.booking_requirement import BookingRequirement, BookingRequirementCreate
from app.models.slot import Slot, SlotAvailability, SlotCreate, SlotDetail, SlotTable, SlotTableInfo
from app.models.table import CopySlotRequest, SlotTablesAdd, Table, TableCreate
from app.models.user import CurrentUser, ResetData, Roles, User, UserPublic, pwd_reset, UserBookingCreation

__all__ = [
    "AvailabilityResponse",
    "Booking",
    "BookingCreate",
    "BookingTable",
    "BookingUpdate",
    "BookingRequirement",
    "BookingRequirementCreate",
    "CurrentUser",
    "LoginRequest",
    "RegisterRequest",
    "ResetData",
    "ResetPasswordRequest",
    "Roles",
    "Slot",
    "SlotAvailability",
    "SlotCreate",
    "SlotDetail",
    "SlotTable",
    "SlotTableInfo",
    "SlotTablesAdd",
    "Table",
    "TableCreate",
    "TableSeats",
    "CopySlotRequest",
    "User",
    "UserPublic",
    "pwd_reset",
    "UserBookingCreation",
    "RegisterRequestEmployee",
]
