import React from 'react';
import { Link } from 'react-router-dom';
import usmhLogo from '../assets/usmh-logo.png';
import './PortalGateway.css';

const PortalGateway = () => {
  return (
    <div className="portal-gateway-container">
      <div className="gateway-card card">
        <header className="gateway-header">
          <div className="gateway-logo">Tog&Dogs</div>
          <h1>Client Portal</h1>
          <p className="gateway-tagline">Premium Care for Your Best Friend</p>
        </header>

        <div className="gateway-content">
          <p className="welcome-text">
            Welcome to the Tog and Dogs client operations platform. 
            Request services, manage your pet's profile, and view your booking schedule all in one place.
          </p>

          <div className="gateway-actions">
            <Link to="/book" className="button-primary action-btn">
              <span className="icon">📅</span>
              <div className="btn-label">
                <strong>Request Pet Care</strong>
                <span>Submit a new care request</span>
              </div>
            </Link>

            <Link to="/my-bookings" className="button-secondary action-btn">
              <span className="icon">👤</span>
              <div className="btn-label">
                <strong>My Bookings</strong>
                <span>View schedule & client portal</span>
              </div>
            </Link>

            <Link to="/admin" className="button-secondary action-btn staff-btn">
              <span className="icon">🔒</span>
              <div className="btn-label">
                <strong>Staff Portal</strong>
                <span>Internal operational tools</span>
              </div>
            </Link>

          </div>
        </div>

        <footer className="gateway-footer">
          <a href="https://toganddogs.com" className="external-link">
            ← Back to Tog and Dogs Website
          </a>
          <div className="powered-by" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '10px', marginTop: '12px' }}>
            <img src={usmhLogo} alt="US Mission Hero logo" style={{ height: '32px', width: 'auto', objectFit: 'contain' }} />
            <span>Powered by <span className="usmh-logo">US Mission Hero</span></span>
          </div>
        </footer>
      </div>
    </div>
  );
};

export default PortalGateway;
