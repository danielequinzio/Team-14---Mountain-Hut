import React, { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import NavBar from "../components/NavBar";
import { bookForHiker, deleteGuest, findHikerByEmail, getAvailability } from "../api";
import "./ReserveForHiker.css";

// MH-07: an employee enters a reservation for a hiker (phone, in person...).
// Step 1: who (find by email, or arrive from "Create hiker" with the profile).
// Step 2: when, how many, requirements. Step 3: review and confirm.

const STEPS = ["Hiker", "Reservation", "Confirm"];
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

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
  const [email, setEmail] = useState("");
  const [searching, setSearching] = useState(false);
  const [notFound, setNotFound] = useState(false);
  const [searchError, setSearchError] = useState("");

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

  async function findHiker(event) {
    event.preventDefault();
    const value = email.trim();
    setNotFound(false);
    setSearchError("");

    if (!EMAIL_PATTERN.test(value)) {
      setSearchError("Enter a valid email address.");
      return;
    }

    setSearching(true);
    try {
      const found = await findHikerByEmail(value);
      if (!found) {
        setNotFound(true);
        return;
      }
      setHiker({ id: found.id, email: found.email, label: found.email, isGuest: found.is_guest });
      setStep(1); // found: straight to the reservation details
    } catch (err) {
      setSearchError(err.message || "Could not look the hiker up.");
    } finally {
      setSearching(false);
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
    setEmail("");
    setNotFound(false);
    setSearchError("");
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
    setEmail("");
    setNotFound(false);
    setSearchError("");
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
              <form className="rh-search" onSubmit={findHiker} noValidate>
                <label className="rh-field">
                  <span>Find them by the email they registered with</span>
                  <div className="rh-search-row">
                    <input
                      type="email"
                      value={email}
                      onChange={(event) => {
                        setEmail(event.target.value);
                        setNotFound(false);
                        setSearchError("");
                      }}
                      placeholder="hiker@example.com"
                      autoComplete="off"
                    />
                    <button type="submit" className="rh-btn rh-btn--primary" disabled={searching}>
                      {searching ? "Searching..." : "Find hiker"}
                    </button>
                  </div>
                </label>

                {searchError && (
                  <div className="rh-error" role="alert">
                    {searchError}
                  </div>
                )}

                {notFound && (
                  <div className="rh-notfound" role="status">
                    <strong>No hiker has this email.</strong>
                    <p>
                      Create a profile first: a full hiker with an account, or a quick guest with
                      just a name.
                    </p>
                  </div>
                )}
              </form>

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
