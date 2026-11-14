import React, { useEffect } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { isStaff , isHiker } from "../auth/roles";
import { hut } from "../content/hutInfo";
import "./landing.css";

function MountainRidge() {
  return (
    <svg
      className="lp-ridge"
      viewBox="0 0 1440 320"
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <path
        fill="#182433"
        d="M0 220 L120 150 L220 190 L360 90 L470 170 L600 120 L720 200 L860 110 L980 180 L1100 100 L1230 170 L1340 130 L1440 180 L1440 320 L0 320Z"
      />
      <path
        fill="#121b27"
        d="M0 260 L140 200 L260 240 L420 160 L540 230 L700 180 L820 250 L980 190 L1120 250 L1260 200 L1440 250 L1440 320 L0 320Z"
      />
      <path
        fill="#0d1117"
        d="M0 292 L180 262 L340 286 L520 258 L700 289 L900 264 L1100 291 L1280 270 L1440 293 L1440 320 L0 320Z"
      />
    </svg>
  );
}

export default function Landing() {
  const { user, loading, logout } = useAuth();

  // The employee and the warden manage the slots; everyone else books a table.
  // Without this, staff would have no link back to their page from the home page.
  const staff = isStaff(user);
  const hiker = isHiker(user);
  const mainLink = staff ? "/staff/slots" : hiker ? "/booking" : "/availability";

  useEffect(() => {
    document.title = `${hut.name} · Mountain Hut`;
  }, []);

  return (
    <div className="lp">
      <header className="lp-nav">
        <Link to="/" className="lp-brand" aria-label={`${hut.name} home`}>
          <span className="lp-brand-mark">▲</span>
          <span>
            <strong>{hut.name}</strong>
            <small>Mountain hut</small>
          </span>
        </Link>

        <nav className="lp-links" aria-label="Page sections">
          <a href="#about">The hut</a>
          <a href="#how-it-works">Booking</a>
          <a href="#getting-there">Getting there</a>
          <a href="#around">Around the hut</a>
        </nav>

        <div className="lp-nav-actions">
          {!loading && user && (
            <>
              <span className="lp-user lp-hide-small">
                <strong>{user.username}</strong>
                <small>{user.role}</small>
              </span>
              <button
                type="button"
                className="lp-btn lp-btn--ghost lp-hide-small"
                onClick={logout}
              >
                Log out
              </button>
            </>
          )}
          {!loading && !user && (
            <>
              <Link to="/login" className="lp-btn lp-btn--ghost lp-hide-small">
                Log in
              </Link>
              <Link
                to="/register"
                className="lp-btn lp-btn--ghost lp-hide-small"
              >
                Register
              </Link>
            </>
          )}
          <Link to={mainLink} className="lp-btn lp-btn--primary">
            {staff ? "Manage slots" : hiker ? "View Bookings" : "Book a table"}
          </Link>
        </div>
      </header>

      <main>
        <section className="lp-hero">
          <div className="lp-container lp-hero-content">
            <span className="lp-eyebrow">{hut.region}</span>
            <h1>{hut.name}</h1>
            <p>{hut.tagline}</p>
            <div className="lp-hero-actions">
              <Link to={mainLink} className="lp-btn lp-btn--primary lp-btn--large">
                {staff ? "Manage slots" : hiker ? "Book a table" : "Check availability"}
              </Link>
              {!loading && !user && (
                <Link
                  to="/register"
                  className="lp-btn lp-btn--ghost lp-btn--large"
                >
                  Create an account
                </Link>
                
              )}
              {!loading && isHiker(user) && (
                <Link
                  to="/my-bookings"
                  className="lp-btn lp-btn--ghost lp-btn--large"
                >
                  View Bookings
                </Link>
                
              )}
            </div>
          </div>
          <MountainRidge />
        </section>

        <div className="lp-container">
          <dl className="lp-facts">
            {hut.facts.map((fact) => (
              <div key={fact.label} className="lp-fact">
                <dt>{fact.label}</dt>
                <dd>{fact.value}</dd>
              </div>
            ))}
          </dl>
        </div>

        <section
          id="about"
          className="lp-section lp-container"
          aria-labelledby="about-title"
        >
          <span className="lp-eyebrow">The hut</span>
          <h2 id="about-title">A place to eat, rest and recharge</h2>
          <p className="lp-lead">{hut.intro}</p>

          <div className="lp-grid">
            {hut.offers.map((offer) => (
              <article key={offer.title} className="lp-card">
                <h3>{offer.title}</h3>
                <p>{offer.text}</p>
              </article>
            ))}
          </div>
        </section>

        <section
          id="how-it-works"
          className="lp-section lp-container"
          aria-labelledby="how-title"
        >
          <span className="lp-eyebrow">Booking</span>
          <h2 id="how-title">Reserve your table in three steps</h2>

          <ol className="lp-steps">
            {hut.steps.map((step, index) => (
              <li key={step.title} className="lp-card lp-step">
                <span className="lp-step-number">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <h3>{step.title}</h3>
                <p>{step.text}</p>
              </li>
            ))}
          </ol>
        </section>

        <section
          id="getting-there"
          className="lp-section lp-container"
          aria-labelledby="getting-title"
        >
          <span className="lp-eyebrow">How to get here</span>
          <h2 id="getting-title">Getting to the hut</h2>
          <p className="lp-lead">
            The hut can only be reached on foot. Plan your arrival with enough
            daylight and check the weather before you set off.
          </p>

          <div className="lp-grid">
            {hut.routes.map((route) => (
              <article key={route.title} className="lp-card">
                <span className="lp-tag">{route.tag}</span>
                <h3>{route.title}</h3>
                <p>{route.detail}</p>
              </article>
            ))}
          </div>
        </section>

        <section
          id="around"
          className="lp-section lp-container"
          aria-labelledby="around-title"
        >
          <span className="lp-eyebrow">Nearby</span>
          <h2 id="around-title">Worth a walk from the hut</h2>

          <div className="lp-grid">
            {hut.attractions.map((place) => (
              <article key={place.title} className="lp-card">
                <span className="lp-tag lp-tag--time">{place.time} on foot</span>
                <h3>{place.title}</h3>
                <p>{place.text}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="lp-section lp-container">
          <div className="lp-cta">
            <div>
              <h2>{staff ? "Managing the hut?" : "Planning your stop?"}</h2>
              <p>
                {staff
                  ? "See the meal-time slots and how many seats are booked in each one."
                  : "See which meal times still have seats, then book a table for your party."}
              </p>
            </div>
            <Link to={mainLink} className="lp-btn lp-btn--primary lp-btn--large">
              {staff ? "Manage slots" : hiker ? "View Bookings" : "Check availability"}
            </Link>
          </div>
        </section>
      </main>

      <footer className="lp-footer">
        <div className="lp-container lp-footer-inner">
          <div>
            <strong>{hut.name}</strong>
            <p>{hut.contact.address}</p>
          </div>
          <div>
            <p>
              <a href={`tel:${hut.contact.phone.replace(/\s/g, "")}`}>
                {hut.contact.phone}
              </a>
            </p>
            <p>
              <a href={`mailto:${hut.contact.email}`}>{hut.contact.email}</a>
            </p>
          </div>
          <p className="lp-footer-note">
            Mountain Hut · Team 14 · Software Engineering II, Politecnico di
            Torino
          </p>
        </div>
      </footer>
    </div>
  );
}
