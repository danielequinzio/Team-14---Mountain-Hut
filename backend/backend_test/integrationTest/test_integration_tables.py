"""
Integration tests of the table endpoints (/tables).

The routes run against the real test db created by conftest.py and the real
authentication (the as_warden override is removed: the user logs in for real).
Each test inserts only the rows it needs. Run from the backend folder with:

    python -m pytest backend_test -v
"""
import pytest
from sqlmodel import select

from app.main import app
from app.models import Roles, Table, User
from app.services.auth import hash_password

URL = "/tables"
PASSWORD = "password123"


# ---------- Helpers ----------

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
    """Real login: the client keeps the session cookie for the next requests."""
    response = client.post("/login", json={"email": user.email, "password": PASSWORD})
    assert response.status_code == 200
    return client


def add_table(session, number: int, capacity: int = 4, location: str = "Main hall") -> Table:
    table = Table(number=number, capacity=capacity, location=location)
    session.add(table)
    session.commit()
    session.refresh(table)
    return table


def stored_tables(session) -> list[Table]:
    session.expire_all()  # read what the api committed
    return session.exec(select(Table)).all()


def table_payload(number=1, capacity=4, location="Main hall") -> dict:
    return {"number": number, "capacity": capacity, "location": location}


# ---------- Fixtures ----------

@pytest.fixture(autouse=True)
def real_auth(as_warden):
    """Removes the as_warden override of conftest.py: the real token and role checks run."""
    app.dependency_overrides.clear()


@pytest.fixture
def as_warden_client(client, session):
    return login(client, add_user(session, "luca.bonetti", Roles.WARDEN))


# ---------- Tests: authentication ----------

@pytest.mark.parametrize("method", ["get", "post"])
def test_anonymous_user_is_rejected(client, method):
    assert getattr(client, method)(URL).status_code == 401


def test_hiker_is_forbidden(client, session):
    login(client, add_user(session, "anna.rossi", Roles.HIKER))

    response = client.post(URL, json=table_payload())

    assert response.status_code == 403
    assert response.json() == {"detail": "Not enough permissions"}
    assert stored_tables(session) == []


def test_employee_is_allowed(client, session):
    login(client, add_user(session, "giulia.ferrero", Roles.EMPLOYEE))

    assert client.get(URL).status_code == 200


# ---------- Tests: GET /tables ----------

def test_get_tables_empty(as_warden_client):
    response = as_warden_client.get(URL)

    assert response.status_code == 200
    assert response.json() == []


def test_get_tables_ordered_by_number(as_warden_client, session):
    add_table(session, 3)
    add_table(session, 1, capacity=2, location="Terrace")
    add_table(session, 2)

    response = as_warden_client.get(URL)

    assert response.status_code == 200
    assert [t["number"] for t in response.json()] == [1, 2, 3]
    first = response.json()[0]
    assert first["capacity"] == 2
    assert first["location"] == "Terrace"


# ---------- Tests: POST /tables ----------

def test_create_table(as_warden_client, session):
    response = as_warden_client.post(URL, json=table_payload(number=5, capacity=6, location="Terrace"))

    assert response.status_code == 201
    body = response.json()
    assert body["number"] == 5
    assert body["capacity"] == 6
    assert body["location"] == "Terrace"
    [stored] = stored_tables(session)
    assert stored.id == body["id"]


def test_created_table_appears_in_list(as_warden_client):
    created = as_warden_client.post(URL, json=table_payload(number=5)).json()

    listed = as_warden_client.get(URL).json()

    assert [t["id"] for t in listed] == [created["id"]]


def test_create_table_duplicate_number(as_warden_client, session):
    add_table(session, 5)

    response = as_warden_client.post(URL, json=table_payload(number=5))

    assert response.status_code == 409
    assert response.json() == {"detail": "Table number already exists"}
    assert len(stored_tables(session)) == 1


def test_create_table_after_duplicate_still_works(as_warden_client, session):
    # the rollback after the 409 leaves the session usable
    add_table(session, 5)
    assert as_warden_client.post(URL, json=table_payload(number=5)).status_code == 409

    response = as_warden_client.post(URL, json=table_payload(number=6))

    assert response.status_code == 201
    assert sorted(t.number for t in stored_tables(session)) == [5, 6]


@pytest.mark.parametrize("field, value", [
    ("number", 0),
    ("number", -1),
    ("capacity", 0),
    ("capacity", -2),
    ("location", ""),
])
def test_create_table_invalid_field(as_warden_client, session, field, value):
    payload = table_payload()
    payload[field] = value

    assert as_warden_client.post(URL, json=payload).status_code == 422
    assert stored_tables(session) == []


@pytest.mark.parametrize("missing", ["number", "capacity", "location"])
def test_create_table_missing_field(as_warden_client, session, missing):
    payload = table_payload()
    del payload[missing]

    assert as_warden_client.post(URL, json=payload).status_code == 422
    assert stored_tables(session) == []