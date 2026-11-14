import React, { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import NavBar from "../components/NavBar";
import { getMyBookings } from "../api";
import "./MyBookings.css";

function formatTime(value) {
  if (!value) return null;
  return String(value).slice(0, 5);
}

function hasValue(value) {
  return value !== undefined && value !== null && value !== "";
}

function formatRequirements(requirement) {
  if (!requirement || typeof requirement !== "object") return null;

  const parts = [];
  if (Array.isArray(requirement.allergies) && requirement.allergies.length > 0) {
    parts.push(`Allergies: ${requirement.allergies.join(", ")}`);
  } else if (hasValue(requirement.allergies) && !Array.isArray(requirement.allergies)) {
    parts.push(`Allergies: ${requirement.allergies}`);
  }
  if (hasValue(requirement.description)) {
    parts.push(requirement.description);
  }
  return parts.length ? parts.join(" — ") : null;
}

export default function MyBookings() {
  const [bookings, setBookings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [pageError, setPageError] = useState("");

  const loadBookings = useCallback(async () => {
    setLoading(true);
    setPageError("");
    try {
      const result = await getMyBookings();
      setBookings(Array.isArray(result) ? result : []);
    } catch (error) {
      if (/401|403|not authenticated|unauthorized/i.test(error.message)) {
        setPageError("Please log in with your hiker account to see your bookings.");
      } else {
        setPageError(error.message || "Could not load your bookings.");
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadBookings();
  }, [loadBookings]);

  return (
    <div className="app-shell">
      <NavBar />

      <main className="my-bookings-page">
        <div className="my-bookings-container">
          <div className="my-bookings-heading">
            <p className="my-bookings-eyebrow">YOUR ACCOUNT</p>
            <h1>My Bookings</h1>
            <p>View and manage your table reservations at Rifugio Alpe Serena.</p>
          </div>

          {pageError && (
            <section className="my-bookings-message" role="alert">
              <p>{pageError}</p>
              {/Please log in/i.test(pageError) ? (
                <Link className="my-bookings-primary-link" to="/login">Log in</Link>
              ) : (
                <button className="my-bookings-secondary-button" onClick={loadBookings}>
                  Try again
                </button>
              )}
            </section>
          )}

          {loading ? (
            <section className="my-bookings-message">Loading your bookings…</section>
          ) : !pageError && bookings.length === 0 ? (
            <section className="my-bookings-empty">
              <div className="my-bookings-empty-icon">▣</div>
              <h2>No bookings yet</h2>
              <p>Your table reservations will appear here once you book a table.</p>
              <Link className="my-bookings-primary-link" to="/booking">
                Book a table
              </Link>
            </section>
          ) : !pageError ? (
            <section className="my-bookings-list">
              <div className="my-bookings-list-heading">
                <h2>Your reservations</h2>
                <span>{bookings.length} {bookings.length === 1 ? "booking" : "bookings"}</span>
              </div>

              {bookings.map((booking, index) => {
                const startTime = formatTime(booking.slot_time_start);
                const endTime = formatTime(booking.slot_time_end);
                const requirements = Array.isArray(booking.requirements)
                  ? booking.requirements.map(formatRequirements).filter(Boolean)
                  : [];
                const tables = Array.isArray(booking.tables) ? booking.tables : [];

                return (
                  <article className="my-booking-card" key={booking.id ?? index}>
                    <div className="my-booking-main">
                      <div className="my-booking-date">
                        <span className="my-booking-date-icon">▣</span>
                        <div>
                          <span className="my-booking-label">RESERVATION</span>
                          <h3>{hasValue(booking.id) ? `Booking #${booking.id}` : `Booking ${index + 1}`}</h3>
                        </div>
                      </div>

                      <div className="my-booking-details">
                        {startTime && (
                          <div>
                            <span className="my-booking-label">START TIME</span>
                            <strong>{startTime}</strong>
                          </div>
                        )}
                        {endTime && (
                          <div>
                            <span className="my-booking-label">END TIME</span>
                            <strong>{endTime}</strong>
                          </div>
                        )}
                        {hasValue(booking.party_size) && (
                          <div>
                            <span className="my-booking-label">PARTY SIZE</span>
                            <strong>{booking.party_size} {booking.party_size === 1 ? "guest" : "guests"}</strong>
                          </div>
                        )}
                        {tables.length > 0 && (
                          <div>
                            <span className="my-booking-label">ASSIGNED TABLES</span>
                            <strong>
                              {tables.map((table) => `#${table.number}${hasValue(table.seats) ? ` (${table.seats} seats)` : ""}`).join(", ")}
                            </strong>
                          </div>
                        )}
                      </div>

                      {requirements.length > 0 && (
                        <div className="my-booking-requirements">
                          <span className="my-booking-label">SPECIAL REQUIREMENTS</span>
                          {requirements.map((requirement, requirementIndex) => (
                            <p key={requirementIndex}>{requirement}</p>
                          ))}
                        </div>
                      )}
                    </div>

                    <div className="my-booking-actions">
                      <button type="button" className="my-bookings-secondary-button">
                        Edit booking
                      </button>
                      <button type="button" className="my-bookings-danger-button">
                        Cancel booking
                      </button>
                    </div>
                  </article>
                );
              })}
            </section>
          ) : null}
        </div>
      </main>
    </div>
  );
}
