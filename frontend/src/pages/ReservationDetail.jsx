import React from "react";
import { useLocation, useNavigate } from "react-router-dom";

function formatDate(dateString) {
  return new Date(`${dateString}T00:00:00`).toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

function formatTime(time) {
  return time ? time.slice(0, 5) : "";
}

export default function ReservationSummaryPage() {
  const { state } = useLocation();
  const navigate = useNavigate();

  // If somebody opens /reservation-summary directly
  if (!state) {
    return (
      <main className="summary-page">
        <div className="summary-card">
          <h1>No reservation found</h1>
          <button onClick={() => navigate("/booking")}>
            Return to booking
          </button>
        </div>
      </main>
    );
  }

  const { booking, date, start, end, partySize } = state;

  const tables = booking?.tables ?? [];

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">MH</span>

          <div>
            <strong>Mountain Hut</strong>
            <span>Table reservations</span>
          </div>
        </div>

        <div className="user-chip">
          <span className="user-avatar">H</span>
          <span>Welcome, Hiker</span>
        </div>
      </header>

      <main className="summary-page">
        <div className="summary-intro">
          <span className="eyebrow">Reservation confirmed</span>

          <h1>You're all set.</h1>

          <p>Your table has been successfully reserved.</p>
        </div>

        <section className="summary-card card">
          <div className="success-icon">✓</div>

          <div className="card-label">
            Reservation successful
          </div>

          <h2>Your reservation</h2>

          <div className="reservation-details">

            <div className="detail-row">
              <span>Table</span>

              <strong>
                {tables.length > 0
                  ? tables.map((table) => table.number).join(", ")
                  : "Assigned table"}
              </strong>
            </div>

            <div className="detail-row">
              <span>Date</span>

              <strong>
                {formatDate(date)}
              </strong>
            </div>

            <div className="detail-row">
              <span>Time slot</span>

              <strong>
                {formatTime(start)} – {formatTime(end)}
              </strong>
            </div>

            <div className="detail-row">
              <span>Party size</span>

              <strong>
                {partySize}{" "}
                {partySize === 1 ? "guest" : "guests"}
              </strong>
            </div>

          </div>

          {booking?.id && (
            <div className="reservation-id">
              Reservation #{booking.id}
            </div>
          )}

          <div className="arrival-note">
            <span className="arrival-icon">⌁</span>

            <div>
              <strong>
                Please arrive 10 minutes early
              </strong>

              <p>
                Arriving before the start of your time slot
                helps us accommodate you and make the best
                use of your reservation.
              </p>
            </div>
          </div>
        </section>

        <button
          className="secondary-button"
          onClick={() => navigate("/booking")}
        >
          ← Return to booking
        </button>
      </main>
    </div>
  );
}