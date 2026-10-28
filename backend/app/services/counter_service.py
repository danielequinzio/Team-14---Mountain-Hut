from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import Counter, Counter_Service, Service


def get_counter_404(session: Session, counter_id: int) -> Counter:
    counter = session.get(Counter, counter_id)
    if counter is None:
        raise HTTPException(404, "Counter not found")
    return counter

def check_services_exist(session: Session, ids: list[int]) -> list[int]:
    ids = sorted(set(ids))
    if ids:
        found = session.exec(select(Service.id).where(Service.id.in_(ids))).all()
        if len(found) != len(ids):
            raise HTTPException(422, "Unknown service id in service_ids")
    return ids

def set_counter_services(session: Session, counter_id: int, ids: list[int]) -> None:
    for link in session.exec(select(Counter_Service).where(Counter_Service.counter_id == counter_id)).all():
        session.delete(link)
    session.flush()
    for service_id in ids:
        session.add(Counter_Service(counter_id=counter_id, service_id=service_id))
