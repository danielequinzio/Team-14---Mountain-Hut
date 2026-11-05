from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from app.database import SessionDep
from app.models import CurrentUser, Roles, Table, TableCreate
from app.services.auth import require_role

router = APIRouter(prefix="/tables", tags=["tables"])
EmployeeOrWarden = Annotated[
    CurrentUser, Depends(require_role(Roles.EMPLOYEE, Roles.WARDEN))
]


@router.get("", response_model=list[Table], status_code=200)
def get_tables(session: SessionDep, user: EmployeeOrWarden):
    return session.exec(select(Table).order_by(Table.number)).all()


@router.post("", response_model=Table, status_code=status.HTTP_201_CREATED)
def create_table(data: TableCreate, session: SessionDep, user: EmployeeOrWarden):
    table = Table(**data.model_dump())
    session.add(table)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Table number already exists") from exc
    session.refresh(table)
    return table
