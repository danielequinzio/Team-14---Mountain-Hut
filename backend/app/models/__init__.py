# re-export every model, so the rest of the code can write `from app.models import Booking`
from app.models.auth import LoginRequest, RegisterRequest
from app.models.booking import Booking, BookingCreate, BookingTable, BookingUpdate
from app.models.slot import Slot, SlotAvailability, SlotCreate, SlotDetail, SlotTable, SlotTableInfo
from app.models.table import CopySlotRequest, SlotTablesAdd, Table, TableCreate
from app.models.user import CurrentUser, Roles, User, UserPublic

__all__ = [
    "Booking",
    "BookingCreate",
    "BookingTable",
    "BookingUpdate",
    "CurrentUser",
    "LoginRequest",
    "RegisterRequest",
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
    "CopySlotRequest",
    "User",
    "UserPublic",
]