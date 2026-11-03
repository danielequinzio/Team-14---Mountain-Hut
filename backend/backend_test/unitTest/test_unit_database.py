from unittest.mock import MagicMock

import pytest

from app.database import booking_transaction, get_session, transaction


def test_get_session_yields_and_closes_session(monkeypatch):
    session = MagicMock()
    session_factory = MagicMock()
    session_factory.return_value.__enter__.return_value = session
    monkeypatch.setattr("app.database.Session", session_factory)

    yielded = list(get_session())

    assert yielded == [session]
    session_factory.assert_called_once()
    session_factory.return_value.__exit__.assert_called_once()


def test_transaction_commits_after_success():
    session = MagicMock()

    with transaction(session):
        pass

    session.commit.assert_called_once()
    session.rollback.assert_not_called()


def test_transaction_rolls_back_and_reraises_on_error():
    session = MagicMock()
    error = RuntimeError("database failure")

    with pytest.raises(RuntimeError, match="database failure"):
        with transaction(session):
            raise error

    session.rollback.assert_called_once()
    session.commit.assert_not_called()


def test_booking_transaction_starts_immediate_transaction_on_sqlite():
    session = MagicMock()
    session.get_bind.return_value.dialect.name = "sqlite"

    with booking_transaction(session):
        pass

    session.connection.return_value.exec_driver_sql.assert_called_once_with(
        "BEGIN IMMEDIATE"
    )
    session.commit.assert_called_once()


def test_booking_transaction_does_not_start_immediate_transaction_on_other_databases():
    session = MagicMock()
    session.get_bind.return_value.dialect.name = "postgresql"

    with booking_transaction(session):
        pass

    session.connection.assert_not_called()
    session.commit.assert_called_once()


def test_booking_transaction_rolls_back_and_reraises_on_error():
    session = MagicMock()
    session.get_bind.return_value.dialect.name = "sqlite"

    with pytest.raises(RuntimeError, match="booking failure"):
        with booking_transaction(session):
            raise RuntimeError("booking failure")

    session.rollback.assert_called_once()
    session.commit.assert_not_called()
