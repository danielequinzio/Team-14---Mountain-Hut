import React, { useId, useState } from "react";
import "../auth/auth.css";

// A labelled input with an error message and an optional hint.
//   <FormField label="Email" error={errors.email} type="email" value=... onChange=... />
// Pass as="textarea" for a multi-line field. `adornment` is rendered inside the
// field, on the right (used by the show/hide password button).
export default function FormField({
  label,
  error,
  hint,
  optional = false,
  as: Control = "input",
  adornment = null,
  ...controlProps
}) {
  const id = useId();
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;
  const showHint = Boolean(hint) && !error;
  const describedBy = error ? errorId : showHint ? hintId : undefined;

  return (
    <div className={`au-field${error ? " au-field--error" : ""}`}>
      <label htmlFor={id}>
        {label}
        {optional && <span className="au-optional"> (optional)</span>}
      </label>

      <div className="au-control">
        <Control
          id={id}
          aria-invalid={error ? "true" : undefined}
          aria-describedby={describedBy}
          {...controlProps}
        />
        {adornment}
      </div>

      {showHint && (
        <p className="au-hint" id={hintId}>
          {hint}
        </p>
      )}
      {error && (
        <p className="au-field-error" id={errorId}>
          {error}
        </p>
      )}
    </div>
  );
}

// A password input with a Show / Hide button.
export function PasswordField(props) {
  const [visible, setVisible] = useState(false);

  return (
    <FormField
      {...props}
      type={visible ? "text" : "password"}
      adornment={
        <button
          type="button"
          className="au-show"
          onClick={() => setVisible((value) => !value)}
          aria-label={visible ? "Hide password" : "Show password"}
        >
          {visible ? "Hide" : "Show"}
        </button>
      }
    />
  );
}
