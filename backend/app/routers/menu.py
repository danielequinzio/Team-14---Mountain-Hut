from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from app.database import SessionDep
from app.models import Menu, PublicMenu
from app.services.user import EmployeeOrWarden

router = APIRouter(prefix="/menus", tags=["menu"])


@router.get("", response_model=list[PublicMenu], status_code=200)
def get_predefined_menus(session: SessionDep, user: EmployeeOrWarden):
    # only the ready-made menus, newest first
    return session.exec(
        select(Menu).where(Menu.predefined).order_by(Menu.created_at.desc())
    ).all()


@router.get("/{id}", response_model=PublicMenu, status_code=200)
def get_menu(id: int, session: SessionDep):
    # public: anyone can see a menu, predefined or not
    menu = session.get(Menu, id)
    if not menu:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Menu not found")
    return menu
