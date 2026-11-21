import React, { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import NavBar from "../components/NavBar";
import { cancelBooking, getMyBookings } from "../api";
import "./CancelBooking.css";

function formatTime(dateTime) {
  if (!dateTime) return "";

  // start/end arrive as full ISO datetimes ("2026-11-05T12:00:00"),
  // so take the time portion before trimming to HH:MM
  const time = dateTime.includes("T")
    ? dateTime.split("T")[1]
    : dateTime;

  return time.slice(0, 5);
}


function formatDate(dateTime) {
  if (!dateTime) return "";
  // take the date portion from start time that arrives as full ISO datetimes ("2026-11-05T12:00:00")
  return dateTime.includes("T") ? dateTime.split("T")[0] : dateTime;
}

export default function CancelBooking() {
  const { bookingId } = useParams();
  const navigate = useNavigate();
  const [bookings, setBookings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [pageError, setPageError] = useState("");
  const [showConfirmation, setShowConfirmation] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [cancelError, setCancelError] = useState("");

  useEffect(() => {
    let active = true;

    async function load() {
      setLoading(true);
      setPageError("");
      try {
        const result = await getMyBookings();
        if (active) setBookings(Array.isArray(result) ? result : []);
      } catch (error) {
        if (active) setPageError(error.message || "Could not load this booking.");
      } finally {
        if (active) setLoading(false);
      }
    }

    load();
    return () => {
      active = false;
    };
  }, []);

  const booking = useMemo(
    () => bookings.find((item) => String(item.id) === String(bookingId)),
    [bookings, bookingId]
  );

  const requirements = Array.isArray(booking?.requirements)
    ? booking.requirements.filter(
        (item) => item && typeof item === "object" && item.description
      )
    : [];
  const tables = Array.isArray(booking?.tables) ? booking.tables : [];

  async function handleConfirmCancellation() {
    setCancelling(true);
    setCancelError("");
    try {
      await cancelBooking(bookingId);
      navigate("/my-bookings", {
        replace: true,
        state: { cancellationSuccess: true },
      });
    } catch (error) {
      setCancelError(error.message || "Could not cancel this booking. Please try again.");
      setShowConfirmation(false);
    } finally {
      setCancelling(false);
    }
  }

  return (
    <div className="app-shell">
      <NavBar />
      <main className="cancel-booking-page">
        <div className="cancel-booking-container">
          <Link to="/my-bookings" className="cancel-booking-back">
            ← Back to My Bookings
          </Link>

          <header className="cancel-booking-heading">
            <p className="cancel-booking-eyebrow">MANAGE RESERVATION</p>
            <h1>Cancel booking</h1>
            <p>Review the reservation details before confirming its cancellation.</p>
          </header>

          {loading ? (
            <section className="cancel-booking-message">Loading booking details…</section>
          ) : pageError ? (
            <section className="cancel-booking-message cancel-booking-error" role="alert">
              {pageError}
              <div>
                <Link to="/my-bookings" className="cancel-booking-secondary">
                  Return to My Bookings
                </Link>
              </div>
            </section>
          ) : !booking ? (
            <section className="cancel-booking-message" role="alert">
              <h2>Booking not found</h2>
              <p>This booking may already have been cancelled or may no longer be available.</p>
              <Link to="/my-bookings" className="cancel-booking-secondary">
                Return to My Bookings
              </Link>
            </section>
          ) : (
            <>
              <section className="cancel-booking-card">
                <div className="cancel-booking-card-header">
                  <div>
                    <span className="cancel-booking-label">RESERVATION</span>
                    <h2>Booking #{booking.id}</h2>
                  </div>
                  <span className="cancel-booking-status">Cancellation pending</span>
                </div>

                <div className="cancel-booking-details">
                  <div>
                    <span className="cancel-booking-label">DATE</span>
                    <strong>{formatDate(booking.slot_time_start)}</strong>
                  </div>
                  <div>
                    <span className="cancel-booking-label">START TIME</span>
                    <strong>{formatTime(booking.slot_time_start)}</strong>
                  </div>
                  <div>
                    <span className="cancel-booking-label">END TIME</span>
                    <strong>{formatTime(booking.slot_time_end)}</strong>
                  </div>
                  <div>
                    <span className="cancel-booking-label">PARTY SIZE</span>
                    <strong>{booking.party_size} {booking.party_size === 1 ? "guest" : "guests"}</strong>
                  </div>
                  {tables.length > 0 && (
                    <div className="cancel-booking-full-width">
                      <span className="cancel-booking-label">ASSIGNED TABLES</span>
                      <strong>
                        {tables.map((table) =>
                          `#${table.number}${table.seats ? ` (${table.seats} seats)` : ""}`
                        ).join(", ")}
                      </strong>
                    </div>
                  )}
                </div>

                {requirements.length > 0 && (
                  <section className="cancel-booking-requirements">
                    <span className="cancel-booking-label">SPECIAL REQUIREMENTS</span>
                    {requirements.map((requirement, index) => (
                      <div className="cancel-booking-requirement" key={requirement.id ?? index}>
                        <strong>
                          Requirement {index + 1}
                          {requirement.allergies === true
                            ? " · Allergy flagged"
                            : requirement.allergies === false
                              ? " · Dietary requirement"
                              : ""}
                        </strong>
                        <p>{requirement.description}</p>
                      </div>
                    ))}
                  </section>
                )}
              </section>

              {cancelError && (
                <p className="cancel-booking-inline-error" role="alert">{cancelError}</p>
              )}
              
              <div className="cancel-booking-actions">
                <Link to="/my-bookings" className="cancel-booking-secondary">
                  Keep booking
                </Link>
                <button
                  type="button"
                  className="cancel-booking-danger"
                  onClick={() => setShowConfirmation(true)}
                >
                  Yes, cancel booking
                </button>
              </div>
            </>
          )}
        </div>
      </main>

      {showConfirmation && (
        <div
          className="cancel-booking-modal-backdrop"
          role="presentation"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget && !cancelling) {
              setShowConfirmation(false);
            }
          }}
        >
          <section
            className="cancel-booking-modal"
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="cancel-modal-title"
            aria-describedby="cancel-modal-description"
          >
            <div className="cancel-booking-modal-icon">!</div>
            <h2 id="cancel-modal-title">Confirm cancellation</h2>
            <strong>Are you sure you want to cancel this booking?</strong>
            <p>This action cannot be undone. The seats assigned to this reservation will be released.</p>
            <div className="cancel-booking-modal-actions">
              <button
                type="button"
                className="cancel-booking-secondary"
                disabled={cancelling}
                onClick={() => setShowConfirmation(false)}
              >
                No, keep it
              </button>
              <button
                type="button"
                className="cancel-booking-danger"
                disabled={cancelling}
                onClick={handleConfirmCancellation}
              >
                {cancelling ? "Cancelling…" : "Yes, cancel it"}
              </button>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
