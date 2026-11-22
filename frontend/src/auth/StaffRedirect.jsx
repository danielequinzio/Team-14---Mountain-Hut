import React from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "./AuthContext";
import { isStaff } from "./roles";
import "./auth.css";

// For a page that visitors and hikers may open but staff should not:
//   <StaffRedirect to="/staff/slots"> <Booking /> </StaffRedirect>
// The employee and the warden do not book tables, so they are sent to their own page.
export default function StaffRedirect({ to, children }) {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="au-status" role="status">
        Loading…
      </div>
    );
  }

  // the password sent by email must be changed first: the login page asks for the new one
  if (user?.must_change_password) {
    return <Navigate to="/login" replace />;
  }

  if (isStaff(user)) {
    return <Navigate to={to} replace />;
  }

  return children;
}
