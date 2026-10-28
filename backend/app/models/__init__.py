# re-export every model, so the rest of the code can write `from app.models import Booking`
from app.models.booking import Booking, BookingTable
from app.models.slot import Slot, SlotTable
from app.models.table import Table
from app.models.user import Roles, User, UserPublic

__all__ = ["Booking", "BookingTable", "Roles", "Slot", "SlotTable", "Table", "User", "UserPublic"]