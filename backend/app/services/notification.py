import logging
import smtplib
import ssl
from dataclasses import dataclass
from datetime import datetime
from email.message import EmailMessage

from app.config import (
    EMAIL_FROM,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_USERNAME,
)
from app.models import Booking, Slot, User
from app.services.booking import slot_end, slot_start
from app.services.email_template import render_html

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