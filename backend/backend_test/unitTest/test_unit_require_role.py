"""
Unit tests for require_role (app/services/auth.py).

No route uses it yet, so the dependency it builds is called directly
with a fake logged-in user. Run from the backend folder with:

    python -m pytest backend_test -v
"""
import pytest
from fastapi import HTTPException

from app.services.auth import require_role
from app.models import Roles, UserPublic


# ---------- Tests ----------

def test_require_role_allowed():
    user = UserPublic(username="luca.bonetti", role=Roles.WARDEN)
    checker = require_role(Roles.WARDEN, Roles.EMPLOYEE)

    assert checker(user=user) == user  # the user is let in


def test_require_role_forbidden():
    user = UserPublic(username="anna.rossi", role=Roles.HIKER)
    checker = require_role(Roles.WARDEN, Roles.EMPLOYEE)

    with pytest.raises(HTTPException) as exc:
        checker(user=user)

    assert exc.value.status_code == 403
    assert exc.value.detail == "Not enough permissions"