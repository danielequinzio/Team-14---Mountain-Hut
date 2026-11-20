import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import AuthLayout from "../components/AuthLayout";
import FormField from "../components/FormField";
import { requestPasswordReset } from "../api";

const EMAIL_PATTERN = /^\S+@\S+\.\S+$/;

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [emailError, setEmailError] = useState("");
  const [formError, setFormError] = useState("");
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    document.title = "Recover password · Mountain Hut";
  }, []);

  async function handleSubmit(event) {
    event.preventDefault();
    setEmailError("");
    setFormError("");
    setMessage("");

    const normalizedEmail = email.trim();
    if (!normalizedEmail) {
      setEmailError("Enter your email address.");
      return;
    }
    if (!EMAIL_PATTERN.test(normalizedEmail)) {
      setEmailError("Enter a valid email address.");
      return;
    }

    setSubmitting(true);
    try {
      const result = await requestPasswordReset(normalizedEmail);
      setMessage(
        result?.detail ||
          "If an account is registered with this email, a password reset link has been sent."
      );
    } catch (error) {
      setFormError(error.message || "Could not request a password reset. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthLayout
      title="Recover password"
      subtitle="Enter the email address associated with your account and we'll send you a link to reset your password."
      footer={
        <>
          Remembered your password? <Link to="/login">Back to log in</Link>
        </>
      }
    >
      <form className="au-form" onSubmit={handleSubmit} noValidate>
        {formError && <div className="au-alert" role="alert">{formError}</div>}
        {message && <div className="au-notice" role="status">{message}</div>}

        {!message && (
          <>
            <FormField
              label="Email"
              type="email"
              name="email"
              autoComplete="email"
              inputMode="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              error={emailError}
              autoFocus
            />
            <button
              type="submit"
              className="au-btn au-btn--primary au-btn--block"
              disabled={submitting}
            >
              {submitting ? "Sending…" : "Send reset link"}
            </button>
          </>
        )}
      </form>
    </AuthLayout>
  );
}
