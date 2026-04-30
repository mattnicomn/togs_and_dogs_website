import React, { useState, useEffect } from 'react';
import { signIn, signOut, getSession, getEffectiveRole } from '../api/auth';

import { getAdminRequests, reviewRequest, assignWorker, getGoogleStatus, initiateGoogleAuth, getPet, updatePet, processCancellationDecision, performAdminAction, purgeRecord, disconnectGoogle, getStaff, createStaff, updateStaff, disableStaff, onboardStaff, linkCognitoUser, resendInvite, getClients, createClient, updateClient, disableClient } from '../api/client';




import MasterScheduler from './MasterScheduler';
import CareCard from './CareCard';
import '../Admin.css';


const AdminDashboard = () => {
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [role, setRole] = useState('unknown');

  const [loginData, setLoginData] = useState({ email: '', password: '' });
  const [authChallenge, setAuthChallenge] = useState(null);
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [challengeContext, setChallengeContext] = useState(null);
  const [googleStatus, setGoogleStatus] = useState(null);
  const [staffList, setStaffList] = useState([]);
  const [editingStaffId, setEditingStaffId] = useState(null);
  const [staffLinkPrompt, setStaffLinkPrompt] = useState(null);
  const [staffForm, setStaffForm] = useState({
    display_name: '',
    role: 'Staff',
    email: '',
    is_assignable: true,
    assignment_color: 'var(--staff-ryan)',
    creation_mode: 'onboard', // onboard or profile_only
    send_invite: true,
    phone: '',
    notes: ''
  });

  const [clientList, setClientList] = useState([]);
  const [editingClientId, setEditingClientId] = useState(null);
  const [clientForm, setClientForm] = useState({
    display_name: '',
    email: '',
    phone: '',
    address: '',
    emergency_contact: '',
    notes: ''
  });
  const [isSavingClient, setIsSavingClient] = useState(false);

  const [isSavingStaff, setIsSavingStaff] = useState(false);




  const [view, setView] = useState('SCHEDULER'); // SCHEDULER or LIST
  const [selectedPet, setSelectedPet] = useState(null);
  const [assigningId, setAssigningId] = useState(null); 
  const [modalError, setModalError] = useState(null);
  const [notification, setNotification] = useState(null);
  const [selectedIds, setSelectedIds] = useState([]);
  const [bulkAction, setBulkAction] = useState('');
  const [isBulkUpdating, setIsBulkUpdating] = useState(false);
  const [bulkConfirmModal, setBulkConfirmModal] = useState(null);
  const [purgeModal, setPurgeModal] = useState(null); // { item } — confirmation before permanent delete
  const [purgeConfirmText, setPurgeConfirmText] = useState('');
  const [isBulkPurging, setIsBulkPurging] = useState(false);

  const showNotification = (message, type = 'info') => {
    setNotification({ message, type });
    setTimeout(() => setNotification(null), 5000);
  };
  
  const getStatusClass = (status = "") => {
    const s = (status || "").toUpperCase();
    if (s.includes("NEW") || s.includes("INTAKE") || s.includes("PENDING") || s.includes("REVIEW")) return "status-chip status-chip--new";
    if (s.includes("PROFILE_CREATED")) return "status-chip status-chip--profile";
    if (s.includes("READY") || s.includes("REQUEST")) return "status-chip status-chip--ready";
    if (s.includes("MEET") || s.includes("MG_")) return "status-chip status-chip--ready";
    if (s.includes("QUOTE")) return "status-chip status-chip--quoted";
    if (s.includes("APPROVED") || s.includes("BOOKED")) return "status-chip status-chip--approved";
    if (s.includes("SCHEDULED") || s.includes("ASSIGNED") || s.includes("JOB_CREATED")) return "status-chip status-chip--assigned";
    if (s.includes("IN_PROGRESS")) return "status-chip status-chip--progress";
    if (s.includes("COMPLETED")) return "status-chip status-chip--completed";
    if (s.includes("CANCELLED")) return "status-chip status-chip--cancelled";
    if (s.includes("REJECTED") || s.includes("DECLINED") || s.includes("DENIED")) return "status-chip status-chip--rejected";
    if (s.includes("ARCHIVE")) return "status-chip status-chip--archived";
    if (s.includes("DELETED") || s.includes("TRASH")) return "status-chip status-chip--deleted";
    return "status-chip status-chip--archived";
  };

  const getStatusLabel = (status = "") => {
    const s = (status || "").toUpperCase();
    if (s === 'PENDING_REVIEW' || s === 'NEEDS_REVIEW') return "Needs Review";
    if (s === 'MEET_GREET_REQUIRED' || s === 'NEEDS_MG') return "Needs M&G";
    if (s === 'MG_SCHEDULED') return "M&G Scheduled";
    if (s === 'MG_COMPLETED') return "M&G Completed";
    if (s === 'PROFILE_CREATED') return "Profile Created";
    if (s === 'READY_FOR_APPROVAL' || s === 'NEW_REQUEST') return "New Request";
    if (s === 'QUOTE_NEEDED') return "Quote Needed";
    if (s === 'QUOTE_SENT' || s === 'QUOTED') return "Quoted";
    if (s === 'APPROVED' || s === 'BOOKED') return "Approved";
    if (s === 'ASSIGNED' || s === 'JOB_CREATED' || s === 'SCHEDULED') return "Scheduled";
    if (s === 'IN_PROGRESS') return "In Progress";
    if (s === 'COMPLETED') return "Completed";
    if (s === 'CANCELLATION_REQUESTED') return "Cancel Requested";
    if (s === 'CANCELLATION_DENIED') return "Cancel Denied";
    if (s === 'CANCELLED') return "Cancelled";
    if (s === 'ARCHIVED' || s === 'ARCHIVE') return "Archived";
    if (s === 'DELETED' || s === 'DELETE' || s === 'TRASH') return "Deleted";
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
      state.actions = ["REOPEN_PENDING", "PURGE_FOREVER"]; // Restore or permanently remove
      return state;
    }

    // Active Workflow Status Actions
    switch (status) {
      case 'PENDING_REVIEW':
      case 'NEEDS_REVIEW':
        state.actions = ["CREATE_PROFILE", "MEET_GREET", "APPROVE", "CANCEL"];
        break;
      case 'PROFILE_CREATED':
        state.actions = ["MOVE_TO_NEW_REQUEST", "MEET_GREET", "QUOTE", "APPROVE", "CANCEL", "EDIT_PET"];
        break;
      case 'MEET_GREET_REQUIRED':
      case 'NEEDS_MG':
        state.actions = ["MG_SCHEDULED", "VERIFY_MG", "CANCEL", "EDIT_PET"];
        break;
      case 'MG_SCHEDULED':
        state.actions = ["VERIFY_MG", "MEET_GREET_REQUIRED", "CANCEL", "EDIT_PET"];
        break;
      case 'MG_COMPLETED':
        state.actions = ["QUOTE", "QUOTED", "APPROVE", "ASSIGN", "CANCEL", "EDIT_PET"];
        break;
      case 'QUOTE_NEEDED':
        state.actions = ["QUOTED", "APPROVE", "CANCEL", "EDIT_PET"];
        break;
      case 'QUOTE_SENT':
      case 'QUOTED':
        state.actions = ["APPROVE", "CANCEL", "ARCHIVE", "EDIT_PET"];
        break;

      case 'READY_FOR_APPROVAL':
      case 'NEW_REQUEST':
        state.actions = ["QUOTE", "APPROVE", "CANCEL", "EDIT_PET"];
        break;
      case 'APPROVED':
      case 'BOOKED':
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
        const userRole = getEffectiveRole(session);
        if (['owner', 'admin', 'staff'].includes(userRole)) {
          setIsAuthenticated(true);
          setRole(userRole);
          fetchAllData();
          fetchGoogleStatus();
        } else {
          setError("Access denied. You do not have permission to view the Staff Portal.");
          setIsAuthenticated(false);
        }
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
      const result = await signIn(loginData.email, loginData.password);
      if (result && result.challenge === 'NEW_PASSWORD_REQUIRED') {
        setAuthChallenge('NEW_PASSWORD_REQUIRED');
        setChallengeContext({
          userAttributes: result.userAttributes,
          cognitoUser: result.cognitoUser
        });
        setLoading(false);
        return;
      }
      const session = await getSession();
      const userRole = getEffectiveRole(session);
      if (['owner', 'admin', 'staff'].includes(userRole)) {
        setIsAuthenticated(true);
        setRole(userRole);
        fetchAllData();
        fetchGoogleStatus();
      } else {
        setError("Access denied. Insufficient permissions.");
        setIsAuthenticated(false);
      }

    } catch (err) {
      setError(err.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  const handleCompleteNewPassword = async (e) => {
    e.preventDefault();
    if (newPassword !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }
    if (!newPassword) {
      setError("Please enter a new password.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const { cognitoUser } = challengeContext;
      cognitoUser.completeNewPasswordChallenge(newPassword, {}, {

        onSuccess: async (result) => {
          setAuthChallenge(null);
          setChallengeContext(null);
          const session = await getSession();
          const userRole = getEffectiveRole(session);
          if (['owner', 'admin', 'staff'].includes(userRole)) {
            setIsAuthenticated(true);
            setRole(userRole);
            fetchAllData();
            fetchGoogleStatus();
          } else {
            setError("Access denied. Insufficient permissions.");
            setIsAuthenticated(false);
          }
          setLoading(false);
        },
        onFailure: (err) => {
          setError(err.message || 'Failed to set new password.');
          setLoading(false);
        }
      });
    } catch (err) {
      setError(err.message || 'An error occurred.');
      setLoading(false);
    }
  };


  const fetchStaffData = async () => {
    try {
      const data = await getStaff();
      setStaffList(data.staff || []);
    } catch (err) {
      console.error("Failed to fetch staff list:", err);
    }
  };

  const fetchClientData = async () => {
    try {
      const data = await getClients();
      setClientList(data.clients || []);
    } catch (err) {
      console.error("Failed to fetch client list:", err);
    }
  };


  const handleSaveStaff = async (e) => {
    e.preventDefault();
    if (!staffForm.display_name.trim()) {
      showNotification("Display name is required", "error");
      return;
    }
    if (staffForm.creation_mode === 'onboard' && !editingStaffId && !staffForm.email.trim()) {
      showNotification("Email is required for Cognito onboarding", "error");
      return;
    }
    
    setIsSavingStaff(true);
    try {
      if (editingStaffId) {
        await updateStaff(editingStaffId, staffForm);
        showNotification("Staff updated successfully", "success");
      } else {
        if (staffForm.creation_mode === 'onboard') {
          await onboardStaff(staffForm);
          showNotification("Staff created and Cognito onboarding triggered", "success");
        } else {
          await createStaff(staffForm);
          showNotification("Staff profile created successfully", "success");
        }
      }
      setStaffForm({
        display_name: '',
        role: 'Staff',
        email: '',
        is_assignable: true,
        assignment_color: 'var(--staff-ryan)',
        creation_mode: 'onboard',
        send_invite: true,
        phone: '',
        notes: ''
      });
      setEditingStaffId(null);
      await fetchStaffData();
    } catch (err) {
      if (err.message && err.message.includes("Cognito user already exists")) {
        setStaffLinkPrompt({
          email: staffForm.email,
          display_name: staffForm.display_name,
          role: staffForm.role,
          is_assignable: staffForm.is_assignable,
          assignment_color: staffForm.assignment_color,
          phone: staffForm.phone,
          notes: staffForm.notes
        });
      } else {
        showNotification(err.message || "Failed to save staff", "error");
      }
    } finally {
      setIsSavingStaff(false);
    }
  };

  const handleDisableStaff = async (staffId, hasCognito) => {
    let disableCognito = false;
    if (hasCognito) {
      const choice = window.confirm("Do you also want to disable this staff member's Cognito login access? \n\nClick OK to disable BOTH the profile and Cognito login.\nClick Cancel to disable ONLY the profile.");
      disableCognito = choice;
    } else {
      if (!window.confirm("Are you sure you want to disable this staff profile? They will no longer appear as assignable.")) return;
    }
    
    try {
      await disableStaff(staffId, disableCognito ? { disable_cognito: true } : null);
      showNotification("Staff disabled successfully", "success");
      await fetchStaffData();
    } catch (err) {
      showNotification(err.message || "Failed to disable staff", "error");
    }
  };
  
  const executeStaffAction = async (staffId, action) => {
    let confirmText = "";
    if (action === 'disable') confirmText = "Are you sure you want to disable access?";
    if (action === 'enable') confirmText = "Are you sure you want to re-enable access?";
    if (action === 'unlink') confirmText = "Are you sure you want to unlink Cognito? The profile will no longer map to a login.";
    if (action === 'delete_profile') confirmText = "Are you sure you want to PERMANENTLY delete this profile? This cannot be undone.";
    if (action === 'delete_cognito') {
      const input = window.prompt("Type 'DELETE COGNITO USER' to confirm deleting the Cognito user account:");
      if (input !== 'DELETE COGNITO USER') {
        showNotification("Deletion cancelled. Text did not match.", "info");
        return;
      }
    } else if (confirmText && !window.confirm(confirmText)) {
      return;
    }

    try {
      await updateStaff(staffId, { action });
      showNotification(`Staff action '${action}' completed successfully`, "success");
      await fetchStaffData();
    } catch (err) {
      showNotification(err.message || `Failed to execute ${action}`, "error");
    }
  };

  const executeClientAction = async (clientId, action) => {
    let confirmText = "";
    if (action === 'disable') confirmText = "Are you sure you want to disable client access?";
    if (action === 'enable') confirmText = "Are you sure you want to re-enable client access?";
    if (action === 'unlink') confirmText = "Are you sure you want to unlink Cognito login from this client profile?";
    if (action === 'delete_profile') confirmText = "Are you sure you want to PERMANENTLY delete this client profile?";
    if (action === 'delete_cognito') {
      const input = window.prompt("Type 'DELETE COGNITO USER' to confirm deleting the client login:");
      if (input !== 'DELETE COGNITO USER') {
        showNotification("Deletion cancelled. Text did not match.", "info");
        return;
      }
    } else if (confirmText && !window.confirm(confirmText)) {
      return;
    }

    try {
      await updateClient(clientId, { action });
      showNotification(`Client action '${action}' completed successfully`, "success");
      await fetchClientData();
    } catch (err) {
      showNotification(err.message || `Failed to execute ${action}`, "error");
    }
  };


  const handleEditStaff = (staff) => {
    setEditingStaffId(staff.staff_id);
    setStaffForm({
      display_name: staff.display_name,
      role: staff.role || 'Staff',
      email: staff.email || '',
      is_assignable: staff.is_assignable !== false,
      assignment_color: staff.assignment_color || 'var(--staff-ryan)',
      creation_mode: 'profile_only',
      send_invite: true,
      phone: staff.phone || '',
      notes: staff.notes || ''
    });

    setView('STAFF_MGMT');
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
      fetchStaffData();
      fetchClientData();

      
      if (view === 'SCHEDULER') {

        const data = await getAdminRequests('ALL');
        // Exclude lifecycle/removal statuses from the scheduler timeline
        const terminalStatuses = ['ARCHIVED', 'DELETED', 'COMPLETED', 'CANCELLED'];
        setRequests((data.requests || []).filter(r => !terminalStatuses.includes((r.status || '').toUpperCase())));
      } else {
        const terminalStatuses = ['COMPLETED', 'CANCELLED', 'ARCHIVED', 'DELETED', 'TRASH', 'ARCHIVE'];
        const isActiveFilter = !terminalStatuses.includes(statusFilter.toUpperCase());

        let queryStatus = statusFilter;
        if (statusFilter === 'ARCHIVE' || statusFilter === 'ARCHIVED') queryStatus = 'ARCHIVED';
        if (statusFilter === 'TRASH' || statusFilter === 'DELETED') queryStatus = 'DELETED';

        let data;
        if (isActiveFilter) {
          data = await getAdminRequests('ALL', startKey, timeframeFilter);
        } else {
          data = await getAdminRequests(queryStatus, startKey, timeframeFilter);
        }

        let items = data.requests || [];

        if (isActiveFilter && statusFilter !== 'ALL') {
          items = items.filter(r => {
            const stat = (r.status || '').toUpperCase();
            if (statusFilter === 'NEEDS_ACTION') {
              return (
                stat === 'PENDING_REVIEW' || stat === 'NEEDS_REVIEW' ||
                stat === 'MEET_GREET_REQUIRED' || stat === 'NEEDS_MG' ||
                stat === 'QUOTE_NEEDED' ||
                stat === 'APPROVED' || stat === 'BOOKED' ||
                stat === 'CANCELLATION_REQUESTED'
              );
            }
            if (statusFilter === 'READY_FOR_APPROVAL') return stat === 'READY_FOR_APPROVAL' || stat === 'NEW_REQUEST';
            if (statusFilter === 'MEET_GREET_REQUIRED') return stat === 'MEET_GREET_REQUIRED' || stat === 'NEEDS_MG';
            if (statusFilter === 'QUOTED') return stat === 'QUOTED' || stat === 'QUOTE_SENT';
            if (statusFilter === 'ASSIGNED') return stat === 'ASSIGNED' || stat === 'SCHEDULED';
            return stat === statusFilter.toUpperCase();
          });
        } else if (statusFilter === 'ALL') {
          const exclusionStatuses = ['COMPLETED', 'ARCHIVED', 'DELETED', 'CANCELLED', 'DECLINED'];
          items = items.filter(r => !exclusionStatuses.includes((r.status || '').toUpperCase()));
        }

        setRequests(items);
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
    const currentIds = requests.map(r => r.PK);
    const allSelected = currentIds.length > 0 && currentIds.every(id => selectedIds.includes(id));
    if (allSelected) {
      setSelectedIds(prev => prev.filter(id => !currentIds.includes(id)));
    } else {
      setSelectedIds(prev => [...new Set([...prev, ...currentIds])]);
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
      'QUOTE': 'QUOTE_NEEDED',
      'QUOTED': 'QUOTED',
      'QUOTE_SENT': 'QUOTE_SENT',
      'MG_SCHEDULED': 'MG_SCHEDULED',
      'MEET_GREET_REQUIRED': 'MEET_GREET_REQUIRED',
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
    setError(null);
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
        const actionLabel = bulkAction === 'DELETE' ? 'moved to Trash' : 
                           bulkAction === 'REOPEN_PENDING' ? 'restored to Active' : 
                           `updated to ${getStatusLabel(bulkAction)}`;
        showNotification(`Successfully ${actionLabel}: ${results.success} records.`, "success");
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
    setModalError(null);
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
    setModalError(null);
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
    setError(null);
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
    // Clear any previous notification before this action starts
    setError(null);

    const actionSuccessMessages = {
      'APPROVE':             'Visit approved successfully.',
      'APPROVED':            'Visit approved successfully.',
      'DECLINE':             'Request declined.',
      'DECLINED':            'Request declined.',
      'CANCEL':              'Request cancelled.',
      'CANCELLED':           'Request cancelled.',
      'COMPLETE':            'Visit marked as completed.',
      'COMPLETED':           'Visit marked as completed.',
      'ARCHIVE':             'Record archived.',
      'ARCHIVED':            'Record archived.',
      'DELETE':              'Record moved to trash.',
      'DELETED':             'Record moved to trash.',
      'VERIFY_MG':           'Meet & Greet marked as completed.',
      'VERIFY_MEET_GREET':   'Meet & Greet marked as completed.',
      'MG_SCHEDULED':        'M&G scheduled.',
      'QUOTED':              'Request marked as Quoted.',
      'QUOTE':               'Quote needed flag set.',
      'QUOTE_NEEDED':        'Quote needed flag set.',
      'APPROVE_CANCEL':      'Cancellation approved.',
      'DENY_CANCEL':         'Cancellation denied.',
      'REVERT_TO_APPROVED':  'Reverted to Approved.',
      'REOPEN':              'Record reopened.',
      'REOPEN_PENDING':      'Record restored to Active.',
      'ASSIGN':              'Worker assigned.',
      'CREATE_PROFILE':      'Profile created.',
      'MOVE_TO_NEW_REQUEST': 'Moved to New Request.',
      'MEET_GREET':          'M&G required flag set.',
      'MEET_GREET_REQUIRED': 'M&G required flag set.',
    };

    let actionSucceeded = false;

    try {
      setLoading(true);
      await updateRecordStatus(req, action, note);
      actionSucceeded = true;

      const statusMap = {
        'APPROVE': 'APPROVED',
        'DECLINE': 'DECLINED',
        'CANCEL': 'CANCELLED',
        'COMPLETE': 'COMPLETED',
        'ARCHIVE': 'ARCHIVED',
        'DELETE': 'DELETED'
      };
      const targetStatus = statusMap[action] || action;

      const successMsg = actionSuccessMessages[action] || actionSuccessMessages[targetStatus] || `Status updated to ${getStatusLabel(targetStatus)}.`;
      showNotification(successMsg, "success");

      // Reconcile local state immediately to prevent stale display while refresh is in flight
      setRequests(prev => prev.map(item =>
        (item.PK === req.PK && item.SK === req.SK)
        ? { ...item, status: targetStatus }
        : item
      ));

      // Close modals if they are open for this item
      if (selectedPet?._originItem?.PK === req.PK) {
        setSelectedPet(null);
      }
      if (decisionModal && decisionModal.item.PK === req.PK) {
        setDecisionModal(null);
      }

      setSelectedIds([]);
    } catch (err) {
      console.error("Action failed:", err);
      showNotification("Action failed: " + err.message, "error");
    } finally {
      setLoading(false);
    }

    // Always refresh after action attempt — separately so a refresh failure
    // never overwrites the action result notification.
    try {
      await fetchAllData();
    } catch (refreshErr) {
      console.warn("Post-action refresh failed:", refreshErr);
      if (actionSucceeded) {
        // Show a soft warning — don't overwrite the success toast
        console.warn("Refresh failed after successful action. Data may be stale — reload the page if needed.");
      }
    }
  };


  const handlePurgeRecord = async (item) => {
    setError(null);
    const pk = item.PK;
    const sk = item.SK;
    if (!pk || !sk) {
      showNotification("Error: Missing record keys — cannot purge.", "error");
      return;
    }
    try {
      setLoading(true);
      await purgeRecord(pk, sk);
      // Remove row from local state immediately
      setRequests(prev => prev.filter(r => !(r.PK === pk && r.SK === sk)));
      showNotification("Record permanently deleted.", "success");
      setPurgeModal(null);
    } catch (err) {
      showNotification("Permanent delete failed: " + err.message, "error");
      setPurgeModal(null);
    } finally {
      setLoading(false);
    }
  };

  const handleBulkPurge = async () => {
    setError(null);
    if (selectedIds.length === 0) return;
    setIsBulkPurging(true);

    const selectedItems = requests.filter(r => selectedIds.includes(r.PK) && (r.status || '').toUpperCase() === 'DELETED');
    
    if (selectedItems.length === 0) {
      showNotification("No valid DELETED records selected for permanent delete.", "error");
      setIsBulkPurging(false);
      setBulkConfirmModal(null);
      return;
    }

    const payload = selectedItems.map(item => ({ PK: item.PK, SK: item.SK }));

    try {
      // Import/require purgeRecordsBulk from client
      const response = await purgeRecordsBulk(payload);

      const deletedPKs = selectedItems.map(item => item.PK);
      setRequests(prev => prev.filter(r => !deletedPKs.includes(r.PK)));
      setSelectedIds([]);
      setBulkConfirmModal(null);

      if (response.failed_count > 0 || response.skipped_count > 0) {
        showNotification(
          `Purge completed with issues. Deleted: ${response.deleted_count}, Failed: ${response.failed_count}, Skipped: ${response.skipped_count}`, 
          "error"
        );
      } else {
        showNotification(response.message || "Bulk purge complete.", "success");
      }
    } catch (err) {
      showNotification("Bulk permanent delete failed: " + err.message, "error");
      setBulkConfirmModal(null);
    } finally {
      setIsBulkPurging(false);
      fetchAllData();
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
      
      await updatePet(pid, clientId, { ...updatedPet, request_id: reqId });

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
        <div className="stat-card" onClick={() => { setView('LIST'); setStatusFilter('NEEDS_ACTION'); }}>
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
    if (authChallenge === 'NEW_PASSWORD_REQUIRED') {
      return (
        <div className="section auth-section">
          <div className="card auth-card">
            <h1>Create New Password</h1>
            <p className="subtitle">For security, please create a new password before continuing.</p>
            <form onSubmit={handleCompleteNewPassword} className="premium-form">
              <div className="field">
                <label>New Password</label>
                <input 
                  type="password" 
                  value={newPassword} 
                  onChange={(e) => setNewPassword(e.target.value)} 
                  required 
                />
              </div>
              <div className="field">
                <label>Confirm New Password</label>
                <input 
                  type="password" 
                  value={confirmPassword} 
                  onChange={(e) => setConfirmPassword(e.target.value)} 
                  required 
                />
              </div>
              <button type="submit" className="button-primary" disabled={loading}>
                {loading ? 'Updating...' : 'Set Password & Sign In'}
              </button>
              {error && <p className="error-text">{error}</p>}
              <button type="button" onClick={() => { setAuthChallenge(null); setError(null); }} className="button-secondary" style={{ marginTop: '16px', width: '100%', padding: '12px' }}>
                Back to Sign In
              </button>
            </form>
          </div>
        </div>
      );
    }

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
            {['owner', 'admin'].includes(role) && (
              <button className={view === 'STAFF_MGMT' ? 'active' : ''} onClick={() => setView('STAFF_MGMT')}>Staff Management</button>
            )}
            {['owner', 'admin'].includes(role) && (
              <button className={view === 'CLIENT_MGMT' ? 'active' : ''} onClick={() => setView('CLIENT_MGMT')}>Client Management</button>
            )}


          </nav>
        </div>
        <div className="header-right">
          <button onClick={handleLogout} className="button-secondary">Logout Staff</button>
        </div>
      </header>

      {renderStats()}

      <div className="admin-layout">

        <aside className="admin-sidebar card">
          {view === 'LIST' && (
            <div className="filter-group">
              <h4>Staff Quick View</h4>
              <div className="staff-legend-box">
                {(staffList.length > 0 
                  ? [...staffList, { display_name: 'Unassigned', assignment_color: 'var(--staff-unassigned)' }] 
                  : [{ display_name: 'Unassigned', assignment_color: 'var(--staff-unassigned)' }]
                ).map(s => (
                  <div key={s.display_name} className="legend-item">
                    <span className="dot" style={{ backgroundColor: s.assignment_color || `var(--staff-${s.display_name.toLowerCase()})` }}></span>
                    <span className="legend-label">{s.display_name}</span>
                  </div>
                ))}

              </div>
            </div>
          )}

          {view === 'LIST' && (
            <div className="filter-group">
              <h4>Quick Filters</h4>
              {[
                { id: 'NEEDS_ACTION', label: 'Needs Action' },
                { id: 'READY_FOR_APPROVAL', label: 'New' },
                { id: 'MEET_GREET_REQUIRED', label: 'Needs M&G' },
                { id: 'QUOTED', label: 'Quoted' },
                { id: 'APPROVED', label: 'Approved' },
                { id: 'ASSIGNED', label: 'Scheduled' },
                { id: 'COMPLETED', label: 'Completed' },
                { id: 'ALL', label: 'All Active' }
              ].map(f => {
                const count = f.id === 'ALL' 
                  ? requests.filter(r => !['COMPLETED', 'ARCHIVED', 'DELETED', 'CANCELLED', 'DECLINED'].includes((r.status || '').toUpperCase())).length
                  : f.id === 'NEEDS_ACTION'
                  ? requests.filter(r => {
                      const stat = (r.status || '').toUpperCase();
                      return (
                        stat === 'PENDING_REVIEW' || stat === 'NEEDS_REVIEW' ||
                        stat === 'MEET_GREET_REQUIRED' || stat === 'NEEDS_MG' ||
                        stat === 'QUOTE_NEEDED' ||
                        stat === 'APPROVED' || stat === 'BOOKED' ||
                        stat === 'CANCELLATION_REQUESTED'
                      );
                    }).length
                  : requests.filter(r => (r.status || '').toUpperCase() === f.id || 
                      (f.id === 'READY_FOR_APPROVAL' && (r.status || '').toUpperCase() === 'NEW_REQUEST') ||
                      (f.id === 'MEET_GREET_REQUIRED' && (r.status || '').toUpperCase() === 'NEEDS_MG') ||
                      (f.id === 'QUOTED' && (r.status || '').toUpperCase() === 'QUOTE_SENT') ||
                      (f.id === 'ASSIGNED' && (r.status || '').toUpperCase() === 'SCHEDULED')
                    ).length;
                return (
                  <button 
                    key={f.id}
                    className={`filter-option ${statusFilter === f.id ? 'active' : ''}`}
                    onClick={() => setStatusFilter(f.id)}
                  >
                    {f.label} <span className="filter-count" style={{ float: 'right', opacity: 0.7, fontSize: '11px', fontWeight: 'bold' }}>({count})</span>
                  </button>
                );
              })}

            </div>
          )}

          {view === 'LIST' && (
            <div className="filter-group">
              <h4>Closed / History</h4>
              {[
                { id: 'CANCELLED', label: 'Cancelled' },
                { id: 'ARCHIVED', label: 'Archived' },
                { id: 'DELETED', label: 'Trash / Deleted' }
              ].map(f => {
                const count = requests.filter(r => {
                  const stat = (r.status || '').toUpperCase();
                  if (f.id === 'ARCHIVED') return stat === 'ARCHIVED' || stat === 'ARCHIVE';
                  if (f.id === 'DELETED') return stat === 'DELETED' || stat === 'TRASH';
                  return stat === f.id;
                }).length;
                return (
                  <button 
                    key={f.id}
                    className={`filter-option ${statusFilter === f.id ? 'active' : ''}`}
                    onClick={() => setStatusFilter(f.id)}
                  >
                    {f.label} <span className="filter-count" style={{ float: 'right', opacity: 0.7, fontSize: '11px', fontWeight: 'bold' }}>({count})</span>
                  </button>
                );
              })}

            </div>
          )}

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
              staffList={staffList}
              onReview={(req) => {
                if (req.status === 'CANCELLATION_REQUESTED') {
                  handleProcessCancellation(req);
                } else {
                  setDecisionModal({ item: req, type: 'WORKFLOW_REVIEW' });
                }
              }}
              onAssign={(req) => setAssigningId(req.PK)}
              onSelectPet={handleSelectPet}
            />
          ) : view === 'STAFF_MGMT' && ['owner', 'admin'].includes(role) ? (


            <div className="staff-management-container card" style={{ padding: '24px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
                <h2>{editingStaffId ? 'Edit Staff Profile' : 'Add New Staff Profile'}</h2>
                {editingStaffId && (
                  <button className="button-secondary" onClick={() => {
                    setEditingStaffId(null);
                    setStaffForm({
                      display_name: '',
                      role: 'Staff',
                      email: '',
                      is_assignable: true,
                      assignment_color: 'var(--staff-ryan)',
                      creation_mode: 'onboard',
                      send_invite: true,
                      phone: '',
                      notes: ''
                    });

                  }}>Cancel Edit</button>
                )}
              </div>
              
              <form onSubmit={handleSaveStaff} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px', marginBottom: '32px', borderBottom: '1px solid var(--border)', paddingBottom: '32px' }}>
                {!editingStaffId && (
                  <div className="field" style={{ gridColumn: 'span 2', display: 'flex', gap: '20px', marginBottom: '10px' }}>
                    <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                      <input 
                        type="radio" 
                        name="creation_mode" 
                        value="onboard" 
                        checked={staffForm.creation_mode === 'onboard'} 
                        onChange={(e) => setStaffForm({ ...staffForm, creation_mode: e.target.value })}
                      />
                      Onboard New Cognito User
                    </label>
                    <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                      <input 
                        type="radio" 
                        name="creation_mode" 
                        value="profile_only" 
                        checked={staffForm.creation_mode === 'profile_only'} 
                        onChange={(e) => setStaffForm({ ...staffForm, creation_mode: e.target.value })}
                      />
                      Create Local Profile Only
                    </label>
                  </div>
                )}

                <div className="field">
                  <label>Display Name *</label>
                  <input 
                    type="text" 
                    value={staffForm.display_name} 
                    onChange={(e) => setStaffForm({ ...staffForm, display_name: e.target.value })} 
                    placeholder="e.g. Ryan"
                    required 
                    style={{ width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid var(--border)' }}
                  />
                </div>
                
                <div className="field">
                  <label>Role</label>
                  <select 
                    value={staffForm.role} 
                    onChange={(e) => setStaffForm({ ...staffForm, role: e.target.value })}
                    style={{ width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid var(--border)' }}
                  >
                    <option value="Staff">Staff</option>
                    <option value="Admin">Admin</option>
                    <option value="owner">Owner</option>
                  </select>
                </div>
                
                <div className="field">
                  <label>Email {staffForm.creation_mode === 'onboard' ? '*' : '(Optional)'}</label>
                  <input 
                    type="email" 
                    value={staffForm.email} 
                    onChange={(e) => setStaffForm({ ...staffForm, email: e.target.value })} 
                    placeholder="staff@example.com"
                    required={staffForm.creation_mode === 'onboard'}
                    style={{ width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid var(--border)' }}
                  />
                </div>
                
                <div className="field">
                  <label>Assignment Color</label>
                  <select 
                    value={staffForm.assignment_color} 
                    onChange={(e) => setStaffForm({ ...staffForm, assignment_color: e.target.value })}
                    style={{ width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid var(--border)' }}
                  >
                    <option value="var(--staff-ryan)">Orange (Default)</option>
                    <option value="var(--staff-wife)">Green</option>
                    <option value="var(--staff-nephew1)">Yellow</option>
                    <option value="var(--staff-nephew2)">Red</option>
                    <option value="#9c27b0">Purple</option>
                    <option value="#2196f3">Blue</option>
                    <option value="#00bcd4">Cyan</option>
                  </select>
                </div>

                <div className="field">
                  <label>Phone (Optional)</label>
                  <input 
                    type="text" 
                    value={staffForm.phone} 
                    onChange={(e) => setStaffForm({ ...staffForm, phone: e.target.value })} 
                    placeholder="555-123-4567"
                    style={{ width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid var(--border)' }}
                  />
                </div>

                <div className="field">
                  <label>Notes (Optional)</label>
                  <input 
                    type="text" 
                    value={staffForm.notes} 
                    onChange={(e) => setStaffForm({ ...staffForm, notes: e.target.value })} 
                    placeholder="Internal scheduling notes"
                    style={{ width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid var(--border)' }}
                  />
                </div>

                {staffForm.creation_mode === 'onboard' && !editingStaffId && (
                  <div className="field" style={{ display: 'flex', alignItems: 'center', gap: '10px', gridColumn: 'span 2' }}>
                    <input 
                      type="checkbox" 
                      id="send_invite_cb"
                      checked={staffForm.send_invite} 
                      onChange={(e) => setStaffForm({ ...staffForm, send_invite: e.target.checked })} 
                    />
                    <label htmlFor="send_invite_cb" style={{ margin: 0 }}>Send setup email via Cognito</label>
                  </div>
                )}

                {staffLinkPrompt && (
                  <div style={{ gridColumn: 'span 2', backgroundColor: '#fff3e0', padding: '16px', borderRadius: '8px', border: '1px solid #ffe0b2', marginBottom: '16px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                    <p style={{ margin: 0, color: 'var(--text-primary)' }}>
                      <strong>Cognito user already exists with this email ({staffLinkPrompt.email}).</strong>
                    </p>
                    <p style={{ margin: 0, fontSize: '14px', color: 'var(--text-secondary)' }}>
                      A login account already exists for this email. You can link it to this staff profile instead.
                    </p>
                    <div style={{ display: 'flex', gap: '12px' }}>
                      <button 
                        type="button" 
                        className="button-primary" 
                        style={{ padding: '8px 16px', backgroundColor: 'var(--accent-orange)' }}
                        disabled={isSavingStaff}
                        onClick={async () => {
                          try {
                            setIsSavingStaff(true);
                            await onboardStaff({ ...staffLinkPrompt, mode: 'create_or_link' });
                            showNotification("Staff profile linked successfully", "success");
                            setStaffLinkPrompt(null);
                            setStaffForm({
                              display_name: '',
                              role: 'Staff',
                              email: '',
                              is_assignable: true,
                              assignment_color: 'var(--staff-ryan)',
                              creation_mode: 'onboard',
                              send_invite: true,
                              phone: '',
                              notes: ''
                            });
                            await fetchStaffData();
                          } catch (err) {
                            showNotification(err.message || "Failed to link existing user", "error");
                          } finally {
                            setIsSavingStaff(false);
                          }
                        }}
                      >
                        Link Existing User
                      </button>
                      <button 
                        type="button" 
                        className="button-secondary" 
                        style={{ padding: '8px 16px' }}
                        onClick={() => setStaffLinkPrompt(null)}
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}

                <div className="field" style={{ display: 'flex', alignItems: 'center', gap: '10px', gridColumn: 'span 2' }}>
                  <input 
                    type="checkbox" 
                    id="is_assignable_cb"
                    checked={staffForm.is_assignable} 
                    onChange={(e) => setStaffForm({ ...staffForm, is_assignable: e.target.checked })} 
                  />
                  <label htmlFor="is_assignable_cb" style={{ margin: 0 }}>Can be assigned to jobs / bookings</label>
                </div>

                <div style={{ gridColumn: 'span 2' }}>
                  <button type="submit" className="button-primary" disabled={isSavingStaff} style={{ width: '100%', padding: '12px' }}>
                    {isSavingStaff ? 'Saving...' : editingStaffId ? 'Update Staff Profile' : 'Create Staff Profile'}
                  </button>
                </div>
              </form>

              <h2>Active Staff List</h2>
              <div className="staff-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '16px' }}>
                {staffList.map(s => (
                  <div key={s.staff_id} className="staff-profile-card" style={{ border: s.is_virtual ? '1px dashed var(--accent-orange)' : '1px solid var(--border)', borderRadius: '12px', padding: '16px', display: 'flex', flexDirection: 'column', gap: '10px', backgroundColor: 'var(--card-bg)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      <span className="dot" style={{ backgroundColor: s.assignment_color || 'var(--staff-unassigned)', width: '16px', height: '16px', borderRadius: '50%' }}></span>
                      <strong style={{ fontSize: '18px' }}>{s.display_name} {s.is_virtual && <span style={{ color: 'var(--accent-orange)', fontSize: '12px', marginLeft: '6px', backgroundColor: 'rgba(255, 152, 0, 0.15)', padding: '2px 6px', borderRadius: '4px', border: '1px solid var(--accent-orange)' }}>Cognito Only</span>}</strong>
                    </div>
                    <div style={{ fontSize: '14px', color: 'var(--text-secondary)' }}>
                      <p style={{ margin: '2px 0' }}><strong>Role:</strong> {s.role}</p>
                      {s.email && <p style={{ margin: '2px 0' }}><strong>Email:</strong> {s.email}</p>}
                      {s.phone && <p style={{ margin: '2px 0' }}><strong>Phone:</strong> {s.phone}</p>}
                      <p style={{ margin: '2px 0' }}><strong>Assignable:</strong> {s.is_assignable !== false ? 'Yes' : 'No'}</p>
                      <p style={{ margin: '2px 0' }}>
                        <strong>Cognito:</strong> {s.cognito_sub ? (s.cognito_status || 'Linked') : <span style={{ color: 'var(--accent-orange)' }}>Not Linked</span>}
                      </p>
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginTop: '4px' }}>
                      {s.cognito_sub ? (
                        ['FORCE_CHANGE_PASSWORD', 'UNCONFIRMED'].includes(s.cognito_status) && (
                          <button 
                            className="button-secondary" 
                            style={{ fontSize: '12px', padding: '6px' }} 
                            onClick={async () => {
                              try {
                                await resendInvite(s.staff_id);
                                showNotification("Invite resent successfully", "success");
                              } catch(err) {
                                showNotification(err.message || "Failed to resend invite", "error");
                              }
                            }}
                          >
                            Resend Invite
                          </button>
                        )
                      ) : (
                        <button 
                          className="button-secondary" 
                          style={{ fontSize: '12px', padding: '6px' }} 
                          onClick={async () => {
                            const username = window.prompt("Enter existing Cognito Email to link:");
                            if (!username || !username.trim()) return;
                            try {
                              await linkCognitoUser(s.staff_id, { username: username.trim() });
                              showNotification("Cognito user linked successfully", "success");
                              await fetchStaffData();
                            } catch(err) {
                              showNotification(err.message || "Failed to link user", "error");
                            }
                          }}
                        >
                          Link Cognito Login
                        </button>
                      )}
                    </div>

                    <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: 'auto', paddingTop: '10px', borderTop: '1px solid var(--border)' }}>
                      {s.is_virtual ? (
                        <>
                          <button className="btn-small" style={{ backgroundColor: 'var(--accent-orange)', color: 'white' }} onClick={() => {
                            setStaffForm({
                              display_name: s.display_name,
                              role: s.role || 'Staff',
                              email: s.email,
                              is_assignable: true,
                              assignment_color: 'var(--staff-ryan)',
                              creation_mode: 'onboard',
                              send_invite: false,
                              phone: '',
                              notes: ''
                            });
                            showNotification("Form populated for " + s.email, "info");
                          }}>Create Profile</button>
                          
                          {s.is_active !== false ? (
                            <button className="btn-small error" onClick={() => executeStaffAction(s.staff_id, 'disable')}>Disable Cognito</button>
                          ) : (
                            <>
                              <button className="btn-small" style={{ backgroundColor: 'var(--accent-teal)', color: 'white' }} onClick={() => executeStaffAction(s.staff_id, 'enable')}>Enable Cognito</button>
                              <button className="btn-small error" onClick={() => executeStaffAction(s.staff_id, 'delete_cognito')}>Delete Cognito User</button>
                            </>
                          )}
                        </>
                      ) : (
                        <>
                          <button className="btn-small" onClick={() => handleEditStaff(s)}>Edit</button>
                          
                          {s.is_active !== false ? (
                            <button className="btn-small error" onClick={() => executeStaffAction(s.staff_id, 'disable')}>Disable Access</button>
                          ) : (
                            <button className="btn-small" style={{ backgroundColor: 'var(--accent-teal)', color: 'white' }} onClick={() => executeStaffAction(s.staff_id, 'enable')}>Enable Access</button>
                          )}
                          
                          {s.cognito_sub && (
                            <button className="btn-small" style={{ backgroundColor: '#2196f3', color: 'white' }} onClick={() => executeStaffAction(s.staff_id, 'unlink')}>Unlink Cognito</button>
                          )}

                          {s.is_active === false && (
                            <button className="btn-small error" onClick={() => executeStaffAction(s.staff_id, 'delete_profile')}>Delete Profile</button>
                          )}
                        </>
                      )}
                    </div>
                  </div>
                ))}

                {staffList.length === 0 && (
                  <p style={{ gridColumn: 'span 3', color: 'var(--text-secondary)', textAlign: 'center', padding: '24px' }}>No active staff profiles found.</p>
                )}
              </div>
            </div>
          ) : view === 'CLIENT_MGMT' && ['owner', 'admin'].includes(role) ? (
            <div className="client-management-container card" style={{ padding: '24px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
                <h2>{editingClientId ? 'Edit Client Profile' : 'Add New Client Profile'}</h2>
                {editingClientId && (
                  <button className="button-secondary" onClick={() => {
                    setEditingClientId(null);
                    setClientForm({
                      display_name: '',
                      email: '',
                      phone: '',
                      address: '',
                      emergency_contact: '',
                      notes: ''
                    });
                  }}>Cancel Edit</button>
                )}
              </div>

              <form onSubmit={async (e) => {
                e.preventDefault();
                if (!clientForm.display_name.trim() || !clientForm.email.trim()) {
                  showNotification("Display name and Email are required", "error");
                  return;
                }
                setIsSavingClient(true);
                try {
                  if (editingClientId) {
                    await updateClient(editingClientId, clientForm);
                    showNotification("Client profile updated successfully", "success");
                  } else {
                    await createClient(clientForm);
                    showNotification("Client profile created successfully", "success");
                  }
                  setClientForm({
                    display_name: '',
                    email: '',
                    phone: '',
                    address: '',
                    emergency_contact: '',
                    notes: ''
                  });
                  setEditingClientId(null);
                  await fetchClientData();
                } catch(err) {
                  showNotification(err.message || "Failed to save client", "error");
                } finally {
                  setIsSavingClient(false);
                }
              }} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px', marginBottom: '40px', backgroundColor: 'var(--surface-color)', padding: '20px', borderRadius: '12px' }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <label>Display Name *</label>
                  <input type="text" value={clientForm.display_name} onChange={(e) => setClientForm({ ...clientForm, display_name: e.target.value })} required />
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <label>Email *</label>
                  <input type="email" value={clientForm.email} onChange={(e) => setClientForm({ ...clientForm, email: e.target.value })} required />
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <label>Phone</label>
                  <input type="text" value={clientForm.phone} onChange={(e) => setClientForm({ ...clientForm, phone: e.target.value })} />
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <label>Emergency Contact</label>
                  <input type="text" value={clientForm.emergency_contact} onChange={(e) => setClientForm({ ...clientForm, emergency_contact: e.target.value })} />
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', gridColumn: 'span 2' }}>
                  <label>Address</label>
                  <textarea rows="2" value={clientForm.address} onChange={(e) => setClientForm({ ...clientForm, address: e.target.value })}></textarea>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', gridColumn: 'span 2' }}>
                  <label>Notes</label>
                  <textarea rows="3" value={clientForm.notes} onChange={(e) => setClientForm({ ...clientForm, notes: e.target.value })}></textarea>
                </div>
                <div style={{ gridColumn: 'span 2', display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: '10px' }}>
                  <button type="submit" className="button-primary" disabled={isSavingClient}>
                    {isSavingClient ? 'Saving...' : editingClientId ? 'Save Changes' : 'Create Profile'}
                  </button>
                </div>
              </form>

              <div style={{ borderTop: '1px solid var(--border)', paddingTop: '20px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                  <h3>Client Profiles</h3>
                  <div style={{ display: 'flex', gap: '10px' }}>
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '13px' }}>
                      <span style={{ width: '10px', height: '10px', borderRadius: '50%', backgroundColor: 'var(--success-color)' }}></span> Active
                    </span>
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '13px' }}>
                      <span style={{ width: '10px', height: '10px', borderRadius: '50%', backgroundColor: 'var(--text-muted)' }}></span> Disabled
                    </span>
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '20px' }}>
                  {clientList.map(c => (
                    <div key={c.client_id} className="card" style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '12px', border: c.is_virtual ? '1px dashed var(--accent-orange)' : '1px solid var(--border)', opacity: c.is_active === false ? 0.6 : 1, position: 'relative', backgroundColor: 'var(--surface-color)' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                        <div>
                          <h4 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: c.is_active === false ? 'var(--text-muted)' : 'var(--success-color)', display: 'inline-block' }}></span>
                            {c.display_name}
                            {c.is_virtual && <span style={{ color: 'var(--accent-orange)', fontSize: '11px', marginLeft: '6px', backgroundColor: 'rgba(255, 152, 0, 0.15)', padding: '2px 4px', borderRadius: '4px', border: '1px solid var(--accent-orange)' }}>Cognito Only</span>}
                          </h4>
                          <p style={{ margin: '4px 0 0 16px', fontSize: '13px', color: 'var(--text-muted)' }}>{c.email}</p>
                        </div>
                        <span className="status-chip" style={{ fontSize: '11px', padding: '2px 6px' }}>
                          Portal: {c.portal_enabled ? 'Enabled' : 'Disabled'}
                        </span>
                      </div>

                      <div style={{ fontSize: '13px', color: 'var(--text-secondary)', paddingLeft: '16px' }}>
                        {c.phone && <p style={{ margin: '2px 0' }}>📞 {c.phone}</p>}
                        {c.address && <p style={{ margin: '2px 0' }}>🏠 {c.address}</p>}
                        <p style={{ margin: '6px 0 0', fontSize: '11px', color: 'var(--text-muted)' }}>Status: {c.cognito_status || 'not_linked'}</p>
                      </div>

                      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: 'auto', paddingTop: '10px', borderTop: '1px solid var(--border)' }}>
                        {c.is_virtual ? (
                          <>
                            <button className="btn-small" style={{ backgroundColor: 'var(--accent-orange)', color: 'white' }} onClick={() => {
                              setClientForm({
                                display_name: c.display_name,
                                email: c.email,
                                phone: '',
                                address: '',
                                emergency_contact: '',
                                notes: ''
                              });
                              showNotification("Form populated for " + c.email, "info");
                            }}>Create Profile</button>
                            
                            {c.is_active !== false ? (
                              <button className="btn-small error" onClick={() => executeClientAction(c.client_id, 'disable')}>Disable Cognito</button>
                            ) : (
                              <>
                                <button className="btn-small" style={{ backgroundColor: 'var(--accent-teal)', color: 'white' }} onClick={() => executeClientAction(c.client_id, 'enable')}>Enable Cognito</button>
                                <button className="btn-small error" onClick={() => executeClientAction(c.client_id, 'delete_cognito')}>Delete Cognito User</button>
                              </>
                            )}
                          </>
                        ) : (
                          <>
                            <button className="btn-small" onClick={() => {
                              setEditingClientId(c.client_id);
                              setClientForm({
                                display_name: c.display_name || '',
                                email: c.email || '',
                                phone: c.phone || '',
                                address: c.address || '',
                                emergency_contact: c.emergency_contact || '',
                                notes: c.notes || ''
                              });
                            }}>Edit</button>
                            
                            {c.is_active !== false ? (
                              <button className="btn-small error" onClick={() => executeClientAction(c.client_id, 'disable')}>Disable Access</button>
                            ) : (
                              <button className="btn-small" style={{ backgroundColor: 'var(--accent-teal)', color: 'white' }} onClick={() => executeClientAction(c.client_id, 'enable')}>Enable Access</button>
                            )}

                            {c.cognito_sub && (
                              <button className="btn-small" style={{ backgroundColor: '#2196f3', color: 'white' }} onClick={() => executeClientAction(c.client_id, 'unlink')}>Unlink Cognito</button>
                            )}

                            {c.is_active === false && (
                              <button className="btn-small error" onClick={() => executeClientAction(c.client_id, 'delete_profile')}>Delete Profile</button>
                            )}
                          </>
                        )}
                      </div>
                    </div>
                  ))}

                  {clientList.length === 0 && (
                    <p style={{ gridColumn: 'span 3', color: 'var(--text-secondary)', textAlign: 'center', padding: '24px' }}>No client profiles found.</p>
                  )}
                </div>
              </div>
            </div>
          ) : (


            <div className="list-view-container card">
              <div className="list-header-bar">
                <h2>Request List — {(() => {
                  const filter = [
                    { id: 'NEEDS_ACTION', label: 'Needs Action' },
                    { id: 'READY_FOR_APPROVAL', label: 'New' },
                    { id: 'MEET_GREET_REQUIRED', label: 'Needs M&G' },
                    { id: 'QUOTED', label: 'Quoted' },
                    { id: 'APPROVED', label: 'Approved' },
                    { id: 'ASSIGNED', label: 'Scheduled' },
                    { id: 'COMPLETED', label: 'Completed' },
                    { id: 'CANCELLED', label: 'Cancelled' },
                    { id: 'ARCHIVED', label: 'Archived' },
                    { id: 'DELETED', label: 'Trash / Deleted' },
                    { id: 'ALL', label: 'All Active' }
                  ].find(f => f.id === statusFilter);

                  return filter ? filter.label : 'Items';
                })()}</h2>
                <span className="micro-text">Showing records requiring action in the {statusFilter.replace(/_/g, ' ')} phase</span>
              </div>
              {selectedIds.length > 0 && (
                <div className="bulk-toolbar">
                  <div className="bulk-info">
                    <span className="count">{selectedIds.length}</span>
                    <span>visits selected</span>
                  </div>
                  <div className="bulk-actions">
                    {/* Bulk purge — only shown in Trash/Deleted view */}
                    {statusFilter === 'DELETED' && (
                      <button
                        className="btn-small purge"
                        disabled={isBulkPurging}
                        onClick={() => setBulkConfirmModal({ count: selectedIds.length, target: '__PURGE__' })}
                      >
                        {isBulkPurging ? 'Purging...' : `Delete ${selectedIds.length} Permanently`}
                      </button>
                    )}
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
                      <option value="DELETE">Move to Trash / Deleted</option>
                      <option value="REOPEN_PENDING">Restore to Active</option>
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
                        checked={requests.length > 0 && requests.map(r => r.PK).every(id => selectedIds.includes(id))}
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
                                    {staffList.filter(s => !s.is_virtual && s.is_assignable !== false && s.is_active !== false).map(s => (
                                      <option key={s.display_name} value={s.display_name}>{s.display_name}</option>
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

                               // PURGE_FOREVER: intercept here — do NOT route through onReviewAction
                               if (action === 'PURGE_FOREVER') {
                                 return (
                                   <button
                                     key="PURGE_FOREVER"
                                     onClick={() => setPurgeModal({ item })}
                                     className="btn-micro purge"
                                     title="Permanently delete this record — cannot be undone"
                                   >
                                     Delete Permanently
                                   </button>
                                 );
                               }
                               
                               const labels = {
                                 'APPROVE': 'Approve',
                                 'QUOTE': 'Quote',
                                 'QUOTED': 'Mark Quoted',
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
               <h2>
                 {decisionModal.type === 'APPROVE' ? 'Approve Booking' : 
                  decisionModal.type === 'DECLINE' ? 'Decline Booking' : 
                  'Process Workflow'}
               </h2>
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
                placeholder={decisionModal.type === 'APPROVE' ? "e.g. Can't wait to see Rover!" : "e.g. Note for client..."}
                value={adminNote}
                onChange={(e) => setAdminNote(e.target.value)}
              />
            </div>

            <div className="modal-footer">
              <button onClick={() => { setDecisionModal(null); setModalError(null); }} className="btn-secondary">Cancel</button>
              
              {decisionModal.type === 'APPROVE' ? (
                <button onClick={submitDecision} className="btn-small success">Approve & Notify</button>
              ) : decisionModal.type === 'DECLINE' ? (
                <button onClick={submitDecision} className="btn-small danger">Decline & Notify</button>
              ) : decisionModal.type === 'WORKFLOW_REVIEW' ? (
                <div className="workflow-actions-row">
                  {getWorkflowState(decisionModal.item).actions.map(action => {
                    if (action === 'EDIT_PET' || action === 'ASSIGN' || action === 'CHANGE_WORKER' || action === 'PURGE_FOREVER') return null;
                    
                    const labels = {
                      'APPROVE': 'Approve', 'QUOTE': 'Quote Needed', 'QUOTED': 'Mark Quoted',
                      'CANCEL': 'Cancel', 'VERIFY_MG': 'Mark M&G Complete',
                      'REVERT_TO_APPROVED': 'Back to Approved', 'COMPLETE': 'Complete',
                      'REOPEN': 'Reopen', 'REOPEN_PENDING': 'Restore to Active',
                      'ARCHIVE': 'Archive', 'CREATE_PROFILE': 'Create Profile',
                      'MOVE_TO_NEW_REQUEST': 'To New Request', 'DELETE': 'Move to Trash',
                      'MEET_GREET': 'Require Meet & Greet', 'MG_SCHEDULED': 'M&G Scheduled'
                    };
                    
                    const getButtonClass = (act) => {
                      if (act === 'DELETE' || act === 'CANCEL') return 'btn-small danger';
                      if (['APPROVE', 'VERIFY_MG', 'QUOTED'].includes(act)) return 'btn-small success';
                      if (['QUOTE', 'MEET_GREET', 'MG_SCHEDULED'].includes(act)) return 'btn-small highlight';
                      return 'btn-small primary';
                    };
                    
                    return (
                      <button 
                        key={action}
                        onClick={() => {
                          onReviewAction(decisionModal.item, action, adminNote);
                          setDecisionModal(null);
                        }} 
                        className={getButtonClass(action)}
                        style={{ marginRight: '8px', marginBottom: '8px' }}
                      >
                        {labels[action] || action}
                      </button>
                    );
                  })}
                </div>
              ) : null}
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
          userRole={role}
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
              {bulkConfirmModal.target === '__PURGE__' ? (
                <>
                  <p className="purge-warning-text">You are about to <strong>permanently delete {bulkConfirmModal.count} record(s)</strong> from the Trash.</p>
                  <div className="safety-notice">
                    <p>● Only records currently in DELETED / Trash status will be purged.</p>
                    <p>● <strong>This cannot be undone.</strong> Records will be removed from the database entirely.</p>
                  </div>
                </>
              ) : (
                <>
                  <p>Target Status: <span className="highlight-status">{getStatusLabel(bulkConfirmModal.target)}</span></p>
                  <div className="safety-notice">
                    <p>● This action will update only the currently selected visible records.</p>
                    {bulkConfirmModal.target === 'ARCHIVED' || bulkConfirmModal.target === 'ARCHIVE' ? (
                      <p>● This uses archive/soft-delete behavior. Records can be restored from the Archived view.</p>
                    ) : (bulkConfirmModal.target === 'DELETE' || bulkConfirmModal.target === 'DELETED') ? (
                      <p>● Move {bulkConfirmModal.count} selected visits to Trash? These records will be hidden from active workflows but can still be restored unless permanently deleted.</p>
                    ) : (bulkConfirmModal.target === 'REOPEN_PENDING' || bulkConfirmModal.target === 'PENDING_REVIEW') ? (
                      <p>● Restore {bulkConfirmModal.count} selected visits to Active? This will move records back to the Intake Queue (Pending Review).</p>
                    ) : (
                      <p>● Records will be moved to the {getStatusLabel(bulkConfirmModal.target)} workflow phase.</p>
                    )}
                  </div>
                </>
              )}
            </div>

            <div className="modal-footer">
              <button 
                className="button-secondary" 
                onClick={() => setBulkConfirmModal(null)}
                disabled={isBulkUpdating}
              >
                Cancel
              </button>
              {bulkConfirmModal.target === '__PURGE__' ? (
                <button
                  className="btn-small purge"
                  onClick={handleBulkPurge}
                  disabled={isBulkPurging}
                >
                  {isBulkPurging ? 'Purging...' : 'Yes, Delete Permanently'}
                </button>
              ) : (
                <button 
                  className="button-primary" 
                  onClick={handleBulkUpdate}
                  disabled={isBulkUpdating}
                >
                  {isBulkUpdating ? 'Updating...' : 'Confirm & Apply'}
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Purge Confirmation Modal */}
      {purgeModal && (() => {
        const item = purgeModal.item;
        const recordName = [
          item.pet_name || item.client_name || '',
          item.client_name && item.pet_name ? `(${item.client_name})` : ''
        ].filter(Boolean).join(' ') || 'this record';
        return (
          <div className="modal-overlay">
            <div className="modal-content purge-confirm-modal">
              <div className="modal-header">
                <h2>⚠️ Permanently Delete Record?</h2>
                <p className="purge-warning-text">
                  This will permanently delete <strong>{recordName}</strong> and cannot be undone.
                </p>
              </div>
              <div className="field" style={{ margin: '0' }}>
                <label style={{ fontWeight: 700, fontSize: '0.85rem' }}>Type <code>DELETE</code> to confirm:</label>
                <input
                  type="text"
                  value={purgeConfirmText}
                  onChange={(e) => setPurgeConfirmText(e.target.value)}
                  placeholder="DELETE"
                  autoFocus
                  style={{ marginTop: '8px' }}
                />
              </div>
              <div className="modal-footer">
                <button
                  className="btn-secondary"
                  onClick={() => { setPurgeModal(null); setPurgeConfirmText(''); }}
                  disabled={loading}
                >
                  Cancel
                </button>
                <button
                  className="btn-small purge"
                  onClick={() => { handlePurgeRecord(item); setPurgeConfirmText(''); }}
                  disabled={loading || purgeConfirmText !== 'DELETE'}
                >
                  {loading ? 'Deleting...' : 'Permanently Delete'}
                </button>
              </div>
            </div>
          </div>
        );
      })()}
    </div>
  );
};

export default AdminDashboard;
