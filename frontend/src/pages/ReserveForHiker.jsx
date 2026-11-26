import React, { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import NavBar from "../components/NavBar";
import { bookForHiker, deleteGuest, getAvailability, searchHikers } from "../api";
import "./ReserveForHiker.css";

// MH-07: an employee enters a reservation for a hiker (phone, in person...).
// Step 1: who (search by name, email or phone as you type, or arrive from
// "Create hiker" with the profile).
// Step 2: when, how many, requirements. Step 3: review and confirm.

const STEPS = ["Hiker", "Reservation", "Confirm"];
const MIN_QUERY_LENGTH = 2; // characters typed before the search starts
const SEARCH_DELAY_MS = 250; // wait for a pause in typing before calling the backend

function hikerName(hiker) {
  return [hiker.name, hiker.surname].filter(Boolean).join(" ");
}

// "Anna Rossi (anna@example.com)", or just the email / name if the other is missing
function hikerLabel(hiker) {
  const name = hikerName(hiker);
  if (name && hiker.email) return `${name} (${hiker.email})`;
  return name || hiker.email || `Hiker #${hiker.id}`;
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

// 25/11/2026, same format as the hiker's own confirmation page
function formatShortDate(dateKey) {
  return parseKey(dateKey).toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
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

export default function ReserveForHiker() {
  const location = useLocation();
  const navigate = useNavigate();

  // arriving from "Create hiker": the profile is already known
  const startHiker = location.state?.hiker ?? null;

  const [step, setStep] = useState(startHiker ? 1 : 0);
  const [hiker, setHiker] = useState(startHiker); // { id, email, label, isGuest }
  const [leaving, setLeaving] = useState(false);
  const [leaveError, setLeaveError] = useState("");

  // step 1
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState("");
  const [listOpen, setListOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);

  // step 2
  const today = useMemo(() => {
    const now = new Date();
    now.setHours(0, 0, 0, 0);
    return now;
  }, []);
  const [availability, setAvailability] = useState({});
  const [loadingSlots, setLoadingSlots] = useState(false);
  const [slotsError, setSlotsError] = useState("");
  const [selectedDate, setSelectedDate] = useState(null);
  const [selectedSlotIndex, setSelectedSlotIndex] = useState("");
  const [partySizeInput, setPartySizeInput] = useState("2");
  const [requirements, setRequirements] = useState([]);
  const [stepError, setStepError] = useState("");

  // step 3
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [result, setResult] = useState(null);

  const trimmedQuery = query.trim();
  const queryIsLongEnough = trimmedQuery.length >= MIN_QUERY_LENGTH;

  // Autocomplete: search while the staff member types, after a short pause.
  // `cancelled` drops the answer of an outdated search, so a slow earlier request
  // can never overwrite the results of what is typed now.
  useEffect(() => {
    if (step !== 0 || hiker) return undefined;
    if (!queryIsLongEnough) {
      setResults([]);
      setSearching(false);
      setSearchError("");
      return undefined;
    }

    let cancelled = false;
    setSearching(true);
    const timer = setTimeout(async () => {
      try {
        const found = await searchHikers(trimmedQuery);
        if (cancelled) return;
        // the backend already leaves guests out of /hikers/search
        setResults(found ?? []);
        setActiveIndex(-1);
        setSearchError("");
      } catch (err) {
        if (cancelled) return;
        setResults([]);
        setSearchError(err.message || "Could not look the hiker up.");
      } finally {
        if (!cancelled) setSearching(false);
      }
    }, SEARCH_DELAY_MS);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [trimmedQuery, queryIsLongEnough, step, hiker]);

  useEffect(() => {
    if (step !== 1 || Object.keys(availability).length > 0) return undefined;
    let cancelled = false;

    async function load() {
      setLoadingSlots(true);
      setSlotsError("");
      try {
        const data = await getAvailability();
        if (!cancelled) setAvailability(data ?? {});
      } catch (err) {
        if (!cancelled) setSlotsError(err.message || "Could not load the available slots.");
      } finally {
        if (!cancelled) setLoadingSlots(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [step, availability]);

  const dateKeys = Object.keys(availability)
    .filter((key) => availability[key].length > 0 && parseKey(key) >= today)
    .sort();
  const selectedSlots = selectedDate ? availability[selectedDate] ?? [] : [];
  const selectedSlot =
    selectedSlotIndex === "" ? null : selectedSlots[Number(selectedSlotIndex)];

  const partySize = Number(partySizeInput);
  const maxSeats = selectedSlot ? selectedSlot.availableSeats : null;
  const isPartySizeValid =
    partySizeInput.trim() !== "" &&
    Number.isInteger(partySize) &&
    partySize >= 1 &&
    (maxSeats === null || partySize <= maxSeats);

  function chooseHiker(found) {
    setHiker({ id: found.id, email: found.email, label: hikerLabel(found), isGuest: Boolean(found.is_guest) });
    setListOpen(false);
    setStep(1); // chosen: straight to the reservation details
  }

  function handleSearchKeyDown(event) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      if (results.length === 0) return;
      setListOpen(true);
      setActiveIndex((current) => (current + 1) % results.length);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      if (results.length === 0) return;
      setListOpen(true);
      setActiveIndex((current) => (current <= 0 ? results.length - 1 : current - 1));
    } else if (event.key === "Enter") {
      event.preventDefault();
      // with a single match there is nothing to choose: Enter takes it
      const picked = results[activeIndex] ?? (results.length === 1 ? results[0] : null);
      if (picked && listOpen) chooseHiker(picked);
    } else if (event.key === "Escape") {
      setListOpen(false);
      setActiveIndex(-1);
    }
  }

  // A guest has no email, so once the staff stop using this profile nobody can
  // find it again: it is removed first (the backend refuses it if it has bookings).
  async function removeGuestIfShown() {
    if (!hiker?.isGuest) return true;
    setLeaving(true);
    setLeaveError("");
    try {
      await deleteGuest(hiker.id);
      return true;
    } catch (err) {
      setLeaveError(err.message || "Could not remove the guest.");
      return false;
    } finally {
      setLeaving(false);
    }
  }

  async function cancelAndLeave() {
    if (leaving) return;
    if (await removeGuestIfShown()) navigate("/staff/slots");
  }

  async function changeHiker() {
    if (leaving) return;
    if (!(await removeGuestIfShown())) return;
    // clear the saved page state too, so a refresh cannot bring the removed guest back
    navigate("/staff/reserve", { replace: true, state: null });
    setHiker(null);
    setQuery("");
    setResults([]);
    setSearchError("");
    setActiveIndex(-1);
    setStep(0);
  }

  function addRequirement() {
    setRequirements((current) => [...current, { allergies: false, description: "" }]);
  }

  function updateRequirement(index, changes) {
    setStepError("");
    setRequirements((current) =>
      current.map((requirement, i) => (i === index ? { ...requirement, ...changes } : requirement))
    );
  }

  function removeRequirement(index) {
    setRequirements((current) => current.filter((_, i) => i !== index));
  }

  function goToReview() {
    if (!selectedSlot) {
      setStepError("Choose a date and a time.");
      return;
    }
    if (!isPartySizeValid) {
      setStepError(
        `Enter a whole number of guests between 1 and ${selectedSlot.availableSeats}.`
      );
      return;
    }
    if (requirements.some((requirement) => !requirement.description.trim())) {
      setStepError("Each requirement needs a description. Fill it in or remove it.");
      return;
    }
    setStepError("");
    setSaveError("");
    setStep(2);
  }

  async function confirm() {
    if (saving) return;
    setSaving(true);
    setSaveError("");
    try {
      const booking = await bookForHiker(hiker.id, {
        date: selectedDate,
        time: selectedSlot.time, // hut-local HH:MM:SS, as the backend expects
        partySize,
        requirements: requirements.map((requirement) => ({
          allergies: requirement.allergies,
          description: requirement.description.trim(),
        })),
      });
      setResult(booking);
    } catch (err) {
      setSaveError(err.message || "Could not create the reservation.");
    } finally {
      setSaving(false);
    }
  }

  function startOver() {
    setResult(null);
    setHiker(null);
    setQuery("");
    setResults([]);
    setSearchError("");
    setActiveIndex(-1);
    setSelectedDate(null);
    setSelectedSlotIndex("");
    setPartySizeInput("2");
    setRequirements([]);
    setStepError("");
    setSaveError("");
    setAvailability({}); // seats changed: load them again
    setStep(0);
  }

  if (result) {
    const tables = result.tables ?? [];
    const doneDate = result.date || selectedDate;
    const doneRequirements = requirements.map((requirement) => ({
      allergies: requirement.allergies,
      description: requirement.description.trim(),
    }));
    return (
      <div className="app-shell">
        <NavBar />

        {/* same look as the hiker's own confirmation page (ReservationDetail) */}
        <main className="summary-page">
          <div className="summary-intro">
            <span className="eyebrow">Reservation confirmed</span>
            <h1>Reservation created</h1>
            <p>
              {hiker.isGuest || !hiker.email
                ? "This guest has no email, so no confirmation was sent."
                : `A confirmation was sent to ${hiker.email}.`}
            </p>
          </div>

          <section className="summary-card card">
            <div className="success-icon">✓</div>

            <div className="card-label">Reservation successful</div>

            <h2>The reservation</h2>

            <div className="reservation-details">
              <div className="detail-row">
                <span>Hiker</span>
                <strong>{hiker.label}</strong>
              </div>

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
                <strong>{formatShortDate(doneDate)}</strong>
              </div>

              <div className="detail-row">
                <span>Time slot</span>
                <strong>
                  {selectedSlot
                    ? formatSlot(selectedSlot)
                    : formatTime(result.time)}
                </strong>
              </div>

              <div className="detail-row">
                <span>Party size</span>
                <strong>{guestsLabel(result.party_size ?? partySize)}</strong>
              </div>
            </div>

            {result.id && (
              <div className="reservation-id">Reservation #{result.id}</div>
            )}

            <section
              className="confirmed-requirements"
              aria-labelledby="confirmed-requirements-title"
            >
              <h3 id="confirmed-requirements-title">Party requirements</h3>

              {doneRequirements.length > 0 ? (
                <div className="confirmed-requirements-list">
                  {doneRequirements.map((requirement, index) => (
                    <article className="confirmed-requirement" key={index}>
                      <div className="confirmed-requirement-heading">
                        <strong>Requirement {index + 1}</strong>
                        {requirement.allergies ? (
                          <span className="allergy-status">Allergy flagged</span>
                        ) : (
                          <span className="dietary-status">Dietary requirement</span>
                        )}
                      </div>
                      <p>{requirement.description}</p>
                    </article>
                  ))}
                </div>
              ) : (
                <p className="no-requirements">
                  No special dietary requirements or allergies were added.
                </p>
              )}
            </section>
          </section>

          <div style={{ display: "flex", gap: 12, flexWrap: "wrap", justifyContent: "center" }}>
            <button type="button" className="secondary-button" onClick={startOver}>
              New reservation
            </button>
            <button
              type="button"
              className="secondary-button"
              onClick={() => navigate("/staff/slots")}
            >
              Back to slots
            </button>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <NavBar />

      <main className="rh-page">
        <header className="rh-header">
          <span className="rh-eyebrow">Staff</span>
          <h1>Reserve for a hiker</h1>
          <p>Enter a reservation received by phone, message or in person.</p>
        </header>

        <ol className="rh-steps" aria-label="Progress">
          {STEPS.map((name, index) => (
            <li
              key={name}
              className={index === step ? "current" : index < step ? "done" : ""}
              aria-current={index === step ? "step" : undefined}
            >
              <span className="rh-step-dot">{index < step ? "✓" : index + 1}</span>
              <span className="rh-step-name">{name}</span>
            </li>
          ))}
        </ol>

        {/* STEP 1: WHO */}
        {step === 0 && (
          <section className="rh-card">
            <h2>Who is the reservation for?</h2>

            {hiker ? (
              <div className="rh-found">
                <div>
                  <span className="rh-found-label">Hiker found</span>
                  <strong>{hiker.label}</strong>
                  <span className="rh-muted">Profile #{hiker.id}</span>
                </div>
                <button type="button" className="rh-link" onClick={changeHiker} disabled={leaving}>
                  {leaving ? "Removing…" : "Change"}
                </button>
              </div>
            ) : (
              <>
              <p className="rh-choice-title">Existing hiker</p>
              <div className="rh-search">
                <div className="rh-field">
                  <span id="rh-hiker-search-label">Search by name, email or phone number</span>
                  <div className="rh-search-row">
                <div className="rh-suggest">
                  <input
                    id="rh-hiker-search"
                    aria-labelledby="rh-hiker-search-label"
                    type="text"
                    role="combobox"
                    aria-expanded={listOpen && queryIsLongEnough}
                    aria-controls="rh-hiker-results"
                    aria-autocomplete="list"
                    aria-activedescendant={
                      activeIndex >= 0 ? `rh-hiker-option-${activeIndex}` : undefined
                    }
                    value={query}
                    onChange={(event) => {
                      setQuery(event.target.value);
                      setListOpen(true);
                      setActiveIndex(-1);
                    }}
                    onFocus={() => setListOpen(true)}
                    onBlur={() => setListOpen(false)}
                    onKeyDown={handleSearchKeyDown}
                    placeholder="Start typing, e.g. Rossi, anna@… or 347…"
                    autoComplete="off"
                    spellCheck={false}
                  />

                  {listOpen && queryIsLongEnough && results.length > 0 && (
                    <ul className="rh-suggest-list" id="rh-hiker-results" role="listbox">
                      {results.map((candidate, index) => (
                        <li
                          key={candidate.id}
                          id={`rh-hiker-option-${index}`}
                          role="option"
                          aria-selected={index === activeIndex}
                          className={`rh-suggest-item ${index === activeIndex ? "active" : ""}`}
                          // mousedown, not click: the input would lose focus and close the list first
                          onMouseDown={(event) => {
                            event.preventDefault();
                            chooseHiker(candidate);
                          }}
                          onMouseEnter={() => setActiveIndex(index)}
                        >
                          <strong>{hikerName(candidate) || candidate.email}</strong>
                          <span className="rh-muted">
                            {[hikerName(candidate) ? candidate.email : null, candidate.mobile_number]
                              .filter(Boolean)
                              .join(" · ")}
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
                  </div>
                </div>

                <p className="rh-muted rh-suggest-status" role="status" aria-live="polite">
                  {!queryIsLongEnough
                    ? `Type at least ${MIN_QUERY_LENGTH} characters.`
                    : searching
                      ? "Searching…"
                      : results.length > 0
                        ? `${results.length} ${results.length === 1 ? "hiker" : "hikers"} found. Pick one to continue.`
                        : ""}
                </p>

                {searchError && (
                  <div className="rh-error" role="alert">
                    {searchError}
                  </div>
                )}

                {queryIsLongEnough && !searching && !searchError && results.length === 0 && (
                  <div className="rh-notfound" role="status">
                    <strong>No hiker matches “{trimmedQuery}”.</strong>
                    <p>
                      Check the spelling, or create a profile first: a full hiker with an account,
                      or a quick guest with just a name.
                    </p>
                  </div>
                )}
              </div>

              <div className="rh-or">or</div>

              <div className="rh-new">
                <div>
                  <p className="rh-choice-title">New hiker or no email?</p>
                  <p className="rh-muted">
                    Create a profile with the full details, or quickly add a guest with just a
                    name.
                  </p>
                </div>
                <Link to="/staff/create-hiker" className="rh-btn rh-btn--ghost">
                  Create a profile
                </Link>
              </div>
              </>
            )}

            {leaveError && (
              <div className="rh-error" role="alert">
                {leaveError}
              </div>
            )}

            <div className="rh-actions">
              {hiker?.isGuest ? (
                <button
                  type="button"
                  className="rh-btn rh-btn--danger"
                  onClick={cancelAndLeave}
                  disabled={leaving}
                >
                  Cancel
                </button>
              ) : (
                <Link to="/staff/slots" className="rh-btn rh-btn--danger">
                  Cancel
                </Link>
              )}
              {/* only when a hiker is already chosen (coming back from step 2) */}
              {hiker && (
                <button
                  type="button"
                  className="rh-btn rh-btn--primary"
                  onClick={() => setStep(1)}
                >
                  Next
                </button>
              )}
            </div>
          </section>
        )}

        {/* STEP 2: WHEN, HOW MANY, REQUIREMENTS */}
        {step === 1 && (
          <section className="rh-card">
            <div className="rh-for">
              Reservation for <strong>{hiker.label}</strong>
            </div>

            <h2>Date and time</h2>
            {loadingSlots && <p className="rh-muted">Loading available dates…</p>}
            {slotsError && (
              <div className="rh-error" role="alert">
                {slotsError}
              </div>
            )}
            {!loadingSlots && !slotsError && dateKeys.length === 0 && (
              <p className="rh-muted">There are no available slots right now.</p>
            )}

            {dateKeys.length > 0 && (
              <div className="rh-dates" role="listbox" aria-label="Available dates">
                {dateKeys.map((key) => {
                  const day = parseKey(key);
                  return (
                    <button
                      type="button"
                      key={key}
                      role="option"
                      aria-selected={selectedDate === key}
                      className={`rh-date ${selectedDate === key ? "selected" : ""}`}
                      onClick={() => {
                        setSelectedDate(key);
                        setSelectedSlotIndex("");
                        setStepError("");
                      }}
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
              <div className="rh-slots">
                {selectedSlots.map((slot, index) => (
                  <button
                    type="button"
                    key={`${slot.start}-${slot.end}-${index}`}
                    className={`rh-slot ${String(index) === selectedSlotIndex ? "selected" : ""}`}
                    onClick={() => {
                      setSelectedSlotIndex(String(index));
                      setStepError("");
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

            <h2>Party size</h2>
            <div className="rh-stepper">
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
                onChange={(event) => {
                  setPartySizeInput(event.target.value);
                  setStepError("");
                }}
                aria-label="Number of guests"
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
              {selectedSlot && (
                <span className="rh-muted">Up to {selectedSlot.availableSeats} for this time</span>
              )}
            </div>

            <h2>
              Requirements <small>optional</small>
            </h2>
            {requirements.map((requirement, index) => (
              <div className="rh-req" key={index}>
                <label className="rh-check">
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
                  className="rh-req-text"
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
                  className="rh-req-remove"
                  onClick={() => removeRequirement(index)}
                  aria-label={`Remove requirement ${index + 1}`}
                >
                  Remove
                </button>
              </div>
            ))}
            <button type="button" className="rh-link" onClick={addRequirement}>
              + Add a requirement
            </button>

            {stepError && (
              <div className="rh-error" role="alert">
                {stepError}
              </div>
            )}

            <div className="rh-actions">
              <button type="button" className="rh-btn rh-btn--ghost" onClick={() => setStep(0)}>
                Back
              </button>
              <button type="button" className="rh-btn rh-btn--primary" onClick={goToReview}>
                Review
              </button>
            </div>
          </section>
        )}

        {/* STEP 3: REVIEW */}
        {step === 2 && selectedSlot && (
          <section className="rh-card">
            <h2>Check the reservation</h2>

            <dl className="rh-list">
              <div>
                <dt>Hiker</dt>
                <dd>{hiker.label}</dd>
              </div>
              <div>
                <dt>Date</dt>
                <dd>{formatDate(selectedDate)}</dd>
              </div>
              <div>
                <dt>Time</dt>
                <dd>{formatSlot(selectedSlot)}</dd>
              </div>
              <div>
                <dt>Party size</dt>
                <dd>{guestsLabel(partySize)}</dd>
              </div>
              <div>
                <dt>Requirements</dt>
                <dd>
                  {requirements.length === 0
                    ? "None"
                    : requirements
                        .map(
                          (requirement) =>
                            `${requirement.allergies ? "Allergy: " : ""}${requirement.description.trim()}`
                        )
                        .join("; ")}
                </dd>
              </div>
            </dl>

            {saveError && (
              <div className="rh-error" role="alert">
                {saveError}
              </div>
            )}

            <div className="rh-actions">
              <button
                type="button"
                className="rh-btn rh-btn--ghost"
                onClick={() => setStep(1)}
                disabled={saving}
              >
                Back
              </button>
              <button
                type="button"
                className="rh-btn rh-btn--primary"
                onClick={confirm}
                disabled={saving}
              >
                {saving ? "Saving..." : "Confirm"}
              </button>
            </div>
          </section>
        )}
      </main>
    </div>
  );
}
