import React from "react";
import { useLocation, useNavigate } from "react-router-dom";
import NavBar from "../components/NavBar";

function formatDate(dateString) {
  return new Date(`${dateString}T00:00:00`).toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

function formatTime(dateTime) {
  if (!dateTime) return "";

  // start/end arrive as full ISO datetimes ("2026-11-05T12:00:00"),
  // so take the time portion before trimming to HH:MM
  const time = dateTime.includes("T")
    ? dateTime.split("T")[1]
    : dateTime;

  return time.slice(0, 5);
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
          <button onClick={() => navigate("/availability")}>
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
      <NavBar />

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

        <div style={{ display: "flex", gap: 12, flexWrap: "wrap", justifyContent: "center" }}>
          <button
            className="secondary-button"
            onClick={() => navigate("/availability")}
          >
            ← Return to booking
          </button>
          <button
            className="secondary-button"
            onClick={() => navigate("/")}
          >
            Back to home
          </button>
        </div>
      </main>
    </div>
  );
}