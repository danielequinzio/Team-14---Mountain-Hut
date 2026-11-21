import React, { useEffect, useMemo, useRef, useState } from "react";
import { Link, Navigate, useLocation } from "react-router-dom";
import { checkAvailability, getAvailability } from "../api";
import { useAuth } from "../auth/AuthContext";
import { isHiker, isStaff } from "../auth/roles";
import { hut } from "../content/hutInfo";
import "./landing.css"; // header and the .lp-btn styles
import "./Availability.css";

// MH-04: anyone (no login) checks if a party fits at a given date and time.
// The page is a small search form. The answer comes from GET /availability and
// no other slots are suggested: the visitor just checks another date or time.

function toDateKey(date) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function formatDate(dateKey) {
  return new Date(`${dateKey}T00:00:00`).toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
  });
}

function formatShortDate(dateKey) {
  return new Date(`${dateKey}T00:00:00`).toLocaleDateString("en-US", {
    weekday: "short",
    day: "numeric",
    month: "short",
  });
}

function formatTime(dateTime) {
  if (!dateTime) return "";
  const time = dateTime.includes("T") ? dateTime.split("T")[1] : dateTime;
  return time.slice(0, 5);
}

function formatSlot(slot) {
  return `${formatTime(slot.start)} – ${formatTime(slot.end)}`;
}

function guestsLabel(count) {
  return `${count} ${count === 1 ? "guest" : "guests"}`;
}

// The backend messages, in plain words.
function friendlyError(message) {
  if (/closed less than two hours/i.test(message)) {
    return "Bookings for this slot are already closed: they close two hours before it starts.";
  }
  if (/slot not available/i.test(message)) {
    return "There is no time slot at that date and time.";
  }
  return message || "Could not check availability. Please try again.";
}

export default function Availability() {
  const location = useLocation();
  const { user, loading: authLoading, logout } = useAuth();

  // Coming back from login or register, the page opens with the date, time and
  // party size the visitor had chosen (?date=2026-11-25&time=19:00:00&party=4)
  // and checks again.
  const wanted = useMemo(() => {
    const query = new URLSearchParams(location.search);
    const date = query.get("date");
    const time = query.get("time");
    const party = query.get("party");
    return {
      date: /^\d{4}-\d{2}-\d{2}$/.test(date ?? "") ? date : null,
      time: /^\d{2}:\d{2}:\d{2}$/.test(time ?? "") ? time : null,
      party: /^[1-9]\d*$/.test(party ?? "") ? Number(party) : null,
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
  const todayKey = toDateKey(today);

  const [slotsByDate, setSlotsByDate] = useState({});
  const [slotsLoading, setSlotsLoading] = useState(true);
  const [slotsError, setSlotsError] = useState("");

  const [date, setDate] = useState(wanted.date ?? "");
  const [time, setTime] = useState(wanted.time ?? "");
  const [guests, setGuests] = useState(wanted.party ? String(wanted.party) : "1");

  const [checking, setChecking] = useState(false);
  const [formError, setFormError] = useState("");
  // what the last check was for, and what the backend answered
  const [result, setResult] = useState(null); // { date, time, slot, guests, available, tables }
  const [checkError, setCheckError] = useState("");

  // the open time slots by date: they tell which times can be chosen
  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const all = await getAvailability();
        if (cancelled) return;
        setSlotsByDate(all && typeof all === "object" && !Array.isArray(all) ? all : {});
      } catch (err) {
        if (!cancelled) setSlotsError(err.message || "Could not load the time slots.");
      } finally {
        if (!cancelled) setSlotsLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  const openDates = useMemo(
    () =>
      Object.keys(slotsByDate)
        .filter((key) => key >= todayKey && slotsByDate[key].length > 0)
        .sort(),
    [slotsByDate, todayKey]
  );

  const slotsOfDate = useMemo(
    () =>
      [...(slotsByDate[date] ?? [])].sort((a, b) =>
        String(a.start).localeCompare(String(b.start))
      ),
    [slotsByDate, date]
  );

  const guestCount = Number(guests);
  const guestsValid = /^\d+$/.test(guests.trim()) && guestCount >= 1;

  // after the slots load, run the check the visitor had asked for before login
  useEffect(() => {
    if (restored.current || slotsLoading) return;
    restored.current = true;
    if (wanted.date && wanted.time && wanted.party && wanted.date >= todayKey) {
      runCheck(wanted.date, wanted.time, wanted.party);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slotsLoading]);

  // a changed field makes the old answer stale
  function clearAnswer() {
    setResult(null);
    setCheckError("");
    setFormError("");
  }

  function changeDate(value) {
    setDate(value);
    setTime("");
    clearAnswer();
  }

  function changeTime(value) {
    setTime(value);
    clearAnswer();
  }

  function changeGuests(value) {
    setGuests(value);
    clearAnswer();
  }

  async function runCheck(checkDate, checkTime, checkGuests) {
    setChecking(true);
    setResult(null);
    setCheckError("");
    try {
      const answer = await checkAvailability({
        date: checkDate,
        time: checkTime,
        partySize: checkGuests,
      });
      const slot = (slotsByDate[checkDate] ?? []).find((item) => item.time === checkTime);
      setResult({
        date: checkDate,
        time: checkTime,
        slot: slot ?? null,
        guests: checkGuests,
        available: Boolean(answer.available),
        tables: answer.tables ?? [],
      });
    } catch (err) {
      setCheckError(friendlyError(err.message));
    } finally {
      setChecking(false);
    }
  }

  function submit(event) {
    event.preventDefault();
    if (checking) return;
    setFormError("");
    if (!date) return setFormError("Choose a date.");
    if (date < todayKey) return setFormError("Choose today or a later date.");
    if (!time) return setFormError("Choose a time.");
    if (!guestsValid) return setFormError("Enter how many guests, at least 1.");
    runCheck(date, time, guestCount);
  }

  // login and register bring the visitor back here with the same search
  const returnPath =
    date && time && guestsValid
      ? `/availability?date=${encodeURIComponent(date)}&time=${encodeURIComponent(time)}&party=${guestCount}`
      : "/availability";

  const split = result?.tables.map((table) => table.seats).join(" + ");

  // A logged-in hiker books directly: the Booking page opens with the date, time
  // and guests already chosen when they come with them (?date&time&party).
  if (authLoading) return <div className="lp" />;
  if (isHiker(user)) return <Navigate to={`/booking${location.search}`} replace />;

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

        <div className="lp-nav-actions">
          {!authLoading && user && (
            <>
              <span className="lp-user">
                <strong>{user.username}</strong>
                <small>{user.role}</small>
              </span>
              <button type="button" className="lp-btn lp-btn--ghost" onClick={logout}>
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

      <main className="av-page">
        <header className="av-head">
          <span className="av-eyebrow">Check availability</span>
          <h1>Is there a table for you?</h1>
          <p>Pick a date, a time and the number of guests. No login needed.</p>
        </header>

        <form className="av-search" onSubmit={submit} noValidate>
          <label className="av-field">
            <span>Date</span>
            <input
              type="date"
              value={date}
              min={todayKey}
              onChange={(event) => changeDate(event.target.value)}
            />
          </label>

          <label className="av-field">
            <span>Time</span>
            <select
              value={time}
              onChange={(event) => changeTime(event.target.value)}
              disabled={!date || slotsOfDate.length === 0}
            >
              <option value="">
                {!date ? "Pick a date first" : slotsOfDate.length === 0 ? "No slots" : "Choose a time"}
              </option>
              {slotsOfDate.map((slot) => (
                <option key={slot.id ?? slot.time} value={slot.time}>
                  {formatSlot(slot)}
                </option>
              ))}
            </select>
          </label>

          <div className="av-field">
            <span id="av-guests-label">Guests</span>
            <div className="av-stepper" role="group" aria-labelledby="av-guests-label">
              <button
                type="button"
                aria-label="One guest less"
                disabled={!guestsValid || guestCount <= 1}
                onClick={() => changeGuests(String(Math.max(1, guestCount - 1)))}
              >
                −
              </button>
              <input
                inputMode="numeric"
                value={guests}
                onChange={(event) => changeGuests(event.target.value)}
                aria-label="Number of guests"
              />
              <button
                type="button"
                aria-label="One guest more"
                disabled={guestsValid && guestCount >= 99}
                onClick={() => changeGuests(String((guestsValid ? guestCount : 0) + 1))}
              >
                +
              </button>
            </div>
          </div>

          <button type="submit" className="av-check" disabled={checking}>
            {checking ? "Checking…" : "Check availability"}
          </button>
        </form>

        {date && !slotsLoading && slotsOfDate.length === 0 && !slotsError && (
          <p className="av-note">There are no time slots on {formatDate(date)}. Try another date.</p>
        )}
        {formError && (
          <p className="av-error" role="alert">
            {formError}
          </p>
        )}
        {slotsError && (
          <p className="av-error" role="alert">
            {slotsError}
          </p>
        )}

        {openDates.length > 0 && (
          <div className="av-days">
            <span>Open days</span>
            <div>
              {openDates.slice(0, 10).map((key) => (
                <button
                  type="button"
                  key={key}
                  className={key === date ? "selected" : ""}
                  onClick={() => changeDate(key)}
                >
                  {formatShortDate(key)}
                </button>
              ))}
            </div>
          </div>
        )}

        <section className="av-answer" aria-live="polite">
          {checkError && (
            <div className="av-card av-card--error" role="alert">
              <strong>We could not check this</strong>
              <p>{checkError}</p>
            </div>
          )}

          {result && result.available && (
            <div className="av-card av-card--yes">
              <span className="av-badge">Available</span>
              <h2>There is room for {guestsLabel(result.guests)}</h2>
              <p className="av-when">
                {formatDate(result.date)}
                {result.slot ? ` · ${formatSlot(result.slot)}` : ` · ${formatTime(result.time)}`}
              </p>

              <div className="av-seating">
                <span>
                  {result.tables.length === 1 ? "Seated at one table" : `Seated at ${result.tables.length} tables`}
                </span>
                <strong>{split} seats</strong>
                <ul>
                  {result.tables.map((table) => (
                    <li key={table.number}>
                      Table {table.number}
                      <b>{table.seats} {table.seats === 1 ? "seat" : "seats"}</b>
                    </li>
                  ))}
                </ul>
              </div>

              {authLoading ? null : !user ? (
                <div className="av-next">
                  <p>Log in or register to book it.</p>
                  <div>
                    <Link to="/login" state={{ from: returnPath }} className="lp-btn lp-btn--ghost">
                      Log in
                    </Link>
                    <Link to="/register" state={{ from: returnPath }} className="lp-btn lp-btn--primary">
                      Register
                    </Link>
                  </div>
                </div>
              ) : (
                isStaff(user) && (
                  <div className="av-next">
                    <p>To book it for a hiker, use “Reserve for hiker”.</p>
                    <div>
                      <Link to="/staff/reserve" className="lp-btn lp-btn--primary">
                        Reserve for hiker
                      </Link>
                    </div>
                  </div>
                )
              )}
            </div>
          )}

          {result && !result.available && (
            <div className="av-card av-card--no">
              <span className="av-badge av-badge--no">Not available</span>
              <h2>No room for {guestsLabel(result.guests)} at this time</h2>
              <p className="av-when">
                {formatDate(result.date)}
                {result.slot ? ` · ${formatSlot(result.slot)}` : ` · ${formatTime(result.time)}`}
              </p>
              <p className="av-hint">Check a different time or date above.</p>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
