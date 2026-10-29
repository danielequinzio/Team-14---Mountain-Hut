from contextlib import asynccontextmanager
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect
from sqlmodel import Session, SQLModel, select

from app.database import engine, transaction
from app.auth import hash_password
from app.models import Booking, BookingTable, Roles, Slot, SlotTable, Table, User
from app.routers import auth, slot
from app.config import CORS_ORIGINS, DATA_SEED


@asynccontextmanager
async def lifespan(app: FastAPI):
    drop_unused_salt_column()
    drop_username_unique_constraint()
    SQLModel.metadata.create_all(engine)  # creates db + table on startup
    add_user_profile_columns()

    # add some sample data the first time the db is created
    with Session(engine) as session:
        seeding(session)
    yield


USERS = [
    # username, name, surname, email, password, role, mobile number, notes, emergency contact
    ("luca.bonetti", "Luca", "Bonetti", "luca.bonetti@rifugio.example", "warden", Roles.WARDEN,
     "+39 333 123 4567", "Available for on-call emergencies.", "+39 333 765 4321 - Marco Bonetti"),
    ("giulia.ferrero", "Giulia", "Ferrero", "giulia.ferrero@rifugio.example", "employee", Roles.EMPLOYEE,
     "+39 333 234 5678", None, None),
    ("anna.rossi", "Anna", "Rossi", "anna.rossi@mail.example", "hiker", Roles.HIKER,
     "+39 333 345 6789", "Vegetarian meals preferred.", "+39 333 876 5432 - Elena Rossi"),
    ("paolo.bianchi", "Paolo", "Bianchi", "paolo.bianchi@mail.example", "hiker", Roles.HIKER,
     "+39 333 456 7890", "Arrives after 18:00.", None),
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


def drop_unused_salt_column():
    inspector = inspect(engine)
    if not inspector.has_table("user"):
        return
    if "salt" not in {column["name"] for column in inspector.get_columns("user")}:
        return
    with engine.begin() as connection:
        connection.exec_driver_sql('ALTER TABLE "user" DROP COLUMN salt')


def drop_username_unique_constraint():
    inspector = inspect(engine)
    if not inspector.has_table("user"):
        return
    unique_constraints = inspector.get_unique_constraints("user")
    if not any(constraint["column_names"] == ["username"] for constraint in unique_constraints):
        return

    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        connection.exec_driver_sql(
            """
            CREATE TABLE user_new (
                id INTEGER NOT NULL PRIMARY KEY,
                username VARCHAR NOT NULL,
                name VARCHAR NOT NULL,
                surname VARCHAR NOT NULL,
                email VARCHAR NOT NULL,
                mobile_number VARCHAR,
                notes VARCHAR,
                emergency_contact VARCHAR,
                password_hash VARCHAR NOT NULL,
                role VARCHAR NOT NULL
            )
            """
        )
        connection.exec_driver_sql(
            """
            INSERT INTO user_new (
                id, username, name, surname, email, mobile_number, notes,
                emergency_contact, password_hash, role
            )
            SELECT id, username, name, surname, email, NULL, NULL, NULL, password_hash, role
            FROM user
            """
        )
        connection.exec_driver_sql('DROP TABLE "user"')
        connection.exec_driver_sql("ALTER TABLE user_new RENAME TO user")
        connection.exec_driver_sql("CREATE UNIQUE INDEX user_email ON user (email)")
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")


def add_user_profile_columns():
    inspector = inspect(engine)
    if not inspector.has_table("user"):
        return

    existing_columns = {column["name"] for column in inspector.get_columns("user")}
    missing_columns = {
        "mobile_number": "VARCHAR",
        "notes": "VARCHAR",
        "emergency_contact": "VARCHAR",
    }
    with engine.begin() as connection:
        for column_name, column_type in missing_columns.items():
            if column_name not in existing_columns:
                connection.exec_driver_sql(
                    f'ALTER TABLE "user" ADD COLUMN {column_name} {column_type}'
                )


def seeding(session: Session):
    # only when SEED_DATA is on, and only the first time the db is created
    if not DATA_SEED:
        return
    if session.exec(select(User)).first():
        return
    with transaction(session):
        users = {}
        for username, name, surname, email, password, role, mobile_number, notes, emergency_contact in USERS:
            users[username] = User(username=username, name=name, surname=surname, email=email,
                                   mobile_number=mobile_number, notes=notes,
                                   emergency_contact=emergency_contact,
                                   password_hash=hash_password(password), role=role)
        tables = {number: Table(number=number, capacity=capacity, location=location)
                  for number, capacity, location in TABLES}
        session.add_all([*users.values(), *tables.values()])
        session.flush()  # gives the rows their ids, needed by the foreign keys below

        # the db wants timezone-aware datetimes: slot times are in the hut's local time
        hut_tz = ZoneInfo("Europe/Rome")
        tomorrow = date.today() + timedelta(days=1)
        slots = [Slot(start_time=datetime.combine(tomorrow, start, hut_tz),
                      end_time=datetime.combine(tomorrow, end, hut_tz),
                      created_by=users["luca.bonetti"].id)
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(slot.router)
app.include_router(auth.router)
"""
app.include_router(tickets.router)
app.include_router(services.router)
app.include_router(counters.router)
"""