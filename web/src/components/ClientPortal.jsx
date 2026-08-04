import React, { useState, useEffect } from 'react';
import { getSession, signIn, getEffectiveRole } from '../api/auth';
import { getClientRequests, requestCancellation } from '../api/client';
import UserProfile from './UserProfile';
import { getKnownServiceTypeLabel } from '../utils/serviceLabels.js';
import '../Portal.css';

// Date and Visit Window display helper utilities
const parseDate = (d) => {
  if (!d) return new Date();
  const [year, month, day] = d.split('-');
  return new Date(year, month - 1, day);
};

const formatDate = (dateObj, includeYear = false) => {
  const options = { month: 'short', day: 'numeric' };
  if (includeYear) options.year = 'numeric';
  return dateObj.toLocaleDateString('en-US', options);
};

const getVisitWindowLabel = (windowVal) => {
  if (!windowVal) return 'Anytime';
  const friendly = {
    'MORNING': 'Morning (7–10 AM)',
    'MIDDAY': 'Midday (10 AM–2 PM)',
    'AFTERNOON': 'Afternoon (2–5 PM)',
    'EVENING': 'Evening (5–8 PM)',
    'ANYTIME': 'Anytime'
  };
  return friendly[windowVal] || windowVal;
};

const formatVisitDates = (item) => {
  if (!item) return '';

  if (item.selected_dates && item.selected_dates.length > 0) {
    const sorted = [...item.selected_dates].sort();
    
    if (sorted.length === 1) {
      return formatDate(parseDate(sorted[0]), true);
    }

    let consecutive = true;
    for (let i = 1; i < sorted.length; i++) {
      const d1 = parseDate(sorted[i - 1]);
      const d2 = parseDate(sorted[i]);
      const diffTime = Math.abs(d2 - d1);
      const diffDays = Math.round(diffTime / (1000 * 60 * 60 * 24));
      if (diffDays !== 1) {
        consecutive = false;
        break;
      }
    }

    if (consecutive) {
      const d1 = parseDate(sorted[0]);
      const d2 = parseDate(sorted[sorted.length - 1]);
      const m1 = formatDate(d1, false);
      const m2 = formatDate(d2, false);
      const y1 = d1.getFullYear();
      const y2 = d2.getFullYear();

      if (y1 !== y2) {
        return `${formatDate(d1, true)}–${formatDate(d2, true)}`;
      } else if (d1.getMonth() !== d2.getMonth()) {
        return `${m1}–${m2}, ${y1}`;
      } else {
        return `${m1.split(' ')[0]} ${d1.getDate()}–${d2.getDate()}, ${y1}`;
      }
    } else {
      const parsed = sorted.map(d => parseDate(d));
      const firstYear = parsed[0].getFullYear();
      const allSameYear = parsed.every(d => d.getFullYear() === firstYear);
      const firstMonth = parsed[0].getMonth();
      const allSameMonth = parsed.every(d => d.getMonth() === firstMonth);

      if (allSameMonth && allSameYear) {
        const monthStr = parsed[0].toLocaleDateString('en-US', { month: 'short' });
        if (sorted.length <= 3) {
          const days = parsed.map(d => d.getDate()).join(', ');
          return `${monthStr} ${days}, ${firstYear}`;
        } else {
          const days = parsed.slice(0, 3).map(d => d.getDate()).join(', ');
          const extra = sorted.length - 3;
          return `${monthStr} ${days} +${extra} more`;
        }
      } else {
        const formatSingle = (dObj) => {
          return dObj.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        };
        if (sorted.length <= 3) {
          const list = parsed.map(d => formatSingle(d)).join(', ');
          const lastYear = parsed[parsed.length - 1].getFullYear();
          return `${list}, ${lastYear}`;
        } else {
          const list = parsed.slice(0, 3).map(d => formatSingle(d)).join(', ');
          const extra = sorted.length - 3;
          return `${list} +${extra} more`;
        }
      }
    }
  }

  if (item.start_date && item.end_date) {
      const d1 = parseDate(item.start_date);
      const d2 = parseDate(item.end_date);
      if (d1.getTime() === d2.getTime()) {
         return formatDate(d1, true);
      }
      const m1 = formatDate(d1, false);
      const m2 = formatDate(d2, false);
      const y1 = d1.getFullYear();
      const y2 = d2.getFullYear();

      if (y1 !== y2) {
        return `${formatDate(d1, true)}–${formatDate(d2, true)}`;
      } else if (d1.getMonth() !== d2.getMonth()) {
        return `${m1}–${m2}, ${y1}`;
      } else {
        return `${m1.split(' ')[0]} ${d1.getDate()}–${d2.getDate()}, ${y1}`;
      }
  } else if (item.start_date) {
      return formatDate(parseDate(item.start_date), true);
  }
  
  return '';
};

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
    const serviceDate = parseDate(req.start_date);
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
      <div className="portal-header">
        <div>
          <h1>My Bookings</h1>
          <p className="subtitle">View and manage your pet sitting schedule.</p>
        </div>
        <div className="portal-header-actions">
          <button 
            onClick={() => window.location.href = '/book'} 
            className="button-primary btn-new-request"
          >
            + New Request
          </button>
          <UserProfile />
        </div>
      </div>

      {error && (
        <div className="card error-card">
          <p className="error-text">{error}</p>
        </div>
      )}

      <div className="bookings-list">
        {loading ? (
          <div className="card loading-card">
            <p>Loading your schedule...</p>
          </div>
        ) : (
          requests.length === 0 ? (
            <div className="card empty-bookings-card">
              <div className="empty-bookings-icon">🐾</div>
              <h3>No bookings yet</h3>
              <p className="empty-bookings-text">When you submit care requests, they will appear here.</p>
              <button 
                onClick={() => window.location.href = '/book'} 
                className="button-secondary btn-first-visit"
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
                <div key={req.PK || req.request_id} className="booking-card card">
                  <div className="booking-info">
                    <div className="booking-date-box">
                      <div className="booking-date-weekday">{parseDate(req.start_date).toLocaleDateString(undefined, { weekday: 'short' })}</div>
                      <div className="booking-date-day">{parseDate(req.start_date).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}</div>
                    </div>
                    
                    <div className="booking-main-details">
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                        <h4 style={{ margin: 0 }}>
                          {getKnownServiceTypeLabel(req.service_type) ?? (req.service_type?.replace(/_/g, ' ') || 'Pet Care Visit')}
                        </h4>
                        {(req.is_multi_day || (req.selected_dates && req.selected_dates.length > 1) || (req.end_date && req.start_date && req.end_date !== req.start_date)) && (
                          <span className="multi-day-badge" style={{
                            fontSize: '0.65rem', fontWeight: 700,
                            background: 'var(--bg-muted, rgba(255,255,255,0.05))', color: 'var(--text-muted, #8a8a86)',
                            padding: '2px 6px', borderRadius: '4px', border: '1px solid var(--border-soft, #333)'
                          }}>
                            Multi-Day
                          </span>
                        )}
                      </div>
                      
                      <div style={{ fontSize: '0.9rem', color: 'var(--text-secondary, #ccc)', marginTop: '4px' }}>
                        📅 {formatVisitDates(req)}
                      </div>

                      <div className="booking-meta-row" style={{ marginTop: '8px' }}>
                        <span>🐕 <strong>{petNames}</strong></span>
                        <span className="booking-time-windows">
                          ⏰ {(req.visit_windows || [req.visit_window || 'ANYTIME'])
                               .map(w => getVisitWindowLabel(w)).join(', ')}
                        </span>
                        {isScheduled && req.worker_name && (
                          <span className="booking-worker-label">👤 {req.worker_name}</span>
                        )}
                        {isScheduled && !req.worker_name && (
                          <span className="booking-worker-label">👤 Tog & Dogs Team</span>
                        )}
                      </div>

                      {(req.is_multi_day || (req.selected_dates && req.selected_dates.length > 1) || (req.total_occurrences && req.total_occurrences > 1)) && (
                        <div style={{ marginTop: '8px' }}>
                          <span style={{
                            fontSize: '0.7rem',
                            fontWeight: 700,
                            background: (req.completed_count || 0) >= (req.selected_dates?.length || req.total_occurrences || 1) ? 'rgba(74, 124, 89, 0.15)' : 'rgba(43, 108, 176, 0.15)',
                            color: (req.completed_count || 0) >= (req.selected_dates?.length || req.total_occurrences || 1) ? '#4a7c59' : '#2b6cb0',
                            padding: '2px 6px',
                            borderRadius: '4px',
                            display: 'inline-block',
                            width: 'fit-content',
                            border: (req.completed_count || 0) >= (req.selected_dates?.length || req.total_occurrences || 1) ? '1px solid rgba(74, 124, 89, 0.3)' : '1px solid rgba(43, 108, 176, 0.3)'
                          }}>
                            {req.completed_count || 0}/{(req.selected_dates?.length || req.total_occurrences || 1)} visits done
                          </span>
                        </div>
                      )}

                      {status.msg && (
                        <p className="booking-status-msg" style={{ marginTop: '8px' }}>
                          {status.msg}
                        </p>
                      )}
                    </div>
                  </div>

                  <div className="booking-status-actions">
                    <span 
                      className="booking-status-badge"
                      style={{ 
                        backgroundColor: status.bg, 
                        color: status.color,
                      }}
                    >
                      {status.label}
                    </span>

                    <div className="booking-actions">
                      {canCancel && (
                        <button 
                          className="btn-cancel-custom" 
                          onClick={() => handleCancelRequest(req)}
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
