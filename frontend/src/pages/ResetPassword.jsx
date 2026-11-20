import React, { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import NavBar from "../components/NavBar";
import { resetPassword } from "../auth/authApi";
import "./ChangePassword.css";

// Anyone (no login needed) sets a new password using a one-time reset token,
// e.g. from an emailed link: /reset-password?token=abc123
// POST /auth/reset-password { token, new_password }
// The token proves who the user is, so no current password is asked for.

const MIN_PASSWORD_LENGTH = 8; // same rule as the backend

function validate(newPassword, confirm) {
  const errors = {};
  if (!newPassword) errors.newPassword = "Choose a new password.";
  else if (newPassword.length < MIN_PASSWORD_LENGTH)
    errors.newPassword = `Use at least ${MIN_PASSWORD_LENGTH} characters.`;
  if (!errors.newPassword && confirm !== newPassword)
    errors.confirm = "The two passwords do not match.";
  return errors;
}

export default function ResetPassword() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token");

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
    const errors = validate(newPassword, confirm);
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;

    setSubmitting(true);
    try {
      await resetPassword(token, newPassword);
      setNewPassword("");
      setConfirm("");
      setDone(true);
    } catch (error) {
      const backend = error.fieldErrors ?? {};
      setFieldErrors({ newPassword: backend.new_password });
      setFormError(error.message || "Something went wrong. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  function edit(setter) {
    return (event) => {
      setter(event.target.value);
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
          <h1>Reset password</h1>

          {!token ? (
            <>
              <div className="cp-alert" role="alert">
                This reset link is missing its token. Request a new link and try again.
              </div>
              <div className="cp-actions">
                <Link to="/login" className="cp-btn cp-btn--ghost">
                  Back to login
                </Link>
              </div>
            </>
          ) : done ? (
            <>
              <div className="cp-success" role="status">
                <strong>Password changed.</strong> You can now log in with your new password.
              </div>
              <div className="cp-actions">
                <Link to="/login" className="cp-btn cp-btn--primary">
                  Go to login
                </Link>
              </div>
            </>
          ) : (
            <>
              <p className="cp-sub">
                Choose a new password of at least {MIN_PASSWORD_LENGTH} characters.
              </p>

              <form className="cp-form" onSubmit={submit} noValidate>
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
                  {fieldErrors.newPassword && (
                    <em className="cp-error">{fieldErrors.newPassword}</em>
                  )}
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
                  <input
                    type="checkbox"
                    checked={show}
                    onChange={(e) => setShow(e.target.checked)}
                  />
                  <span>Show passwords</span>
                </label>

                {formError && (
                  <div className="cp-alert" role="alert">
                    {formError}
                  </div>
                )}

                <div className="cp-actions">
                  <Link to="/login" className="cp-btn cp-btn--ghost">
                    Back to login
                  </Link>
                  <button type="submit" className="cp-btn cp-btn--primary" disabled={submitting}>
                    {submitting ? "Saving..." : "Reset password"}
                  </button>
                </div>
              </form>
            </>
          )}
        </section>
      </main>
    </div>
  );
}
