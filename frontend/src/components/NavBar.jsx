import React from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { ROLES, isStaff } from "../auth/roles";
import "../auth/auth.css";

// Top bar for the logged-in area: links depend on the role.
export default function NavBar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  async function handleLogout() {
    await logout();
    navigate("/");
  }

  return (
    <header className="au-nav">
      <Link to="/" className="au-brand" aria-label="Mountain Hut home">
        <span className="au-brand-mark">▲</span>
        <span>
          <strong>Mountain Hut</strong>
          <small>Table reservations</small>
        </span>
      </Link>

      <nav className="au-links" aria-label="Main">
        <NavLink to="/">Home</NavLink>
        {user?.role === ROLES.HIKER && <NavLink to="/availability">Book a table</NavLink>}
        {isStaff(user) && <NavLink to="/staff/slots">Slots</NavLink>}
      </nav>

      <div className="au-nav-actions">
        {user ? (
          <>
            <span className="au-user">
              <span className="au-avatar" aria-hidden="true">
                {user.username.charAt(0).toUpperCase()}
              </span>
              <span>
                <strong>{user.username}</strong>
                <small>{user.role}</small>
              </span>
            </span>
            <button type="button" className="au-btn au-btn--ghost" onClick={handleLogout}>
              Log out
            </button>
          </>
        ) : (
          <>
            <Link to="/login" className="au-btn au-btn--ghost">
              Log in
            </Link>
            <Link to="/register" className="au-btn au-btn--primary">
              Register
            </Link>
          </>
        )}
      </div>
    </header>
  );
}
