"""
Integration tests for MH-06 "Change a booking": PATCH /booking/{booking_id}.

Run from the backend folder with:

    python -m pytest backend_test/integrationTest/test_integration_change_booking.py -v
"""
from datetime import date, datetime, time, timedelta
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest
from sqlmodel import select

import app.routers.booking as booking_router
import app.services.notification as notification
from app.main import app
from app.models import Booking, BookingRequirement, Roles, Slot, SlotTable, Table, User
from app.services.auth import hash_password

HUT_TZ = ZoneInfo("Europe/Rome")
URL = "/booking"
LUNCH = time(12, 0)
DINNER = time(19, 0)
TABLES = {1: 2, 2: 4, 3: 6}  # table number -> seats: 12 seats per slot
PASSWORD = "password123"
TOO_LATE = "Booking changes must be made at least 48 hours before the slot"


# ---------- Helpers ----------

def far_day() -> date:
    """5 days from now: over the 48 hours, so changes are allowed."""
    return datetime.now(HUT_TZ).date() + timedelta(days=5)


def at(day: date, start: time) -> datetime:
    return datetime.combine(day, start, HUT_TZ)


def add_user(session, username: str, role: Roles) -> User:
    name, surname = username.split(".")
    user = User(username=username, name=name.title(), surname=surname.title(),
                email=f"{username}@mail.example", mobile_number="+39 333 000 0000",
                password_hash=hash_password(PASSWORD), role=role)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def login(client, user: User):
    response = client.post("/login", json={"email": user.email, "password": PASSWORD})
    assert response.status_code == 200
    return client


def book(client, party_size, day=None, start=LUNCH, requirements=None) -> int:
    payload = {"date": (day or far_day()).isoformat(), "time": start.isoformat(),
               "party_size": party_size, "requirements": requirements or []}
    response = client.post(URL, json=payload)
    assert response.status_code == 201
    return response.json()["id"]


def change(client, booking_id: int, **payload):
    return client.patch(f"{URL}/{booking_id}", json=payload)


def stored_booking(session, booking_id: int) -> Booking:
    session.expire_all()  # read what the api committed
    return session.get(Booking, booking_id)


def occupied_seats(session, slot_id: int) -> dict[int, int]:
    session.expire_all()
    rows = session.exec(
        select(Table.number, SlotTable.occupied_seats)
        .join(Table, Table.id == SlotTable.table_id)
        .where(SlotTable.slot_id == slot_id)
    ).all()
    return dict(rows)


def stored_requirements(session) -> list[tuple[bool, str | None]]:
    session.expire_all()
    rows = session.exec(select(BookingRequirement).order_by(BookingRequirement.id)).all()
    return [(row.allergies, row.description) for row in rows]


def seats_by_table(response) -> dict[int, int]:
    return {table["number"]: table["seats"] for table in response.json()["tables"]}


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
def lunch(add_slot) -> int:
    return add_slot(at(far_day(), LUNCH))


@pytest.fixture
def dinner(add_slot) -> int:
    return add_slot(at(far_day(), DINNER))


@pytest.fixture
def sent_changes(monkeypatch) -> list:
    """Captures the change emails handed to the background task."""
    sent = []
    monkeypatch.setattr(booking_router, "send_booking_change", sent.append)
    return sent


@pytest.fixture
def smtp(monkeypatch):
    """The real send_booking_change runs; only the SMTP server is fake."""
    server = MagicMock()
    smtp_class = MagicMock()
    smtp_class.return_value.__enter__.return_value = server
    monkeypatch.setattr(notification.smtplib, "SMTP", smtp_class)
    monkeypatch.setattr(notification, "SMTP_HOST", "smtp.test")
    monkeypatch.setattr(notification, "SMTP_USERNAME", "")
    monkeypatch.setattr(notification, "EMAIL_FROM", "hut@test.example")
    return server


# ---------- Tests: successful changes ----------

def test_bigger_party_releases_the_seats_and_gets_tables_again(as_hiker, session, lunch, sent_changes):
    # MH-06 clarification: the party no longer fits its table -> treated as a new booking
    booking_id = book(as_hiker, 2)  # table 1 (2 seats)

    response = change(as_hiker, booking_id, party_size=3)

    assert response.status_code == 200
    assert response.json()["party_size"] == 3
    assert seats_by_table(response) == {2: 3}
    assert stored_booking(session, booking_id).party_size == 3
    assert occupied_seats(session, lunch) == {1: 0, 2: 3, 3: 0}  # table 1 released
    [email] = sent_changes
    assert (email.reference, email.party_size) == (f"BK-{booking_id:06d}", 3)


def test_own_seats_count_as_free(as_hiker, session, add_slot):
    # the slot is full only because of the hiker's own booking: the change is accepted
    slot = add_slot(at(far_day(), LUNCH), occupied={2: 4, 3: 6})
    booking_id = book(as_hiker, 2)  # the last 2 seats, table 1

    response = change(as_hiker, booking_id, party_size=1)

    assert response.status_code == 200
    assert occupied_seats(session, slot) == {1: 1, 2: 4, 3: 6}


def test_booking_moves_to_another_slot(as_hiker, session, lunch, dinner, sent_changes):
    booking_id = book(as_hiker, 2)

    response = change(as_hiker, booking_id, date=far_day().isoformat(), time=DINNER.isoformat())

    assert response.status_code == 200
    assert response.json()["time"] == "19:00:00"
    assert stored_booking(session, booking_id).slot_id == dinner
    assert occupied_seats(session, lunch) == {1: 0, 2: 0, 3: 0}  # released in the old slot
    assert occupied_seats(session, dinner) == {1: 2, 2: 0, 3: 0}
    assert sent_changes[0].start == at(far_day(), DINNER)


@pytest.mark.parametrize(
    ("payload", "stored", "emailed"),
    [
        ({"requirements": [{"allergies": True, "description": "Nuts"}]},
         [(True, "Nuts")], "- [Allergy] Nuts"),
        ({"requirements": []}, [], None),
        ({"party_size": 3}, [(False, "Vegan")], "- Vegan"),  # not sent: kept
    ],
    ids=["replaced", "removed", "kept"],
)
def test_requirements_after_the_change(as_hiker, session, lunch, sent_changes,
                                       payload, stored, emailed):
    booking_id = book(as_hiker, 2, requirements=[{"description": "Vegan"}])

    assert change(as_hiker, booking_id, **payload).status_code == 200

    assert stored_requirements(session) == stored
    assert sent_changes[0].requirements == emailed


def test_booking_without_assigned_tables_gets_them(as_hiker, session, hiker, lunch):
    # a booking with no seats to release (release_tables returns early)
    booking = Booking(user_id=hiker.id, slot_id=lunch, party_size=2)
    session.add(booking)
    session.commit()

    response = change(as_hiker, booking.id, party_size=3)

    assert response.status_code == 200
    assert occupied_seats(session, lunch) == {1: 0, 2: 3, 3: 0}


def test_change_email_is_sent(as_hiker, lunch, smtp):
    booking_id = book(as_hiker, 2)

    change(as_hiker, booking_id, party_size=3, requirements=[{"allergies": True, "description": "Nuts"}])

    message = smtp.send_message.call_args.args[0]  # the last email: the change
    assert message["Subject"] == f"Booking changed BK-{booking_id:06d}"
    assert message["To"] == "anna.rossi@mail.example"
    assert [part.get_content_type() for part in message.iter_parts()] == ["text/plain", "text/html"]
    plain = message.get_body(preferencelist=("plain",)).get_content()
    assert "Party size: 3" in plain
    assert "- [Allergy] Nuts" in plain
    html = message.get_body(preferencelist=("html",)).get_content()
    assert "Booking changed" in html
    assert "Party requirements" in html


def test_change_email_without_requirements(as_hiker, lunch, smtp):
    booking_id = book(as_hiker, 2)

    change(as_hiker, booking_id, party_size=3)

    message = smtp.send_message.call_args.args[0]
    assert "Party requirements" not in message.get_body(preferencelist=("plain",)).get_content()
    assert "Party requirements" not in message.get_body(preferencelist=("html",)).get_content()


def test_change_email_uses_tls_and_login_with_a_real_provider(as_hiker, lunch, smtp, monkeypatch):
    # e.g. Gmail: SMTP_USERNAME is set
    monkeypatch.setattr(notification, "SMTP_USERNAME", "login")
    booking_id = book(as_hiker, 2)
    smtp.reset_mock()  # keep only the calls of the change email

    change(as_hiker, booking_id, party_size=3)

    assert [call[0] for call in smtp.method_calls] == ["starttls", "login", "send_message"]


def test_change_is_kept_when_the_email_cannot_be_sent(as_hiker, session, lunch, smtp, caplog):
    smtp.send_message.side_effect = OSError("SMTP server down")
    booking_id = book(as_hiker, 2)

    response = change(as_hiker, booking_id, party_size=3)

    assert response.status_code == 200
    assert stored_booking(session, booking_id).party_size == 3
    assert f"Change email BK-{booking_id:06d} not sent" in caplog.text


def test_plain_text_is_sent_when_the_html_cannot_be_built(as_hiker, lunch, smtp, monkeypatch, caplog):
    def broken(_change):
        raise RuntimeError("template bug")

    monkeypatch.setattr(notification, "render_change_html", broken)
    booking_id = book(as_hiker, 2)

    change(as_hiker, booking_id, party_size=3)

    message = smtp.send_message.call_args.args[0]
    assert message.get_content_type() == "text/plain"
    assert "Party size: 3" in message.get_content()
    assert f"HTML version of change BK-{booking_id:06d} not built" in caplog.text


# ---------- Tests: refused changes (booking unchanged, no email) ----------

def test_not_enough_seats_leaves_the_booking_as_it_was(as_hiker, session, add_slot, sent_changes):
    slot = add_slot(at(far_day(), LUNCH), occupied={3: 6})  # 6 free seats
    booking_id = book(as_hiker, 2, requirements=[{"description": "Vegan"}])

    response = change(as_hiker, booking_id, party_size=7,
                      requirements=[{"allergies": True, "description": "Nuts"}])

    assert response.status_code == 409
    assert response.json() == {"detail": "There are not enough seats for this party"}
    assert stored_booking(session, booking_id).party_size == 2
    assert occupied_seats(session, slot) == {1: 2, 2: 0, 3: 6}  # released seats are back
    assert stored_requirements(session) == [(False, "Vegan")]
    assert sent_changes == []


def test_change_within_48_hours_is_refused(as_hiker, session, add_slot, sent_changes):
    start = (datetime.now(HUT_TZ) + timedelta(hours=47)).replace(second=0, microsecond=0)
    add_slot(start)
    booking_id = book(as_hiker, 2, day=start.date(), start=start.time())

    response = change(as_hiker, booking_id, party_size=3)

    assert response.status_code == 400
    assert response.json() == {"detail": TOO_LATE}
    assert stored_booking(session, booking_id).party_size == 2
    assert sent_changes == []


def test_new_slot_within_48_hours_is_refused(as_hiker, session, lunch, add_slot, sent_changes):
    soon = datetime.now(HUT_TZ).date() + timedelta(days=1)
    add_slot(at(soon, LUNCH))
    booking_id = book(as_hiker, 2)

    response = change(as_hiker, booking_id, date=soon.isoformat(), time=LUNCH.isoformat())

    assert response.status_code == 400
    assert response.json() == {"detail": TOO_LATE}
    assert stored_booking(session, booking_id).slot_id == lunch
    assert sent_changes == []


@pytest.mark.parametrize("field", ["date", "time"])
def test_date_and_time_must_change_together(as_hiker, lunch, sent_changes, field):
    booking_id = book(as_hiker, 2)
    payload = {"date": far_day().isoformat(), "time": DINNER.isoformat()}

    response = change(as_hiker, booking_id, **{field: payload[field]})

    assert response.status_code == 400
    assert response.json() == {"detail": "Date and time must be changed together"}
    assert sent_changes == []


def test_new_slot_already_booked_by_the_hiker(as_hiker, session, lunch, dinner, sent_changes):
    booking_id = book(as_hiker, 2)
    book(as_hiker, 2, start=DINNER)

    response = change(as_hiker, booking_id, date=far_day().isoformat(), time=DINNER.isoformat())

    assert response.status_code == 409
    assert response.json() == {"detail": "A booking already exists for this slot"}
    assert stored_booking(session, booking_id).slot_id == lunch
    assert sent_changes == []


def test_booking_of_another_hiker_is_not_found(client, session, as_hiker, lunch, sent_changes):
    booking_id = book(as_hiker, 2)
    login(client, add_user(session, "paolo.bianchi", Roles.HIKER))

    response = change(client, booking_id, party_size=3)

    assert response.status_code == 404
    assert response.json() == {"detail": "Booking not found"}
    assert stored_booking(session, booking_id).party_size == 2
    assert sent_changes == []


def test_booking_whose_slot_was_deleted(as_hiker, session, lunch, sent_changes):
    # defensive branch: the booking points to a slot that no longer exists
    booking_id = book(as_hiker, 2)
    session.delete(session.get(Slot, lunch))
    session.commit()

    response = change(as_hiker, booking_id, party_size=3)

    assert response.status_code == 500
    assert response.json() == {"detail": "Booking slot not found"}
    assert sent_changes == []