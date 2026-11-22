import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import NavBar from "../components/NavBar";
import { deleteGuest, registerGuest, registerHiker } from "../api";
import "./CreateHiker.css";

// MH-07: staff create a hiker profile. A hiker has an account (the temporary
// password is emailed to them); a guest has no email and cannot log in, they
// only exist to be put in a booking. A guest needs only a name: the phone is
// optional (the backend accepts an empty phone for a guest).

const EMPTY_FORM = {
  name: "",
  surname: "",
  email: "",
  mobileNumber: "",
  notes: "",
  emergencyContact: "",
};

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function CreateHiker() {
  const navigate = useNavigate();
  const [kind, setKind] = useState("hiker"); // "hiker" | "guest"
  const [form, setForm] = useState(EMPTY_FORM);
  const [touched, setTouched] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [created, setCreated] = useState(null); // { kind, name, response }
  const [removing, setRemoving] = useState(false);
  const [removeError, setRemoveError] = useState("");

  const isHiker = kind === "hiker";

  function setField(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
    setError("");
  }

  function chooseKind(next) {
    setKind(next);
    setTouched(false);
    setError("");
  }

  const problems = {};
  if (!form.name.trim()) problems.name = "Enter the name.";
  if (!form.surname.trim()) problems.surname = "Enter the surname.";
  // the story: a guest is "name + optional phone"; a hiker profile needs the full details
  if (isHiker && !form.mobileNumber.trim()) problems.mobileNumber = "Enter a mobile number.";
  if (isHiker) {
    if (!form.email.trim()) problems.email = "Enter the email address.";
    else if (!EMAIL_PATTERN.test(form.email.trim())) problems.email = "Enter a valid email address.";
  }
  const hasProblems = Object.keys(problems).length > 0;

  async function submit(event) {
    event.preventDefault();
    setTouched(true);
    if (hasProblems || saving) return;

    setSaving(true);
    setError("");
    try {
      const name = form.name.trim();
      const surname = form.surname.trim();
      const mobileNumber = form.mobileNumber.trim();

      const response = isHiker
        ? await registerHiker({
            name,
            surname,
            email: form.email.trim(),
            mobileNumber,
            notes: form.notes.trim(),
            emergencyContact: form.emergencyContact.trim(),
          })
        : await registerGuest({ name, surname, mobileNumber });

      setCreated({ kind, name: `${name} ${surname}`, response });
    } catch (err) {
      setError(err.message || "Could not create the profile.");
    } finally {
      setSaving(false);
    }
  }

  function createAnother() {
    setCreated(null);
    setForm(EMPTY_FORM);
    setTouched(false);
    setError("");
  }

  // A guest has no email, so once the staff leave this page nobody can find them
  // again: "Cancel" removes the guest and goes back to where the staff started.
  async function cancelGuest() {
    if (removing) return;
    setRemoving(true);
    setRemoveError("");
    try {
      await deleteGuest(created.response.id);
      navigate("/staff/reserve");
    } catch (err) {
      setRemoveError(err.message || "Could not remove the guest.");
      setRemoving(false);
    }
  }

  const fieldError = (field) => (touched && problems[field] ? problems[field] : "");

  if (created) {
    const createdHiker = created.kind === "hiker";
    return (
      <div className="app-shell">
        <NavBar />

        <main className="ch-page">
          <section className="ch-card ch-done">
            <div className="ch-done-icon">✓</div>
            <span className="ch-eyebrow">{createdHiker ? "Hiker created" : "Guest created"}</span>
            <h1>{created.name}</h1>

            <dl className="ch-done-list">
              <div>
                <dt>Profile ID</dt>
                <dd>#{created.response.id}</dd>
              </div>
              <div>
                <dt>Email</dt>
                <dd>{created.response.email || "No email (guest)"}</dd>
              </div>
            </dl>

            <p className="ch-done-note">
              {createdHiker
                ? "A temporary password was sent to the hiker's email. They must choose a new password the first time they log in."
                : "This guest has no account and cannot log in. Reserve a table now, or cancel to remove this guest."}
            </p>

            {removeError && (
              <div className="ch-error" role="alert">
                {removeError}
              </div>
            )}

            <div className="ch-done-actions">
              {createdHiker ? (
                <>
                  <button type="button" className="ch-btn ch-btn--ghost" onClick={createAnother}>
                    Create another
                  </button>
                  <Link to="/staff/slots" className="ch-btn ch-btn--ghost">
                    Back to slots
                  </Link>
                </>
              ) : (
                <button
                  type="button"
                  className="ch-btn ch-btn--ghost"
                  onClick={cancelGuest}
                  disabled={removing}
                >
                  {removing ? "Removing…" : "Cancel"}
                </button>
              )}
              <Link
                to="/staff/reserve"
                state={{
                  hiker: {
                    id: created.response.id,
                    email: created.response.email,
                    label: created.name,
                    isGuest: Boolean(created.response.is_guest),
                  },
                }}
                className="ch-btn ch-btn--primary"
              >
                Reserve a table
              </Link>
            </div>
          </section>
        </main>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <NavBar />

      <main className="ch-page">
        <header className="ch-header">
          <span className="ch-eyebrow">Staff</span>
          <h1>Create a hiker profile</h1>
          <p>Add a hiker so you can book a table for them.</p>
        </header>

        <section className="ch-card">
          <div className="ch-switch" role="tablist" aria-label="Type of profile">
            <button
              type="button"
              role="tab"
              aria-selected={isHiker}
              className={isHiker ? "active" : ""}
              onClick={() => chooseKind("hiker")}
            >
              <strong>Hiker</strong>
              <span>With an email and an account</span>
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={!isHiker}
              className={!isHiker ? "active" : ""}
              onClick={() => chooseKind("guest")}
            >
              <strong>Guest</strong>
              <span>No email, no account</span>
            </button>
          </div>

          <form className="ch-form" onSubmit={submit} noValidate>
            <div className="ch-grid">
              <label className="ch-field">
                <span>Name</span>
                <input
                  type="text"
                  value={form.name}
                  onChange={(event) => setField("name", event.target.value)}
                  autoComplete="off"
                  aria-invalid={Boolean(fieldError("name"))}
                />
                {fieldError("name") && <em className="ch-field-error">{fieldError("name")}</em>}
              </label>

              <label className="ch-field">
                <span>Surname</span>
                <input
                  type="text"
                  value={form.surname}
                  onChange={(event) => setField("surname", event.target.value)}
                  autoComplete="off"
                  aria-invalid={Boolean(fieldError("surname"))}
                />
                {fieldError("surname") && <em className="ch-field-error">{fieldError("surname")}</em>}
              </label>
            </div>

            {isHiker && (
              <label className="ch-field">
                <span>Email</span>
                <input
                  type="email"
                  value={form.email}
                  onChange={(event) => setField("email", event.target.value)}
                  autoComplete="off"
                  placeholder="hiker@example.com"
                  aria-invalid={Boolean(fieldError("email"))}
                />
                {fieldError("email") && <em className="ch-field-error">{fieldError("email")}</em>}
              </label>
            )}

            <label className="ch-field">
              <span>
                Mobile number {!isHiker && <small>optional</small>}
              </span>
              <input
                type="tel"
                value={form.mobileNumber}
                onChange={(event) => setField("mobileNumber", event.target.value)}
                autoComplete="off"
                placeholder="+39 333 123 4567"
                aria-invalid={Boolean(fieldError("mobileNumber"))}
              />
              {fieldError("mobileNumber") && (
                <em className="ch-field-error">{fieldError("mobileNumber")}</em>
              )}
            </label>

            {isHiker && (
              <>
                <label className="ch-field">
                  <span>
                    Emergency contact <small>optional</small>
                  </span>
                  <input
                    type="text"
                    value={form.emergencyContact}
                    onChange={(event) => setField("emergencyContact", event.target.value)}
                    autoComplete="off"
                    placeholder="Name and phone number"
                  />
                </label>

                <label className="ch-field">
                  <span>
                    Notes <small>optional</small>
                  </span>
                  <textarea
                    rows={3}
                    value={form.notes}
                    onChange={(event) => setField("notes", event.target.value)}
                  />
                </label>

                <p className="ch-hint">
                  The hiker receives a temporary password by email and must change it at the first
                  login.
                </p>
              </>
            )}

            {!isHiker && (
              <p className="ch-hint">
                A guest has no email, so no account and no confirmation emails are sent.
              </p>
            )}

            {error && (
              <div className="ch-error" role="alert">
                {error}
              </div>
            )}

            <div className="ch-actions">
              <Link to="/staff/slots" className="ch-btn ch-btn--ghost">
                Cancel
              </Link>
              <button type="submit" className="ch-btn ch-btn--primary" disabled={saving}>
                {saving ? "Creating..." : isHiker ? "Create hiker" : "Create guest"}
              </button>
            </div>
          </form>
        </section>
      </main>
    </div>
  );
}
