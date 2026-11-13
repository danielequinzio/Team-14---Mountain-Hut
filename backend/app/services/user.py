from typing import Annotated

from fastapi import Depends
from app.models import (
    CurrentUser,
    Roles,
)
from app.services.auth import require_role


EmployeeOrWarden = Annotated[
    CurrentUser, Depends(require_role(Roles.EMPLOYEE, Roles.WARDEN))
]