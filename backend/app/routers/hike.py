from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import col, func, select

from app.database import SessionDep, transaction
from app.models import (
    CurrentUser,
    Hike,
    HikeCopy,
    HikeCreate,
    HikePoint,
    HikePublic,
    Point,
    PointPublic,
    PopularHikeCreate,
    PopularHikePublic,
    Roles,
)
from app.services.auth import require_role
from app.services.user import EmployeeOrWarden

router = APIRouter(prefix="/hike", tags=["hike"])


def _load_points(session: SessionDep, point_ids: list[int]) -> list[Point]:
    # every point must exist before anything is written; given back in the order asked
    points = session.exec(select(Point).where(col(Point.id).in_(point_ids))).all() if point_ids else []
    found = {point.id: point for point in points}
    missing = [point_id for point_id in point_ids if point_id not in found]
    if missing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Points not found: {missing}")
    return [found[point_id] for point_id in point_ids]


@router.post("", response_model=HikePublic, status_code=status.HTTP_201_CREATED)
def create_hike(
    data: HikeCreate,
    session: SessionDep,
    user: Annotated[CurrentUser, Depends(require_role(Roles.HIKER))],
):
    point_ids = data.point_ids or []
    # copied now: the commit below expires the loaded Point objects
    points_out = [PointPublic.model_validate(point) for point in _load_points(session, point_ids)]

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


@router.post("/popular", response_model=PopularHikePublic, status_code=status.HTTP_201_CREATED)
def create_popular_hike(data: PopularHikeCreate, session: SessionDep, user: EmployeeOrWarden):
    # names are unique among suggested hikes, ignoring case
    existing = session.exec(
        select(Hike).where(Hike.suggested == True, func.lower(Hike.name) == data.name.lower())  # noqa: E712
    ).first()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "A popular hike with this name already exists")

    points = _load_points(session, data.point_ids)
    not_predefined = [point.id for point in points if not point.predefined]
    if not_predefined:
        # a suggested hike may only go through points of interest
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Not points of interest: {not_predefined}")

    # copied now: the commit below expires the loaded Point objects
    points_out = [PointPublic.model_validate(point) for point in points]

    # the hike and its points are saved together, or not at all
    with transaction(session):
        hike = Hike(
            name=data.name,
            destination_name=data.destination_name,
            duration_minutes=data.duration_minutes,
            suggested=True,  # no hiker and no times: a template the hikers can follow
        )
        session.add(hike)
        session.flush()  # gives the hike its id
        session.add_all([HikePoint(hike_id=hike.id, point_id=point.id) for point in points_out])

    session.refresh(hike)
    return PopularHikePublic(**hike.model_dump(), points=points_out)  # points in the order sent


def _points_of(session: SessionDep, hikes: list[Hike]) -> dict[int, list[PointPublic]]:
    # the points of all the hikes in one query, each hike's in the order they were added
    hike_ids = [hike.id for hike in hikes]
    rows = session.exec(
        select(HikePoint.hike_id, Point)
        .join(Point, Point.id == HikePoint.point_id)
        .where(col(HikePoint.hike_id).in_(hike_ids))
        .order_by(HikePoint.id)
    ).all() if hike_ids else []
    points: dict[int, list[PointPublic]] = {hike_id: [] for hike_id in hike_ids}
    for hike_id, point in rows:
        points[hike_id].append(PointPublic.model_validate(point))
    return points


@router.get("/popular", response_model=list[PopularHikePublic], status_code=status.HTTP_200_OK)
def get_popular_hikes(
    session: SessionDep,
    user: Annotated[CurrentUser, Depends(require_role(Roles.HIKER, Roles.EMPLOYEE, Roles.WARDEN))],
):
    # any logged-in user: the suggested hikes, shortest first
    hikes = list(session.exec(
        select(Hike).where(Hike.suggested == True).order_by(Hike.duration_minutes, Hike.name)  # noqa: E712
    ).all())
    points = _points_of(session, hikes)
    return [PopularHikePublic(**hike.model_dump(), points=points[hike.id]) for hike in hikes]


@router.get("/mine", response_model=list[HikePublic], status_code=status.HTTP_200_OK)
def get_my_hikes(
    session: SessionDep,
    user: Annotated[CurrentUser, Depends(require_role(Roles.HIKER))],
):
    # the logged-in hiker's hikes, newest first
    hikes = list(session.exec(
        select(Hike).where(Hike.hiker_id == user.id).order_by(col(Hike.start_time).desc())
    ).all())
    points = _points_of(session, hikes)
    return [HikePublic(**hike.model_dump(), points=points[hike.id]) for hike in hikes]


@router.post("/popular/copy", response_model=HikePublic, status_code=status.HTTP_201_CREATED)
def copy_popular_hike(
    data: HikeCopy,
    session: SessionDep,
    user: Annotated[CurrentUser, Depends(require_role(Roles.HIKER))],
):
    # the hiker follows a popular hike: a new hike of theirs, with the same route and their own times
    popular = session.get(Hike, data.hike_id)
    if popular is None or not popular.suggested:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Popular hike not found")

    # copied now: the commit below expires the loaded objects
    name, destination_name = popular.name, popular.destination_name
    points_out = _points_of(session, [popular])[data.hike_id]

    # the hike and its points are saved together, or not at all
    with transaction(session):
        hike = Hike(
            hiker_id=user.id,
            name=name,
            destination_name=destination_name,
            start_time=data.start_time,
            expected_arrival=data.expected_arrival,
            arrived=False,
            suggested=False,
        )
        session.add(hike)
        session.flush()  # gives the hike its id
        session.add_all([HikePoint(hike_id=hike.id, point_id=point.id) for point in points_out])

    session.refresh(hike)
    return HikePublic(**hike.model_dump(), points=points_out)  # same points, same order as the popular hike
