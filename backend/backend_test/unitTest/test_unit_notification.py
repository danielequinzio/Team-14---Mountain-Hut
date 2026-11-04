import smtplib
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest

import app.services.notification as notification
from app.services.notification import (
    BookingConfirmation,
    booking_reference,
    build_confirmation,
    compose_email,
    send_booking_confirmation,
)

HUT_TIMEZONE = ZoneInfo("Europe/Rome")


@pytest.fixture
def confirmation():
    return BookingConfirmation(
        recipient="anna.rossi@mail.example",
        hiker_name="Anna Rossi",
        reference="BK-000042",
        start=datetime(2030, 1, 1, 12, 0, tzinfo=HUT_TIMEZONE),
        end=datetime(2030, 1, 1, 13, 30, tzinfo=HUT_TIMEZONE),
        party_size=4,
    )


@pytest.fixture
def smtp(monkeypatch):
    """Replaces smtplib.SMTP: the mock is what `with smtplib.SMTP(...)` yields."""
    server = MagicMock()
    smtp_class = MagicMock()
    smtp_class.return_value.__enter__.return_value = server
    monkeypatch.setattr(notification.smtplib, "SMTP", smtp_class)
    monkeypatch.setattr(notification, "SMTP_HOST", "smtp.test")
    monkeypatch.setattr(notification, "SMTP_USERNAME", "login")
    monkeypatch.setattr(notification, "EMAIL_FROM", "hut@test.example")
    return SimpleNamespace(cls=smtp_class, server=server)


def test_booking_reference_is_padded():
    assert booking_reference(42) == "BK-000042"


def test_build_confirmation_copies_booking_data():
    user = SimpleNamespace(name="Anna", surname="Rossi", email="anna.rossi@mail.example")
    slot = SimpleNamespace(start_time=datetime(2030, 1, 1, 12, 0), end_time=datetime(2030, 1, 1, 13, 30))
    booking = SimpleNamespace(id=42, party_size=4)

    result = build_confirmation(user, slot, booking)

    assert result.recipient == "anna.rossi@mail.example"
    assert result.hiker_name == "Anna Rossi"
    assert result.reference == "BK-000042"
    assert result.party_size == 4
    assert result.requirements is None
    assert (result.start.hour, result.end.hour, result.end.minute) == (12, 13, 30)


def test_compose_email_contains_every_required_detail(confirmation):
    body = compose_email(confirmation).get_content()

    assert "Anna Rossi" in body
    assert "BK-000042" in body
    assert "01/01/2030" in body
    assert "12:00 - 13:30" in body
    assert "Party size: 4" in body


def test_compose_email_omits_requirements_when_there_are_none(confirmation):
    assert "Party requirements" not in compose_email(confirmation).get_content()


def test_compose_email_shows_requirements(confirmation):
    confirmation = BookingConfirmation(**{**confirmation.__dict__, "requirements": "Nut allergy"})

    assert "Party requirements: Nut allergy" in compose_email(confirmation).get_content()


def test_send_uses_tls_and_login_before_sending(smtp, confirmation):
    send_booking_confirmation(confirmation)

    names = [call[0] for call in smtp.server.method_calls]
    assert names == ["starttls", "login", "send_message"]
    assert smtp.server.send_message.call_args.args[0]["To"] == confirmation.recipient


def test_send_without_username_skips_tls_and_login(smtp, monkeypatch, confirmation):
    monkeypatch.setattr(notification, "SMTP_USERNAME", "")

    send_booking_confirmation(confirmation)

    assert [call[0] for call in smtp.server.method_calls] == ["send_message"]


def test_send_is_skipped_without_smtp_host(smtp, monkeypatch, confirmation):
    monkeypatch.setattr(notification, "SMTP_HOST", "")

    send_booking_confirmation(confirmation)

    smtp.cls.assert_not_called()


@pytest.mark.parametrize("error", [smtplib.SMTPAuthenticationError(535, b"bad key"), OSError("down")])
def test_send_failure_is_logged_and_not_raised(smtp, confirmation, caplog, error):
    smtp.server.send_message.side_effect = error

    send_booking_confirmation(confirmation)

    assert "Confirmation BK-000042 not sent" in caplog.text