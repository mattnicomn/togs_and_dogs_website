import React, { useState, useEffect } from 'react';
import { getSession, signIn, getEffectiveRole } from '../api/auth';
import { getClientRequests, requestCancellation } from '../api/client';
import UserProfile from './UserProfile';
import '../Portal.css';

const ClientPortal = () => {
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(false);
  const [session, setSession] = useState(null);
  const [userRole, setUserRole] = useState(null);
  const [loginData, setLoginData] = useState({ email: '', password: '' });
  const [error, setError] = useState(null);

  useEffect(() => {
    checkSession();
  }, []);

  const checkSession = async () => {
    try {
      const s = await getSession();
      if (s) {
        const role = getEffectiveRole(s);
        if (['owner', 'admin', 'client'].includes(role)) {
          setSession(s);
          setUserRole(role);
          await fetchMyBookings(s, role);
        } else {
          setError("Access denied. Staff members must use the Staff Portal.");
          setSession(null);
        }
      }
    } catch (e) {
      console.error("No session", e);
    }
  };

  const fetchMyBookings = async (activeSession, role) => {
    if (!activeSession) return;
    try {
      setLoading(true);
      const data = await getClientRequests(); 
      if (data.message === "No local profile linked") {
        setRequests([]);
        // Release 6E: Clear role-specific messaging instead of misleading "not linked" for admin/owner
        if (role && ['owner', 'admin'].includes(role)) {
          setError("You are signed in as an administrator. The Client Portal is for client accounts only. To view client bookings, use the Admin Dashboard.");
        } else {
          setError("Your portal account is not yet linked to a client profile. Please contact support.");
        }
      } else {
        setRequests(data.requests || []);
        setError(null);
      }
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

  const getStatusDisplay = (status) => {
    const s = (status || 'PENDING_REVIEW').toUpperCase();
    const mapping = {
      'PENDING_REVIEW': { label: 'Pending Review', msg: 'Your request is being reviewed.', color: '#c28b1e', bg: 'rgba(194, 139, 30, 0.1)' },
      'NEEDS_REVIEW': { label: 'Pending Review', msg: 'Your request is being reviewed.', color: '#c28b1e', bg: 'rgba(194, 139, 30, 0.1)' },
      'MEET_GREET_REQUIRED': { label: 'Meet & Greet Required', msg: 'Ryan will follow up to schedule a meet & greet.', color: '#f08c3a', bg: 'rgba(240, 140, 58, 0.1)' },
      'NEEDS_MG': { label: 'Meet & Greet Required', msg: 'Ryan will follow up to schedule a meet & greet.', color: '#f08c3a', bg: 'rgba(240, 140, 58, 0.1)' },
      'MG_SCHEDULED': { label: 'M&G Scheduled', msg: 'Your meet & greet has been scheduled.', color: '#f08c3a', bg: 'rgba(240, 140, 58, 0.1)' },
      'QUOTE_NEEDED': { label: 'Quote Needed', msg: 'A quote is being prepared for your review.', color: '#e17c80', bg: 'rgba(225, 124, 128, 0.1)' },
      'QUOTE_SENT': { label: 'Quote Sent', msg: 'Check your email for your custom care quote.', color: '#e17c80', bg: 'rgba(225, 124, 128, 0.1)' },
      'QUOTED': { label: 'Quoted', msg: 'A quote has been prepared.', color: '#e17c80', bg: 'rgba(225, 124, 128, 0.1)' },
      'APPROVED': { label: 'Approved', msg: 'Your request has been approved. Ryan will follow up to confirm final scheduling details.', color: '#4a7c59', bg: 'rgba(74, 124, 89, 0.1)' },
      'BOOKED': { label: 'Approved', msg: 'Your request has been approved. Ryan will follow up to confirm final scheduling details.', color: '#4a7c59', bg: 'rgba(74, 124, 89, 0.1)' },
      'ASSIGNED': { label: 'Scheduled', msg: 'Your visit is scheduled.', color: '#2b6cb0', bg: 'rgba(43, 108, 176, 0.1)' },
      'SCHEDULED': { label: 'Scheduled', msg: 'Your visit is scheduled.', color: '#2b6cb0', bg: 'rgba(43, 108, 176, 0.1)' },
      'COMPLETED': { label: 'Completed', msg: 'This visit has been completed.', color: '#718096', bg: 'rgba(113, 128, 150, 0.1)' },
      'CANCELLED': { label: 'Cancelled', msg: 'This request has been cancelled.', color: '#e53e3e', bg: 'rgba(229, 62, 62, 0.1)' },
      'CANCELLATION_REQUESTED': { label: 'Cancellation Pending', msg: 'Your cancellation request is being reviewed.', color: '#e53e3e', bg: 'rgba(229, 62, 62, 0.1)' },
    };
    return mapping[s] || { label: s.replace(/_/g, ' '), msg: '', color: '#8a8a86', bg: 'rgba(138, 138, 134, 0.1)' };
  };

  if (!session) {
    return (
      <div className="card login-card" style={{ maxWidth: '400px', margin: '80px auto', padding: '40px' }}>
        <h2 style={{ textAlign: 'center', marginBottom: '12px' }}>Client Login</h2>
        {error && <p style={{ color: 'red', textAlign: 'center', marginBottom: '16px' }}>{error}</p>}
        <p style={{ textAlign: 'center', color: 'var(--text-muted)', marginBottom: '32px' }}>Sign in to manage your bookings.</p>

        <form onSubmit={async (e) => {
          e.preventDefault();
          try {
            setLoading(true);
            await signIn(loginData.email, loginData.password);
            const s = await getSession();
            const role = getEffectiveRole(s);
            if (['owner', 'admin', 'client'].includes(role)) {
              setSession(s);
              fetchMyBookings(s);
            } else {
              setError("Access denied. Staff members must use the Staff Portal.");
            }
          } catch(err) { 
            alert(err.message); 
          } finally {
            setLoading(false);
          }
        }}>
          <div className="field" style={{ marginBottom: '16px' }}>
            <label>Email Address</label>
            <input 
              type="email" 
              placeholder="alex@example.com" 
              value={loginData.email} 
              onChange={e => setLoginData({...loginData, email: e.target.value})} 
              required 
              autoComplete="email"
            />
          </div>
          <div className="field" style={{ marginBottom: '24px' }}>
            <label>Password</label>
            <input 
              type="password" 
              placeholder="••••••••" 
              value={loginData.password} 
              onChange={e => setLoginData({...loginData, password: e.target.value})} 
              required 
              autoComplete="current-password"
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
      <div className="portal-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '32px' }}>
        <div>
          <h1 style={{ fontSize: '2.5rem', marginBottom: '8px' }}>My Bookings</h1>
          <p className="subtitle" style={{ color: 'var(--text-muted)' }}>View and manage your pet sitting schedule.</p>
        </div>
        <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
          <button 
            onClick={() => window.location.href = '/book'} 
            className="button-primary"
            style={{ padding: '10px 24px', borderRadius: '12px', fontSize: '0.95rem' }}
          >
            + New Request
          </button>
          <UserProfile />
        </div>
      </div>

      {error && (
        <div className="card" style={{ backgroundColor: 'rgba(214, 73, 51, 0.05)', borderColor: 'var(--warning-color)', marginBottom: '24px', padding: '20px' }}>
          <p style={{ color: 'var(--warning-color)', textAlign: 'center', margin: 0 }}>{error}</p>
        </div>
      )}

      <div className="bookings-list" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
        {loading ? (
          <div className="card" style={{ textAlign: 'center', padding: '60px' }}>
            <p>Loading your schedule...</p>
          </div>
        ) : (
          requests.length === 0 ? (
            <div className="card" style={{ textAlign: 'center', padding: '60px' }}>
              <div style={{ fontSize: '3rem', marginBottom: '20px' }}>🐾</div>
              <h3>No bookings yet</h3>
              <p style={{ color: 'var(--text-muted)', marginTop: '12px' }}>When you submit care requests, they will appear here.</p>
              <button 
                onClick={() => window.location.href = '/book'} 
                className="button-secondary"
                style={{ marginTop: '24px' }}
              >
                Request Your First Visit
              </button>
            </div>
          ) : (
            requests.map(req => {
              const status = getStatusDisplay(req.status);
              const isScheduled = req.status === 'ASSIGNED' || req.status === 'SCHEDULED';
              const canCancel = ['APPROVED', 'BOOKED', 'ASSIGNED', 'SCHEDULED', 'JOB_CREATED'].includes(req.status);
              const petNames = req.pet_names || req.pet_name || "---";

              return (
                <div key={req.PK || req.request_id} className="booking-card card" style={{ padding: '24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '20px' }}>
                  <div className="booking-info" style={{ display: 'flex', gap: '24px', alignItems: 'center' }}>
                    <div className="booking-date-box" style={{ textAlign: 'center', background: 'var(--bg-muted)', padding: '12px', borderRadius: '12px', minWidth: '100px' }}>
                      <div style={{ fontSize: '0.75rem', fontWeight: '700', textTransform: 'uppercase', opacity: 0.6 }}>{new Date(req.start_date).toLocaleDateString(undefined, { weekday: 'short' })}</div>
                      <div style={{ fontSize: '1.25rem', fontWeight: '800' }}>{new Date(req.start_date).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}</div>
                    </div>
                    
                    <div className="booking-main-details">
                      <h4 style={{ marginBottom: '4px' }}>{req.service_type?.replace(/_/g, ' ') || 'Pet Care Visit'}</h4>
                      <div style={{ display: 'flex', gap: '12px', fontSize: '0.9rem', color: 'var(--text-muted)', flexWrap: 'wrap' }}>
                        <span>🐕 <strong>{petNames}</strong></span>
                        {req.visit_window && <span>⏰ {req.visit_window}</span>}
                        {req.preferred_time && !req.visit_window && <span>⏰ {req.preferred_time}</span>}
                        {isScheduled && req.worker_name && (
                          <span style={{ color: 'var(--primary)', fontWeight: '600' }}>👤 {req.worker_name}</span>
                        )}
                        {isScheduled && !req.worker_name && (
                          <span style={{ color: 'var(--primary)', fontWeight: '600' }}>👤 Tog & Dogs Team</span>
                        )}
                      </div>
                      {status.msg && (
                        <p style={{ marginTop: '12px', fontSize: '0.85rem', color: 'var(--text-secondary)', fontStyle: 'italic', maxWidth: '400px' }}>
                          {status.msg}
                        </p>
                      )}
                    </div>
                  </div>

                  <div className="booking-status-actions" style={{ display: 'flex', alignItems: 'center', gap: '24px', marginLeft: 'auto' }}>
                    <span style={{ 
                      padding: '6px 16px', 
                      borderRadius: '99px', 
                      fontSize: '0.8rem', 
                      fontWeight: '700', 
                      backgroundColor: status.bg, 
                      color: status.color,
                      whiteSpace: 'nowrap'
                    }}>
                      {status.label}
                    </span>

                    <div className="booking-actions">
                      {canCancel && (
                        <button 
                          className="btn-cancel" 
                          onClick={() => handleCancelRequest(req)}
                          style={{ 
                            background: 'transparent', 
                            border: '1px solid var(--border-soft)', 
                            padding: '8px 16px', 
                            borderRadius: '8px', 
                            fontSize: '0.85rem', 
                            cursor: 'pointer',
                            color: 'var(--warning-color)'
                          }}
                        >
                          Cancel
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              );
            })
          )
        )}
      </div>
    </div>
  );
};

export default ClientPortal;
