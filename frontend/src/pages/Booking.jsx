import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { createBooking, getAvailability } from "../api";

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
  const time = dateTime.includes("T")
    ? dateTime.split("T")[1]
    : dateTime;

  // Remove timezone information and seconds
  return time.slice(0, 5);
}

export default function Booking() {
    const navigate = useNavigate();
    const today = useMemo(() => {
    const now = new Date();
    now.setHours(0, 0, 0, 0);
    return now;
  }, []);

  const [month, setMonth] = useState(
    () => new Date(today.getFullYear(), today.getMonth(), 1)
  );
  const [availability, setAvailability] = useState({});
  const [selectedDate, setSelectedDate] = useState(null);
  const [selectedSlotIndex, setSelectedSlotIndex] = useState("");
  const [partySize, setPartySize] = useState(1);
  const [booking, setBooking] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const calendarDays = useMemo(() => getCalendarDays(month), [month]);

  const monthRange = useMemo(() => {
    const from = toDateKey(
      new Date(month.getFullYear(), month.getMonth(), 1)
    );
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

  const selectedSlots = selectedDate
    ? availability[selectedDate] ?? []
    : [];

  const selectedSlot =
    selectedSlotIndex === "" ? null : selectedSlots[Number(selectedSlotIndex)];

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

  function selectSlot(event) {
    const value = event.target.value;

    if (value === "") {
      setSelectedSlotIndex("");
      setPartySize(1);
      return;
    }

    const slot = selectedSlots[Number(value)];
    setSelectedSlotIndex(value);
    setPartySize((current) =>
      Math.min(Math.max(current, 1), slot.availableSeats)
    );
  }

  function changePartySize(event) {
    const value = Number(event.target.value);

    if (!selectedSlot) {
      setPartySize(1);
      return;
    }

    setPartySize(
      Math.min(
        Math.max(Number.isFinite(value) ? value : 1, 1),
        selectedSlot.availableSeats
      )
    );
  }

  async function confirmBooking() {
    if (!selectedDate || !selectedSlot || booking) return;
    setBooking(true); setError("");
    try {
      const result = await createBooking({ date: selectedDate, time: selectedSlot.time, partySize });
      navigate("/reservation-detail", { state: {
        booking: result, date: selectedDate, start: selectedSlot.start,
        end: selectedSlot.end, partySize, availableSeats: selectedSlot.availableSeats,
      }});
    } catch (err) {
      setError(err.message || "Could not create reservation.");
    } finally { setBooking(false); }
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">MH</div>
          <div>
            <strong>MH</strong>
            <span>Mountain Huts Service</span>
          </div>
        </div>

        <div className="profile">
          <div className="profile-avatar">H</div>
          <div>
            <span className="profile-label">Signed in as</span>
            <strong>HIKER</strong>
          </div>
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
                <span><i className="legend-dot" /> Available</span>
                <span><i className="legend-dot muted" /> Unavailable</span>
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
                            Math.min(
                              Math.max(current, 1),
                              slot.availableSeats
                            )
                          );
                        }}
                      >
                        <span className="slot-time">
                          {formatSlot(slot)}
                        </span>
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
                <p>
                  Your available time slots will appear here.
                </p>
              </div>
            )}

            <div className="party-section">
              <div className="panel-heading compact">
                <div>
                  <span className="step">03</span>
                  <h2>Party size</h2>
                </div>
              </div>

              <div className="party-control">
                <button
                  type="button"
                  disabled={!selectedSlot || partySize <= 1}
                  onClick={() => setPartySize((value) => Math.max(1, value - 1))}
                  aria-label="Decrease party size"
                >
                  −
                </button>

                <div className="party-number">
                  <strong>{partySize}</strong>
                  <span>{partySize === 1 ? "guest" : "guests"}</span>
                </div>

                <button
                  type="button"
                  disabled={
                    !selectedSlot ||
                    partySize >= (selectedSlot?.availableSeats ?? 1)
                  }
                  onClick={() =>
                    setPartySize((value) =>
                      Math.min(
                        value + 1,
                        selectedSlot?.availableSeats ?? value
                      )
                    )
                  }
                  aria-label="Increase party size"
                >
                  +
                </button>
              </div>

              {selectedSlot && (
                <p className="capacity">
                  Maximum {selectedSlot.availableSeats}{" "}
                  {selectedSlot.availableSeats === 1 ? "guest" : "guests"} for
                  this time slot.
                </p>
              )}
            </div>

            {error && <div className="error">{error}</div>}
          </div>
        </section>

        <div className="booking-footer">
          <div className="summary">
            {selectedDate && selectedSlot ? (
              <>
                <span>Your selection</span>
                <strong>
                  {formatDate(selectedDate)} · {formatSlot(selectedSlot)}
                </strong>
              </>
            ) : (
              <>
                <span>Your selection</span>
                <strong>Choose a date and time to continue</strong>
              </>
            )}
          </div>

          <button
            type="button"
            className="confirm-button"
            disabled={!selectedDate || !selectedSlot}
            onClick={confirmBooking}
          >
            {booking ? "Confirming..." : "Confirm reservation"}
            {!booking && <span>→</span>}
          </button>
        </div>
      </main>
    </div>
  );
}
