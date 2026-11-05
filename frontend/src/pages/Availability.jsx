import React, { useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { createBooking, getAvailability } from "../api";
import { useAuth } from "../auth/AuthContext";
import { hut } from "../content/hutInfo";
import "./landing.css"; // provides the .lp-btn styles used by the auth buttons

const WEEKDAYS = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"];

function toDateKey(date) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function getCalendarDays(monthDate) {
  const first = new Date(monthDate.getFullYear(), monthDate.getMonth(), 1);
  const mondayIndex = (first.getDay() + 6) % 7;

  const start = new Date(first);
  start.setDate(first.getDate() - mondayIndex);

  return Array.from({ length: 42 }, (_, index) => {
    const day = new Date(start);
    day.setDate(start.getDate() + index);
    return day;
  });
}

function monthLabel(date) {
  return date.toLocaleDateString("en-US", {
    month: "long",
    year: "numeric",
  });
}

function formatDate(dateKey) {
  return new Date(`${dateKey}T00:00:00`).toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
  });
}

function formatSlot(slot) {
  return `${formatTime(slot.start)} – ${formatTime(slot.end)}`;
}

function formatTime(dateTime) {
  if (!dateTime) return "";

  // Extract the time portion from an ISO date
  const time = dateTime.includes("T") ? dateTime.split("T")[1] : dateTime;

  // Remove timezone information and seconds
  return time.slice(0, 5);
}

export default function Availability() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, loading: authLoading, logout } = useAuth();

  // A visitor who logs in or registers from this page comes back here with the
  // date and time they had chosen in the address (?date=2026-11-06&time=12:00:00).
  const wanted = useMemo(() => {
    const query = new URLSearchParams(location.search);
    const date = query.get("date");
    const time = query.get("time");
    return {
      date: /^\d{4}-\d{2}-\d{2}$/.test(date ?? "") ? date : null,
      time: /^\d{2}:\d{2}:\d{2}$/.test(time ?? "") ? time : null,
    };
    // read once, when the page opens
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const restored = useRef(false);

  const today = useMemo(() => {
    const now = new Date();
    now.setHours(0, 0, 0, 0);
    return now;
  }, []);

  const [month, setMonth] = useState(() => {
    if (wanted.date) {
      const [year, monthNumber] = wanted.date.split("-").map(Number);
      return new Date(year, monthNumber - 1, 1);
    }
    return new Date(today.getFullYear(), today.getMonth(), 1);
  });
  const [availability, setAvailability] = useState({});
  const [selectedDate, setSelectedDate] = useState(null);
  const [selectedSlotIndex, setSelectedSlotIndex] = useState("");
  const [partySize, setPartySize] = useState(1);
  const [booking, setBooking] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const calendarDays = useMemo(() => getCalendarDays(month), [month]);

  const monthRange = useMemo(() => {
    const from = toDateKey(new Date(month.getFullYear(), month.getMonth(), 1));
    const to = toDateKey(
      new Date(month.getFullYear(), month.getMonth() + 1, 0)
    );
    return { from, to };
  }, [month]);

  useEffect(() => {
    let cancelled = false;

    async function loadMonth() {
      setLoading(true);
      setError("");

      try {
        const dates = await getAvailability(monthRange.from, monthRange.to);
        if (cancelled) return;

        let mapped;

        if (Array.isArray(dates)) {
          mapped = Object.fromEntries(
            dates.map((item) => [item.date, item.slots ?? []])
          );
        } else if (dates && typeof dates === "object") {
          mapped = Object.fromEntries(
            Object.entries(dates).map(([date, slots]) => [
              date,
              Array.isArray(slots) ? slots : [],
            ])
          );
        } else {
          throw new Error("Availability response has an unexpected format.");
        }

        setAvailability(mapped);

        // first load after coming back from login: select the remembered date and slot
        if (!restored.current && wanted.date) {
          restored.current = true;
          const slots = mapped[wanted.date] ?? [];
          const notPast = new Date(`${wanted.date}T00:00:00`) >= today;
          if (notPast && slots.length > 0) {
            setSelectedDate(wanted.date);
            const index = wanted.time
              ? slots.findIndex((slot) => slot.time === wanted.time)
              : -1;
            if (index >= 0) setSelectedSlotIndex(String(index));
          }
        }

        if (
          selectedDate &&
          !Object.prototype.hasOwnProperty.call(mapped, selectedDate)
        ) {
          setSelectedDate(null);
          setSelectedSlotIndex("");
          setPartySize(1);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.message || "Could not load availability.");
          setAvailability({});
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadMonth();

    return () => {
      cancelled = true;
    };
  }, [monthRange.from, monthRange.to]);

  const selectedSlots = selectedDate ? availability[selectedDate] ?? [] : [];

  const selectedSlot =
    selectedSlotIndex === "" ? null : selectedSlots[Number(selectedSlotIndex)];

  // where login and register send the visitor back to, with the current choice
  const returnPath = selectedDate
    ? `/availability?date=${encodeURIComponent(selectedDate)}${
        selectedSlot?.time ? `&time=${encodeURIComponent(selectedSlot.time)}` : ""
      }`
    : "/availability";

  function isPast(day) {
    return day < today;
  }

  function isCurrentMonth(day) {
    return day.getMonth() === month.getMonth();
  }

  function hasAvailability(day) {
    const key = toDateKey(day);
    return (
      Object.prototype.hasOwnProperty.call(availability, key) &&
      availability[key].length > 0
    );
  }

  function selectDate(day) {
    const key = toDateKey(day);

    if (isPast(day) || !isCurrentMonth(day) || !hasAvailability(day)) {
      return;
    }

    setSelectedDate(key);
    setSelectedSlotIndex("");
    setPartySize(1);
  }

  function changeMonth(offset) {
    setMonth(
      (current) =>
        new Date(current.getFullYear(), current.getMonth() + offset, 1)
    );
    setSelectedDate(null);
    setSelectedSlotIndex("");
    setPartySize(1);
  }

  async function confirmBooking() {
    if (!user || !selectedDate || !selectedSlot || booking) return;
    setBooking(true);
    setError("");
    try {
      const result = await createBooking({
        date: selectedDate,
        time: selectedSlot.time, // hut-local HH:MM:SS, which is what POST /booking expects
        partySize,
      });
      navigate("/reservation-detail", {
        state: {
          booking: result,
          date: selectedDate,
          start: selectedSlot.start,
          end: selectedSlot.end,
          partySize,
          availableSeats: selectedSlot.availableSeats,
        },
      });
    } catch (err) {
      setError(err.message || "Could not create reservation.");
    } finally {
      setBooking(false);
    }
  }

  return (
    <div className="lp">
      <header className="lp-nav">
        <Link to="/" className="lp-brand" aria-label={`${hut.name} home`}>
            <span className="lp-brand-mark">▲</span>
            <span>
            <strong>{hut.name}</strong>
            <small>Mountain hut</small>
            </span>
        </Link>

        {/* Top right: auth buttons from Landing (replaces "Signed in as HIKER") */}
        <div className="lp-nav-actions">
          {!authLoading && user && (
            <>
              <span className="lp-user">
                <strong>{user.username}</strong>
                <small>{user.role}</small>
              </span>
              <button
                type="button"
                className="lp-btn lp-btn--ghost"
                onClick={logout}
              >
                Log out
              </button>
            </>
          )}
          {!authLoading && !user && (
            <>
              <Link to="/login" state={{ from: returnPath }} className="lp-btn lp-btn--ghost">
                Log in
              </Link>
              <Link to="/register" state={{ from: returnPath }} className="lp-btn lp-btn--primary">
                Register
              </Link>
            </>
          )}
        </div>
      </header>

      <main className="main-content">
        <div className="intro">
          <div>
            <span className="eyebrow">TABLE RESERVATION</span>
            <h1>Reserve your table</h1>
            <p>
              Choose a date, select an available time, and tell us how many
              guests will be joining you.
            </p>
          </div>
        </div>

        <section className="booking-layout">
          <div className="panel calendar-panel">
            <div className="panel-heading">
              <div>
                <span className="step">01</span>
                <h2>Choose a date</h2>
              </div>
              <span className="hint">Available dates are highlighted</span>
            </div>

            <div className="calendar">
              <div className="calendar-header">
                <button
                  type="button"
                  className="month-button"
                  onClick={() => changeMonth(-1)}
                  aria-label="Previous month"
                >
                  ‹
                </button>

                <div className="month-title">{monthLabel(month)}</div>

                <button
                  type="button"
                  className="month-button"
                  onClick={() => changeMonth(1)}
                  aria-label="Next month"
                >
                  ›
                </button>
              </div>

              <div className="weekdays">
                {WEEKDAYS.map((day) => (
                  <span key={day}>{day}</span>
                ))}
              </div>

              <div className="calendar-grid">
                {calendarDays.map((day) => {
                  const key = toDateKey(day);
                  const currentMonth = isCurrentMonth(day);
                  const available =
                    currentMonth && !isPast(day) && hasAvailability(day);
                  const selected = selectedDate === key;

                  return (
                    <button
                      type="button"
                      key={key}
                      className={[
                        "day",
                        !currentMonth ? "outside-month" : "",
                        available ? "available" : "unavailable",
                        selected ? "selected" : "",
                      ].join(" ")}
                      disabled={!available || loading}
                      onClick={() => selectDate(day)}
                    >
                      <span>{day.getDate()}</span>
                      {available && !selected && <i />}
                    </button>
                  );
                })}
              </div>

              <div className="calendar-legend">
                <span>
                  <i className="legend-dot" /> Available
                </span>
                <span>
                  <i className="legend-dot muted" /> Unavailable
                </span>
              </div>
            </div>
          </div>

          <div className="panel details-panel">
            <div className="panel-heading">
              <div>
                <span className="step">02</span>
                <h2>Choose a time</h2>
              </div>
            </div>

            {selectedDate ? (
              <>
                <div className="selected-date">
                  <span className="calendar-icon">▣</span>
                  <div>
                    <span>Selected date</span>
                    <strong>{formatDate(selectedDate)}</strong>
                  </div>
                </div>

                <div className="slot-list">
                  {selectedSlots.map((slot, index) => {
                    const selected = String(index) === selectedSlotIndex;

                    return (
                      <button
                        type="button"
                        key={`${slot.start}-${slot.end}-${index}`}
                        className={`slot-card ${selected ? "selected" : ""}`}
                        onClick={() => {
                          setSelectedSlotIndex(String(index));
                          setPartySize((current) =>
                            Math.min(Math.max(current, 1), slot.availableSeats)
                          );
                        }}
                      >
                        <span className="slot-time">{formatSlot(slot)}</span>
                        <span className="slot-seats">
                          {slot.availableSeats}{" "}
                          {slot.availableSeats === 1 ? "seat" : "seats"} left
                        </span>
                      </button>
                    );
                  })}
                </div>
              </>
            ) : (
              <div className="empty-state">
                <div className="empty-icon">01</div>
                <strong>Select an available date</strong>
                <p>Your available time slots will appear here.</p>
              </div>
            )}

            {error && <div className="error">{error}</div>}
          </div>
        </section>

        <div className="booking-footer">
          <div className="summary">
            <span>Your selection</span>
            {!authLoading && !user && (
              <strong>Please Log in or register to make a reservation.</strong>
            )}
            <strong>
              {selectedDate && selectedSlot
                ? `${formatDate(selectedDate)} · ${formatSlot(selectedSlot)}`
                : "Selected date and time will appear here."}
            </strong>
          </div>

          {/* Bottom right: auth buttons from Landing take the place of the
              confirm button until the visitor is signed in. */}
          {!authLoading && !user ? (
            <div className="lp-nav-actions">
              <Link to="/login" state={{ from: returnPath }} className="lp-btn lp-btn--ghost">
                Log in
              </Link>
              <Link to="/register" state={{ from: returnPath }} className="lp-btn lp-btn--primary">
                Register
              </Link>
            </div>
          ) : (
            <button
              type="button"
              className="confirm-button"
              disabled={!selectedDate || !selectedSlot || booking}
              onClick={confirmBooking}
            >
              {booking ? "Confirming..." : "Confirm reservation"}
              {!booking && <span>→</span>}
            </button>
          )}
        </div>
      </main>
    </div>
  );
}
