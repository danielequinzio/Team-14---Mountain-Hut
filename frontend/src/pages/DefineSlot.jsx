import React, { useCallback, useEffect, useMemo, useState } from "react";
import NavBar from "../components/NavBar";
import { createEmployeeSlot, getEmployeeSlots, getHutTables, getTablesForSlot, USE_MOCK_SLOT_DATA } from "../api";

const byNumber = (a, b) => a.number - b.number;

const WEEKDAYS = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"];
const dateKey = (d) => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`;
function getCalendarDays(month) {
  const first = new Date(month.getFullYear(), month.getMonth(), 1);
  const start = new Date(first);
  start.setDate(first.getDate() - ((first.getDay() + 6) % 7));
  return Array.from({ length: 42 }, (_, i) => {
    const d = new Date(start);
    d.setDate(start.getDate() + i);
    return d;
  });
}

const monthLabel = (d) =>
  d.toLocaleDateString("en-US", { month: "long", year: "numeric" });
const dateLabel = (key) =>
  new Date(`${key}T12:00:00`).toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  });

function timeLabel(value) {
  if (!value) return "";
  const [h,m] = String(value).slice(0,5).split(":");
  const n=Number(h);
  return `${n%12||12}:${m} ${n>=12?"PM":"AM"}`;
}

export default function DefineSlot() {
  const [month,setMonth]=useState(()=>{const d=new Date();return new Date(d.getFullYear(),d.getMonth(),1);});
  const [selectedDate,setSelectedDate]=useState(dateKey(new Date()));
  const [start,setStart]=useState("11:00"),[end,setEnd]=useState("12:00"),[tables,setTables]=useState([]);
  const [addOpen,setAddOpen]=useState(false),[copyOpen,setCopyOpen]=useState(false);
  const [tableNo,setTableNo]=useState(""),[tableSize,setTableSize]=useState("2"),[tableLocation,setTableLocation]=useState("");
  const [copyDate,setCopyDate]=useState(""),[copySlots,setCopySlots]=useState([]),[copySlotId,setCopySlotId]=useState("");
  const [copySourceId,setCopySourceId]=useState(null);
  const [copyLoading,setCopyLoading]=useState(false),[saving,setSaving]=useState(false),[error,setError]=useState(""),[success,setSuccess]=useState("");
  const [hutTables,setHutTables]=useState([]),[hutLoading,setHutLoading]=useState(true),[hutError,setHutError]=useState("");
  const days=useMemo(()=>getCalendarDays(month),[month]);

  // The hut's physical tables (GET /tables): staff tick the ones the slot offers.
  const loadHutTables = useCallback(async () => {
    setHutLoading(true);
    setHutError("");
    try {
      setHutTables(await getHutTables());
    } catch (e) {
      setHutError(e.message || "Could not load the hut's tables.");
    } finally {
      setHutLoading(false);
    }
  }, []);

  useEffect(() => {
    loadHutTables();
  }, [loadHutTables]);

  // Hut tables plus the new ones added in this form (created when the slot is saved).
  const hutNumbers = new Set(hutTables.map((t) => t.number));
  const selectedNumbers = new Set(tables.map((t) => t.number));
  const tableRows = [
    ...hutTables.map((t) => ({ ...t, isNew: false })),
    ...tables.filter((t) => !hutNumbers.has(t.number)).map((t) => ({ ...t, isNew: true })),
  ].sort(byNumber);
  const allSelected = tableRows.length > 0 && tableRows.every((t) => selectedNumbers.has(t.number));

  function toggleTable(table) {
    setTables((current) =>
      current.some((t) => t.number === table.number)
        ? current.filter((t) => t.number !== table.number)
        : [...current, { id: table.id, number: table.number, size: table.size, capacity: table.capacity, location: table.location }].sort(byNumber),
    );
    setCopySourceId(null);
    setError("");
    setSuccess("");
  }

  function toggleAll() {
    // "Clear" keeps nothing; "Select all" ticks every hut table and keeps the new ones
    setTables(allSelected ? [] : tableRows.map(({ isNew, ...t }) => t));
    setCopySourceId(null);
    setError("");
    setSuccess("");
  }

  useEffect(() => {
    if (!copyDate) {
      setCopySlots([]);
      setCopySlotId("");
      return;
    }

    let cancelled = false;
    (async () => {
      setCopyLoading(true);
      setCopySlotId("");
      setError("");
      try {
        const result = await getEmployeeSlots(copyDate);
        if (!cancelled) setCopySlots(Array.isArray(result) ? result : []);
      } catch (e) {
        if (!cancelled) setError(e.message || "Could not load time slots.");
      } finally {
        if (!cancelled) setCopyLoading(false);
      }
    })();
    return ()=>{cancelled=true;};
  },[copyDate]);

  function addTable(e){
    e.preventDefault();
    const number = Number(tableNo),
      size = Number(tableSize);
    if (!Number.isInteger(number) || number < 1) {
      setError("Enter a valid positive table number.");
      return;
    }
    if (!Number.isInteger(size) || size < 1) {
      setError("Table capacity must be at least one seat.");
      return;
    }
    if (!tableLocation.trim()) {
      setError("Enter the table location.");
      return;
    }
    if (tables.some((t) => t.number === number)) {
      setError(`Table ${number} is already in this time slot.`);
      return;
    }
    // Table numbers are unique in the hut: reuse the existing table instead of a duplicate
    const existing = hutTables.find((t) => t.number === number);
    if (existing) {
      toggleTable(existing);
      setTableNo("");
      setTableSize("2");
      setTableLocation("");
      setAddOpen(false);
      setSuccess(
        `Table ${number} already exists (${existing.size} seats, ${existing.location}), so it has been selected.`,
      );
      return;
    }
    setTables((current) =>
      [
        ...current,
        { number, size, capacity: size, location: tableLocation.trim() },
      ].sort((a, b) => a.number - b.number),
    );
    setTableNo("");
    setTableSize("2");
    setTableLocation("");
    setAddOpen(false);
    setError("");
    setSuccess("");
    setCopySourceId(null);
  }

  async function copyTables() {
    if (!copySlotId) return;
    try {
      const source = await getTablesForSlot(copySlotId);
      const copied = source.map((t) => ({
        id: t.id,
        number: Number(t.number),
        size: Number(t.capacity ?? t.size),
        capacity: Number(t.capacity ?? t.size),
        location: t.location ?? "",
      }));
      if (!copied.length)
        throw new Error("The selected time slot has no tables to copy.");
      setTables(copied.sort((a, b) => a.number - b.number));
      setCopySourceId(String(copySlotId));
      setCopyOpen(false);
      setError("");
      setSuccess(
        `Ready to copy ${copied.length} table${copied.length === 1 ? "" : "s"} from the selected slot.`,
      );
    } catch (e) {
      setError(e.message || "Could not copy tables.");
    }
  }

  async function submit(){
    setError("");setSuccess("");
    if(!selectedDate){setError("Choose a date.");return;}
    if(!start||!end||end<=start){setError("The ending time must be later than the starting time.");return;}
    if(!tables.length){setError("Add at least one table before creating the time slot.");return;}
    setSaving(true);
    try {
      const result = await createEmployeeSlot({
        date: selectedDate,
        start,
        end,
        tables,
        sourceSlotId: copySourceId,
      });
      setSuccess(
        `Time slot created successfully${result?.id ? ` (ID: ${result.id})` : ""}.`,
      );
      setTables([]);
      setCopySourceId(null);
      loadHutTables(); // tables created with this slot now belong to the hut
    } catch (e) {
      setError(e.message || "Could not create the time slot.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
    <NavBar />
    <div className="slot-page">
      <main className="slot-main">
        <div className="slot-intro">
          <div>
            <small>STAFF TOOLS</small>
            <h1>Create a time slot</h1>
            <p>
              Set the service hours and assign the tables available for this
              date.
            </p>
          </div>
        </div>
        <div className="slot-columns">
          <section className="slot-panel">
            <div className="slot-heading">
              <h2>
                <i>01</i> Choose a date
              </h2>
              <small>Select any calendar date</small>
            </div>
            <div className="slot-calendar">
              <div className="slot-month">
                <button type="button" onClick={()=>setMonth(d=>new Date(d.getFullYear(),d.getMonth()-1,1))}>‹</button>
                <strong>{monthLabel(month)}</strong>
                <button
                  type="button"
                  onClick={() =>
                    setMonth(
                      (d) => new Date(d.getFullYear(), d.getMonth() + 1, 1),
                    )
                  }
                >
                  ›
                </button>
              </div>
              <div className="slot-weekdays">
                {WEEKDAYS.map((d) => (
                  <span key={d}>{d}</span>
                ))}
              </div>
              <div className="slot-days">
                {days.map((d) => {
                  const key = dateKey(d);
                  return (
                    <button
                      type="button"
                      key={key}
                      className={`${d.getMonth() !== month.getMonth() ? "outside" : ""} ${key === selectedDate ? "active" : ""}`}
                      onClick={() => {
                        setSelectedDate(key);
                        setError("");
                        setSuccess("");
                      }}
                    >
                      {d.getDate()}
                    </button>
                  );
                })}
              </div>
            </div>
            <div className="slot-date-summary">
              <span>▣</span>
              <div>
                <small>SELECTED DATE</small>
                <strong>{dateLabel(selectedDate)}</strong>
              </div>
            </div>
            <div className="slot-times">
              <label><b>02</b> Starting time<input type="time" value={start} onChange={e=>setStart(e.target.value)}/></label>
              <label><b>03</b> Ending time<input type="time" value={end} onChange={e=>setEnd(e.target.value)}/></label>
            </div>
          </section>
          <section className="slot-panel">
            <div className="slot-heading">
              <h2>
                <i>04</i> Tables for this slot
              </h2>
              <small>
                {tables.length} of {tableRows.length} selected
                {tableRows.length > 0 && (
                  <button type="button" className="slot-link" onClick={toggleAll}>
                    {allSelected ? "Clear" : "Select all"}
                  </button>
                )}
              </small>
            </div>
            {hutError && (
              <p className="slot-table-note error" role="alert">
                {hutError}{" "}
                <button type="button" className="slot-link" onClick={loadHutTables}>Try again</button>
              </p>
            )}
            {tableRows.length ? (
              <div className="slot-table-list pick-list">
                <div className="slot-table-row pick header">
                  <span />
                  <span>Table</span>
                  <span>Seats</span>
                  <span>Location</span>
                </div>
                {tableRows.map((t) => {
                  const checked = selectedNumbers.has(t.number);
                  return (
                    <label className={`slot-table-row pick ${checked ? "checked" : ""}`} key={t.number}>
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => toggleTable(t)}
                        aria-label={`Use table ${t.number} in this slot`}
                      />
                      <strong>Table {t.number}</strong>
                      <span>{t.size} seats</span>
                      <span>
                        {t.location}
                        {t.isNew && <em className="slot-new">New</em>}
                      </span>
                    </label>
                  );
                })}
              </div>
            ) : hutLoading ? (
              <p className="slot-table-note">Loading the hut's tables…</p>
            ) : (
              <div className="slot-empty">
                <span>▦</span>
                <strong>The hut has no tables yet</strong>
                <p>
                  Add the first table: it will be created together with this
                  time slot and reusable for the next ones.
                </p>
              </div>
            )}
            <div className="slot-actions">
              <button
                type="button"
                className="gold"
                onClick={() => {
                  setError("");
                  setAddOpen(true);
                }}
              >
                ＋ Add table
              </button>
              <button
                type="button"
                className="outline"
                onClick={() => {
                  setError("");
                  setCopyDate("");
                  setCopySlots([]);
                  setCopySlotId("");
                  setCopySourceId(null);
                  setCopyOpen(true);
                }}
              >
                ⧉ Copy tables
              </button>
            </div>
            <p className="slot-help">Tick the hut's tables this slot offers, or add a new one. Copying selects the same tables as another slot, without changing it.</p>
          </section>
        </div>
        {error&&<div className="slot-alert error" role="alert">{error}</div>}
        {success&&<div className="slot-alert success" role="status">{success}</div>}
        <footer className="slot-footer">
          <div>
            <small>NEW TIME SLOT</small>
            <strong>
              {dateLabel(selectedDate)} · {timeLabel(start)} – {timeLabel(end)}
            </strong>
            <span>
              {tables.length} tables · {tables.reduce((n, t) => n + t.size, 0)}
              {" "}seats total
            </span>
          </div>
          <button
            type="button"
            className="gold create"
            disabled={saving}
            onClick={submit}
          >
            {saving ? "Creating…" : "Create time slot →"}
          </button>
        </footer>
        {USE_MOCK_SLOT_DATA&&<p className="slot-mock-note">Development mode: mock changes reset when the page reloads.</p>}
      </main>

      {addOpen && (
        <div
          className="slot-backdrop"
          onMouseDown={(e) => {
            if (e.target === e.currentTarget) setAddOpen(false);
          }}
        >
          <section className="slot-modal">
            <button
              type="button"
              className="close"
              onClick={() => setAddOpen(false)}
            >
              ×
            </button>
            <small>TABLE CONFIGURATION</small>
            <h2>Add a table</h2>
            <p>Enter the table number, seating capacity and location.</p>
            <form onSubmit={addTable}>
              <label>
                Table number
                <input
                  autoFocus
                  type="number"
                  min="1"
                  step="1"
                  required
                  value={tableNo}
                  onChange={(e) => setTableNo(e.target.value)}
                  placeholder="e.g. 12"
                />
              </label>
              <label>
                Table capacity <em>(number of seats)</em>
                <input
                  type="number"
                  min="1"
                  step="1"
                  required
                  value={tableSize}
                  onChange={(e) => setTableSize(e.target.value)}
                />
              </label>
              <label>
                Location
                <input
                  required
                  value={tableLocation}
                  onChange={(e) => setTableLocation(e.target.value)}
                  placeholder="e.g. Main hall"
                />
              </label>
              <div className="modal-actions">
                <button
                  type="button"
                  className="outline"
                  onClick={() => setAddOpen(false)}
                >
                  Cancel
                </button>
                <button className="gold" type="submit">
                  Add table
                </button>
              </div>
            </form>
          </section>
        </div>
      )}

      {copyOpen && (
        <div
          className="slot-backdrop"
          onMouseDown={(e) => {
            if (e.target === e.currentTarget) setCopyOpen(false);
          }}
        >
          <section className="slot-modal copy-modal">
            <button
              type="button"
              className="close"
              onClick={() => setCopyOpen(false)}
            >
              ×
            </button>
            <small>REUSE A CONFIGURATION</small>
            <h2>Copy tables from another slot</h2>
            <p>Choose a date, then select one of its existing time slots.</p>
            <label>
              Source date
              <input
                type="date"
                value={copyDate}
                onChange={(e) => setCopyDate(e.target.value)}
              />
            </label>
            <div className="copy-results">
              {!copyDate ? (
                <p>Choose a date to see its existing time slots.</p>
              ) : copyLoading ? (
                <p>Loading time slots…</p>
              ) : !copySlots.length ? (
                <p>There are no time slots on this date.</p>
              ) : (
                copySlots.map((s) => (
                  <label
                    className={`copy-option ${String(copySlotId) === String(s.id) ? "active" : ""}`}
                    key={s.id}
                  >
                    <input
                      type="radio"
                      name="copy-slot"
                      checked={String(copySlotId) === String(s.id)}
                      value={s.id}
                      onChange={() => setCopySlotId(String(s.id))}
                    />
                    <span>
                      <strong>
                        {timeLabel(s.start ?? s.start_time)} – {timeLabel(s.end ?? s.end_time)}
                      </strong>
                      <small>{s.tables?.length ?? "—"} tables</small>
                    </span>
                  </label>
                ))
              )}
            </div>
            <div className="modal-actions">
              <button
                type="button"
                className="outline"
                onClick={() => setCopyOpen(false)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="gold"
                disabled={!copySlotId || copyLoading}
                onClick={copyTables}
              >
                Use selected tables
              </button>
            </div>
          </section>
        </div>
      )}
    </div>
    </>
  );
}
