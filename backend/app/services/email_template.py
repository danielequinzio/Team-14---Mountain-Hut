"""HTML version of the booking confirmation email (MH-57).

The plain-text message built by `notification.compose_email` stays the fallback:
`send_booking_confirmation` attaches this HTML as an alternative, so mail clients
that can't show HTML (or have it switched off) still get every detail.

Email clients ignore most modern CSS, so the design uses what they all support:
a table layout, inline styles and no images or web fonts. Every value that comes
from a user (name, requirements) is escaped before it is put into the markup.
"""

from __future__ import annotations

from html import escape
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # notification.py imports this module, so a normal import would be circular
    from app.services.notification import BookingConfirmation

# fixed English names: strftime("%A") would follow the server's locale
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
MONTHS = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)

HUT_NAME = "Mountain Hut"

# colours of the website, so the email feels like the same product
INK = "#17130c"
DARK = "#0d1117"
GOLD = "#e7b96a"
PAPER = "#f4f1ea"
CARD = "#ffffff"
TEXT = "#1d2530"
MUTED = "#6b7684"
LINE = "#e6e1d6"
WARN_BG = "#fff6e5"
WARN_LINE = "#e7b96a"

FONT = "-apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"


def format_long_date(moment) -> str:
    return f"{WEEKDAYS[moment.weekday()]}, {moment.day} {MONTHS[moment.month - 1]} {moment.year}"


def _guests(count: int) -> str:
    return f"{count} guest" if count == 1 else f"{count} guests"


def _text(value: str) -> str:
    """Escapes a user value; line breaks stay line breaks."""
    return escape(value.strip(), quote=True).replace("\r\n", "\n").replace("\n", "<br>")


def _row(label: str, value: str, last: bool = False) -> str:
    border = "" if last else f"border-bottom:1px solid {LINE};"
    return (
        "<tr>"
        f'<td style="padding:14px 0;{border}font-size:13px;color:{MUTED};width:42%;'
        f'font-family:{FONT};">{label}</td>'
        f'<td align="right" style="padding:14px 0;{border}font-size:15px;font-weight:600;'
        f'color:{TEXT};font-family:{FONT};">{value}</td>'
        "</tr>"
    )


def render_html(confirmation: BookingConfirmation) -> str:
    name = escape(confirmation.hiker_name.strip(), quote=True)
    reference = escape(confirmation.reference, quote=True)
    date_text = format_long_date(confirmation.start)
    time_text = f"{confirmation.start:%H:%M} &ndash; {confirmation.end:%H:%M}"

    requirements = ""
    if confirmation.requirements and confirmation.requirements.strip():
        requirements = (
            f'<tr><td style="padding:0 32px 8px;">'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
            f'style="background:{WARN_BG};border:1px solid {WARN_LINE};border-radius:10px;">'
            f'<tr><td style="padding:14px 16px;font-family:{FONT};">'
            f'<div style="font-size:11px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;'
            f'color:#8a5a00;">Party requirements</div>'
            f'<div style="margin-top:6px;font-size:14px;line-height:1.6;color:{TEXT};">'
            f"{_text(confirmation.requirements)}</div>"
            f"</td></tr></table></td></tr>"
        )

    rows = "".join(
        [
            _row("Booking reference", f'<span style="font-family:Consolas,Menlo,monospace;'
                 f"letter-spacing:0.04em;background:{PAPER};padding:4px 8px;border-radius:6px;\">{reference}</span>"),
            _row("Date", date_text),
            _row("Time slot", time_text),
            _row("Party size", _guests(confirmation.party_size), last=True),
        ]
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<title>Booking confirmation {reference}</title>
</head>
<body style="margin:0;padding:0;background:{PAPER};">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;">
Your table is booked: {date_text}, {confirmation.start:%H:%M} &ndash; {confirmation.end:%H:%M}. Reference {reference}.
</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:{PAPER};">
<tr><td align="center" style="padding:28px 12px;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
         style="max-width:600px;background:{CARD};border-radius:16px;overflow:hidden;border:1px solid {LINE};">
    <tr><td style="background:{DARK};padding:22px 32px;">
      <table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>
        <td style="width:34px;height:34px;background:{GOLD};border-radius:9px;text-align:center;
                   color:{INK};font-size:14px;font-family:{FONT};">&#9650;</td>
        <td style="padding-left:12px;font-family:{FONT};">
          <div style="color:#ffffff;font-size:14px;font-weight:700;letter-spacing:0.06em;">{HUT_NAME}</div>
          <div style="color:#8593a3;font-size:10px;letter-spacing:0.1em;text-transform:uppercase;">Table reservations</div>
        </td>
      </tr></table>
    </td></tr>
    <tr><td style="padding:32px 32px 8px;font-family:{FONT};">
      <div style="font-size:11px;font-weight:700;letter-spacing:0.16em;text-transform:uppercase;color:#b47d1c;">
        Booking confirmed</div>
      <h1 style="margin:10px 0 0;font-size:26px;line-height:1.2;color:{TEXT};letter-spacing:-0.02em;">
        You&rsquo;re all set, {name}.</h1>
      <p style="margin:14px 0 0;font-size:15px;line-height:1.7;color:{MUTED};">
        Your table at the mountain hut has been reserved. Here are the details of your booking.</p>
    </td></tr>
    <tr><td style="padding:12px 32px 20px;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
             style="border-top:1px solid {LINE};">{rows}</table>
    </td></tr>
    {requirements}
    <tr><td style="padding:12px 32px 32px;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
             style="background:{PAPER};border-radius:10px;">
        <tr><td style="padding:14px 16px;font-family:{FONT};">
          <div style="font-size:14px;font-weight:700;color:{TEXT};">Please arrive 10 minutes early</div>
          <div style="margin-top:4px;font-size:13px;line-height:1.6;color:{MUTED};">
            Arriving before the start of your time slot helps us accommodate you and make the best use of your reservation.</div>
        </td></tr>
      </table>
    </td></tr>
    <tr><td style="padding:18px 32px;border-top:1px solid {LINE};font-family:{FONT};
                   font-size:12px;line-height:1.6;color:{MUTED};">
      This is an automatic confirmation from {HUT_NAME}. Please keep your booking reference
      <strong style="color:{TEXT};white-space:nowrap;">{reference}</strong> with you.
    </td></tr>
  </table>
</td></tr>
</table>
</body>
</html>
"""
