import React, { useEffect, useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { resolveAfterLogin } from "../auth/roles";
import AuthLayout from "../components/AuthLayout";
import FormField, { PasswordField } from "../components/FormField";

const EMAIL_PATTERN = /^\S+@\S+\.\S+$/;
const MIN_PASSWORD_LENGTH = 8; // same rule as the backend (RegisterRequest)

const EMPTY_FORM = {
  name: "",
  surname: "",
  email: "",
  mobile_number: "",
  password: "",
  confirm: "",
  notes: "",
  emergency_contact: "",
};

function countDigits(text) {
  return (text.match(/\d/g) ?? []).length;
}

function validate(values) {
  const errors = {};
  if (!values.name.trim()) errors.name = "Enter your first name.";
  if (!values.surname.trim()) errors.surname = "Enter your last name.";

  if (!values.email.trim()) errors.email = "Enter your email address.";
  else if (!EMAIL_PATTERN.test(values.email.trim())) errors.email = "Enter a valid email address.";

  if (!values.mobile_number.trim()) errors.mobile_number = "Enter your mobile number.";
  else if (countDigits(values.mobile_number) < 6) {
    errors.mobile_number = "Enter a valid mobile number, for example +39 333 123 4567.";
  }

  if (values.password.length < MIN_PASSWORD_LENGTH) {
    errors.password = `Use at least ${MIN_PASSWORD_LENGTH} characters.`;
  }
  if (values.confirm !== values.password) errors.confirm = "The passwords do not match.";

  return errors;
}

export default function Register() {
  const { user, loading, register, login } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const from = location.state?.from;

  const [values, setValues] = useState(EMPTY_FORM);
  const [fieldErrors, setFieldErrors] = useState({});
  const [formError, setFormError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    document.title = "Register · Mountain Hut";
  }, []);

  if (loading) {
    return (
      <div className="au-status" role="status">
        Loading…
      </div>
    );
  }

  if (user) {
    return <Navigate to={resolveAfterLogin(user, from)} replace />;
  }

  function update(field) {
    return (event) => {
      setValues((current) => ({ ...current, [field]: event.target.value }));
    };
  }

  async function handleSubmit(event) {
    event.preventDefault();
    if (submitting) return;

    setFormError("");
    const errors = validate(values);
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;

    const payload = {
      name: values.name.trim(),
      surname: values.surname.trim(),
      email: values.email.trim(),
      mobile_number: values.mobile_number.trim(),
      password: values.password,
      notes: values.notes.trim() || null,
      emergency_contact: values.emergency_contact.trim() || null,
    };

    setSubmitting(true);
    try {
      await register(payload);
    } catch (error) {
      if (error.status === 409) {
        // "Email already registered"
        setFieldErrors({ email: "This email is already registered. Try logging in." });
      } else {
        setFieldErrors(error.fieldErrors ?? {});
        setFormError(error.message || "Something went wrong. Please try again.");
      }
      setSubmitting(false);
      return;
    }

    // The account exists. Registering does not log in, so do it now.
    try {
      await login(payload.email, payload.password);
      // `user` is now set: the redirect above happens on the next render
    } catch {
      navigate("/login", {
        replace: true,
        state: {
          from,
          email: payload.email,
          notice: "Your account was created. Please log in to continue.",
        },
      });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthLayout
      wide
      title="Create your account"
      subtitle="Register as a hiker to book tables at the hut."
      footer={
        <>
          Already have an account?{" "}
          <Link to="/login" state={{ from }}>
            Log in
          </Link>
        </>
      }
    >
      <form className="au-form" onSubmit={handleSubmit} noValidate>
        {formError && (
          <div className="au-alert" role="alert">
            {formError}
          </div>
        )}

        <div className="au-grid-2">
          <FormField
            label="First name"
            name="name"
            autoComplete="given-name"
            value={values.name}
            onChange={update("name")}
            error={fieldErrors.name}
            autoFocus
          />
          <FormField
            label="Last name"
            name="surname"
            autoComplete="family-name"
            value={values.surname}
            onChange={update("surname")}
            error={fieldErrors.surname}
          />
        </div>

        <div className="au-grid-2">
          <FormField
            label="Email"
            type="email"
            name="email"
            autoComplete="email"
            inputMode="email"
            value={values.email}
            onChange={update("email")}
            error={fieldErrors.email}
          />
          <FormField
            label="Mobile number"
            type="tel"
            name="mobile_number"
            autoComplete="tel"
            inputMode="tel"
            value={values.mobile_number}
            onChange={update("mobile_number")}
            error={fieldErrors.mobile_number}
          />
        </div>

        <div className="au-grid-2">
          <PasswordField
            label="Password"
            name="password"
            autoComplete="new-password"
            value={values.password}
            onChange={update("password")}
            error={fieldErrors.password}
            hint={`At least ${MIN_PASSWORD_LENGTH} characters.`}
          />
          <PasswordField
            label="Confirm password"
            name="confirm"
            autoComplete="new-password"
            value={values.confirm}
            onChange={update("confirm")}
            error={fieldErrors.confirm}
          />
        </div>

        <FormField
          label="Notes"
          optional
          as="textarea"
          rows={3}
          name="notes"
          value={values.notes}
          onChange={update("notes")}
          error={fieldErrors.notes}
          hint='For example "registered mountain guide".'
        />

        <FormField
          label="Emergency contact"
          optional
          name="emergency_contact"
          value={values.emergency_contact}
          onChange={update("emergency_contact")}
          error={fieldErrors.emergency_contact}
          hint="A name and phone number the hut can call in an emergency."
        />

        <button
          type="submit"
          className="au-btn au-btn--primary au-btn--block"
          disabled={submitting}
        >
          {submitting ? "Creating account…" : "Create account"}
        </button>
      </form>
    </AuthLayout>
  );
}
