import React, { useState, useEffect } from 'react';
import { getSession, signIn } from '../api/auth';
import { getAdminRequests, requestCancellation } from '../api/client';

const ClientPortal = () => {
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(false);
  const [session, setSession] = useState(null);
  const [loginData, setLoginData] = useState({ email: '', password: '' });

  useEffect(() => {
    checkSession();
  }, []);

  const checkSession = async () => {
    try {
      const s = await getSession();
      if (s) {
        setSession(s);
        fetchMyBookings();
      }
    } catch (e) {
      console.error("No session", e);
    }
  };

  const fetchMyBookings = async () => {
    try {
      setLoading(true);
      // NOTE: In a mature system, we'd have a /client/bookings endpoint.
      // For Milestone 4 MVP, we leverage the shared framework.
      const data = await getAdminRequests('ALL'); // Filters will be applied client-side for MVP
      setRequests(data.requests || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleCancelRequest = async (req) => {
    const serviceDate = new Date(req.start_date);
    const now = new Date();
    const hoursDiff = (serviceDate - now) / (1000 * 60 * 60);

    let confirmMsg = "Are you sure you want to request a cancellation for this visit?";
    if (hoursDiff < 24 && hoursDiff > 0) {
      confirmMsg = "⚠️ WARNING: This visit is scheduled within 24 hours. Cancellations this close to the service may be subject to a fee. Do you still wish to submit the request?";
    }

    if (!window.confirm(confirmMsg)) return;

    const reason = prompt("Please provide a reason for the cancellation:", "");
    if (reason === null) return;

    try {
      setLoading(true);
      await requestCancellation(req.request_id, req.client_id, reason);
      alert("Cancellation request submitted. Ryan will review and confirm shortly.");
      fetchMyBookings();
    } catch (err) {
      alert("Failed to submit request: " + err.message);
    } finally {
      setLoading(false);
    }
  };

  if (!session) {
    return (
      <div className="card login-card" style={{ maxWidth: '400px', margin: '40px auto' }}>
        <h2>Client Login</h2>
        <p>Sign in to manage your bookings.</p>
        <form onSubmit={async (e) => {
          e.preventDefault();
          try {
            await signIn(loginData.email, loginData.password);
            checkSession();
          } catch(err) { alert(err.message); }
        }}>
          <input 
            type="email" 
            placeholder="Email" 
            value={loginData.email} 
            onChange={e => setLoginData({...loginData, email: e.target.value})} 
            required 
            style={{ width: '100%', marginBottom: '10px', padding: '10px' }}
          />
          <input 
            type="password" 
            placeholder="Password" 
            value={loginData.password} 
            onChange={e => setLoginData({...loginData, password: e.target.value})} 
            required 
            style={{ width: '100%', marginBottom: '20px', padding: '10px' }}
          />
          <button type="submit" className="button-primary" style={{ width: '100%' }}>Sign In</button>
        </form>
      </div>
    );
  }

  return (
    <div className="client-portal">
      <div className="portal-header">
        <h1>My Bookings</h1>
        <p className="subtitle">View and manage your pet sitting schedule.</p>
      </div>

      <div className="bookings-list">
        {loading ? <p>Loading your schedule...</p> : (
          requests.length === 0 ? <p>No bookings found.</p> : (
            requests.map(req => (
              <div key={req.PK} className="booking-card card">
                <div className="booking-left">
                  <span className="booking-date">{req.start_date}</span>
                  <span className="booking-type">{req.service_type}</span>
                </div>
                <div className="booking-status">
                  <span className={`badge ${req.status}`}>{req.status.replace(/_/g, ' ')}</span>
                </div>
                <div className="booking-actions">
                  {(req.status === 'APPROVED' || req.status === 'ASSIGNED') && (
                    <button className="btn-cancel" onClick={() => handleCancelRequest(req)}>Request Cancellation</button>
                  )}
                  {req.status === 'CANCELLATION_REQUESTED' && (
                    <span className="pending-msg">Review in progress...</span>
                  )}
                </div>
              </div>
            ))
          )
        )}
      </div>

      <style jsx>{`
        .client-portal { max-width: 800px; margin: 0 auto; padding: 20px; }
        .portal-header { margin-bottom: 30px; }
        .booking-card { 
          display: flex; 
          justify-content: space-between; 
          align-items: center; 
          padding: 20px; 
          margin-bottom: 16px;
          border-left: 4px solid var(--primary);
        }
        .booking-left { display: flex; flex-direction: column; gap: 4px; }
        .booking-date { font-weight: 700; font-size: 1.1rem; }
        .booking-type { font-size: 0.85rem; color: var(--primary); font-weight: 600; text-transform: uppercase; }
        .badge { padding: 4px 10px; border-radius: 99px; font-size: 0.7rem; font-weight: 700; background: var(--bg-warm); }
        .badge.APPROVED, .badge.ASSIGNED { background: #dcfce7; color: #166534; }
        .badge.CANCELLATION_REQUESTED { background: #fef9c3; color: #854d0e; }
        .btn-cancel { 
          background: #fee2e2; 
          color: #991b1b; 
          border: none; 
          padding: 8px 16px; 
          border-radius: 8px; 
          font-weight: 600; 
          cursor: pointer;
          transition: all 0.2s;
        }
        .btn-cancel:hover { background: #fecaca; }
        .pending-msg { font-size: 0.8rem; font-style: italic; color: var(--text-muted); }
      `}</style>
    </div>
  );
};

export default ClientPortal;
