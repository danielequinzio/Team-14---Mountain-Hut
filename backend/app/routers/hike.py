from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import col, select

from app.database import SessionDep, transaction
from app.models import CurrentUser, Hike, HikeCreate, HikePoint, HikePublic, Point, PointPublic, Roles
from app.services.auth import require_role

router = APIRouter(prefix="/hike", tags=["hike"])


@router.post("", response_model=HikePublic, status_code=status.HTTP_201_CREATED)
def create_hike(
    data: HikeCreate,
    session: SessionDep,
    user: Annotated[CurrentUser, Depends(require_role(Roles.HIKER))],
):
    point_ids = data.point_ids or []

    # every point must exist before anything is written
    points = session.exec(select(Point).where(col(Point.id).in_(point_ids))).all() if point_ids else []
    found = {point.id: point for point in points}
    missing = [point_id for point_id in point_ids if point_id not in found]
    if missing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Points not found: {missing}")

    # copied now: the commit below expires the loaded Point objects
    points_out = [PointPublic.model_validate(found[point_id]) for point_id in point_ids]

    # the hike and its points are saved together, or not at all
    with transaction(session):
        hike = Hike(
            hiker_id=user.id,
            name=data.name,
            destination_name=data.destination_name,
            start_time=data.start_time,
            expected_arrival=data.expected_arrival,
            arrived=False,
            suggested=False,
        )
        session.add(hike)
        session.flush()  # gives the hike its id
        session.add_all([HikePoint(hike_id=hike.id, point_id=point_id) for point_id in point_ids])

    session.refresh(hike)
    return HikePublic(**hike.model_dump(), points=points_out)  # points in the order the client sent them
