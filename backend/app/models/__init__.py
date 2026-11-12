# re-export every model, so the rest of the code can write `from app.models import Booking`
from app.models.auth import LoginRequest, RegisterRequest, ResetPasswordRequest
from app.models.booking import (
    AvailabilityResponse,
    Booking,
    BookingCreate,
    BookingTable,
    BookingUpdate,
    TableSeats,
)
from app.models.slot import Slot, SlotAvailability, SlotCreate, SlotDetail, SlotTable, SlotTableInfo
from app.models.table import CopySlotRequest, SlotTablesAdd, Table, TableCreate
from app.models.user import CurrentUser, ResetData, Roles, User, UserPublic, pwd_reset

__all__ = [
    "AvailabilityResponse",
    "Booking",
    "BookingCreate",
    "BookingTable",
    "BookingUpdate",
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
]
