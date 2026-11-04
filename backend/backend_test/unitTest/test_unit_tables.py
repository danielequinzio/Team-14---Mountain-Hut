"""
Unit tests of the table endpoints (/tables) in app/routers/tables.py.

The route functions are called directly with a fake session, so no db and no http are involved.
"""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.models import Table, TableCreate
from app.routers.tables import create_table, get_tables


USER = SimpleNamespace(id=5, role="warden")


class FakeSession:
    """Stands in for the db session.

    `results` are the rows of each session.exec call, consumed in order.
    `fail_commit=True` makes commit raise IntegrityError, as the db does for a duplicate table number.
    """

    def __init__(self, results=None, fail_commit=False):
        self.results = list(results or [])
        self.fail_commit = fail_commit
        self.added = []
        self.commits = 0
        self.rollbacks = 0
        self.refreshed = []

    def exec(self, query):
        rows = self.results.pop(0)
        return SimpleNamespace(all=lambda: rows)

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        if self.fail_commit:
            raise IntegrityError("INSERT INTO table", {}, Exception("UNIQUE constraint failed: table.number"))
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def refresh(self, obj):
        obj.id = 1
        self.refreshed.append(obj)


def make_table(table_id, number=1, capacity=12, location="dentro"):
    return Table(id=table_id, number=number, capacity=capacity, location=location)


# ---------- GET /tables ----------

def test_get_tables():
    tables = [make_table(1, 1), make_table(2, 2), make_table(3, 3), make_table(4, 4)]
    session = FakeSession(results=[tables])

    assert [t.id for t in get_tables(session, USER)] == [1, 2, 3, 4]


def test_get_tables_returns_rows_unchanged():
    table = make_table(1, number=7, capacity=4, location="terrazza")
    session = FakeSession(results=[[table]])

    assert get_tables(session, USER) == [table]


def test_get_tables_empty():
    session = FakeSession(results=[[]])

    assert get_tables(session, USER) == []


# ---------- POST /tables ----------

def test_add_table():
    session = FakeSession()

    result = create_table(TableCreate(number=5, capacity=6, location="dentro"), session, USER)

    assert session.added == [result]
    assert session.commits == 1
    assert session.refreshed == [result]
    assert session.rollbacks == 0
    assert result.id == 1
    assert result.number == 5
    assert result.capacity == 6
    assert result.location == "dentro"


def test_add_table_duplicate_number():
    session = FakeSession(fail_commit=True)

    with pytest.raises(HTTPException) as exc:
        create_table(TableCreate(number=5, capacity=6, location="dentro"), session, USER)

    assert exc.value.status_code == 409
    assert exc.value.detail == "Table number already exists"
    assert session.rollbacks == 1
    assert session.refreshed == []


# ---------- TableCreate validation ----------

@pytest.mark.parametrize("number", [0, -1])
def test_table_create_rejects_non_positive_number(number):
    with pytest.raises(ValueError):
        TableCreate(number=number, capacity=6, location="dentro")


@pytest.mark.parametrize("capacity", [0, -3])
def test_table_create_rejects_non_positive_capacity(capacity):
    with pytest.raises(ValueError):
        TableCreate(number=1, capacity=capacity, location="dentro")


def test_table_create_rejects_empty_location():
    with pytest.raises(ValueError):
        TableCreate(number=1, capacity=6, location="")