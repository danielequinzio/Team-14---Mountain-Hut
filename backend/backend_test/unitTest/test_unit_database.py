from unittest.mock import MagicMock

import pytest

from app.database import get_session, transaction


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
