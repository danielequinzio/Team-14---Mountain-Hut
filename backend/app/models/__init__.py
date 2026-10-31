# re-export every model, so the rest of the code can write `from app.models import Booking`
from app.models.auth import LoginRequest, RegisterRequest
from app.models.booking import Booking, BookingCreate, BookingTable, BookingUpdate
from app.models.slot import Slot, SlotAvailability, SlotDetail, SlotTable, SlotTableInfo
from app.models.table import Table
from app.models.user import Roles, User, UserPublic

__all__ = [
    "Booking",
    "BookingCreate",
    "BookingTable",
    "BookingUpdate",
    "LoginRequest",
    "RegisterRequest",
    "Roles",
    "Slot",
    "SlotAvailability",
    "SlotDetail",
    "SlotTable",
    "SlotTableInfo",
    "Table",
    "User",
    "UserPublic",
]