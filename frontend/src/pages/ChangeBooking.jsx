import React, { useEffect, useMemo, useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import NavBar from "../components/NavBar";
import { getAvailability, updateBooking } from "../api";
import "./ChangeBooking.css";

// MH-06: a hiker changes the date/time, the party size or the requirements
// of a booking. The booking arrives from "My bookings" in the router state.
// The bookings list carries no date, so only the time of the current
// booking can be shown.

function toDateKey(date) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function parseKey(dateKey) {
  return new Date(`${dateKey}T00:00:00`);
}

function formatDate(dateKey) {
  return parseKey(dateKey).toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
  });
}

function formatTime(value) {
  if (!value) return "";
  const time = String(value).includes("T") ? String(value).split("T")[1] : String(value);
  return time.slice(0, 5);
}

function formatSlot(slot) {
  return `${formatTime(slot.start)} – ${formatTime(slot.end)}`;
}

function guestsLabel(count) {
  return `${count} ${count === 1 ? "guest" : "guests"}`;
}

function tablesLabel(tables) {
  return tables.map((table) => `#${table.number} (${table.seats} seats)`).join(", ");
}

// The requirements as the backend stores them, ready to compare.
function normalizeRequirements(list) {
  return (list ?? []).map((requirement) => ({
    allergies: Boolean(requirement.allergies),
    description: (requirement.description ?? "").trim(),
  }));
}

function requirementsText(list) {
  const items = (list ?? [])
    .map((requirement) => (requirement.description ?? "").trim())
    .filter(Boolean);
  return items.length > 0 ? items.join("; ") : "none";
}

export default function ChangeBooking() {
  const { state } = useLocation();
  const navigate = useNavigate();
  const original = state?.booking ?? null;

  const today = useMemo(() => {
    const now = new Date();
    now.setHours(0, 0, 0, 0);
    return now;
  }, []);

  const [availability, setAvailability] = useState({});
  const [loading, setLoading] = useState(false);
  const [openSection, setOpenSection] = useState(null); // "when" | "guests" | "requirements"
  const [selectedDate, setSelectedDate] = useState(null);
  const [selectedSlotIndex, setSelectedSlotIndex] = useState("");
  const [partySizeInput, setPartySizeInput] = useState(
    String(original?.party_size ?? 1)
  );
  const [requirements, setRequirements] = useState(() =>
    (original?.requirements ?? []).map((requirement) => ({
      allergies: Boolean(requirement.allergies),
      description: requirement.description ?? "",
    }))
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  useEffect(() => {
    if (!original) return undefined;
    let cancelled = false;

    async function loadAvailability() {
      setLoading(true);
      try {
        const data = await getAvailability();
        if (!cancelled) setAvailability(data ?? {});
      } catch (err) {
        if (!cancelled) {
          setError(err.message || "Could not load availability.");
          setAvailability({});
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadAvailability();
    return () => {
      cancelled = true;
    };
  }, [original]);

  if (!original) {
    // opened directly, without choosing a booking first
    return <Navigate to="/my-bookings" replace />;
  }

  const dateKeys = Object.keys(availability)
    .filter((key) => availability[key].length > 0 && parseKey(key) >= today)
    .sort();

  const selectedSlots = selectedDate ? availability[selectedDate] ?? [] : [];
  const selectedSlot =
    selectedSlotIndex === "" ? null : selectedSlots[Number(selectedSlotIndex)];

  const partySize = Number(partySizeInput);
  // Keeping the current slot: the free seats are unknown to the page (the
  // backend checks them). A new slot: its free seats are the limit.
  const maxSeats = selectedSlot ? selectedSlot.availableSeats : null;
  const isPartySizeValid =
    partySizeInput.trim() !== "" &&
    Number.isInteger(partySize) &&
    partySize >= 1 &&
    (maxSeats === null || partySize <= maxSeats);

  const slotChanged = selectedSlot !== null;
  const sizeChanged = isPartySizeValid && partySize !== original.party_size;
  const requirementsChanged =
    JSON.stringify(normalizeRequirements(requirements)) !==
    JSON.stringify(normalizeRequirements(original.requirements));
  const hasChanges = slotChanged || sizeChanged || requirementsChanged;

  const currentTime = `${formatTime(original.slot_time_start)} – ${formatTime(original.slot_time_end)}`;
  const currentTables = original.tables ?? [];

  function toggleSection(name) {
    setOpenSection((current) => (current === name ? null : name));
  }

  function selectDate(key) {
    setSelectedDate(key);
    setSelectedSlotIndex("");
    setError("");
  }

  function keepCurrentSlot() {
    setSelectedDate(null);
    setSelectedSlotIndex("");
    setError("");
  }

  function addRequirement() {
    setRequirements((current) => [...current, { allergies: false, description: "" }]);
  }

  function updateRequirement(index, changes) {
    setRequirements((current) =>
      current.map((requirement, i) =>
        i === index ? { ...requirement, ...changes } : requirement
      )
    );
  }

  function removeRequirement(index) {
    setRequirements((current) => current.filter((_, i) => i !== index));
  }

  async function saveChanges() {
    if (saving || !hasChanges || !isPartySizeValid) return;

    if (requirements.some((requirement) => !requirement.description.trim())) {
      setOpenSection("requirements");
      setError("Each requirement needs a description. Fill it in or remove it.");
      return;
    }

    const changes = {};
    if (slotChanged) {
      changes.date = selectedDate;
      changes.time = selectedSlot.time; // hut-local HH:MM:SS, as the backend expects
    }
    if (sizeChanged) {
      changes.partySize = partySize;
    }
    if (requirementsChanged) {
      changes.requirements = normalizeRequirements(requirements);
    }

    setSaving(true);
    setError("");
    try {
      const updated = await updateBooking(original.id, changes);
      // the answer has no requirements: show what was saved (or the unchanged ones)
      setResult({
        ...updated,
        requirements: changes.requirements ?? normalizeRequirements(original.requirements),
      });
    } catch (err) {
      setError(err.message || "Could not change the booking.");
    } finally {
      setSaving(false);
    }
  }

  if (result) {
    const tables = result.tables ?? [];
    return (
      <div className="app-shell">
        <NavBar />

        <main className="cb-page">
          <section className="cb-done">
            <div className="cb-done-icon">✓</div>
            <span className="cb-eyebrow">Booking #{result.id}</span>
            <h1>Your booking was changed</h1>
            <p>You will also receive an email with the new details.</p>

            <dl className="cb-done-list">
              <div>
                <dt>Date</dt>
                <dd>{result.date ? formatDate(result.date) : "—"}</dd>
              </div>
              <div>
                <dt>Time</dt>
                <dd>{formatTime(result.time)}</dd>
              </div>
              <div>
                <dt>Party size</dt>
                <dd>{guestsLabel(result.party_size)}</dd>
              </div>
              <div>
                <dt>Tables</dt>
                <dd>{tables.length > 0 ? tablesLabel(tables) : "Assigned by the hut"}</dd>
              </div>
              <div>
                <dt>Requirements</dt>
                <dd>
                  {result.requirements.length === 0 ? (
                    "None"
                  ) : (
                    <ul className="cb-done-reqs">
                      {result.requirements.map((requirement, index) => (
                        <li key={index}>
                          {requirement.allergies && (
                            <span className="cb-done-tag">Allergy</span>
                          )}
                          {requirement.description}
                        </li>
                      ))}
                    </ul>
                  )}
                </dd>
              </div>
            </dl>

            <button
              type="button"
              className="secondary-button"
              onClick={() => navigate("/my-bookings")}
            >
              ← Back to my bookings
            </button>
          </section>
        </main>
      </div>
    );
  }

  const whenValue = slotChanged
    ? `${formatDate(selectedDate)} · ${formatSlot(selectedSlot)}`
    : `${currentTime} (current)`;
  const guestsValue = guestsLabel(isPartySizeValid ? partySize : original.party_size);
  const requirementsValue =
    requirements.length === 0
      ? "None"
      : `${requirements.length} ${requirements.length === 1 ? "requirement" : "requirements"}`;

  return (
    <div className="app-shell">
      <NavBar />

      <main className="cb-page">
        <header className="cb-header">
          <span className="cb-eyebrow">Change booking</span>
          <h1>Change your booking</h1>
          <p>Open a row to change it. Changes are possible until 2 days before the meal.</p>
        </header>

        <section className="cb-ticket" aria-label="Current booking">
          <div className="cb-ticket-main">
            <span className="cb-ticket-label">Current booking #{original.id}</span>
            <strong className="cb-ticket-time">{currentTime}</strong>
          </div>
          <div className="cb-ticket-side">
            <span>{guestsLabel(original.party_size)}</span>
            {currentTables.length > 0 && <span>Tables {tablesLabel(currentTables)}</span>}
          </div>
        </section>

        <div className="cb-rows">
          {/* DATE AND TIME */}
          <section className={`cb-row ${slotChanged ? "changed" : ""}`}>
            <button
              type="button"
              className="cb-row-head"
              aria-expanded={openSection === "when"}
              onClick={() => toggleSection("when")}
            >
              <span className="cb-row-title">Date &amp; time</span>
              <span className="cb-row-value">{whenValue}</span>
              <span className="cb-row-action">{openSection === "when" ? "Close" : "Change"}</span>
            </button>

            {openSection === "when" && (
              <div className="cb-row-body">
                {loading && <p className="cb-note">Loading available dates…</p>}
                {!loading && dateKeys.length === 0 && (
                  <p className="cb-note">No other dates are available right now.</p>
                )}

                {dateKeys.length > 0 && (
                  <div className="cb-dates" role="listbox" aria-label="Available dates">
                    {dateKeys.map((key) => {
                      const day = parseKey(key);
                      return (
                        <button
                          type="button"
                          key={key}
                          role="option"
                          aria-selected={selectedDate === key}
                          className={`cb-date ${selectedDate === key ? "selected" : ""}`}
                          onClick={() => selectDate(key)}
                        >
                          <span>{day.toLocaleDateString("en-US", { weekday: "short" })}</span>
                          <strong>{day.getDate()}</strong>
                          <span>{day.toLocaleDateString("en-US", { month: "short" })}</span>
                        </button>
                      );
                    })}
                  </div>
                )}

                {selectedDate && (
                  <div className="cb-slots">
                    {selectedSlots.map((slot, index) => (
                      <button
                        type="button"
                        key={`${slot.start}-${slot.end}-${index}`}
                        className={`cb-slot ${String(index) === selectedSlotIndex ? "selected" : ""}`}
                        onClick={() => {
                          setSelectedSlotIndex(String(index));
                          setError("");
                        }}
                      >
                        <strong>{formatSlot(slot)}</strong>
                        <span>
                          {slot.availableSeats} {slot.availableSeats === 1 ? "seat" : "seats"} left
                        </span>
                      </button>
                    ))}
                  </div>
                )}

                {(selectedDate || slotChanged) && (
                  <button type="button" className="cb-link" onClick={keepCurrentSlot}>
                    Keep the current date and time
                  </button>
                )}
              </div>
            )}
          </section>

          {/* GUESTS */}
          <section className={`cb-row ${sizeChanged ? "changed" : ""}`}>
            <button
              type="button"
              className="cb-row-head"
              aria-expanded={openSection === "guests"}
              onClick={() => toggleSection("guests")}
            >
              <span className="cb-row-title">Guests</span>
              <span className="cb-row-value">{guestsValue}</span>
              <span className="cb-row-action">{openSection === "guests" ? "Close" : "Change"}</span>
            </button>

            {openSection === "guests" && (
              <div className="cb-row-body">
                <div className="cb-stepper">
                  <button
                    type="button"
                    disabled={isPartySizeValid && partySize <= 1}
                    onClick={() => setPartySizeInput(String(Math.max(1, (partySize || 1) - 1)))}
                    aria-label="Decrease party size"
                  >
                    −
                  </button>
                  <input
                    type="number"
                    min="1"
                    max={maxSeats ?? ""}
                    step="1"
                    value={partySizeInput}
                    onChange={(event) => setPartySizeInput(event.target.value)}
                    aria-label="Number of guests"
                    aria-invalid={!isPartySizeValid}
                  />
                  <button
                    type="button"
                    disabled={maxSeats !== null && isPartySizeValid && partySize >= maxSeats}
                    onClick={() => {
                      const next = (Number.isInteger(partySize) ? partySize : 0) + 1;
                      setPartySizeInput(String(maxSeats !== null ? Math.min(next, maxSeats) : next));
                    }}
                    aria-label="Increase party size"
                  >
                    +
                  </button>
                </div>

                <p className="cb-note">
                  {selectedSlot
                    ? `Maximum ${selectedSlot.availableSeats} ${selectedSlot.availableSeats === 1 ? "guest" : "guests"} for the new time slot.`
                    : "The hut checks the free seats when you save. If there are not enough, the booking stays as it is."}
                </p>
                {!isPartySizeValid && (
                  <p className="cb-error" role="alert">
                    Enter a whole number
                    {maxSeats !== null ? ` between 1 and ${maxSeats}` : " of at least 1"}.
                  </p>
                )}
              </div>
            )}
          </section>

          {/* REQUIREMENTS */}
          <section className={`cb-row ${requirementsChanged ? "changed" : ""}`}>
            <button
              type="button"
              className="cb-row-head"
              aria-expanded={openSection === "requirements"}
              onClick={() => toggleSection("requirements")}
            >
              <span className="cb-row-title">Requirements</span>
              <span className="cb-row-value">{requirementsValue}</span>
              <span className="cb-row-action">
                {openSection === "requirements" ? "Close" : "Change"}
              </span>
            </button>

            {openSection === "requirements" && (
              <div className="cb-row-body">
                {requirements.length === 0 && (
                  <p className="cb-note">No special requirements.</p>
                )}

                {requirements.map((requirement, index) => (
                  <div className="cb-req" key={index}>
                    <label className="cb-check">
                      <input
                        type="checkbox"
                        checked={requirement.allergies}
                        onChange={(event) =>
                          updateRequirement(index, { allergies: event.target.checked })
                        }
                      />
                      <span>Allergy</span>
                    </label>
                    <input
                      type="text"
                      className="cb-req-text"
                      value={requirement.description}
                      onChange={(event) =>
                        updateRequirement(index, { description: event.target.value })
                      }
                      placeholder="E.g. 2 vegetarians, 1 peanut allergy"
                      maxLength={500}
                      aria-label={`Requirement ${index + 1}`}
                    />
                    <button
                      type="button"
                      className="cb-req-remove"
                      onClick={() => removeRequirement(index)}
                      aria-label={`Remove requirement ${index + 1}`}
                    >
                      Remove
                    </button>
                  </div>
                ))}

                <button type="button" className="cb-link" onClick={addRequirement}>
                  + Add a requirement
                </button>
              </div>
            )}
          </section>
        </div>

        <section className="cb-review" aria-label="Your changes">
          <div className="cb-review-bar">
            <div className="cb-review-title">
              <h2>Your changes</h2>
              {!hasChanges && <p className="cb-note">Nothing changed yet.</p>}
            </div>

            <div className="cb-actions">
              <button
                type="button"
                className="cb-btn cb-btn--cancel"
                onClick={() => navigate("/my-bookings")}
              >
                Cancel
              </button>
              <button
                type="button"
                className="cb-btn cb-btn--save"
                disabled={!hasChanges || !isPartySizeValid || saving}
                onClick={saveChanges}
              >
                {saving ? "Saving..." : "Save changes"}
              </button>
            </div>
          </div>

          {hasChanges && (
            <ul className="cb-diff">
              {slotChanged && (
                <li>
                  <span>Date &amp; time</span>
                  <span className="cb-from">{currentTime}</span>
                  <span className="cb-arrow">→</span>
                  <strong className="cb-to">{whenValue}</strong>
                </li>
              )}
              {sizeChanged && (
                <li>
                  <span>Guests</span>
                  <span className="cb-from">{original.party_size}</span>
                  <span className="cb-arrow">→</span>
                  <strong className="cb-to">{partySize}</strong>
                </li>
              )}
              {requirementsChanged && (
                <li>
                  <span>Requirements</span>
                  <span className="cb-from">{requirementsText(original.requirements)}</span>
                  <span className="cb-arrow">→</span>
                  <strong className="cb-to">{requirementsText(requirements)}</strong>
                </li>
              )}
            </ul>
          )}

          {error && (
            <div className="cb-error" role="alert">
              {error}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
