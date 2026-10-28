import hashlib
import secrets
from contextlib import asynccontextmanager
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import FastAPI
from sqlmodel import Session, SQLModel, select

from app.database import engine, transaction
from app.models import Booking, BookingTable, Roles, Slot, SlotTable, Table, User
from app.routers import slot
from app.config import DATA_SEED


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)  # creates db + table on startup

    # add some sample data the first time the db is created
    with Session(engine) as session:
        seeding(session)
    yield


USERS = [
    # username, name, surname, email, password, role
    ("warden", "Luca", "Bonetti", "luca.bonetti@rifugio.example", "warden", Roles.WARDEN),
    ("giulia.ferrero", "Giulia", "Ferrero", "giulia.ferrero@rifugio.example", "employee", Roles.EMPLOYEE),
    ("anna.rossi", "Anna", "Rossi", "anna.rossi@mail.example", "hiker", Roles.HIKER),
    ("paolo.bianchi", "Paolo", "Bianchi", "paolo.bianchi@mail.example", "hiker", Roles.HIKER),
]

TABLES = [
    # number, capacity, location
    (1, 4, "Main hall"),
    (2, 4, "Main hall"),
    (3, 6, "Main hall"),
    (4, 6, "Main hall"),
    (5, 8, "Main hall"),
    (6, 2, "Window"),
    (7, 2, "Window"),
    (8, 4, "Stube"),
    (9, 6, "Stube"),
    (10, 4, "Terrace"),
]

SLOTS = [
    # start, end (tomorrow); every slot offers all the tables
    (time(12, 0), time(13, 30)),
    (time(13, 30), time(15, 0)),
    (time(19, 0), time(20, 30)),
]

BOOKINGS = [
    # username, slot index, party size, [(table number, seats booked)]
    ("anna.rossi", 0, 4, [(1, 4)]),
    ("paolo.bianchi", 0, 2, [(6, 2)]),
    ("paolo.bianchi", 0, 5, [(4, 5)]),
    ("anna.rossi", 1, 10, [(5, 8), (7, 2)]),  # a group split over two tables
    ("paolo.bianchi", 1, 3, [(2, 3)]),
    ("anna.rossi", 2, 6, [(3, 6)]),
    ("paolo.bianchi", 2, 2, [(6, 2)]),
    ("anna.rossi", 2, 4, [(8, 4)]),
]


def scrypt_hash(password: str) -> tuple[str, str]:
    # as in the ERD: scrypt of the password with a random per-user salt
    salt = secrets.token_hex(16)
    hashed = hashlib.scrypt(password.encode(), salt=salt.encode(), n=2**14, r=8, p=1, dklen=32)
    return hashed.hex(), salt


def seeding(session: Session):
    # only when SEED_DATA is on, and only the first time the db is created
    if not DATA_SEED:
        return
    if session.exec(select(User)).first():
        return
    with transaction(session):
        users = {}
        for username, name, surname, email, password, role in USERS:
            password_hash, salt = scrypt_hash(password)
            users[username] = User(username=username, name=name, surname=surname, email=email,
                                   password_hash=password_hash, salt=salt, role=role)
        tables = {number: Table(number=number, capacity=capacity, location=location)
                  for number, capacity, location in TABLES}
        session.add_all([*users.values(), *tables.values()])
        session.flush()  # gives the rows their ids, needed by the foreign keys below

        # the db wants timezone-aware datetimes: slot times are in the hut's local time
        hut_tz = ZoneInfo("Europe/Rome")
        tomorrow = date.today() + timedelta(days=1)
        slots = [Slot(start_time=datetime.combine(tomorrow, start, hut_tz),
                      end_time=datetime.combine(tomorrow, end, hut_tz),
                      created_by=users["warden"].id)
                 for start, end in SLOTS]
        session.add_all(slots)
        session.flush()

        slot_tables = {(i, number): SlotTable(slot_id=slot.id, table_id=table.id)
                       for i, slot in enumerate(slots) for number, table in tables.items()}
        session.add_all(slot_tables.values())
        session.flush()

        for username, i, party_size, seats in BOOKINGS:
            booking = Booking(user_id=users[username].id, slot_id=slots[i].id, party_size=party_size)
            session.add(booking)
            session.flush()
            session.add_all([BookingTable(booking_id=booking.id, slot_table_id=slot_tables[i, number].id,
                                          seats_booked=seats_booked)
                             for number, seats_booked in seats])


app = FastAPI(lifespan=lifespan)

app.include_router(slot.router)
"""
app.include_router(auth.router)
app.include_router(tickets.router)
app.include_router(services.router)
app.include_router(counters.router)
"""