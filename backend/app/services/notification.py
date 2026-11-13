import logging
import smtplib
import ssl
from dataclasses import dataclass
from datetime import datetime
from email.message import EmailMessage
from urllib.parse import urlencode

from app.config import (
    EMAIL_FROM,
    FRONTEND_URL,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_USERNAME,
)
from app.models import Booking, ResetData, Slot, User
from app.services.booking import slot_end, slot_start
from app.services.email_template import render_account_html, render_html

logger = logging.getLogger(__name__)

SMTP_TIMEOUT_SECONDS = 10


@dataclass(frozen=True)
class BookingConfirmation:
    # plain data, so the background task doesn't depend on the request's db session
    recipient: str
    hiker_name: str
    reference: str
    start: datetime
    end: datetime
    party_size: int
    requirements: str | None = None


def booking_reference(booking_id: int) -> str:
    return f"BK-{booking_id:06d}"


def build_confirmation(
    user: User,
    slot: Slot,
    booking: Booking,
    requirements: str | None = None,  # filled in once MH-05 stores them
) -> BookingConfirmation:
    return BookingConfirmation(
        recipient=user.email,
        hiker_name=f"{user.name} {user.surname}",
        reference=booking_reference(booking.id),
        start=slot_start(slot),
        end=slot_end(slot),
        party_size=booking.party_size,
        requirements=requirements,
    )


def compose_email(confirmation: BookingConfirmation) -> EmailMessage:
    lines = [
        f"Hello {confirmation.hiker_name},",
        "",
        "your booking at the mountain hut is confirmed.",
        "",
        f"Booking reference: {confirmation.reference}",
        f"Date: {confirmation.start:%d/%m/%Y}",
        f"Time slot: {confirmation.start:%H:%M} - {confirmation.end:%H:%M}",
        f"Party size: {confirmation.party_size}",
    ]
    if confirmation.requirements:
        lines.append(f"Party requirements: {confirmation.requirements}")

    message = EmailMessage()
    message["Subject"] = f"Booking confirmation {confirmation.reference}"
    message["From"] = EMAIL_FROM
    message["To"] = confirmation.recipient
    message.set_content("\n".join(lines))
    return message


def send_booking_confirmation(confirmation: BookingConfirmation) -> None:
    # runs after the booking is committed: a failure here must not undo it, so it is only logged
    if not SMTP_HOST:
        logger.warning("SMTP_HOST not set: confirmation %s not sent", confirmation.reference)
        return

    try:
        message = compose_email(confirmation)
        try:
            message.add_alternative(render_html(confirmation), subtype="html")
        except Exception:  # the design must never stop the plain-text email from being sent
            logger.exception("HTML version of %s not built: sending plain text only", confirmation.reference)
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=SMTP_TIMEOUT_SECONDS) as smtp:
            if SMTP_USERNAME:  # a real provider; a local Mailpit needs neither TLS nor login
                smtp.starttls(context=ssl.create_default_context())
                smtp.login(SMTP_USERNAME, SMTP_PASSWORD)
            smtp.send_message(message)
    except (smtplib.SMTPException, OSError, ValueError):  # ValueError: malformed address
        logger.exception("Confirmation %s not sent", confirmation.reference)


def send_pwd_reset(recipient: str, reset: ResetData) -> None:
    # runs after the reset row is committed: a failure here is only logged
    # never log the token itself: anyone reading the logs could reset the password
    if not SMTP_HOST:
        logger.warning("SMTP_HOST not set: password reset email not sent")
        return

    # the page reads the token from the url and sends it to the backend in the request body
    link = f"{FRONTEND_URL}/reset-password?{urlencode({'token': reset.token})}"

    try:
        message = EmailMessage()
        message["Subject"] = "Password reset"
        message["From"] = EMAIL_FROM
        message["To"] = recipient
        message.set_content(
            "\n".join([
                "Hello,",
                "",
                "open this link to reset your password:",
                "",
                link,
                "",
                f"It expires at {reset.expire_at:%d/%m/%Y %H:%M} UTC.",
                "If you didn't ask for a reset, ignore this email.",
            ])
        )
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=SMTP_TIMEOUT_SECONDS) as smtp:
            if SMTP_USERNAME:  # a real provider; a local Mailpit needs neither TLS nor login
                smtp.starttls(context=ssl.create_default_context())
                smtp.login(SMTP_USERNAME, SMTP_PASSWORD)
            smtp.send_message(message)
    except (smtplib.SMTPException, OSError, ValueError):  # ValueError: malformed address
        logger.exception("Password reset email not sent")


@dataclass(frozen=True)
class AccountCreated:
    # plain data, so the background task doesn't depend on the request's db session
    recipient: str
    name: str
    surname: str
    username: str
    mobile_number: str
    password: str  # the plain temporary password: only ever goes in the email, never in the logs


def build_account_created(user: User, password: str) -> AccountCreated:
    return AccountCreated(
        recipient=user.email,
        name=user.name,
        surname=user.surname,
        username=user.username,
        mobile_number=user.mobile_number,
        password=password,
    )


def login_url() -> str:
    return f"{FRONTEND_URL}/login"


def compose_account_email(account: AccountCreated) -> EmailMessage:
    lines = [
        f"Hello {account.name} {account.surname},",
        "",
        "an account at the mountain hut has been created for you.",
        "",
        f"Name: {account.name} {account.surname}",
        f"Username: {account.username}",
        f"Email: {account.recipient}",
        f"Mobile number: {account.mobile_number}",
        f"Password: {account.password}",
        "",
        "This password is temporary: please change it as soon as you log in.",
        "",
        f"Log in here: {login_url()}",
    ]

    message = EmailMessage()
    message["Subject"] = "Your Mountain Hut account"
    message["From"] = EMAIL_FROM
    message["To"] = account.recipient
    message.set_content("\n".join(lines))
    return message


def send_account_created(account: AccountCreated) -> None:
    # runs after the user is committed: a failure here must not undo it, so it is only logged
    # never log the password: anyone reading the logs could log in as the hiker
    if not SMTP_HOST:
        logger.warning("SMTP_HOST not set: account email not sent")
        return

    try:
        message = compose_account_email(account)
        try:
            message.add_alternative(render_account_html(account, login_url()), subtype="html")
        except Exception:  # the design must never stop the plain-text email from being sent
            logger.exception("HTML version of the account email not built: sending plain text only")
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=SMTP_TIMEOUT_SECONDS) as smtp:
            if SMTP_USERNAME:  # a real provider; a local Mailpit needs neither TLS nor login
                smtp.starttls(context=ssl.create_default_context())
                smtp.login(SMTP_USERNAME, SMTP_PASSWORD)
            smtp.send_message(message)
    except (smtplib.SMTPException, OSError, ValueError):  # ValueError: malformed address
        logger.exception("Account email not sent")
