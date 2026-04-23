import React, { useState, useEffect } from 'react';
import { getSession, signIn } from '../api/auth';
import { getAdminRequests, requestCancellation } from '../api/client';

import '../Portal.css';

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
        await fetchMyBookings(s);
      }
    } catch (e) {
      console.error("No session", e);
    }
  };

  const fetchMyBookings = async (activeSession) => {
    if (!activeSession) return;
    try {
      setLoading(true);
      const userEmail = (activeSession.idToken.payload.email || "").toLowerCase().trim();
      const data = await getAdminRequests('ALL'); 
      const myRequests = data.requests || [];
      // Secondary client-side safety filter (the backend already filters, but this handles edge cases)
      const filtered = myRequests.filter(r => (r.client_email || "").toLowerCase().trim() === userEmail);
      setRequests(filtered);
    } catch (err) {
      console.error("Fetch failed", err);
    } finally {
      setLoading(false);
    }
  };

  const handleCancelRequest = async (req) => {
    const { reqId, clientId } = resolveIds(req);
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
      await requestCancellation(reqId, clientId, reason);
      alert("Cancellation request submitted. Ryan will review and confirm shortly.");
      fetchMyBookings(session);
    } catch (err) {
      alert("Failed to submit request: " + err.message);
    } finally {
      setLoading(false);
    }
  };

  const resolveIds = (item) => {
    if (!item) return { reqId: null, clientId: null };
    const reqId = item.request_id || (item.PK?.startsWith('REQ#') ? item.PK.split('#')[1] : null);
    const clientId = item.client_id || (item.PK?.startsWith('CLIENT#') ? item.PK.split('#')[1] : (item.SK?.startsWith('CLIENT#') ? item.SK.split('#')[1] : null));
    return { reqId, clientId };
  };

  if (!session) {
    return (
      <div className="card login-card" style={{ maxWidth: '400px', margin: '80px auto', padding: '40px' }}>
        <h2 style={{ textAlign: 'center', marginBottom: '12px' }}>Client Login</h2>
        <p style={{ textAlign: 'center', color: 'var(--text-muted)', marginBottom: '32px' }}>Sign in to manage your bookings.</p>
        <form onSubmit={async (e) => {
          e.preventDefault();
          try {
            setLoading(true);
            await signIn(loginData.email, loginData.password);
            const s = await getSession();
            setSession(s);
            fetchMyBookings(s);
          } catch(err) { 
            alert(err.message); 
          } finally {
            setLoading(false);
          }
        }}>
          <div className="field" style={{ marginBottom: '16px' }}>
            <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 700, marginBottom: '4px' }}>Email Address</label>
            <input 
              type="email" 
              placeholder="alex@example.com" 
              value={loginData.email} 
              onChange={e => setLoginData({...loginData, email: e.target.value})} 
              required 
              style={{ width: '100%', padding: '12px', borderRadius: '8px', border: '1px solid var(--border-soft)' }}
            />
          </div>
          <div className="field" style={{ marginBottom: '24px' }}>
            <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 700, marginBottom: '4px' }}>Password</label>
            <input 
              type="password" 
              placeholder="••••••••" 
              value={loginData.password} 
              onChange={e => setLoginData({...loginData, password: e.target.value})} 
              required 
              style={{ width: '100%', padding: '12px', borderRadius: '8px', border: '1px solid var(--border-soft)' }}
            />
          </div>
          <button type="submit" className="button-primary" style={{ width: '100%', padding: '14px' }} disabled={loading}>
            {loading ? 'Signing in...' : 'Sign In'}
          </button>
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
        {loading ? <p style={{ textAlign: 'center' }}>Loading your schedule...</p> : (
          requests.length === 0 ? (
            <div className="card" style={{ textAlign: 'center', padding: '40px' }}>
              <p>No bookings found.</p>
            </div>
          ) : (
            requests.map(req => (
              <div key={req.PK || req.request_id} className="booking-card card">
                <div className="booking-left">
                  <span className="booking-date">{req.start_date}</span>
                  <span className="booking-type">{req.service_type}</span>
                </div>
                <div className="booking-status">
                  <span className={`badge ${req.status}`}>{req.status?.replace(/_/g, ' ') || 'PENDING'}</span>
                </div>
                <div className="booking-actions">
                  {(req.status === 'APPROVED' || req.status === 'ASSIGNED' || req.status === 'JOB_CREATED') && (
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
    </div>
  );
};

export default ClientPortal;
