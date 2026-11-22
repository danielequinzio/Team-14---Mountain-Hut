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

# ---------- helpers for the other emails ----------

def plain_body(message):
    """The plain-text part, whether or not an HTML alternative was attached."""
    return message.get_body(preferencelist=("plain",)).get_content()


def sent_message(smtp):
    return smtp.server.send_message.call_args.args[0]


def call_names(smtp):
    return [call[0] for call in smtp.server.method_calls]


@pytest.fixture
def reset():
    return notification.ResetData(token="tok123", expire_at=datetime(2030, 1, 1, 12, 30))


@pytest.fixture
def account():
    return notification.AccountCreated(
        recipient="anna.rossi@mail.example",
        name="Anna",
        surname="Rossi",
        username="anna.rossi",
        mobile_number="3331234567",
        password="Temp-Pass-1",
    )


# ---------- password reset ----------

def test_pwd_reset_uses_tls_and_login_and_sends_link(smtp, monkeypatch, reset):
    monkeypatch.setattr(notification, "FRONTEND_URL", "http://front.test")

    notification.send_pwd_reset("anna.rossi@mail.example", reset)

    assert call_names(smtp) == ["starttls", "login", "send_message"]
    message = sent_message(smtp)
    assert message["To"] == "anna.rossi@mail.example"
    assert message["Subject"] == "Password reset"
    body = plain_body(message)
    assert "http://front.test/reset-password?token=tok123" in body
    assert "01/01/2030 12:30" in body
    assert message.get_body(preferencelist=("html",)) is not None


def test_pwd_reset_without_username_skips_tls_and_login(smtp, monkeypatch, reset):
    monkeypatch.setattr(notification, "SMTP_USERNAME", "")

    notification.send_pwd_reset("anna.rossi@mail.example", reset)

    assert call_names(smtp) == ["send_message"]


def test_pwd_reset_is_skipped_without_smtp_host(smtp, monkeypatch, reset):
    monkeypatch.setattr(notification, "SMTP_HOST", "")

    notification.send_pwd_reset("anna.rossi@mail.example", reset)

    smtp.cls.assert_not_called()


@pytest.mark.parametrize("error", [smtplib.SMTPAuthenticationError(535, b"bad key"), OSError("down")])
def test_pwd_reset_failure_is_logged_and_not_raised(smtp, reset, caplog, error):
    smtp.server.send_message.side_effect = error

    notification.send_pwd_reset("anna.rossi@mail.example", reset)

    assert "Password reset email not sent" in caplog.text
    assert "tok123" not in caplog.text  # the token must never end up in the logs


# ---------- account created ----------

def test_login_url_points_to_the_frontend(monkeypatch):
    monkeypatch.setattr(notification, "FRONTEND_URL", "http://front.test")

    assert notification.login_url() == "http://front.test/login"


def test_compose_account_email_contains_every_detail(monkeypatch, account):
    monkeypatch.setattr(notification, "FRONTEND_URL", "http://front.test")

    message = notification.compose_account_email(account)
    body = message.get_content()

    assert message["Subject"] == "Your Mountain Hut account"
    assert message["To"] == "anna.rossi@mail.example"
    assert "Hello Anna Rossi," in body
    assert "Username: anna.rossi" in body
    assert "Email: anna.rossi@mail.example" in body
    assert "Mobile number: 3331234567" in body
    assert "Password: Temp-Pass-1" in body
    assert "Log in here: http://front.test/login" in body


def test_account_created_uses_tls_and_login_before_sending(smtp, account):
    notification.send_account_created(account)

    assert call_names(smtp) == ["starttls", "login", "send_message"]
    message = sent_message(smtp)
    assert message["To"] == "anna.rossi@mail.example"
    assert message.get_body(preferencelist=("html",)) is not None


def test_account_created_without_username_skips_tls_and_login(smtp, monkeypatch, account):
    monkeypatch.setattr(notification, "SMTP_USERNAME", "")

    notification.send_account_created(account)

    assert call_names(smtp) == ["send_message"]


def test_account_created_is_skipped_without_smtp_host(smtp, monkeypatch, account):
    monkeypatch.setattr(notification, "SMTP_HOST", "")

    notification.send_account_created(account)

    smtp.cls.assert_not_called()


def test_account_created_sends_plain_text_when_html_fails(smtp, monkeypatch, account, caplog):
    def broken(*args, **kwargs):
        raise RuntimeError("template broken")

    monkeypatch.setattr(notification, "render_account_html", broken)

    notification.send_account_created(account)

    message = sent_message(smtp)
    assert not message.is_multipart()
    assert "Password: Temp-Pass-1" in message.get_content()
    assert "HTML version of the account email not built" in caplog.text


@pytest.mark.parametrize("error", [smtplib.SMTPAuthenticationError(535, b"bad key"), OSError("down")])
def test_account_created_failure_is_logged_and_not_raised(smtp, account, caplog, error):
    smtp.server.send_message.side_effect = error

    notification.send_account_created(account)

    assert "Account email not sent" in caplog.text
    assert "Temp-Pass-1" not in caplog.text  # the password must never end up in the logs


# ---------- booking cancelled ----------

def test_compose_cancellation_email_contains_every_detail(confirmation):
    message = notification.compose_cancellation_email(confirmation)
    body = message.get_content()

    assert message["Subject"] == "Booking cancelled BK-000042"
    assert message["To"] == confirmation.recipient
    assert "Anna Rossi" in body
    assert "has been cancelled" in body
    assert "01/01/2030" in body
    assert "12:00 - 13:30" in body
    assert "Party size: 4" in body
    assert "please contact the hut" in body
    assert "Party requirements" not in body


def test_compose_cancellation_email_shows_requirements(confirmation):
    confirmation = BookingConfirmation(**{**confirmation.__dict__, "requirements": "Nut allergy"})

    body = notification.compose_cancellation_email(confirmation).get_content()

    assert "Party requirements: Nut allergy" in body


def test_cancellation_uses_tls_and_login_before_sending(smtp, confirmation):
    notification.send_booking_cancellation(confirmation)

    assert call_names(smtp) == ["starttls", "login", "send_message"]
    message = sent_message(smtp)
    assert message["To"] == confirmation.recipient
    assert message.get_body(preferencelist=("html",)) is not None


def test_cancellation_without_username_skips_tls_and_login(smtp, monkeypatch, confirmation):
    monkeypatch.setattr(notification, "SMTP_USERNAME", "")

    notification.send_booking_cancellation(confirmation)

    assert call_names(smtp) == ["send_message"]


def test_cancellation_is_skipped_without_smtp_host(smtp, monkeypatch, confirmation):
    monkeypatch.setattr(notification, "SMTP_HOST", "")

    notification.send_booking_cancellation(confirmation)

    smtp.cls.assert_not_called()


def test_cancellation_sends_plain_text_when_html_fails(smtp, monkeypatch, confirmation, caplog):
    def broken(*args, **kwargs):
        raise RuntimeError("template broken")

    monkeypatch.setattr(notification, "render_cancellation_html", broken)

    notification.send_booking_cancellation(confirmation)

    message = sent_message(smtp)
    assert not message.is_multipart()
    assert "BK-000042" in message.get_content()
    assert "HTML version of cancellation BK-000042 not built" in caplog.text


@pytest.mark.parametrize("error", [smtplib.SMTPAuthenticationError(535, b"bad key"), OSError("down")])
def test_cancellation_failure_is_logged_and_not_raised(smtp, confirmation, caplog, error):
    smtp.server.send_message.side_effect = error

    notification.send_booking_cancellation(confirmation)

    assert "Cancellation email BK-000042 not sent" in caplog.text
