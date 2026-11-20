import React, { useEffect, useState } from "react";
import { Link, Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { resolveAfterLogin } from "../auth/roles";
import AuthLayout from "../components/AuthLayout";
import FormField, { PasswordField } from "../components/FormField";

const EMAIL_PATTERN = /^\S+@\S+\.\S+$/;

function validate(email, password) {
  const errors = {};
  if (!email.trim()) errors.email = "Enter your email address.";
  else if (!EMAIL_PATTERN.test(email.trim())) errors.email = "Enter a valid email address.";
  if (!password) errors.password = "Enter your password.";
  return errors;
}

export default function Login() {
  const { user, loading, login } = useAuth();
  const location = useLocation();

  // set by RequireRole (the page the user wanted) and by the registration page
  const from = location.state?.from;
  const notice = location.state?.notice;

  const [email, setEmail] = useState(location.state?.email ?? "");
  const [password, setPassword] = useState("");
  const [fieldErrors, setFieldErrors] = useState({});
  const [formError, setFormError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    document.title = "Log in · Mountain Hut";
  }, []);

  if (loading) {
    return (
      <div className="au-status" role="status">
        Loading…
      </div>
    );
  }

  // logged in with the password sent by email: the new one must be chosen before going on.
  // `password` is still the temporary one just typed, empty after a page reload
  if (user?.must_change_password) {
    return <ChangePasswordStep temporaryPassword={password} />;
  }

  // already logged in (or just logged in): go where the user belongs
  if (user) {
    return <Navigate to={resolveAfterLogin(user, from)} replace />;
  }

  async function handleSubmit(event) {
    event.preventDefault();
    if (submitting) return;

    setFormError("");
    const errors = validate(email, password);
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;

    setSubmitting(true);
    try {
      await login(email.trim(), password);
      // `user` is now set: the redirect above happens on the next render
    } catch (error) {
      setFieldErrors(error.fieldErrors ?? {});
      setFormError(error.message || "Something went wrong. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthLayout
      title="Log in"
      subtitle="Welcome back. Log in to book a table or manage the hut."
      footer={
        <>
          No account yet?{" "}
          <Link to="/register" state={{ from }}>
            Register
          </Link>
        </>
      }
    >
      {notice && (
        <div className="au-notice" role="status">
          {notice}
        </div>
      )}

      <form className="au-form" onSubmit={handleSubmit} noValidate>
        {formError && (
          <div className="au-alert" role="alert">
            {formError}
          </div>
        )}

        <FormField
          label="Email"
          type="email"
          name="email"
          autoComplete="username"
          inputMode="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          error={fieldErrors.email}
          autoFocus
        />

        <PasswordField
          label="Password"
          name="password"
          autoComplete="current-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          error={fieldErrors.password}
        />

        <button
          type="submit"
          className="au-btn au-btn--primary au-btn--block"
          disabled={submitting}
        >
          {submitting ? "Logging in…" : "Log in"}
        </button>
        
        <Link to="/forgot-password" className="au-link au-recover-password">
          Recover password
        </Link>
      </form>
    </AuthLayout>
  );
}

const MIN_PASSWORD_LENGTH = 8; // same rule as the backend (ChangePasswordRequest)

function validateNewPassword(current, newPassword, confirm) {
  const errors = {};
  if (!current) errors.current = "Enter the password you received by email.";
  if (!newPassword) errors.newPassword = "Choose a new password.";
  else if (newPassword.length < MIN_PASSWORD_LENGTH)
    errors.newPassword = `Use at least ${MIN_PASSWORD_LENGTH} characters.`;
  else if (newPassword === current)
    errors.newPassword = "The new password must be different from the one you received.";
  if (!errors.newPassword && confirm !== newPassword)
    errors.confirm = "The two passwords do not match.";
  return errors;
}

// Shown instead of the login form when the account was created by the staff and the
// password arrived by email: the user types the new one twice. Once it's changed the
// server sends a new session cookie and the user is let in (Login redirects as usual).
function ChangePasswordStep({ temporaryPassword }) {
  const { user, changePassword, logout } = useAuth();

  // after a page reload the temporary password is no longer known: ask for it again
  const askCurrent = !temporaryPassword;
  const [current, setCurrent] = useState(temporaryPassword);
  const [newPassword, setNewPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [fieldErrors, setFieldErrors] = useState({});
  const [formError, setFormError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    document.title = "Choose a new password · Mountain Hut";
  }, []);

  async function handleSubmit(event) {
    event.preventDefault();
    if (submitting) return;

    setFormError("");
    const errors = validateNewPassword(current, newPassword, confirm);
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;

    setSubmitting(true);
    try {
      await changePassword(current, newPassword);
      // `user.must_change_password` is now false: Login redirects on the next render
    } catch (error) {
      const backend = error.fieldErrors ?? {};
      setFieldErrors({ current: backend.current_password, newPassword: backend.new_password });
      setFormError(error.message || "Something went wrong. Please try again.");
      setSubmitting(false);
    }
  }

  return (
    <AuthLayout
      title="Choose a new password"
      subtitle={`Welcome, ${user.username}. The password you received by email is temporary: choose your own to continue.`}
      footer={
        <>
          Not you?{" "}
          <button type="button" className="au-link" onClick={logout}>
            Log out
          </button>
        </>
      }
    >
      <form className="au-form" onSubmit={handleSubmit} noValidate>
        {formError && (
          <div className="au-alert" role="alert">
            {formError}
          </div>
        )}

        {askCurrent && (
          <PasswordField
            label="Password received by email"
            name="current_password"
            autoComplete="current-password"
            value={current}
            onChange={(event) => setCurrent(event.target.value)}
            error={fieldErrors.current}
            autoFocus
          />
        )}

        <PasswordField
          label="New password"
          name="new_password"
          autoComplete="new-password"
          value={newPassword}
          onChange={(event) => setNewPassword(event.target.value)}
          error={fieldErrors.newPassword}
          hint={`At least ${MIN_PASSWORD_LENGTH} characters.`}
          autoFocus={!askCurrent}
        />

        <PasswordField
          label="Repeat the new password"
          name="confirm_password"
          autoComplete="new-password"
          value={confirm}
          onChange={(event) => setConfirm(event.target.value)}
          error={fieldErrors.confirm}
        />

        <button
          type="submit"
          className="au-btn au-btn--primary au-btn--block"
          disabled={submitting}
        >
          {submitting ? "Saving…" : "Save and continue"}
        </button>
      </form>
    </AuthLayout>
  );
}
