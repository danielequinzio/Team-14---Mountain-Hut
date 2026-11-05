import React, { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import NavBar from "../components/NavBar";
import { getSlot, listSlots, listTables } from "../staff/slotsApi";
import {
  addDays,
  formatLongDay,
  formatTimeRange,
  hutDay,
  isValidDay,
  occupancyStatus,
  percentBooked,
  summariseSlot,
  todayInHut,
} from "../staff/slotUtils";
import "../auth/auth.css";
import "../staff/staff.css";

// Staff page (employee and warden): the slots of one day and how many seats
// each one has. It is read-only: slots and tables are created elsewhere.
export default function StaffSlots() {
  const [day, setDay] = useState(null); // "YYYY-MM-DD", null until the first load
  const [slots, setSlots] = useState([]);
  const [status, setStatus] = useState("loading"); // loading | ready | error
  const [error, setError] = useState(null);
  const tablesRef = useRef(null); // Map(table id -> { number, location })
  const requestId = useRef(0); // ignores answers that arrive after a newer request

  useEffect(() => {
    document.title = "Slots · Mountain Hut";
  }, []);

  // First visit: open on the first upcoming day that has slots (today if none).
  useEffect(() => {
    let cancelled = false;
    const today = todayInHut();
    listSlots({ fromDate: today })
      .then((upcoming) => {
        if (cancelled) return;
        const days = upcoming.map((slot) => hutDay(slot.start_time)).sort();
        setDay(days[0] ?? today);
      })
      .catch(() => {
        // the day load below shows the real error with a retry button
        if (!cancelled) setDay(today);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const loadDay = useCallback(async (targetDay) => {
    const id = ++requestId.current;
    setStatus("loading");
    setError(null);

    try {
      const [daySlots, tableList] = await Promise.all([
        listSlots({ date: targetDay }),
        tablesRef.current ? Promise.resolve(null) : listTables().catch(() => []),
      ]);

      if (tableList) {
        tablesRef.current = new Map(tableList.map((table) => [table.id, table]));
      }

      const details = await Promise.allSettled(daySlots.map((slot) => getSlot(slot.id)));

      if (id !== requestId.current) return; // a newer request replaced this one

      setSlots(
        details.map((result, index) =>
          result.status === "fulfilled"
            ? summariseSlot(result.value, tablesRef.current)
            : { id: daySlots[index].id, failed: true, start: daySlots[index].start_time, end: daySlots[index].end_time }
        )
      );
      setStatus("ready");
    } catch (caught) {
      if (id !== requestId.current) return;
      setError(caught);
      setStatus("error");
    }
  }, []);

  useEffect(() => {
    if (day) loadDay(day);
  }, [day, loadDay]);

  function changeDay(next) {
    if (next && isValidDay(next)) setDay(next);
  }

  const loaded = slots.filter((slot) => !slot.failed);
  const totals = loaded.reduce(
    (sum, slot) => ({
      booked: sum.booked + slot.booked,
      free: sum.free + slot.free,
      capacity: sum.capacity + slot.capacity,
    }),
    { booked: 0, free: 0, capacity: 0 }
  );

  return (
    <div className="au-page">
      <NavBar />

      <main className="st-main">
        <header className="st-header">
          <div>
            <span className="au-eyebrow">Staff</span>
            <h1>Slots and capacity</h1>
            <p className="st-lead">
              The time slots of the hut and how many seats are booked in each one.
            </p>
          </div>

          <div className="st-controls" role="group" aria-label="Choose the day">
            <button
              type="button"
              className="au-btn au-btn--ghost"
              onClick={() => day && changeDay(addDays(day, -1))}
              disabled={!day}
              aria-label="Previous day"
            >
              ‹
            </button>
            <label className="st-date">
              <span className="st-sr-only">Date</span>
              <input
                type="date"
                value={day ?? ""}
                onChange={(event) => changeDay(event.target.value)}
                disabled={!day}
              />
            </label>
            <button
              type="button"
              className="au-btn au-btn--ghost"
              onClick={() => day && changeDay(addDays(day, 1))}
              disabled={!day}
              aria-label="Next day"
            >
              ›
            </button>
            <button
              type="button"
              className="au-btn au-btn--ghost"
              onClick={() => changeDay(todayInHut())}
            >
              Today
            </button>
            <button
              type="button"
              className="au-btn au-btn--ghost"
              onClick={() => day && loadDay(day)}
              disabled={!day || status === "loading"}
            >
              Refresh
            </button>
          </div>
        </header>

        {day && <h2 className="st-day">{formatLongDay(day)}</h2>}

        {status === "loading" && (
          <p className="st-state" role="status">
            Loading slots…
          </p>
        )}

        {status === "error" && (
          <div className="st-state st-state--error" role="alert">
            <p>
              {error?.status === 401 ? (
                <>
                  Your session has expired. <Link to="/login" state={{ from: "/staff/slots" }}>Log in again</Link>.
                </>
              ) : (
                error?.message || "Something went wrong while loading the slots."
              )}
            </p>
            {error?.status !== 401 && (
              <button type="button" className="au-btn au-btn--ghost" onClick={() => loadDay(day)}>
                Try again
              </button>
            )}
          </div>
        )}

        {status === "ready" && slots.length === 0 && (
          <div className="st-state">
            <p>
              <strong>No slots on this day.</strong>
            </p>
            <p>Pick another date to see the slots that have been defined.</p>
          </div>
        )}

        {status === "ready" && slots.length > 0 && (
          <>
            <dl className="st-summary" aria-label="Totals for the day">
              <div>
                <dt>Slots</dt>
                <dd>{slots.length}</dd>
              </div>
              <div>
                <dt>Seats booked</dt>
                <dd>{totals.booked}</dd>
              </div>
              <div>
                <dt>Seats free</dt>
                <dd>{totals.free}</dd>
              </div>
              <div>
                <dt>Total seats</dt>
                <dd>{totals.capacity}</dd>
              </div>
            </dl>

            <ul className="st-slots">
              {slots.map((slot) => (
                <SlotCard key={slot.id} slot={slot} />
              ))}
            </ul>
          </>
        )}
      </main>
    </div>
  );
}

function SlotCard({ slot }) {
  const [open, setOpen] = useState(false);
  const panelId = `st-tables-${slot.id}`;

  if (slot.failed) {
    return (
      <li className="st-slot">
        <div className="st-slot-head">
          <h3 className="st-time">{formatTimeRange(slot.start, slot.end)}</h3>
          <span className="st-badge st-badge--muted">Unavailable</span>
        </div>
        <p className="st-hint">The tables of this slot could not be loaded. Use Refresh to try again.</p>
      </li>
    );
  }

  const state = occupancyStatus(slot);
  const percent = percentBooked(slot);

  return (
    <li className="st-slot">
      <div className="st-slot-head">
        <div>
          <h3 className="st-time">{formatTimeRange(slot.start, slot.end)}</h3>
          <p className="st-meta">
            {slot.tables.length} {slot.tables.length === 1 ? "table" : "tables"} · {slot.capacity} seats
          </p>
        </div>
        <span className={`st-badge st-badge--${state.tone}`}>{state.label}</span>
      </div>

      <div
        className="st-bar"
        role="img"
        aria-label={`${slot.booked} of ${slot.capacity} seats booked`}
      >
        <span style={{ width: `${percent}%` }} />
      </div>

      <dl className="st-figures">
        <div>
          <dt>Booked</dt>
          <dd>{slot.booked}</dd>
        </div>
        <div>
          <dt>Free</dt>
          <dd>{slot.free}</dd>
        </div>
        <div>
          <dt>Capacity</dt>
          <dd>{slot.capacity}</dd>
        </div>
      </dl>

      {slot.tables.length === 0 ? (
        <p className="st-hint">No tables have been assigned to this slot yet.</p>
      ) : (
        <>
          <button
            type="button"
            className="st-toggle"
            aria-expanded={open}
            aria-controls={panelId}
            onClick={() => setOpen((current) => !current)}
          >
            {open ? "Hide tables" : "Show tables"}
          </button>

          {open && (
            <ul className="st-tables" id={panelId}>
              {slot.tables.map((table) => (
                <li key={table.key} className="st-table">
                  <div>
                    <strong>{table.number !== null ? `Table ${table.number}` : "Table"}</strong>
                    {table.location && <span>{table.location}</span>}
                  </div>
                  <div className="st-table-seats">
                    <span className="st-seat-bar" aria-hidden="true">
                      <span style={{ width: `${percentBooked(table)}%` }} />
                    </span>
                    <span>
                      {table.booked} / {table.capacity} booked
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </li>
  );
}
