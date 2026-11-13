"""
Integration tests for the booking routes:
- MH-01 "Book a table": POST /booking
- the hiker's own bookings: GET /booking
- MH-05 "Provide party requirements": POST /booking with requirements, confirmation email
 
The routes run against the real test db created by conftest.py and the real
authentication (the as_warden override is removed: only hikers can book and
see their bookings).
Each test inserts only the rows it needs. Run from the backend folder with:
 
    python -m pytest backend_test -v
"""
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlmodel import select

import app.routers.booking as booking_router
from app.main import app
from app.models import Booking, BookingRequirement, BookingTable, Roles, Slot, SlotTable, Table, User
from app.services.auth import hash_password
from app.services.email_template import render_html
from app.services.notification import compose_email

HUT_TZ = ZoneInfo("Europe/Rome")
URL = "/booking"
LUNCH = time(12, 0)
DINNER = time(19, 0)
TABLES = {1: 2, 2: 4, 3: 6}  # table number -> seats: 12 seats per slot
PASSWORD = "password123"

NOT_ENOUGH_SEATS = "There are not enough seats for this party"


# ---------- Helpers ----------

def tomorrow() -> date:
    return datetime.now(HUT_TZ).date() + timedelta(days=1)


def at(day: date, start: time) -> datetime:
    return datetime.combine(day, start, HUT_TZ)


def login(client, user: User):
    """Real login: the client keeps the session cookie for the next requests."""
    response = client.post("/login", json={"email": user.email, "password": PASSWORD})
    assert response.status_code == 200
    return client


def book(client, party_size, day=None, start=LUNCH, requirements=None):
    payload = {
        "date": (day or tomorrow()).isoformat(),
        "time": start.isoformat(),
        "party_size": party_size,
    }
    if requirements is not None:
        payload["requirements"] = requirements
    return client.post(URL, json=payload)


def add_user(session, username: str, role: Roles) -> User:
    name, surname = username.split(".")
    user = User(username=username, name=name.title(), surname=surname.title(),
                email=f"{username}@mail.example", mobile_number="+39 333 000 0000",
                password_hash=hash_password(PASSWORD), role=role)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def bookings(session) -> list[Booking]:
    session.expire_all()  # read what the api committed
    return session.exec(select(Booking)).all()


def occupied_seats(session, slot_id: int) -> dict[int, int]:
    """Occupied seats per table number of a slot, as stored in the db."""
    session.expire_all()
    rows = session.exec(
        select(Table.number, SlotTable.occupied_seats)
        .join(Table, Table.id == SlotTable.table_id)
        .where(SlotTable.slot_id == slot_id)
    ).all()
    return dict(rows)


def stored_requirements(session) -> list[tuple[int, bool, str | None]]:
    """(booking id, allergies, description) of every requirement in the db."""
    session.expire_all()
    rows = session.exec(select(BookingRequirement).order_by(BookingRequirement.id)).all()
    return [(row.booking_id, row.allergies, row.description) for row in rows]


def seats_by_table(response) -> dict[int, int]:
    return {table["number"]: table["seats"] for table in response.json()["tables"]}

def my_bookings(client):
    """GET /booking: the bookings of the logged-in user."""
    return client.get(URL)


# ---------- Fixtures ----------

@pytest.fixture(autouse=True)
def real_auth(as_warden):
    """Removes the as_warden override of conftest.py: the real token and role checks run."""
    app.dependency_overrides.clear()


@pytest.fixture
def hiker(session) -> User:
    return add_user(session, "anna.rossi", Roles.HIKER)


@pytest.fixture
def as_hiker(client, hiker):
    """Client logged in as the registered hiker."""
    return login(client, hiker)


@pytest.fixture
def add_slot(session):
    """Factory: adds a slot offering all TABLES, optionally with seats already occupied."""
    warden_id = add_user(session, "luca.bonetti", Roles.WARDEN).id
    tables = [Table(number=n, capacity=c, location="Main hall") for n, c in TABLES.items()]
    session.add_all(tables)
    session.flush()
    table_ids = {table.number: table.id for table in tables}
    session.commit()

    def _add_slot(start: datetime, occupied: dict[int, int] | None = None) -> int:
        occupied = occupied or {}
        slot = Slot(start_time=start, end_time=start + timedelta(minutes=90), created_by=warden_id)
        session.add(slot)
        session.flush()
        slot_id = slot.id
        session.add_all([
            SlotTable(slot_id=slot_id, table_id=table_ids[n], occupied_seats=occupied.get(n, 0))
            for n in sorted(table_ids)
        ])
        session.commit()
        return slot_id

    return _add_slot


@pytest.fixture
def add_booking(session):
    """Factory: adds a booking with its seats per table number and its requirements."""
    def _add_booking(user: User, slot_id: int, seats: dict[int, int],
                     requirements: list[tuple[bool, str | None]] = ()) -> int:
        booking = Booking(user_id=user.id, slot_id=slot_id, party_size=sum(seats.values()))
        session.add(booking)
        session.flush()
        booking_id = booking.id
        slot_tables = dict(session.exec(  # table number -> slot_table id
            select(Table.number, SlotTable.id)
            .join(Table, Table.id == SlotTable.table_id)
            .where(SlotTable.slot_id == slot_id)
        ).all())
        session.add_all([
            BookingTable(booking_id=booking_id, slot_table_id=slot_tables[n], seats_booked=booked)
            for n, booked in seats.items()
        ])
        session.add_all([
            BookingRequirement(booking_id=booking_id, allergies=allergies, description=description)
            for allergies, description in requirements
        ])
        session.commit()
        return booking_id
 
    return _add_booking


@pytest.fixture
def sent_emails(monkeypatch) -> list:
    """Captures the confirmations that POST /booking hands to the email background task."""
    sent = []
    monkeypatch.setattr(booking_router, "send_booking_confirmation", sent.append)
    return sent


@pytest.fixture
def lunch(add_slot) -> int:
    """Tomorrow's 12:00 slot with all the tables free."""
    return add_slot(at(tomorrow(), LUNCH))


# ---------- Tests: authentication ----------

def test_anonymous_user_cannot_book(client):
    assert book(client, 2).status_code == 401


@pytest.mark.parametrize("role", [Roles.WARDEN, Roles.EMPLOYEE])
def test_staff_cannot_book(client, session, role):
    login(client, add_user(session, "giulia.ferrero", role))

    response = book(client, 2)

    assert response.status_code == 403
    assert response.json() == {"detail": "Not enough permissions"}


def test_session_of_deleted_hiker_is_rejected(as_hiker, session, hiker):
    # the session cookie is still valid, but its user id is no longer in the db
    session.delete(hiker)
    session.commit()

    response = book(as_hiker, 2)

    assert response.status_code == 401
    assert response.json() == {"detail": "User not found"}


# ---------- Tests: mandatory fields ----------

@pytest.mark.parametrize("missing", ["date", "time", "party_size"])
def test_missing_field_is_rejected(as_hiker, lunch, missing):
    payload = {"date": tomorrow().isoformat(), "time": "12:00:00", "party_size": 2}
    del payload[missing]

    assert as_hiker.post(URL, json=payload).status_code == 422


@pytest.mark.parametrize("party_size", [0, -1])
def test_party_size_must_be_positive(as_hiker, lunch, party_size):
    assert book(as_hiker, party_size).status_code == 422


# ---------- Tests: slot selection ----------

def test_time_not_matching_a_slot_start(as_hiker, lunch):
    response = book(as_hiker, 2, start=time(12, 30))

    assert response.status_code == 400
    assert response.json() == {"detail": "Slot not available"}


def test_date_without_slots(as_hiker, lunch):
    response = book(as_hiker, 2, day=tomorrow() + timedelta(days=1))

    assert response.status_code == 400
    assert response.json() == {"detail": "Slot not available"}


@pytest.mark.parametrize(
    "offset", [timedelta(hours=1), timedelta(days=-1)], ids=["within-2-hours", "past"]
)
def test_booking_closes_two_hours_before_the_slot(as_hiker, session, add_slot, offset):
    start = (datetime.now(HUT_TZ) + offset).replace(second=0, microsecond=0)
    add_slot(start)

    response = book(as_hiker, 2, day=start.date(), start=start.time())

    assert response.status_code == 400
    assert response.json() == {"detail": "Bookings are closed less than two hours before the slot"}
    assert bookings(session) == []


# ---------- Tests: table assignment ----------

def test_booking_is_returned_and_stored(as_hiker, session, hiker, lunch):
    response = book(as_hiker, 3)

    assert response.status_code == 201
    [booking] = bookings(session)
    assert (booking.user_id, booking.slot_id, booking.party_size) == (hiker.id, lunch, 3)
    assert response.json() == {
        "id": booking.id,
        "date": tomorrow().isoformat(),
        "time": "12:00:00",
        "party_size": 3,
        "tables": [{"number": 2, "seats": 3}],
    }
    [row] = session.exec(select(BookingTable)).all()
    assert (row.booking_id, row.seats_booked) == (booking.id, 3)
    assert occupied_seats(session, lunch) == {1: 0, 2: 3, 3: 0}


@pytest.mark.parametrize(("party_size", "expected"), [(2, {1: 2}), (3, {2: 3}), (5, {3: 5})])
def test_whole_party_at_the_smallest_table_that_fits(as_hiker, session, lunch, party_size, expected):
    response = book(as_hiker, party_size)

    assert response.status_code == 201
    assert seats_by_table(response) == expected
    assert occupied_seats(session, lunch) == {n: expected.get(n, 0) for n in TABLES}


def test_party_shares_a_table_with_other_guests(as_hiker, session, add_slot):
    slot = add_slot(at(tomorrow(), LUNCH), occupied={2: 3, 3: 2})  # free: 2, 1, 4

    response = book(as_hiker, 4)

    assert response.status_code == 201
    assert seats_by_table(response) == {3: 4}
    assert occupied_seats(session, slot) == {1: 0, 2: 3, 3: 6}


@pytest.mark.parametrize(
    ("party_size", "expected"),
    [(7, {3: 6, 1: 1}), (10, {3: 6, 2: 4}), (12, {3: 6, 2: 4, 1: 2})],
    ids=["fewest-seats", "two-tables", "all-tables"],
)
def test_party_is_split_over_the_fewest_tables(as_hiker, session, lunch, party_size, expected):
    response = book(as_hiker, party_size)

    assert response.status_code == 201
    assert seats_by_table(response) == expected
    assert occupied_seats(session, lunch) == {n: expected.get(n, 0) for n in TABLES}


@pytest.mark.parametrize(
    ("occupied", "party_size"),
    [({}, 13), ({3: 6}, 7)],
    ids=["over-slot-capacity", "seats-already-taken"],
)
def test_not_enough_seats_stores_nothing(as_hiker, session, add_slot, occupied, party_size):
    slot = add_slot(at(tomorrow(), LUNCH), occupied)

    response = book(as_hiker, party_size)

    assert response.status_code == 409
    assert response.json() == {"detail": NOT_ENOUGH_SEATS}
    assert bookings(session) == []
    assert occupied_seats(session, slot) == {n: occupied.get(n, 0) for n in TABLES}


def test_response_reports_table_numbers_on_any_slot(as_hiker, lunch, add_slot):
    # second slot: its slot_table ids (4..6) differ from the table ids (1..3)
    add_slot(at(tomorrow(), DINNER))

    response = book(as_hiker, 3, start=DINNER)

    assert response.status_code == 201
    assert seats_by_table(response) == {2: 3}


# ---------- Tests: one booking per slot ----------

def test_second_booking_on_the_same_slot_is_rejected(as_hiker, session, lunch):
    assert book(as_hiker, 2).status_code == 201

    response = book(as_hiker, 2)

    assert response.status_code == 409
    assert response.json() == {"detail": "A booking already exists for this slot"}
    assert len(bookings(session)) == 1
    assert occupied_seats(session, lunch) == {1: 2, 2: 0, 3: 0}


def test_same_hiker_can_book_another_slot(as_hiker, session, lunch, add_slot):
    add_slot(at(tomorrow(), DINNER))

    assert book(as_hiker, 2).status_code == 201
    assert book(as_hiker, 2, start=DINNER).status_code == 201
    assert len(bookings(session)) == 2


# ---------- Tests: party requirements (MH-05) ----------

PARTY_REQUIREMENTS = [  # the example of the MH-05 clarifications
    {"allergies": True, "description": "1 vegan, peanut allergy"},
    {"allergies": True, "description": "1 shellfish allergy"},
    {"allergies": False, "description": "2 vegetarians"},
]


def test_requirements_are_stored_with_the_booking(as_hiker, session, lunch):
    response = book(as_hiker, 4, requirements=PARTY_REQUIREMENTS)

    assert response.status_code == 201
    booking_id = response.json()["id"]
    assert stored_requirements(session) == [
        (booking_id, True, "1 vegan, peanut allergy"),
        (booking_id, True, "1 shellfish allergy"),
        (booking_id, False, "2 vegetarians"),
    ]


@pytest.mark.parametrize("requirements", [None, []], ids=["field-missing", "empty-list"])
def test_booking_without_requirements_stores_none(as_hiker, session, lunch, requirements):
    response = book(as_hiker, 2, requirements=requirements)

    assert response.status_code == 201
    assert stored_requirements(session) == []


@pytest.mark.parametrize(
    ("requirement", "expected"),
    [({"description": "2 vegetarians"}, (False, "2 vegetarians")), ({"allergies": True}, (True, None))],
    ids=["allergies-default-false", "description-optional"],
)
def test_requirement_fields_have_defaults(as_hiker, session, lunch, requirement, expected):
    response = book(as_hiker, 2, requirements=[requirement])

    assert response.status_code == 201
    assert stored_requirements(session) == [(response.json()["id"], *expected)]


@pytest.mark.parametrize(
    "requirements",
    ["no list", [{"allergies": "maybe"}], [{"description": 12}]],
    ids=["not-a-list", "allergies-not-boolean", "description-not-text"],
)
def test_invalid_requirements_are_rejected(as_hiker, session, lunch, requirements):
    response = book(as_hiker, 2, requirements=requirements)

    assert response.status_code == 422
    assert bookings(session) == []
    assert stored_requirements(session) == []


def test_requirements_are_not_stored_when_the_booking_fails(as_hiker, session, lunch):
    response = book(as_hiker, 13, requirements=PARTY_REQUIREMENTS)  # over the 12 seats of the slot

    assert response.status_code == 409
    assert bookings(session) == []
    assert stored_requirements(session) == []


def test_requirements_belong_to_their_own_booking(as_hiker, session, lunch, add_slot):
    add_slot(at(tomorrow(), DINNER))

    lunch_booking = book(as_hiker, 2, requirements=[{"description": "2 vegetarians"}]).json()["id"]
    dinner_booking = book(as_hiker, 1, start=DINNER, requirements=[{"allergies": True}]).json()["id"]

    assert stored_requirements(session) == [
        (lunch_booking, False, "2 vegetarians"),
        (dinner_booking, True, None),
    ]


def test_requirements_are_listed_with_the_booking(as_hiker, lunch):
    book(as_hiker, 4, requirements=PARTY_REQUIREMENTS)

    response = my_bookings(as_hiker)

    assert response.status_code == 200
    assert response.json()[0]["requirements"] == PARTY_REQUIREMENTS


# ---------- Tests: confirmation email with requirements (MH-05) ----------

def test_confirmation_email_lists_every_requirement(as_hiker, lunch, sent_emails):
    response = book(as_hiker, 4, requirements=PARTY_REQUIREMENTS)

    assert response.status_code == 201
    [confirmation] = sent_emails
    assert confirmation.requirements == (
        "- [Allergy] 1 vegan, peanut allergy\n"
        "- [Allergy] 1 shellfish allergy\n"
        "- 2 vegetarians"
    )
    assert "Party requirements: " + confirmation.requirements in compose_email(confirmation).get_content()
    assert "1 vegan, peanut allergy<br>- [Allergy] 1 shellfish allergy" in render_html(confirmation)


def test_confirmation_email_without_requirements(as_hiker, lunch, sent_emails):
    assert book(as_hiker, 2).status_code == 201

    [confirmation] = sent_emails
    assert confirmation.requirements is None
    assert "Party requirements" not in compose_email(confirmation).get_content()
    assert "Party requirements" not in render_html(confirmation)


def test_confirmation_email_skips_requirements_without_allergy_or_text(as_hiker, session, lunch, sent_emails):
    empty = [{"allergies": False, "description": "   "}, {"allergies": False}]

    response = book(as_hiker, 2, requirements=[*empty, {"description": "2 vegetarians"}])

    assert response.status_code == 201
    assert len(stored_requirements(session)) == 3  # stored as sent
    [confirmation] = sent_emails
    assert confirmation.requirements == "- 2 vegetarians"  # only what says something is emailed


def test_no_confirmation_email_when_the_booking_fails(as_hiker, lunch, sent_emails):
    assert book(as_hiker, 13, requirements=PARTY_REQUIREMENTS).status_code == 409

    assert sent_emails == []


# ---------- Tests: GET /booking authentication ----------
 
def test_anonymous_user_cannot_see_bookings(client):
    assert my_bookings(client).status_code == 401
 
 
@pytest.mark.parametrize("role", [Roles.WARDEN, Roles.EMPLOYEE])
def test_staff_cannot_see_bookings(client, session, role):
    login(client, add_user(session, "giulia.ferrero", role))
 
    response = my_bookings(client)
 
    assert response.status_code == 403
    assert response.json() == {"detail": "Not enough permissions"}
 
 
def test_deleted_hiker_cannot_see_bookings(as_hiker, session, hiker):
    # the session cookie is still valid, but its user id is no longer in the db
    session.delete(hiker)
    session.commit()
 
    response = my_bookings(as_hiker)
 
    assert response.status_code == 401
    assert response.json() == {"detail": "User not found"}
 
 
# ---------- Tests: GET /booking list ----------
 
def test_hiker_without_bookings_gets_empty_list(as_hiker, lunch):
    response = my_bookings(as_hiker)
 
    assert response.status_code == 200
    assert response.json() == []
 
 
def test_booking_is_listed_with_slot_times_in_hut_time(as_hiker, hiker, lunch, add_booking):
    booking_id = add_booking(hiker, lunch, {2: 3})
 
    response = my_bookings(as_hiker)
 
    assert response.status_code == 200
    assert response.json() == [{
        "id": booking_id,
        "party_size": 3,
        "slot_time_start": "12:00:00",
        "slot_time_end": "13:30:00",
        "tables": [{"number": 2, "seats": 3}],
        "requirements": [],
    }]
 
 
def test_party_split_over_two_tables_is_listed_once(as_hiker, hiker, lunch, add_booking):
    add_booking(hiker, lunch, {3: 6, 1: 1})
 
    response = my_bookings(as_hiker)
 
    assert response.status_code == 200
    [booking] = response.json()
    assert booking["party_size"] == 7
    assert {t["number"]: t["seats"] for t in booking["tables"]} == {3: 6, 1: 1}
 
 
def test_every_booking_of_the_hiker_is_listed(as_hiker, hiker, lunch, add_slot, add_booking):
    dinner = add_slot(at(tomorrow(), DINNER))
    lunch_booking = add_booking(hiker, lunch, {1: 2})
    dinner_booking = add_booking(hiker, dinner, {3: 5})
 
    response = my_bookings(as_hiker)
 
    assert response.status_code == 200
    times = {b["id"]: (b["slot_time_start"], b["slot_time_end"]) for b in response.json()}
    assert times == {
        lunch_booking: ("12:00:00", "13:30:00"),
        dinner_booking: ("19:00:00", "20:30:00"),
    }
 
 
def test_bookings_of_other_hikers_are_not_listed(as_hiker, hiker, session, lunch, add_booking):
    other = add_user(session, "paolo.bianchi", Roles.HIKER)
    add_booking(other, lunch, {3: 4}, requirements=[(True, "Nuts")])
    own_booking = add_booking(hiker, lunch, {1: 2})
 
    response = my_bookings(as_hiker)
 
    assert response.status_code == 200
    assert [b["id"] for b in response.json()] == [own_booking]
    assert response.json()[0]["requirements"] == []
 
 
def test_booking_created_with_post_is_listed(as_hiker, lunch):
    created = book(as_hiker, 3).json()
 
    response = my_bookings(as_hiker)
 
    assert response.status_code == 200
    [booking] = response.json()
    assert booking["id"] == created["id"]
    assert booking["slot_time_start"] == created["time"]
    assert booking["tables"] == created["tables"]
 
 
# ---------- Tests: GET /booking requirements ----------
 
def test_requirements_are_listed_once_per_booking(as_hiker, hiker, lunch, add_booking):
    # the booking uses two tables: its requirements must not be repeated per table
    add_booking(hiker, lunch, {3: 6, 2: 2},
                requirements=[(True, "Gluten free"), (False, "High chair")])
 
    response = my_bookings(as_hiker)
 
    assert response.status_code == 200
    assert response.json()[0]["requirements"] == [
        {"allergies": True, "description": "Gluten free"},
        {"allergies": False, "description": "High chair"},
    ]
 
 
def test_requirement_without_description_is_listed(as_hiker, hiker, lunch, add_booking):
    add_booking(hiker, lunch, {2: 3}, requirements=[(True, None)])
 
    response = my_bookings(as_hiker)
 
    assert response.status_code == 200
    assert response.json()[0]["requirements"] == [{"allergies": True, "description": None}]
 