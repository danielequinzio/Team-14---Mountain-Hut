from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.dialects import sqlite

from app.database import get_session
from app.main import app
from app.models import Roles, User

URL = "/hikers/search"


@pytest.fixture
def mock_session():
    return MagicMock()


@pytest.fixture
def client(mock_session):
    app.dependency_overrides[get_session] = lambda: mock_session
    yield TestClient(app)
    app.dependency_overrides.pop(get_session, None)


@pytest.fixture
def hiker():
    return User(
        id=7,
        username="anna.rossi",
        name="Anna",
        surname="Rossi",
        email="anna.rossi@mail.example",
        mobile_number="+39 333 345 6789",
        password_hash="must-not-be-returned",
        role=Roles.HIKER,
    )


def test_search_returns_only_public_hiker_fields(client, mock_session, hiker):
    mock_session.exec.return_value.all.return_value = [hiker]

    response = client.get(URL, params={"q": "333", "limit": 5})

    assert response.status_code == 200
    assert response.json() == [{
        "id": 7,
        "name": "Anna",
        "surname": "Rossi",
        "email": "anna.rossi@mail.example",
        "mobile_number": "+39 333 345 6789",
    }]

    statement = mock_session.exec.call_args.args[0]
    compiled = statement.compile(dialect=sqlite.dialect())
    assert "user.role =" in compiled.string
    assert "user.is_guest IS 0" in compiled.string
    assert "replace(" in compiled.string
    assert 5 in compiled.params.values()


def test_search_escapes_wildcards_in_user_query(client, mock_session):
    mock_session.exec.return_value.all.return_value = []

    response = client.get(URL, params={"q": "anna%_"})

    assert response.status_code == 200
    assert response.json() == []

    statement = mock_session.exec.call_args.args[0]
    params = statement.compile(dialect=sqlite.dialect()).params.values()
    assert "%anna\\%\\_%" in params


def test_search_with_whitespace_query_returns_empty_without_querying(client, mock_session):
    response = client.get(URL, params={"q": "   "})

    assert response.status_code == 200
    assert response.json() == []
    mock_session.exec.assert_not_called()


@pytest.mark.parametrize("params", [{"q": ""}, {"q": "anna", "limit": 51}])
def test_search_rejects_invalid_query_parameters(client, mock_session, params):
    response = client.get(URL, params=params)

    assert response.status_code == 422
    mock_session.exec.assert_not_called()
