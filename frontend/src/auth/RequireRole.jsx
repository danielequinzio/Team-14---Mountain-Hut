import React from "react";
import { Link, Navigate, useLocation } from "react-router-dom";
import NavBar from "../components/NavBar";
import { useAuth } from "./AuthContext";
import "./auth.css";

// Wraps a page that needs a login, and optionally a role:
//   <RequireRole roles={STAFF_ROLES}> <SlotsPage /> </RequireRole>
// - not logged in -> redirected to /login (and sent back here after logging in)
// - wrong role    -> a "not allowed" message
export default function RequireRole({ roles, children }) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="au-status" role="status">
        Loading…
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  if (roles && !roles.includes(user.role)) {
    return (
      <div className="au-page">
        <NavBar />
        <main className="au-denied">
          <span className="au-eyebrow">403</span>
          <h1>You are not allowed to see this page</h1>
          <p>
            You are logged in as <strong>{user.username}</strong> ({user.role}),
            and this page is reserved for another role.
          </p>
          <Link to="/" className="au-btn au-btn--primary">
            Back to the home page
          </Link>
        </main>
      </div>
    );
  }

  return children;
}
