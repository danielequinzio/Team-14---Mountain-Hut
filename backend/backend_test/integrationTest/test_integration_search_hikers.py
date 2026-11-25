from app.main import app
from app.models import CurrentUser, Roles, User
from app.services.auth import get_current_user, hash_password

SEARCH_URL = "/hikers/search"


def add_user(session, name: str, surname: str, email: str | None, mobile_number: str,
             role: Roles = Roles.HIKER, is_guest: bool = False) -> User:
    user = User(
        username=f"{name.lower()}.{surname.lower()}",
        name=name,
        surname=surname,
        email=email,
        mobile_number=mobile_number,
        password_hash=hash_password("password123"),
        role=role,
        is_guest=is_guest,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def test_employee_searches_registered_hikers_by_name_email_and_phone(client, session):
    hiker = add_user(
        session,
        "Anna",
        "Rossi",
        "anna.rossi@mail.example",
        "+39 333 111 2222",
    )
    add_user(session, "Anna", "Guest", None, "+39 333 111 9999", is_guest=True)
    add_user(session, "Anna", "Employee", "anna.employee@mail.example", "+39 333 111 8888",
             role=Roles.EMPLOYEE)

    for query in ("Anna Ro", "ANNA.ROSSI@", "333111"):
        response = client.get(SEARCH_URL, params={"q": query})

        assert response.status_code == 200
        assert response.json() == [{
            "id": hiker.id,
            "name": "Anna",
            "surname": "Rossi",
            "email": "anna.rossi@mail.example",
            "mobile_number": "+39 333 111 2222",
        }]


def test_employee_search_returns_empty_list_when_no_hikers_match(client):
    response = client.get(SEARCH_URL, params={"q": "nobody"})

    assert response.status_code == 200
    assert response.json() == []


def test_employee_search_requires_non_empty_query(client):
    response = client.get(SEARCH_URL, params={"q": "   "})

    assert response.status_code == 200
    assert response.json() == []


def test_employee_search_rejects_invalid_limit(client):
    response = client.get(SEARCH_URL, params={"q": "anna", "limit": 51})

    assert response.status_code == 422


def test_employee_search_respects_result_limit(client, session):
    add_user(session, "Anna", "Bianchi", "anna.bianchi@mail.example", "+39 333 111 2222")
    add_user(session, "Anna", "Rossi", "anna.rossi@mail.example", "+39 333 111 3333")

    response = client.get(SEARCH_URL, params={"q": "anna", "limit": 1})

    assert response.status_code == 200
    assert [hiker["surname"] for hiker in response.json()] == ["Bianchi"]


def test_hikers_cannot_search_registered_hikers(client):
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=1,
        username="test-hiker",
        role=Roles.HIKER,
    )
    try:
        response = client.get(SEARCH_URL, params={"q": "anna"})
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 403
