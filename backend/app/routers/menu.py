from datetime import datetime

from fastapi import APIRouter, HTTPException, status, Response
from sqlmodel import select

from app.database import SessionDep
from app.models import Menu, MenuCreate, PublicMenu, Slot
from app.routers.slot import HUT_TIMEZONE, _slot_start
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


@router.post("", response_model=PublicMenu, status_code=status.HTTP_201_CREATED)
def create_menu(data: MenuCreate, response: Response, session: SessionDep, user: EmployeeOrWarden):
    slot = session.get(Slot, data.slot_id)
    if not slot:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Slot not found")
    if _slot_start(slot) <= datetime.now(HUT_TIMEZONE):
        # the menu of a started or past slot stays fixed
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot set the menu of a started or past slot")
    if slot.menu_id is not None:
        # replacing a menu is the update route's job: no orphan menus here
        raise HTTPException(status.HTTP_409_CONFLICT, "The slot already has a menu")

    # a predefined menu picked without changes: link it, don't store a copy
    menu = session.exec(
        select(Menu).where(Menu.predefined, Menu.text_menu == data.text_menu)
    ).first()

    if menu:
        response.status_code = status.HTTP_200_OK   # nothing new was created
    else:
        # new or modified menu: always a new row, the predefined ones are never changed
        menu = Menu(text_menu=data.text_menu, predefined=data.predefined)
        session.add(menu)
        session.flush()   # gives menu.id before the commit

    slot.menu_id = menu.id
    session.add(slot)
    session.commit()
    session.refresh(menu)
    return menu