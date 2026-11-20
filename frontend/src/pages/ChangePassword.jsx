import React, { useState } from "react";
import { Link } from "react-router-dom";
import NavBar from "../components/NavBar";
import { useAuth } from "../auth/AuthContext";
import "./ChangePassword.css";

// A logged-in user (hiker, employee or warden) chooses a new password.
// POST /auth/change-password needs the current password and a new one of at
// least 8 characters. (The forced change after a temporary password is a
// different screen: it lives on the login page.)

const MIN_PASSWORD_LENGTH = 8; // same rule as the backend (ChangePasswordRequest)

function validate(current, newPassword, confirm) {
  const errors = {};
  if (!current) errors.current = "Enter your current password.";
  if (!newPassword) errors.newPassword = "Choose a new password.";
  else if (newPassword.length < MIN_PASSWORD_LENGTH)
    errors.newPassword = `Use at least ${MIN_PASSWORD_LENGTH} characters.`;
  else if (newPassword === current)
    errors.newPassword = "The new password must be different from the current one.";
  if (!errors.newPassword && confirm !== newPassword)
    errors.confirm = "The two passwords do not match.";
  return errors;
}

export default function ChangePassword() {
  const { user, changePassword } = useAuth();

  const [current, setCurrent] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [show, setShow] = useState(false);
  const [fieldErrors, setFieldErrors] = useState({});
  const [formError, setFormError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  async function submit(event) {
    event.preventDefault();
    if (submitting) return;

    setFormError("");
    const errors = validate(current, newPassword, confirm);
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;

    setSubmitting(true);
    try {
      await changePassword(current, newPassword);
      setCurrent("");
      setNewPassword("");
      setConfirm("");
      setDone(true);
    } catch (error) {
      const message = error.message || "Something went wrong. Please try again.";
      if (/current password/i.test(message)) {
        setFieldErrors({ current: message }); // "Current password is wrong"
      } else {
        const backend = error.fieldErrors ?? {};
        setFieldErrors({ newPassword: backend.new_password });
        setFormError(message);
      }
    } finally {
      setSubmitting(false);
    }
  }

  function edit(setter) {
    return (event) => {
      setter(event.target.value);
      setDone(false);
      setFormError("");
    };
  }

  const type = show ? "text" : "password";

  return (
    <div className="app-shell">
      <NavBar />

      <main className="cp-page">
        <section className="cp-card">
          <span className="cp-eyebrow">Account</span>
          <h1>Change password</h1>
          <p className="cp-sub">
            Signed in as <strong>{user?.username}</strong>. Choose a new password of at least{" "}
            {MIN_PASSWORD_LENGTH} characters.
          </p>

          {done && (
            <div className="cp-success" role="status">
              <strong>Password changed.</strong> Use the new password the next time you log in.
            </div>
          )}

          <form className="cp-form" onSubmit={submit} noValidate>
            <label className="cp-field">
              <span>Current password</span>
              <input
                type={type}
                name="current_password"
                autoComplete="current-password"
                value={current}
                onChange={edit(setCurrent)}
                aria-invalid={Boolean(fieldErrors.current)}
              />
              {fieldErrors.current && <em className="cp-error">{fieldErrors.current}</em>}
            </label>

            <label className="cp-field">
              <span>New password</span>
              <input
                type={type}
                name="new_password"
                autoComplete="new-password"
                value={newPassword}
                onChange={edit(setNewPassword)}
                aria-invalid={Boolean(fieldErrors.newPassword)}
              />
              {fieldErrors.newPassword && <em className="cp-error">{fieldErrors.newPassword}</em>}
            </label>

            <label className="cp-field">
              <span>Repeat the new password</span>
              <input
                type={type}
                name="confirm_password"
                autoComplete="new-password"
                value={confirm}
                onChange={edit(setConfirm)}
                aria-invalid={Boolean(fieldErrors.confirm)}
              />
              {fieldErrors.confirm && <em className="cp-error">{fieldErrors.confirm}</em>}
            </label>

            <label className="cp-check">
              <input type="checkbox" checked={show} onChange={(e) => setShow(e.target.checked)} />
              <span>Show passwords</span>
            </label>

            {formError && (
              <div className="cp-alert" role="alert">
                {formError}
              </div>
            )}

            <div className="cp-actions">
              <Link to="/" className="cp-btn cp-btn--ghost">
                Back home
              </Link>
              <button type="submit" className="cp-btn cp-btn--primary" disabled={submitting}>
                {submitting ? "Saving..." : "Change password"}
              </button>
            </div>
          </form>
        </section>
      </main>
    </div>
  );
}
