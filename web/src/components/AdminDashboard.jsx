import React, { useState, useEffect } from 'react';
import { signIn, signOut, getSession } from '../api/auth';
import { getAdminRequests, reviewRequest, assignWorker, getGoogleStatus, initiateGoogleAuth, getPet, updatePet, processCancellationDecision, performAdminAction, disconnectGoogle } from '../api/client';
import MasterScheduler from './MasterScheduler';
import CareCard from './CareCard';
import { STAFF_MEMBERS } from '../constants/staff';
import '../Admin.css';

const AdminDashboard = () => {
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [loginData, setLoginData] = useState({ email: '', password: '' });
  const [googleStatus, setGoogleStatus] = useState(null);
  const [view, setView] = useState('SCHEDULER'); // SCHEDULER or LIST
  const [selectedPet, setSelectedPet] = useState(null);
  const [assigningId, setAssigningId] = useState(null); 
  const [modalError, setModalError] = useState(null);
  
  const getStatusClass = (status = "") => {
    const s = (status || "").toUpperCase();
    if (s.includes("NEW") || s.includes("PENDING")) return "status-chip status-chip--new";
    if (s.includes("READY")) return "status-chip status-chip--ready";
    if (s.includes("APPROVED")) return "status-chip status-chip--approved";
    if (s.includes("ASSIGNED")) return "status-chip status-chip--assigned";
    if (s.includes("JOB_CREATED")) return "status-chip status-chip--job-created";
    if (s.includes("CANCELLED")) return "status-chip status-chip--cancelled";
    if (s.includes("REJECTED") || s.includes("DECLINED") || s.includes("DENIED")) return "status-chip status-chip--rejected";
    if (s.includes("ARCHIVE")) return "status-chip status-chip--archived";
    return "status-chip status-chip--archived";
  };

  const getStatusLabel = (status = "") => {
    const s = (status || "").toUpperCase();
    if (s === 'PENDING_REVIEW') return "Pending";
    if (s === 'MEET_GREET_REQUIRED') return "M&G Required";
    if (s === 'READY_FOR_APPROVAL') return "Ready";
    if (s === 'APPROVED') return "Approved";
    if (s === 'ASSIGNED') return "Assigned";
    if (s === 'JOB_CREATED') return "Job Created";
    if (s === 'CANCELLATION_REQUESTED') return "Cancel Requested";
    if (s === 'CANCELLATION_DENIED') return "Cancel Denied";
    if (s === 'CANCELLED') return "Cancelled";
    if (s === 'ARCHIVED') return "Archived";
    return s || "Unknown";
  };

  // Operational States
  const [statusFilter, setStatusFilter] = useState('PENDING_REVIEW');
  const [timeframeFilter, setTimeframeFilter] = useState('ALL');
  const [lastKey, setLastKey] = useState(null);
  const [decisionModal, setDecisionModal] = useState(null); 
  const [adminNote, setAdminNote] = useState('');

  useEffect(() => {
    checkAuth();
  }, []);

  const checkAuth = async () => {
    try {
      const session = await getSession();
      if (session) {
        setIsAuthenticated(true);
        fetchAllData();
        fetchGoogleStatus();
      }
    } catch (err) {
      console.error("Auth check failed", err);
    }
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await signIn(loginData.email, loginData.password);
      setIsAuthenticated(true);
      fetchAllData();
      fetchGoogleStatus();
    } catch (err) {
      setError(err.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    signOut();
    setIsAuthenticated(false);
    setRequests([]);
  };

  const fetchAllData = async (startKey = null) => {
    try {
      setLoading(true);
      if (view === 'SCHEDULER') {
        const data = await getAdminRequests('ALL');
        // Exclude archived from the scheduler timeline
        setRequests((data.requests || []).filter(r => r.status !== 'ARCHIVED'));
      } else {
        const queryStatus = statusFilter === 'ARCHIVE' ? 'ARCHIVED' : statusFilter;
        const data = await getAdminRequests(queryStatus, startKey, timeframeFilter);
        setRequests(data.requests || []);
        setLastKey(data.lastKey);
      }
    } catch (err) {
      setError("Failed to fetch data: " + err.message);
      setRequests([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isAuthenticated) {
      fetchAllData();
    }
  }, [view, statusFilter, timeframeFilter, isAuthenticated]);

  const resolveIds = (item) => {
    if (!item) return { reqId: null, clientId: null, jobId: null };
    
    // Request ID: Priority to direct field, then PK/SK parsing
    const reqId = item.request_id || 
                  (item.PK?.startsWith('REQ#') ? item.PK.split('#')[1] : 
                  (item.SK?.startsWith('REQ#') ? item.SK.split('#')[1] : null));
    
    // Client ID: Priority to direct field, then PK/SK parsing
    const clientId = item.client_id || 
                     (item.PK?.startsWith('CLIENT#') ? item.PK.split('#')[1] : 
                     (item.SK?.startsWith('CLIENT#') ? item.SK.split('#')[1] : null));
    
    // Job ID: Priority to job_id field (often present in REQUEST after approval), then PK if entity is JOB
    const jobId = item.job_id || (item.entity_type === 'JOB' ? item.PK?.split('#')[1] : null);
    
    return { reqId, clientId, jobId };
  };

  const submitDecision = async () => {
    if (!decisionModal) return;
    const { item, type } = decisionModal;
    const { reqId, clientId } = resolveIds(item);
    
    if (!reqId || !clientId) {
      setModalError("Could not resolve Request or Client ID for this record.");
      return;
    }

    setModalError(null);
    try {
      setLoading(true);
      await reviewRequest(reqId, clientId, type === 'APPROVE' ? 'APPROVED' : 'DECLINED', adminNote);
      setDecisionModal(null);
      setAdminNote('');
      fetchAllData();
    } catch (err) {
      setModalError(err.message || "An error occurred during review.");
    } finally {
      setLoading(false);
    }
  };

  const handleQuickVerify = async () => {
    if (!decisionModal) return;
    const { item } = decisionModal;
    const { reqId, clientId } = resolveIds(item);

    if (!reqId || !clientId) {
      setModalError("Could not resolve IDs for verification.");
      return;
    }

    setModalError(null);
    try {
      setLoading(true);
      await reviewRequest(reqId, clientId, 'VERIFY_MEET_GREET');
      alert("Meet & Greet marked as completed!");
      fetchAllData();
    } catch (err) {
      setModalError("Failed to verify M&G: " + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleAdminAction = async (item, action) => {
    // Ensuring visibility and automation support by providing direct feedback instead of blocking confirmation
    const pk = item.PK || (item.request_id ? `REQ#${item.request_id}` : null);
    const sk = item.SK || (item.client_id ? `CLIENT#${item.client_id}` : null);

    if (!pk || !sk) {
      alert("Error: Missing primary keys (PK/SK) for administrative action.");
      return;
    }

    try {
      setLoading(true);
      await performAdminAction(pk, sk, action);
      alert(`Success: Record has been ${action.toLowerCase()}d.`);
      fetchAllData();
    } catch (err) {
      alert("Admin action failed: " + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleDisconnectGoogle = async () => {
    if (!window.confirm("Disconnect Google Calendar? Future syncs will stop.")) return;
    try {
      setLoading(true);
      await disconnectGoogle();
      fetchGoogleStatus();
    } catch (err) {
      alert("Disconnect failed: " + err.message);
    } finally {
      setLoading(false);
    }
  };

  const fetchGoogleStatus = async () => {
    try {
      const data = await getGoogleStatus();
      setGoogleStatus(data.status || 'NOT_CONNECTED');
    } catch (err) {
      setGoogleStatus('NOT_CONNECTED');
    }
  };

  const handleConnectGoogle = async () => {
    try {
      setLoading(true);
      const { auth_url } = await initiateGoogleAuth();
      if (auth_url) {
        window.location.href = auth_url;
      }
    } catch (err) {
      alert("Connection failed: " + err.message);
    } finally {
      setLoading(false);
    }
  };

  const onReviewAction = async (req, action) => {
    // Basic mapping for simpler UI buttons
    const statusMap = {
      'APPROVE': 'APPROVED',
      'DECLINE': 'DECLINED',
      'MEET_GREET': 'MEET_GREET_REQUIRED',
      'VERIFY': 'VERIFY_MEET_GREET',
      'READY': 'READY_FOR_APPROVAL',
      'DENY_CANCEL': 'CANCELLATION_DENIED'
    };

    const { reqId, clientId } = resolveIds(req);
    
    if (!reqId || !clientId) {
      alert("Error: Missing Request or Client ID.");
      return;
    }
    
    try {
      console.log(`[Admin] Review Action: ${action} for Req:${reqId} Client:${clientId}`);
      setLoading(true);
      await reviewRequest(reqId, clientId, statusMap[action] || action);
      fetchAllData();
    } catch (err) {
      alert("Action failed: " + err.message);
      fetchAllData(); // Refresh to sync UI with actual DB state
    } finally {
      setLoading(false);
    }
  };
  
  const handleProcessCancellation = async (req) => {
    const decision = window.confirm("Approve this cancellation request?") ? 'APPROVE' : 'DENY';
    const note = prompt("Administrative note (required for audit):", "");
    if (note === null) return; // Cancelled prompt

    const { reqId, clientId } = resolveIds(req);

    if (!reqId || !clientId) {
      alert("Error: Missing IDs for cancellation processing.");
      return;
    }
    
    try {
      setLoading(true);
      await processCancellationDecision(reqId, clientId, decision, note);
      fetchAllData();
    } catch (err) {
      alert("Cancellation process failed: " + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleAssignAction = async (item, workerId) => {
    if (!workerId) {
      setAssigningId(null);
      return;
    }

    // ROBUST ID EXTRACTION
    const { reqId, clientId, jobId } = resolveIds(item);

    if (!reqId) {
      alert("Error: Record has no valid Request ID. Assignment blocked.");
      return;
    }

    if (item.entity_type === 'REQUEST' && !jobId) {
      alert("Note: This request hasn't been approved yet. Approving it will create the job mapping needed for assignment.");
      return;
    }

    try {
      setLoading(true);
      await assignWorker(jobId || reqId, reqId, clientId, workerId);
      setAssigningId(null);
      fetchAllData();
    } catch (err) {
      alert("Assignment failed: " + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectPet = async (item) => {
    // If the item has pet_id, fetch full care card
    if (item.pet_id) {
      try {
        setLoading(true);
        const petData = await getPet(item.pet_id, item.client_id);
        setSelectedPet(petData);
      } catch (err) {
        alert("Failed to load care card: " + err.message);
      } finally {
        setLoading(false);
      }
    } else {
      // Basic client-only record preview
      setSelectedPet({
        name: item.client_name,
        pet_id: null, // No longer using "NEW" as an unsafe fallback
        client_id: item.client_id,
        meet_and_greet_completed: false,
        care_instructions: item.pet_info || 'No care instructions on file yet.'
      });
    }
  };

  const handleUpdatePet = async (updatedPet) => {
    try {
      setLoading(true);
      const { clientId } = resolveIds(selectedPet || updatedPet);
      const pid = updatedPet.pet_id || selectedPet?.pet_id || 'NEW';
      
      if (!clientId) throw new Error("Could not resolve Client ID for pet update.");
      
      await updatePet(pid, clientId, updatedPet);
      setSelectedPet(null);
      fetchAllData();
    } catch (err) {
      alert("Failed to update/create pet record: " + err.message);
    } finally {
      setLoading(false);
    }
  };

  if (!isAuthenticated) {
    return (
      <div className="section auth-section">
        <div className="card auth-card">
          <h1>Staff Portal</h1>
          <p className="subtitle">Please sign in to manage operations.</p>
          <form onSubmit={handleLogin} className="premium-form">
            <div className="field">
              <label>Email Address</label>
              <input 
                type="email" 
                value={loginData.email} 
                onChange={(e) => setLoginData({...loginData, email: e.target.value})} 
                required 
              />
            </div>
            <div className="field">
              <label>Password</label>
              <input 
                type="password" 
                value={loginData.password} 
                onChange={(e) => setLoginData({...loginData, password: e.target.value})} 
                required 
              />
            </div>
            <button type="submit" className="button-primary" disabled={loading}>
              {loading ? 'Verifying...' : 'Sign In'}
            </button>
            {error && <p className="error-text">{error}</p>}
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="admin-container">
      <div className="admin-header-bar card">
        <div className="header-left">
          <h1>Togs & Dogs Admin</h1>
          <div className="view-selector">
            <button className={view === 'SCHEDULER' ? 'active' : ''} onClick={() => { setView('SCHEDULER'); setStatusFilter('ALL'); }}>Scheduler</button>
            <button className={view === 'LIST' ? 'active' : ''} onClick={() => setView('LIST')}>Request List</button>
          </div>
        </div>
        <button onClick={handleLogout} className="btn-secondary">Logout</button>
      </div>

      <div className="admin-layout">

        <aside className="admin-sidebar card">
          <div className="filter-group">
            <h4>Quick Filters</h4>
            {[
              { id: 'PENDING_REVIEW', label: 'New Requests' },
              { id: 'READY_FOR_APPROVAL', label: 'Ready' },
              { id: 'APPROVED', label: 'Approved' },
              { id: 'ASSIGNED', label: 'Assigned / Job Created' },
              { id: 'CANCELLED', label: 'Cancelled' },
              { id: 'ARCHIVED', label: 'Archive' },
              { id: 'ALL', label: 'Snapshot (Scan)' }
            ].map(f => (
              <button 
                key={f.id}
                className={`filter-option ${statusFilter === f.id ? 'active' : ''}`}
                onClick={() => setStatusFilter(f.id)}
              >
                {f.label}
              </button>
            ))}
          </div>

          <div className="filter-group">
            <h4>Timeframe</h4>
            <select value={timeframeFilter} onChange={(e) => setTimeframeFilter(e.target.value)} className="staff-select">
              <option value="ALL">All Time</option>
              <option value="DAILY">Daily</option>
              <option value="WEEKLY">Weekly</option>
              <option value="MONTHLY">Monthly</option>
            </select>
          </div>

          <div className="settings-section">
            <h4>Integrations</h4>
            <div className="integration-card">
              <div className="info">
                <strong>Google Calendar</strong>
                <div className={`status-indicator ${googleStatus === 'CONNECTED' ? 'connected' : 'not_connected'}`}>
                   {googleStatus === 'CONNECTED' ? '● Connected' : '○ Disconnected'}
                </div>
              </div>
              {googleStatus === 'CONNECTED' ? (
                <button onClick={handleDisconnectGoogle} className="btn-small">Disconnect</button>
              ) : (
                <button onClick={handleConnectGoogle} className="btn-small primary">Connect</button>
              )}
            </div>
          </div>
        </aside>

        <main className="admin-main">

          {view === 'SCHEDULER' ? (
            <MasterScheduler 
              items={requests} 
              onReview={(req) => {
                if (req.status === 'CANCELLATION_REQUESTED') {
                  handleProcessCancellation(req);
                } else {
                  setDecisionModal({ item: req, type: 'APPROVE' });
                }
              }}
              onAssign={(req) => setAssigningId(req.PK)}
              onSelectPet={handleSelectPet}
            />
          ) : (
            <div className="list-view-container card">
              <table className="request-table">
                <thead>
                  <tr>
                    <th>Customer / Service</th>
                    <th>Dates / Window</th>
                    <th>Status</th>
                    <th>Staff</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {requests.map(item => (
                    <tr key={item.PK}>
                      <td onClick={() => handleSelectPet(item)} className="clickable-cell">
                        <div className="info-stack">
                          <span className="bold">{item.pet_names || item.pet_name || '---'} ({item.client_name})</span>
                          <span className="micro-text">{item.service_type}</span>
                        </div>
                      </td>
                      <td>
                        <div className="info-stack">
                          <span className="small">{item.start_date} {item.end_date ? `to ${item.end_date}` : ''}</span>
                          <span className="badge-window">{item.visit_window || 'ANYTIME'}</span>
                        </div>
                      </td>
                      <td style={{ width: '180px' }}>
                        <select 
                          className={getStatusClass(item.status)}
                          value={item.status || 'PENDING_REVIEW'}
                          onChange={(e) => onReviewAction(item, e.target.value)}
                        >
                          <option value="PENDING_REVIEW">Pending</option>
                          <option value="MEET_GREET_REQUIRED">M&G Required</option>
                          <option value="READY_FOR_APPROVAL">Ready</option>
                          <option value="APPROVED">Approved</option>
                          <option value="JOB_CREATED">Job Created</option>
                          <option value="ASSIGNED">Assigned</option>
                          <option value="CANCELLATION_REQUESTED">Cancel Requested</option>
                          <option value="CANCELLATION_DENIED">Cancel Denied</option>
                          <option value="CANCELLED">Cancelled</option>
                          <option value="ARCHIVED">Archived</option>
                        </select>
                      </td>
                      <td>
                        {(item.status === 'APPROVED' || item.status === 'JOB_CREATED' || item.status === 'ASSIGNED') && (item.entity_type === 'JOB' || item.entity_type === 'REQUEST') ? (
                          <div className="assignment-wrapper">
                            {assigningId === item.PK ? (
                              <select 
                                autoFocus
                                className="staff-select"
                                onChange={(e) => handleAssignAction(item, e.target.value)}
                                onBlur={() => setAssigningId(null)}
                              >
                                <option value="">Select Staff...</option>
                                {STAFF_MEMBERS.map(s => (
                                  <option key={s.id} value={s.id}>{s.label}</option>
                                ))}
                              </select>
                            ) : (
                              <button 
                                onClick={() => {
                                  const { jobId } = resolveIds(item);
                                  if (!jobId && item.status === 'APPROVED') {
                                    alert("Job record is still initializing. Please wait a moment and refresh.");
                                    fetchAllData();
                                  } else {
                                    setAssigningId(item.PK);
                                  }
                                }} 
                                className={`btn-small ${item.worker_id ? 'success' : 'primary-outline'}`}
                                disabled={!resolveIds(item).jobId && item.status === 'APPROVED'}
                              >
                                {item.worker_id || (item.status === 'APPROVED' && !resolveIds(item).jobId ? 'Initializing...' : 'Assign Staff')}
                              </button>
                            )}
                          </div>
                        ) : '---'}
                      </td>
                      <td>
                        <div className="btn-group">
                           {item.status === 'PENDING_REVIEW' && (
                             <button onClick={() => setDecisionModal({ item, type: 'APPROVE' })} className="btn-small highlight">Review</button>
                           )}
                           <button onClick={() => handleAdminAction(item, 'ARCHIVE')} className="btn-small">Archive</button>
                           <button onClick={() => handleAdminAction(item, 'DELETE')} className="btn-small urgent">Delete</button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <div className="pagination-footer">
                <span className="small text-muted">Showing {requests.length} records</span>
                {lastKey && (
                  <button onClick={() => fetchAllData(lastKey)} className="btn-small primary">Next Page →</button>
                )}
              </div>
            </div>
          )}
        </main>
      </div>

      {decisionModal && (
        <div className="modal-overlay">
          <div className="modal-content">
            <div className="modal-header">
               <h2>{decisionModal.type === 'APPROVE' ? 'Approve Booking' : 'Decline Booking'}</h2>
               <p className="text-muted">For {decisionModal.item.client_name} - {decisionModal.item.start_date}</p>
            </div>
            
            {modalError && (
              <div className="modal-error-banner">
                <p><strong>Error:</strong> {modalError}</p>
                {modalError.includes("Meet-and-Greet required") && (
                  <button onClick={handleQuickVerify} className="btn-small success">Mark M&G Completed Now</button>
                )}
              </div>
            )}

            <div className="field">
              <label>Custom Message to Customer (Optional)</label>
              <textarea 
                rows="4"
                placeholder={decisionModal.type === 'APPROVE' ? "e.g. Can't wait to see Rover!" : "e.g. Sorry, we are booked that day."}
                value={adminNote}
                onChange={(e) => setAdminNote(e.target.value)}
              />
            </div>

            <div className="modal-footer">
              <button onClick={() => { setDecisionModal(null); setModalError(null); }} className="btn-secondary">Cancel</button>
              {decisionModal.type === 'APPROVE' ? (
                <button onClick={submitDecision} className="btn-small success">Approve & Notify</button>
              ) : (
                <button onClick={submitDecision} className="btn-small urgent">Confirm Decline</button>
              )}
            </div>
          </div>
        </div>
      )}

      {selectedPet && (
        <CareCard 
          pet={selectedPet} 
          onClose={() => setSelectedPet(null)}
          onUpdate={handleUpdatePet}
        />
      )}
    </div>
  );
};

export default AdminDashboard;
