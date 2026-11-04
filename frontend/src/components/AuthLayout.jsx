import React from "react";
import NavBar from "./NavBar";
import "../auth/auth.css";

// The frame shared by the login and registration pages: navbar + a centred card.
export default function AuthLayout({ title, subtitle, footer, wide = false, children }) {
  return (
    <div className="au-page">
      <NavBar />
      <main className="au-main">
        <section
          className={`au-card${wide ? " au-card--wide" : ""}`}
          aria-labelledby="au-title"
        >
          <span className="au-eyebrow">Mountain Hut</span>
          <h1 id="au-title">{title}</h1>
          {subtitle && <p className="au-subtitle">{subtitle}</p>}
          {children}
          {footer && <p className="au-switch">{footer}</p>}
        </section>
      </main>
    </div>
  );
}
