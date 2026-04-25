import React from 'react';
import { Link } from 'react-router-dom';
import './PortalGateway.css';

const PortalGateway = () => {
  return (
    <div className="portal-gateway-container">
      <div className="gateway-card card">
        <header className="gateway-header">
          <div className="gateway-logo">Togs & Dogs</div>
          <h1>Client Portal</h1>
          <p className="gateway-tagline">Premium Care for Your Best Friend</p>
        </header>

        <div className="gateway-content">
          <p className="welcome-text">
            Welcome to the Togs & Dogs client operations platform. 
            Request services, manage your pet's profile, and view your booking schedule all in one place.
          </p>

          <div className="gateway-actions">
            <Link to="/book" className="button-primary action-btn">
              <span className="icon">📅</span>
              <div className="btn-label">
                <strong>Request Pet Care</strong>
                <span>New and existing clients</span>
              </div>
            </Link>

            <Link to="/my-bookings" className="button-secondary action-btn">
              <span className="icon">👤</span>
              <div className="btn-label">
                <strong>Client / Admin Login</strong>
                <span>View schedule & manage account</span>
              </div>
            </Link>
          </div>
        </div>

        <footer className="gateway-footer">
          <a href="https://toganddogs.com" className="external-link">
            ← Back to Togs & Dogs Website
          </a>
          <div className="powered-by">
            Powered by <span className="usmh-logo">US Mission Hero</span>
          </div>
        </footer>
      </div>
    </div>
  );
};

export default PortalGateway;
