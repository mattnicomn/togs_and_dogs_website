import { useState, useEffect } from 'react';
import { signIn, signOut, getSession } from '../api/auth';
import { getAdminRequests, reviewRequest, assignWorker, getGoogleStatus, initiateGoogleAuth, getPet, updatePet, processCancellationDecision } from '../api/client';
import MasterScheduler from './MasterScheduler';
import CareCard from './CareCard';

const AdminDashboard = () => {
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [loginData, setLoginData] = useState({ email: '', password: '' });
  const [googleStatus, setGoogleStatus] = useState(null);
  const [view, setView] = useState('SCHEDULER'); // SCHEDULER or LIST
  const [selectedPet, setSelectedPet] = useState(null);

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

  const fetchAllData = async () => {
    try {
      setLoading(true);
      // Fetch 'ALL' for the scheduler view
      const data = await getAdminRequests('ALL');
      setRequests(data.requests || []);
    } catch (err) {
      setError("Failed to fetch data: " + err.message);
      setRequests([]);
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
      'READY': 'READY_FOR_APPROVAL'
    };
    
    try {
      setLoading(true);
      await reviewRequest(req.request_id, req.client_id, statusMap[action] || action);
      fetchAllData();
    } catch (err) {
      alert("Action failed: " + err.message);
    } finally {
      setLoading(false);
    }
  };
  
  const handleProcessCancellation = async (req) => {
    const decision = window.confirm("Approve this cancellation request?") ? 'APPROVE' : 'DENY';
    const note = prompt("Administrative note (required for audit):", "");
    if (note === null) return; // Cancelled prompt
    
    try {
      setLoading(true);
      await processCancellationDecision(req.request_id, req.client_id, decision, note);
      fetchAllData();
    } catch (err) {
      alert("Cancellation process failed: " + err.message);
    } finally {
      setLoading(false);
    }
  };

  const onAssignAction = async (req) => {
    const workerId = prompt("Assign to: Ryan, Wife, Nephew1, or Nephew2?");
    if (!workerId) return;
    try {
      setLoading(true);
      // For assignment, we pass the job_id if it exists, or request_id
      await assignWorker(req.job_id || req.request_id, req.request_id, workerId);
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
    if (!updatedPet.pet_id) {
      alert("Error: This record does not have a valid Pet ID. Persistent updates require a registered pet profile.");
      return;
    }
    
    try {
      setLoading(true);
      await updatePet(updatedPet.pet_id, updatedPet.client_id, updatedPet);
      setSelectedPet(null);
      fetchAllData();
    } catch (err) {
      alert("Failed to update pet: " + err.message);
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
    <div className="section admin-section">
      <div className="admin-hero">
        <div className="admin-titles">
          <h1>Operations Hub</h1>
          <p className="subtitle">Family-run dispatcher for Togs & Dogs.</p>
        </div>
        <div className="admin-actions">
           <button onClick={() => setView(view === 'SCHEDULER' ? 'LIST' : 'SCHEDULER')} className="button-secondary">
             {view === 'SCHEDULER' ? 'Table View' : 'Master Scheduler'}
           </button>
           <button onClick={handleLogout} className="button-outline">Sign Out</button>
        </div>
      </div>

      <div className="admin-controls-row">
        <div className="integration-status">
            {googleStatus === 'CONNECTED' ? (
              <span className="badge success-light">● Google Calendar Active</span>
            ) : (
              <button onClick={handleConnectGoogle} className="btn-link">Connect Calendar</button>
            )}
        </div>
      </div>

      {view === 'SCHEDULER' ? (
        <MasterScheduler 
          items={requests} 
          onReview={(req) => {
            if (req.status === 'CANCELLATION_REQUESTED') {
              handleProcessCancellation(req);
            } else {
              onReviewAction(req, 'READY');
            }
          }}
          onAssign={(req) => onAssignAction(req)}
          onSelectPet={handleSelectPet}
        />
      ) : (
        <div className="request-management card">
          <div className="card-header">
            <h3>Operational Records</h3>
            <button onClick={fetchAllData} className="btn-refresh" title="Refresh data">⟳</button>
          </div>
          <div className="table-responsive">
            <table className="request-table">
              <thead>
                <tr>
                  <th>Client / Entity</th>
                  <th>Status</th>
                  <th>Staff</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {requests.map(item => (
                  <tr key={item.PK}>
                    <td>
                      <div className="client-cell">
                        <span className="client-name">{item.client_name}</span>
                        <span className="entity-type">{item.entity_type} {item.service_type && `- ${item.service_type}`}</span>
                      </div>
                    </td>
                    <td><span className={`badge-status ${item.status}`}>{item.status}</span></td>
                    <td>{item.worker_id || '---'}</td>
                    <td className="actions-cell">
                      {item.status === 'PENDING_REVIEW' && (
                        <div className="btn-group">
                          <button onClick={() => onReviewAction(item, 'MEET_GREET')} className="btn-action">Meet & Greet</button>
                          <button onClick={() => onReviewAction(item, 'READY')} className="btn-action approve">Ready</button>
                        </div>
                      )}
                      {item.status === 'READY_FOR_APPROVAL' && (
                        <button onClick={() => onReviewAction(item, 'APPROVE')} className="btn-action primary">Approve & Job Creation</button>
                      )}
                      {item.status === 'CANCELLATION_REQUESTED' && (
                        <button onClick={() => handleProcessCancellation(item)} className="btn-action urgent-bg">Process Cancellation</button>
                      )}
                      {(item.status === 'APPROVED' || item.status === 'JOB_CREATED') && (
                        <button onClick={() => onAssignAction(item)} className="btn-action">Assign Staff</button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
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
      
      <style jsx>{`
        .admin-section {
          padding-top: 20px;
        }
        .admin-hero {
          display: flex;
          justify-content: space-between;
          align-items: flex-end;
          margin-bottom: 32px;
        }
        .admin-actions {
          display: flex;
          gap: 12px;
        }
        .admin-controls-row {
          margin-bottom: 24px;
        }
        .btn-link {
          background: none;
          border: none;
          color: var(--primary);
          text-decoration: underline;
          cursor: pointer;
          font-weight: 600;
        }
        .badge-status {
          padding: 4px 10px;
          border-radius: 6px;
          font-size: 0.75rem;
          font-weight: 700;
          background: var(--bg-muted);
          color: var(--text-muted);
        }
        .badge-status.APPROVED, .badge-status.JOB_CREATED { background: hsla(142, 70%, 50%, 0.2); color: #22c55e; }
        .badge-status.PENDING_REVIEW { background: hsla(45, 100%, 50%, 0.2); color: #eab308; }
        .badge-status.MEET_GREET_REQUIRED { background: hsla(0, 100%, 50%, 0.2); color: #ef4444; }
        .badge-status.CANCELLATION_REQUESTED { background: hsla(0, 100%, 50%, 0.2); color: #ef4444; }
        .urgent-bg { background: #ef4444 !important; color: white !important; }
        .btn-action {
          padding: 6px 12px;
          border-radius: 6px;
          border: 1px solid var(--border-soft);
          background: var(--bg-muted);
          color: var(--text-main);
          font-size: 0.85rem;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.2s ease;
        }
        .btn-action:hover { background: var(--bg-surface); border-color: var(--primary); }
        .btn-action.primary { background: var(--primary); color: white; border: none; }
        .btn-action.approve { color: #22c55e; border-color: hsla(142, 70%, 50%, 0.4); }
        .success-light { background: hsla(142, 70%, 50%, 0.15); color: #22c55e; border: 1px solid hsla(142, 70%, 50%, 0.3); }
        .btn-refresh {
          background: none;
          border: none;
          font-size: 1.2rem;
          cursor: pointer;
          color: var(--primary);
        }
      `}</style>
    </div>
  );
};

export default AdminDashboard;
