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
      </form>
    </AuthLayout>
  );
}
