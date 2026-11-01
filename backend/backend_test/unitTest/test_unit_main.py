import asyncio
from unittest.mock import MagicMock

import app.main as main


def test_lifespan_runs_database_initialization(monkeypatch):
    calls = []
    session = MagicMock()
    session_factory = MagicMock()
    session_factory.return_value.__enter__.return_value = session

    monkeypatch.setattr(main, "drop_unused_salt_column", lambda: calls.append("drop_salt"))
    monkeypatch.setattr(
        main,
        "drop_username_unique_constraint",
        lambda: calls.append("drop_username"),
    )
    monkeypatch.setattr(
        main.SQLModel.metadata,
        "create_all",
        lambda engine: calls.append("create_all"),
    )
    monkeypatch.setattr(main, "add_user_profile_columns", lambda: calls.append("add_columns"))
    monkeypatch.setattr(main, "seeding", lambda current_session: calls.append(current_session))
    monkeypatch.setattr(main, "Session", session_factory)

    async def run_lifespan():
        async with main.lifespan(main.app):
            calls.append("ready")

    asyncio.run(run_lifespan())

    assert calls == ["drop_salt", "drop_username", "create_all", "add_columns", session, "ready"]
    session_factory.assert_called_once_with(main.engine)
