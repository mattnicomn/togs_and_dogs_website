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
  const [notification, setNotification] = useState(null);
  const [selectedIds, setSelectedIds] = useState([]);
  const [bulkAction, setBulkAction] = useState('');
  const [isBulkUpdating, setIsBulkUpdating] = useState(false);
  const [bulkConfirmModal, setBulkConfirmModal] = useState(null);

  const showNotification = (message, type = 'info') => {
    setNotification({ message, type });
    setTimeout(() => setNotification(null), 5000);
  };
  
  const getStatusClass = (status = "") => {
    const s = (status || "").toUpperCase();
    if (s.includes("NEW") || s.includes("INTAKE") || s.includes("PENDING")) return "status-chip status-chip--new";
    if (s.includes("PROFILE_CREATED")) return "status-chip status-chip--profile";
    if (s.includes("READY") || s.includes("REQUEST")) return "status-chip status-chip--ready";
    if (s.includes("APPROVED")) return "status-chip status-chip--approved";
    if (s.includes("SCHEDULED") || s.includes("ASSIGNED") || s.includes("JOB_CREATED")) return "status-chip status-chip--assigned";
    if (s.includes("IN_PROGRESS")) return "status-chip status-chip--progress";
    if (s.includes("COMPLETED")) return "status-chip status-chip--completed";
    if (s.includes("CANCELLED")) return "status-chip status-chip--cancelled";
    if (s.includes("REJECTED") || s.includes("DECLINED") || s.includes("DENIED")) return "status-chip status-chip--rejected";
    if (s.includes("ARCHIVE")) return "status-chip status-chip--archived";
    if (s.includes("DELETED")) return "status-chip status-chip--deleted";
    return "status-chip status-chip--archived";
  };

  const getStatusLabel = (status = "") => {
    const s = (status || "").toUpperCase();
    if (s === 'PENDING_REVIEW') return "Intake";
    if (s === 'MEET_GREET_REQUIRED') return "M&G Required";
    if (s === 'PROFILE_CREATED') return "Profile Created";
    if (s === 'READY_FOR_APPROVAL') return "New Request";
    if (s === 'QUOTED') return "Quoted";
    if (s === 'APPROVED') return "Approved";
    if (s === 'ASSIGNED' || s === 'JOB_CREATED') return "Scheduled";
    if (s === 'IN_PROGRESS') return "In Progress";
    if (s === 'COMPLETED') return "Completed";
    if (s === 'CANCELLATION_REQUESTED') return "Cancel Requested";
    if (s === 'CANCELLATION_DENIED') return "Cancel Denied";
    if (s === 'CANCELLED') return "Cancelled";
    if (s === 'ARCHIVED') return "Archived";
    if (s === 'DELETED') return "Deleted";
    return s || "Unknown";
  };

  /**
   * Lifecycle Helpers
   * NOTE: Currently the backend uses the 'status' field for both workflow phase and lifecycle state.
   * We treat ARCHIVED and DELETED as lifecycle states while others are active workflow statuses.
   */
  const isArchivedRecord = (item) => (item.status || "").toUpperCase() === 'ARCHIVED';
  const isDeletedRecord = (item) => (item.status || "").toUpperCase() === 'DELETED';
  const isActiveRecord = (item) => !isArchivedRecord(item) && !isDeletedRecord(item);

  const getWorkflowState = (item) => {
    const status = (item.status || 'PENDING_REVIEW').toUpperCase();
    const hasWorker = Boolean(item.worker_id);
    const isInvalidAssigned = status === 'ASSIGNED' && !hasWorker;

    const state = {
      displayStatus: getStatusLabel(status),
      statusClass: getStatusClass(status),
      isInvalid: isInvalidAssigned,
      actions: []
    };

    if (isInvalidAssigned) {
      state.displayStatus = "Needs Assignment";
      state.statusClass = "status-chip status-chip--urgent";
      state.actions = ["ASSIGN", "REVERT_TO_APPROVED", "CANCEL"];
      return state;
    }

    // Lifecycle-based Actions
    // If a record is archived or deleted, its workflow status is terminal and it only supports recovery/trash actions.
    if (isArchivedRecord(item)) {
      state.actions = ["REOPEN_PENDING", "DELETE"];
      return state;
    }
    
    if (isDeletedRecord(item)) {
      state.actions = ["REOPEN_PENDING"]; // Restore only, avoid re-archiving trash
      return state;
    }

    // Active Workflow Status Actions
    switch (status) {
      case 'PENDING_REVIEW':
        state.actions = ["CREATE_PROFILE", "VERIFY_MG", "APPROVE", "CANCEL"];
        break;
      case 'PROFILE_CREATED':
        state.actions = ["MOVE_TO_NEW_REQUEST", "VERIFY_MG", "APPROVE", "CANCEL", "EDIT_PET"];
        break;
      case 'MEET_GREET_REQUIRED':
        state.actions = ["VERIFY_MG", "CANCEL", "EDIT_PET"];
        break;
      case 'READY_FOR_APPROVAL':
        state.actions = ["QUOTE", "APPROVE", "CANCEL", "EDIT_PET"];
        break;
      case 'QUOTED':
        state.actions = ["APPROVE", "CANCEL", "EDIT_PET"];
        break;
      case 'APPROVED':
      case 'JOB_CREATED':
        state.actions = ["ASSIGN", "CANCEL", "ARCHIVE", "EDIT_PET"];
        break;
      case 'ASSIGNED':
      case 'SCHEDULED':
        state.actions = ["CHANGE_WORKER", "REVERT_TO_APPROVED", "COMPLETE", "CANCEL", "EDIT_PET"];
        break;
      case 'IN_PROGRESS':
        state.actions = ["COMPLETE", "CANCEL", "EDIT_PET"];
        break;
      case 'COMPLETED':
        state.actions = ["REOPEN", "ARCHIVE"];
        break;
      case 'CANCELLED':
      case 'DECLINED':
        // Cancelled/Declined active records can be archived or deleted, but not "restored" directly to Pending Review
        // (Use Restore only from Archived/Trash state)
        state.actions = ["ARCHIVE", "DELETE"];
        break;
      default:
        state.actions = ["CANCEL", "ARCHIVE"];
    }

    return state;
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
      if (!startKey) setSelectedIds([]); // Reset selection on fresh fetch
      
      if (view === 'SCHEDULER') {
        const data = await getAdminRequests('ALL');
        // Exclude lifecycle/removal statuses from the scheduler timeline to prevent stale display
        const terminalStatuses = ['ARCHIVED', 'DELETED'];
        setRequests((data.requests || []).filter(r => !terminalStatuses.includes((r.status || '').toUpperCase())));
      } else {
        // Handle filter mapping
        let queryStatus = statusFilter;
        if (statusFilter === 'ARCHIVE' || statusFilter === 'ARCHIVED') queryStatus = 'ARCHIVED';
        if (statusFilter === 'TRASH' || statusFilter === 'DELETED') queryStatus = 'DELETED';
        
        const data = await getAdminRequests(queryStatus, startKey, timeframeFilter);
        setRequests(data.requests || []);
        setLastKey(data.lastKey);
      }
    } catch (err) {
      setError("Failed to fetch data: " + err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isAuthenticated) {
      fetchAllData();
    }
  }, [view, statusFilter, timeframeFilter, isAuthenticated]);

  const toggleSelectAll = () => {
    if (selectedIds.length === requests.length) {
      setSelectedIds([]);
    } else {
      setSelectedIds(requests.map(r => r.PK));
    }
  };

  const toggleSelectOne = (id) => {
    setSelectedIds(prev => 
      prev.includes(id) ? prev.filter(i => i !== id) : [...prev, id]
    );
  };

  const updateRecordStatus = async (req, action, note = "") => {
    const statusMap = {
      'APPROVE': 'APPROVED',
      'DECLINE': 'DECLINED',
      'CANCEL': 'CANCELLED',
      'MEET_GREET': 'MEET_GREET_REQUIRED',
      'VERIFY': 'VERIFY_MEET_GREET',
      'VERIFY_MG': 'VERIFY_MEET_GREET',
      'READY': 'READY_FOR_APPROVAL',
      'DENY_CANCEL': 'CANCELLATION_DENIED',
      'REVERT_TO_APPROVED': 'APPROVED',
      'COMPLETE': 'COMPLETED',
      'REOPEN': 'ASSIGNED',
      'REOPEN_PENDING': 'PENDING_REVIEW',
      'ARCHIVE': 'ARCHIVED',
      'CREATE_PROFILE': 'PROFILE_CREATED',
      'MOVE_TO_NEW_REQUEST': 'READY_FOR_APPROVAL',
      'QUOTE': 'QUOTED',
      'DELETE': 'DELETED'
    };

    const targetStatus = statusMap[action] || action;
    const isLifecycleAction = ['ARCHIVED', 'DELETED', 'COMPLETED', 'CANCELLED'].includes(targetStatus.toUpperCase());
    
    if (isLifecycleAction && req.PK && req.SK) {
      // Direct record update for terminal states
      return performAdminAction(req.PK, req.SK, targetStatus === 'DELETED' ? 'DELETE' : (targetStatus === 'ARCHIVED' ? 'ARCHIVE' : targetStatus));
    } else {
      // Workflow transition update
      const { reqId, clientId } = resolveIds(req);
      if (!reqId || !clientId) throw new Error("Missing IDs for transition");
      return reviewRequest(reqId, clientId, targetStatus, note);
    }
  };

  const handleBulkUpdate = async () => {
    if (!bulkAction || selectedIds.length === 0) return;
    
    setIsBulkUpdating(true);
    const results = { success: 0, failed: 0 };
    
    const selectedRequests = requests.filter(r => selectedIds.includes(r.PK));
    
    const updates = selectedRequests.map(async (req) => {
      return updateRecordStatus(req, bulkAction, `Bulk update: ${bulkAction}`);
    });

    try {
      const settled = await Promise.allSettled(updates);
      settled.forEach(res => {
        if (res.status === 'fulfilled') results.success++;
        else results.failed++;
      });

      if (results.failed > 0) {
        showNotification(`Bulk update partial: ${results.success} success, ${results.failed} failed.`, "error");
      } else {
        showNotification(`Successfully updated ${results.success} records.`, "success");
      }
      
      setSelectedIds([]);
      setBulkAction('');
      setBulkConfirmModal(null);
      await fetchAllData();
    } catch (err) {
      showNotification("Bulk update failed: " + err.message, "error");
    } finally {
      setIsBulkUpdating(false);
    }
  };

  const resolveIds = (item) => {
    if (!item) return { reqId: null, clientId: null, jobId: null };
    
    const pk = String(item.PK || '');
    const sk = String(item.SK || '');
    
    // Request ID: Priority to direct field, then PK/SK parsing
    const reqId = item.request_id || 
                  (pk.startsWith('REQ#') ? pk.split('#')[1] : 
                  (sk.startsWith('REQ#') ? sk.split('#')[1] : null));
    
    // Client ID: Priority to direct field, then PK/SK parsing
    const clientId = item.client_id || 
                     (pk.startsWith('CLIENT#') ? pk.split('#')[1] : 
                     (sk.startsWith('CLIENT#') ? sk.split('#')[1] : null));
    
    // Job ID: Priority to job_id field (often present in REQUEST after approval), then PK if entity is JOB
    const jobId = item.job_id || (item.entity_type === 'JOB' ? pk.split('#')[1] : null);
    
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
      showNotification("Meet & Greet marked as completed!", "success");
      fetchAllData();
    } catch (err) {
      setModalError("Failed to verify M&G: " + err.message);
    } finally {
      setLoading(false);
    }
  };

  const _handleAdminAction = async (item, action) => {
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
      showNotification(`Record successfully ${action.toLowerCase()}d.`, "success");
      fetchAllData();
    } catch (err) {
      showNotification("Admin action failed: " + err.message, "error");
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
    } catch {
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

  const onReviewAction = async (req, action, note = "") => {
    try {
      setLoading(true);
      await updateRecordStatus(req, action, note);
      
      const statusMap = {
        'APPROVE': 'APPROVED',
        'DECLINE': 'DECLINED',
        'CANCEL': 'CANCELLED',
        'COMPLETE': 'COMPLETED',
        'ARCHIVE': 'ARCHIVED',
        'DELETE': 'DELETED'
      };
      const targetStatus = statusMap[action] || action;

      showNotification(`Status successfully updated to ${getStatusLabel(targetStatus)}`, "success");
      
      // Reconcile local state: Update the item in the local requests array immediately
      // to prevent stale data display while fetchAllData is in flight.
      setRequests(prev => prev.map(item => 
        (item.PK === req.PK && item.SK === req.SK) 
        ? { ...item, status: targetStatus } 
        : item
      ));

      // Close modal if open for this item
      if (selectedPet?._originItem?.PK === req.PK) {
        setSelectedPet(null);
      }
      
      // Refresh data to sync UI from source of truth
      await fetchAllData();
      setSelectedIds([]); // Clear bulk selection after individual action to be safe
    } catch (err) {
      console.error("Action failed:", err);
      showNotification("Action failed: " + err.message, "error");
      await fetchAllData(); // Refresh to sync UI with actual DB state
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
        setSelectedPet({ ...petData, _originItem: item });
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
        care_instructions: item.pet_info || 'No care instructions on file yet.',
        _originItem: item
      });
    }
  };

  const handleUpdatePet = async (updatedPet) => {
    try {
      setLoading(true);
      const originItem = selectedPet?._originItem;
      const { clientId, reqId } = resolveIds(originItem || selectedPet || updatedPet);
      const pid = updatedPet.pet_id || selectedPet?.pet_id || 'NEW';
      
      if (!clientId) throw new Error("Could not resolve Client ID for pet update.");
      
      await updatePet(pid, clientId, updatedPet);

      // Transition workflow if this was an intake record
      const intakeStatuses = ['PENDING_REVIEW', 'MEET_GREET_REQUIRED'];
      if (pid === 'NEW' && reqId && (!originItem?.status || intakeStatuses.includes(originItem.status))) {
        await reviewRequest(reqId, clientId, 'PROFILE_CREATED', "Automated: Profile created.");
      }

      setSelectedPet(null);
      fetchAllData();
    } catch (err) {
      alert("Failed to update/create pet record: " + err.message);
    } finally {
      setLoading(false);
    }
  };

  const renderStats = () => {
    const stats = {
      intake: requests.filter(r => r.status === 'PENDING_REVIEW').length,
      unassigned: requests.filter(r => (r.status === 'APPROVED' || r.status === 'JOB_CREATED') && !r.worker_id).length,
      scheduled: requests.filter(r => r.status === 'ASSIGNED' || r.status === 'SCHEDULED' || (r.status === 'JOB_CREATED' && r.worker_id)).length,
      alerts: requests.filter(r => r.status === 'CANCELLATION_REQUESTED').length
    };

    return (
      <div className="admin-stats-grid">
        <div className="stat-card" onClick={() => { setView('LIST'); setStatusFilter('PENDING_REVIEW'); }}>
          <span className="label">Intake Queue</span>
          <span className="value">{stats.intake}</span>
          <span className="trend neutral">New registrations</span>
        </div>
        <div className="stat-card" onClick={() => { setView('LIST'); setStatusFilter('READY_FOR_APPROVAL'); }}>
          <span className="label">Needs Assignment</span>
          <span className="value" style={{ color: stats.unassigned > 0 ? 'var(--warning-color)' : 'inherit' }}>
            {stats.unassigned}
          </span>
          <span className="trend">Approved, no staff</span>
        </div>
        <div className="stat-card" onClick={() => { setView('SCHEDULER'); setStatusFilter('ALL'); }}>
          <span className="label">Scheduled Visits</span>
          <span className="value">{stats.scheduled}</span>
          <span className="trend neutral">Total upcoming</span>
        </div>
        {stats.alerts > 0 && (
          <div className="stat-card" style={{ borderColor: 'var(--warning-color)' }} onClick={() => { setView('LIST'); setStatusFilter('ALL'); }}>
            <span className="label" style={{ color: 'var(--warning-color)' }}>Alerts</span>
            <span className="value" style={{ color: 'var(--warning-color)' }}>{stats.alerts}</span>
            <span className="trend up">Cancellation requests</span>
          </div>
        )}
      </div>
    );
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
    <div className="admin-page-container">
      {notification && (
        <div className={`notification-banner ${notification.type}`}>
          <span className="msg">{notification.message}</span>
          <button onClick={() => setNotification(null)}>&times;</button>
        </div>
      )}
      <header className="admin-header-bar card">
        <div className="header-left">
          <h1>Tog and Dogs Admin</h1>
          <nav className="view-selector">
            <button className={view === 'SCHEDULER' ? 'active' : ''} onClick={() => { setView('SCHEDULER'); setStatusFilter('ALL'); }}>Scheduler</button>
            <button className={view === 'LIST' ? 'active' : ''} onClick={() => setView('LIST')}>Request List</button>
          </nav>
        </div>
        <div className="header-right">
          <button onClick={handleLogout} className="button-secondary">Logout Staff</button>
        </div>
      </header>

      {renderStats()}

      <div className="admin-layout">

        <aside className="admin-sidebar card">
          <div className="filter-group">
            <h4>Staff Quick View</h4>
            <div className="staff-legend-box">
              {['Ryan', 'Wife', 'Nephew1', 'Nephew2', 'Unassigned'].map(name => (
                <div key={name} className="legend-item">
                  <span className="dot" style={{ backgroundColor: `var(--staff-${name.toLowerCase()})` }}></span>
                  <span className="legend-label">{name}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="filter-group">
            <h4>Quick Filters</h4>
            {[
              { id: 'PENDING_REVIEW', label: 'Intake Queue' },
              { id: 'PROFILE_CREATED', label: 'Profile Created' },
              { id: 'READY_FOR_APPROVAL', label: 'New Requests' },
              { id: 'QUOTED', label: 'Quoted' },
              { id: 'APPROVED', label: 'Approved' },
              { id: 'ASSIGNED', label: 'Scheduled' },
              { id: 'CANCELLED', label: 'Cancelled' },
              { id: 'ARCHIVED', label: 'Archived' },
              { id: 'DELETED', label: 'Trash / Deleted' },
              { id: 'ALL', label: 'All Active' }
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
              {selectedIds.length > 0 && (
                <div className="bulk-toolbar">
                  <div className="bulk-info">
                    <span className="count">{selectedIds.length}</span>
                    <span>visits selected</span>
                  </div>
                  <div className="bulk-actions">
                    <select 
                      value={bulkAction} 
                      onChange={(e) => setBulkAction(e.target.value)}
                      disabled={isBulkUpdating}
                      className="staff-select bulk-select"
                    >
                      <option value="">Choose status...</option>
                      <option value="PENDING_REVIEW">Requested / Intake</option>
                      <option value="READY_FOR_APPROVAL">New Request</option>
                      <option value="QUOTED">Quoted</option>
                      <option value="APPROVED">Approved</option>
                      <option value="ASSIGNED">Scheduled</option>
                      <option value="IN_PROGRESS">In Progress</option>
                      <option value="COMPLETED">Completed</option>
                      <option value="CANCELLED">Cancelled</option>
                      <option value="ARCHIVED">Archived</option>
                    </select>
                    <button 
                      onClick={() => setBulkConfirmModal({ count: selectedIds.length, target: bulkAction })}
                      className="button-primary"
                      disabled={!bulkAction || isBulkUpdating}
                    >
                      {isBulkUpdating ? 'Applying...' : 'Apply Bulk Update'}
                    </button>
                    <button 
                      onClick={() => setSelectedIds([])}
                      className="button-secondary"
                      disabled={isBulkUpdating}
                    >
                      Clear
                    </button>
                  </div>
                </div>
              )}
              <table className="request-table">
                <thead>
                  <tr>
                    <th style={{ width: '40px' }}>
                      <input 
                        type="checkbox" 
                        checked={requests.length > 0 && selectedIds.length === requests.length}
                        onChange={toggleSelectAll}
                        disabled={requests.length === 0}
                      />
                    </th>
                    <th>Customer / Service</th>
                    <th>Dates / Window</th>
                    <th>Status</th>
                    <th>Staff</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {requests.map(item => (
                    <tr key={item.PK} className={selectedIds.includes(item.PK) ? 'selected-row' : ''}>
                      <td>
                        <input 
                          type="checkbox" 
                          checked={selectedIds.includes(item.PK)}
                          onChange={() => toggleSelectOne(item.PK)}
                        />
                      </td>
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
                        {(() => {
                          const state = getWorkflowState(item);
                          return (
                            <div className="status-cell">
                              <span className={`${state.statusClass} ${state.isInvalid ? 'status-chip--urgent' : ''}`}>
                                {state.isInvalid ? "Needs Assignment" : getStatusLabel(item.status)}
                              </span>
                              {state.isInvalid && <div className="micro-text urgent-text">Missing worker assignment!</div>}
                            </div>
                          );
                        })()}
                      </td>
                      <td>
                        {(() => {
                          const state = getWorkflowState(item);
                          if (state.actions.includes("ASSIGN") || state.actions.includes("CHANGE_WORKER")) {
                            return (
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
                            );
                          }
                          return item.worker_id || '---';
                        })()}
                      </td>
                      <td>
                        <div className="btn-group-vertical">
                           {(() => {
                             const state = getWorkflowState(item);
                             return state.actions.map(action => {
                               if (action === 'EDIT_PET') return null; // Handled by row click
                               if (action === 'ASSIGN' || action === 'CHANGE_WORKER') return null; // Handled in Staff column
                               
                               const labels = {
                                 'APPROVE': 'Approve',
                                 'QUOTE': 'Quote',
                                 'CANCEL': 'Cancel',
                                 'VERIFY_MG': 'Verify M&G',
                                 'REVERT_TO_APPROVED': 'Back to Approved',
                                 'COMPLETE': 'Complete',
                                 'REOPEN': 'Reopen',
                                 'REOPEN_PENDING': 'Restore to Active',
                                 'ARCHIVE': 'Archive',
                                 'CREATE_PROFILE': 'Create Profile',
                                 'MOVE_TO_NEW_REQUEST': 'To New Request',
                                 'DELETE': 'Move to Trash'
                               };
                               
                               const getButtonClass = (act) => {
                                 if (act === 'DELETE' || act === 'CANCEL') return 'btn-micro urgent';
                                 if (['APPROVE', 'REOPEN', 'REOPEN_PENDING', 'COMPLETE', 'VERIFY_MG'].includes(act)) return 'btn-micro highlight';
                                 return 'btn-micro';
                               };
                               
                               return (
                                 <button 
                                   key={action}
                                   onClick={() => onReviewAction(item, action)} 
                                   className={getButtonClass(action)}
                                 >
                                   {labels[action] || action}
                                 </button>
                               );
                             });
                           })()}
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
          onStatusUpdate={(item, status, note) => onReviewAction(item, status, note)}
        />
      )}

      {bulkConfirmModal && (
        <div className="modal-overlay">
          <div className="modal-content bulk-confirm-modal">
            <div className="modal-header">
              <h2>Confirm Bulk Update</h2>
              <p>You are about to update <strong>{bulkConfirmModal.count}</strong> selected records.</p>
            </div>
            
            <div className="bulk-confirm-details">
              <p>Target Status: <span className="highlight-status">{getStatusLabel(bulkConfirmModal.target)}</span></p>
              <div className="safety-notice">
                <p>● This action will update only the currently selected visible records.</p>
                {bulkConfirmModal.target === 'ARCHIVED' ? (
                  <p>● This uses archive/soft-delete behavior. Records can be restored from the Archived view.</p>
                ) : (
                  <p>● Records will be moved to the {getStatusLabel(bulkConfirmModal.target)} workflow phase.</p>
                )}
              </div>
            </div>

            <div className="modal-footer">
              <button 
                className="button-secondary" 
                onClick={() => setBulkConfirmModal(null)}
                disabled={isBulkUpdating}
              >
                Cancel
              </button>
              <button 
                className="button-primary" 
                onClick={handleBulkUpdate}
                disabled={isBulkUpdating}
              >
                {isBulkUpdating ? 'Updating...' : 'Confirm & Apply'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AdminDashboard;
