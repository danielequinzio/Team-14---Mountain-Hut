from datetime import datetime
from html.parser import HTMLParser
from types import SimpleNamespace
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest

import app.services.notification as notification
from app.services.email_template import format_long_date, render_html
from app.services.notification import BookingConfirmation, compose_email, send_booking_confirmation

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
    monkeypatch.setattr(notification, "SMTP_USERNAME", "")
    monkeypatch.setattr(notification, "EMAIL_FROM", "hut@test.example")
    return SimpleNamespace(cls=smtp_class, server=server)


def with_requirements(confirmation, requirements):
    return BookingConfirmation(**{**confirmation.__dict__, "requirements": requirements})


class _Collector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []
        self.urls = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.urls += [value for name, value in attrs if name in ("src", "href") and value]


def test_html_contains_every_detail_required_by_mh03(confirmation):
    html = render_html(confirmation)

    assert "Anna Rossi" in html  # the name of the hiker
    assert "BK-000042" in html  # the booking reference
    assert "Tuesday, 1 January 2030" in html  # the date
    assert "12:00 &ndash; 13:30" in html  # the time slot
    assert "4 guests" in html  # the party size


def test_html_uses_the_hut_time_not_utc(confirmation):
    # 12:00 in Rome is 11:00 UTC in winter: the email must say 12:00
    assert "11:00" not in render_html(confirmation)


def test_html_says_one_guest_in_the_singular(confirmation):
    one = BookingConfirmation(**{**confirmation.__dict__, "party_size": 1})

    assert "1 guest<" in render_html(one)
    assert "1 guests" not in render_html(one)


def test_html_omits_requirements_when_there_are_none(confirmation):
    assert "Party requirements" not in render_html(confirmation)
    assert "Party requirements" not in render_html(with_requirements(confirmation, "   "))


def test_html_shows_requirements_and_keeps_line_breaks(confirmation):
    html = render_html(with_requirements(confirmation, "1 vegan, peanut allergy\n2 vegetarians"))

    assert "Party requirements" in html
    assert "1 vegan, peanut allergy<br>2 vegetarians" in html


def test_html_escapes_user_supplied_text(confirmation):
    evil = BookingConfirmation(
        **{**confirmation.__dict__, "hiker_name": "<script>alert(1)</script> & Co", "requirements": "<img src=x onerror=alert(2)>"}
    )

    html = render_html(evil)

    assert "<script>" not in html
    assert "<img src=x" not in html
    assert "&lt;script&gt;" in html
    assert "&amp; Co" in html
    assert "&lt;img src=x onerror=alert(2)&gt;" in html


def test_html_is_a_well_formed_standalone_page_without_external_resources(confirmation):
    html = render_html(with_requirements(confirmation, "Nut allergy"))
    collector = _Collector()
    collector.feed(html)

    assert html.startswith("<!DOCTYPE html>")
    assert '<html lang="en">' in html
    assert '<meta charset="utf-8">' in html
    assert collector.urls == []  # no images, fonts or links to load from elsewhere
    assert "<style" not in html and "<link" not in html  # inline styles only, for email clients


def test_long_date_does_not_depend_on_the_server_locale():
    assert format_long_date(datetime(2026, 11, 6)) == "Friday, 6 November 2026"
    assert format_long_date(datetime(2027, 3, 1)) == "Monday, 1 March 2027"


def test_sent_message_is_plain_text_plus_html(smtp, confirmation):
    send_booking_confirmation(confirmation)

    sent = smtp.server.send_message.call_args.args[0]
    assert sent.get_content_type() == "multipart/alternative"
    kinds = [part.get_content_type() for part in sent.iter_parts()]
    assert kinds == ["text/plain", "text/html"]  # plain text first: clients show the last part they can
    assert sent["To"] == "anna.rossi@mail.example"
    assert sent["Subject"] == "Booking confirmation BK-000042"


def test_plain_text_part_is_unchanged(smtp, confirmation):
    send_booking_confirmation(confirmation)

    sent = smtp.server.send_message.call_args.args[0]
    plain = sent.get_body(preferencelist=("plain",)).get_content()
    assert plain == compose_email(confirmation).get_content()


def test_plain_text_is_still_sent_when_the_html_cannot_be_built(smtp, confirmation, monkeypatch, caplog):
    def broken(_confirmation):
        raise RuntimeError("template bug")

    monkeypatch.setattr(notification, "render_html", broken)

    send_booking_confirmation(confirmation)

    sent = smtp.server.send_message.call_args.args[0]
    assert sent.get_content_type() == "text/plain"
    assert "BK-000042" in sent.get_content()
    assert "HTML version of BK-000042 not built" in caplog.text
