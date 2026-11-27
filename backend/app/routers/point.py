from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, func, select

from app.database import SessionDep, transaction
from app.models import CurrentUser, Point, PointCreate, PointPublic, Roles
from app.services.auth import require_role
from app.services.user import EmployeeOrWarden

router = APIRouter(prefix="/point", tags=["point"])


def _predefined_point_named(session: Session, name: str) -> Point | None:
    # names are compared ignoring case: "Colle Bourget" and "colle bourget" are the same point
    return session.exec(
        select(Point).where(Point.predefined == True, func.lower(Point.name) == name.lower())  # noqa: E712
    ).first()


def _save_point(session: Session, name: str, predefined: bool) -> PointPublic:
    point = Point(name=name, predefined=predefined)
    with transaction(session):
        session.add(point)
    session.refresh(point)
    return PointPublic.model_validate(point)


@router.post("", response_model=PointPublic, status_code=status.HTTP_201_CREATED)
def create_point_of_interest(data: PointCreate, session: SessionDep, user: EmployeeOrWarden):
    # a point of interest, added by the staff: always predefined
    if _predefined_point_named(session, data.name):
        raise HTTPException(status.HTTP_409_CONFLICT, "A point of interest with this name already exists")
    return _save_point(session, data.name, predefined=True)


@router.post("/custom", response_model=PointPublic, status_code=status.HTTP_201_CREATED)
def create_custom_point(
    data: PointCreate,
    session: SessionDep,
    user: Annotated[CurrentUser, Depends(require_role(Roles.HIKER))],
):
    # a hiker's own point, made while creating a hike: not a point of interest.
    # different hikers may use the same name, but not the name of a point of interest
    if _predefined_point_named(session, data.name):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "A point of interest with this name already exists: choose it instead",
        )
    return _save_point(session, data.name, predefined=False)
