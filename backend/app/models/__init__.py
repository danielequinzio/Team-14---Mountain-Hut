# re-export every model, so the rest of the code can write `from app.models import Booking`
from app.models.auth import ChangePasswordRequest, LoginRequest, RegisterRequest, ResetPasswordRequest
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
from app.models.hike import Hike, HikeCopy, HikeCreate, HikePoint, HikePublic, Point, PointCreate, PointPublic, PopularHikeCreate, PopularHikePublic
from app.models.slot import Slot, SlotAvailability, SlotCreate, SlotDetail, SlotTable, SlotTableInfo
from app.models.table import CopySlotRequest, SlotTablesAdd, Table, TableCreate
from app.models.user import CurrentUser, ResetData, Roles, User, UserPublic, pwd_reset, UserBookingCreation, Guest

__all__ = [
    "AvailabilityResponse",
    "Booking",
    "BookingCreate",
    "BookingTable",
    "BookingUpdate",
    "ChangePasswordRequest",
    "BookingRequirement",
    "BookingRequirementCreate",
    "CurrentUser",
    "Hike",
    "HikeCopy",
    "HikeCreate",
    "HikePoint",
    "HikePublic",
    "Point",
    "PointCreate",
    "PointPublic",
    "PopularHikeCreate",
    "PopularHikePublic",
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
    "Guest",
]
