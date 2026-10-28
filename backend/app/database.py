from contextlib import contextmanager
from typing import Annotated

from fastapi import Depends
from sqlmodel import Session, create_engine

from app.config import DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # needed for SQLite + FastAPI
)


def get_session():
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]


@contextmanager
def transaction(session: Session):
    # all the writes in the block are committed together, or none of them on any error
    try:
        yield
        session.commit()
    except Exception:
        session.rollback()
        raise
