import React, { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { signIn, forgotPassword, confirmForgotPassword, getSession, getEffectiveRole } from '../api/auth';

import { getAdminRequests, reviewRequest, assignWorker, getGoogleStatus, initiateGoogleAuth, getPet, updatePet, createPet, processCancellationDecision, performAdminAction, purgeRecord, purgeRecordsBulk, getStaff, createStaff, updateStaff, disableStaff, onboardStaff, linkCognitoUser, resendInvite, resetStaffPassword, setStaffTempPassword, getClients, createClient, updateClient, disableClient, onboardClient, resendClientInvite, resetClientPassword, setClientTempPassword, linkClientCognitoUser, getExportData, createAdminBooking, listAdminClientPets, getTenantInfo } from '../api/client';
import { SERVICE_TYPES } from '../generated/contracts';
import * as XLSX from 'xlsx';

import { accountStatusLabel, accountStatusClass, profileStatusLabel, profileStatusClass, getVisibleClients, CLIENT_FILTERS } from '../utils/clientManagement';
import { describeGuidedWorkflowAction, GUIDED_ACTION_SEMANTICS, resolveGuidedWorkflowAction } from '../utils/workflowActions';
import { bootstrapTenantSession, TENANT_ACCESS_ERROR } from '../utils/tenantContext';
import { deriveTenantPresentation, updateDocumentTitle, DEFAULT_BRANDING } from '../utils/tenantPresentation';





import MasterScheduler from './MasterScheduler';
import CareCard from './CareCard';
import UserProfile from './UserProfile';
import DatePickerGrid from './DatePickerGrid';
import ClientDetailDrawer from './ClientDetailDrawer';
import ClientProfileCard from './ClientProfileCard';
import StaffProfileCard from './StaffProfileCard';
import '../Admin.css';

// Release 6H Phase 2: Removed hardcoded PROTECTED_SUBS/PROTECTED_EMAILS.
// Protection is now determined by the backend-provided `is_protected` field on staff/client profiles.

// Admin creation intentionally has a broader compatibility catalog than customer
// intake. Every canonical contract entry remains available here: target services
// support current operations, while legacy entries preserve staff-managed bookings.
const adminServiceTypes = Object.entries(SERVICE_TYPES.services);
const checkInServiceType = adminServiceTypes.find(([, service]) => (
  service.windowSelectionMode === 'match_visits_per_day'
));
const checkInServiceId = checkInServiceType?.[0] || '';

const formatCanonicalTime = (value) => {
  if (!value) return '';
  const [hourValue, minute] = value.split(':');
  const hour = Number(hourValue);
  return `${hour % 12 || 12}:${minute} ${hour >= 12 ? 'PM' : 'AM'}`;
};

const getAdminFixedScheduleLabel = (serviceType) => {
  const service = SERVICE_TYPES.services[serviceType];
  if (service?.scheduleMode !== 'fixed' || !service.fixedStartTime || !service.fixedEndTime) return '';
  return `${formatCanonicalTime(service.fixedStartTime)}–${formatCanonicalTime(service.fixedEndTime)}`;
};

const getAdminCanonicalWindowModel = (serviceType) => {
  const service = SERVICE_TYPES.services[serviceType];
  if (!['match_visits_per_day', 'exactly_one'].includes(service?.windowSelectionMode)) return null;

  const windows = service.allowedWindowIds
    .map((id) => ({ id, ...SERVICE_TYPES.windows[id] }))
    .filter((window) => (
      window.label
      && window.lifecycle === 'active'
      && window.newBookingEligibility === 'eligible'
    ));

  return { service, windows };
};

const getAdminCheckInModel = (serviceType) => {
  const model = getAdminCanonicalWindowModel(serviceType);
  return model?.service.windowSelectionMode === 'match_visits_per_day' ? model : null;
};

const getInitialAdminVisitWindows = (serviceType) => (
  SERVICE_TYPES.services[serviceType]?.windowSelectionMode === 'legacy_compatibility'
    ? ['ANYTIME']
    : []
);

const createInitialNewVisitForm = () => ({
  client_id: '', client_name: '', client_email: '', client_phone: '',
  pet_names: '', pet_ids: [], service_type: 'PET_SITTING',
  selected_dates: [], range_start: '', range_end: '', visit_windows: ['ANYTIME'],
  visits_per_day: null, details: '', preferred_sitter: ''
});

const APPROVAL_JOB_REFRESH_ATTEMPTS = 5;
const APPROVAL_JOB_REFRESH_DELAY_MS = 500;
const APPROVAL_JOB_INITIALIZATION_WARNING = 'Approved successfully; job setup is still initializing. Refresh before assigning.';
const waitForApprovalJobRefresh = () => new Promise(resolve => {
  setTimeout(resolve, APPROVAL_JOB_REFRESH_DELAY_MS);
});

const AdminDashboard = ({ expectedTenantSlug = null }) => {

  const [allRequests, setAllRequests] = useState([]); // Master pool for all records
  const [openMenuId, setOpenMenuId] = useState(null); // Track which row's action menu is open
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [role, setRole] = useState('unknown');
  const [currentUser, setCurrentUser] = useState(null); // { email, sub }

  const [loginData, setLoginData] = useState({ email: '', password: '' });
  const [authChallenge, setAuthChallenge] = useState(null);
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [challengeContext, setChallengeContext] = useState(null);
  const [recoveryMode, setRecoveryMode] = useState('login');
  const [recoveryEmail, setRecoveryEmail] = useState('');
  const [recoveryCode, setRecoveryCode] = useState('');
  const [recoveryNewPassword, setRecoveryNewPassword] = useState('');
  const [recoveryConfirmPassword, setRecoveryConfirmPassword] = useState('');
  const [recoverySuccess, setRecoverySuccess] = useState(false);
  const [googleStatus, setGoogleStatus] = useState(null);
  const [tenantInfo, setTenantInfo] = useState(null);
  const [staffList, setStaffList] = useState([]);
  const [staffLoading, setStaffLoading] = useState(false);
  const [staffError, setStaffError] = useState(null);
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
  // Release 3: Client Management search
  const [clientSearch, setClientSearch] = useState('');
  // Phase 1B.1A: Client Management filters
  const [clientFilter, setClientFilter] = useState('all');
  // Phase 1B.1B: Client detail drawer
  const [clientDetailTarget, setClientDetailTarget] = useState(null);
  const clientDetailBtnRef = useRef(null);
  // Release 5D Hotfix 1: Pets loaded for the selected/editing client
  const [clientPets, setClientPets] = useState([]);
  const [clientForm, setClientForm] = useState({
    display_name: '',
    email: '',
    phone: '',
    address: '',
    emergency_contact: '',
    notes: '',
    creation_mode: 'onboard', // onboard or profile_only
    send_invite: true
  });
  const [isSavingClient, setIsSavingClient] = useState(false);
  const [isSavingStaff, setIsSavingStaff] = useState(false);
  const [clientLinkPrompt, setClientLinkPrompt] = useState(null);
  const [clientDrawerMode, setClientDrawerMode] = useState('view');
  const [clientInitialFormValues, setClientInitialFormValues] = useState(null);

  const hasClientUnsavedChanges = clientDetailTarget && clientDrawerMode !== 'view' && clientInitialFormValues && (
    clientForm.display_name !== clientInitialFormValues.display_name ||
    clientForm.email !== clientInitialFormValues.email ||
    clientForm.phone !== clientInitialFormValues.phone ||
    clientForm.address !== clientInitialFormValues.address ||
    clientForm.emergency_contact !== clientInitialFormValues.emergency_contact ||
    clientForm.notes !== clientInitialFormValues.notes ||
    (clientDrawerMode === 'create' && (
      clientForm.creation_mode !== clientInitialFormValues.creation_mode ||
      clientForm.send_invite !== clientInitialFormValues.send_invite
    ))
  );

  // Release 22J: Profile Editor side drawer states
  const [isStaffDrawerOpen, setIsStaffDrawerOpen] = useState(false);
  const [isStaffEditMode, setIsStaffEditMode] = useState(false);
  const [selectedStaffForDrawer, setSelectedStaffForDrawer] = useState(null);
  const [initialFormValues, setInitialFormValues] = useState(null);
  const [isClientPetsLoading, setIsClientPetsLoading] = useState(false);
  const clientPetRequestSeqRef = useRef(0);
  const activeClientDetailIdRef = useRef(null);


  const [view, setView] = useState('SCHEDULER'); // SCHEDULER or LIST
  const skipNextDataFetchRef = useRef(false);
  const approvalSchedulerHandoffRef = useRef(false);
  const activeTabRef = useRef(null);
  const staffDrawerTriggerRef = useRef(null);
  const staffDrawerCloseBtnRef = useRef(null);
  const clientDrawerTriggerRef = useRef(null);
  // Phase 1B.5C-C: Guard against double-click form submission when entering edit mode
  const staffEditModeGuardRef = useRef(false);
  
  useEffect(() => {
    if (activeTabRef.current) {
      activeTabRef.current.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
    }
  }, [view]);

  const [statusFilter, setStatusFilter] = useState('PENDING_REVIEW');
  const [timeframeFilter, setTimeframeFilter] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [paymentStatusFilter, setPaymentStatusFilter] = useState('ALL');
  const [mobileFilterOpen, setMobileFilterOpen] = useState(false);
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
  const [purgeAnalysis, setPurgeAnalysis] = useState(null);
  const [workflowDropdownOpen, setWorkflowDropdownOpen] = useState(false);
  const [decisionModal, setDecisionModal] = useState(null);
  const [archiveConfirmModal, setArchiveConfirmModal] = useState(null); // { item }
  const [archiveReasonText, setArchiveReasonText] = useState('');
  const [lastKey, setLastKey] = useState(null);
  const [exportModal, setExportModal] = useState(false);
  const [expandedRequestIds, setExpandedRequestIds] = useState({});
  const toggleRequestExpanded = (key) => {
    setExpandedRequestIds(prev => ({ ...prev, [key]: !prev[key] }));
  };
  // Release 6F: New Visit modal for admin-created bookings
  const [newVisitModal, setNewVisitModal] = useState(false);
  const [newVisitForm, setNewVisitForm] = useState(createInitialNewVisitForm);
  const [newVisitClientPets, setNewVisitClientPets] = useState([]);
  const [isCreatingVisit, setIsCreatingVisit] = useState(false);
  const [newVisitScheduleError, setNewVisitScheduleError] = useState('');
  const [isAddingPetInline, setIsAddingPetInline] = useState(false);
  const [inlinePetForm, setInlinePetForm] = useState({ name: '', species: 'DOG', breed: '', age: '' });
  const [isSavingPetInline, setIsSavingPetInline] = useState(false);
  // Confirmation modal state for staff/client actions (replaces window.confirm/prompt)
  const [confirmAction, setConfirmAction] = useState(null);
  // Shape: { type: 'staff'|'client', id: string, action: string, name: string, message: string, consequence: string, variant?: 'confirm'|'disable-choice'|'delete-typed'|'temp-password'|'link-email' }
  const [confirmTypedInput, setConfirmTypedInput] = useState('');
  
  const capabilities = {
    canViewScheduler: ['owner', 'admin', 'staff'].includes(role),
    canViewRequestList: ['owner', 'admin'].includes(role),
    canManageStaff: ['owner', 'admin'].includes(role),
    canManageClients: ['owner', 'admin'].includes(role),
    canExportData: ['owner', 'admin'].includes(role),
    canManageGoogleCalendarIntegration: ['owner', 'admin'].includes(role),
  };

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (openMenuId && !event.target.closest('.action-menu-container')) {
        setOpenMenuId(null);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [openMenuId]);

  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape' && openMenuId) {
        setOpenMenuId(null);
      }
    };
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [openMenuId]);

  // Scroll lock: prevent background scrolling when any modal is open (mobile iOS Safari fix)
  useEffect(() => {
    const isAnyModalOpen = !!(decisionModal || bulkConfirmModal || purgeModal || selectedPet || confirmAction || archiveConfirmModal);
    if (isAnyModalOpen) {
      const scrollY = window.scrollY;
      document.body.style.position = 'fixed';
      document.body.style.top = `-${scrollY}px`;
      document.body.style.width = '100%';
      document.body.style.overflow = 'hidden';
      return () => {
        document.body.style.position = '';
        document.body.style.top = '';
        document.body.style.width = '';
        document.body.style.overflow = '';
        window.scrollTo(0, scrollY);
      };
    }
  }, [decisionModal, bulkConfirmModal, purgeModal, selectedPet, confirmAction, archiveConfirmModal]);

  const showNotification = (message, type = 'info') => {
    setNotification({ message, type });
    setTimeout(() => setNotification(null), 5000);
  };

  // Release 6G Phase 0B: Calendar sync warning helper.
  // Extracts calendar warning from API response and shows appropriate toast.
  // Returns the notification type ('success', 'warning', 'info') based on calendar result.
  const getCalendarNotificationType = (response) => {
    const calResult = response?.calendar_result;
    if (!calResult) return 'success';
    const status = calResult.status || '';
    if (status === 'calendar_failed') return 'warning';
    if (status.startsWith('calendar_skipped')) return 'info';
    return 'success';
  };

  const getCalendarWarningMessage = (response, baseMessage) => {
    const calResult = response?.calendar_result;
    if (!calResult) return baseMessage;
    const status = calResult.status || '';
    if (status === 'calendar_failed') {
      return `${baseMessage} ⚠️ Calendar sync failed — event may not appear on Google Calendar.`;
    }
    if (status.startsWith('calendar_skipped')) {
      const reason = calResult.message || 'no scheduled time set';
      return `${baseMessage} ℹ️ Calendar event skipped (${reason}).`;
    }
    return baseMessage;
  };

  const isProtectedProfile = (staff) => {
    if (!staff) return false;
    // Release 6H Phase 2: Use backend-provided is_protected field instead of hardcoded lists
    return !!staff.is_protected;
  };

  const isSelf = (staff) => {
    if (!staff || !currentUser) return false;
    return staff.cognito_sub === currentUser.sub || staff.email === currentUser.email;
  };

  const canManageProtectedStatus = () => {
    const effectiveRole = (role || '').toLowerCase();
    if (effectiveRole === 'owner' || effectiveRole === 'platform_admin') return true;
    const currentUserStaff = staffList.find(s => isSelf(s));
    if (currentUserStaff && (currentUserStaff.is_protected || currentUserStaff.is_platform_protected)) {
      return true;
    }
    return false;
  };
  
  const getStatusClass = (status = "") => {
    const s = (status || "").toUpperCase();
    if (s === "CANCELLATION_REQUESTED") return "status-chip status-chip--urgent";
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

  const determineWorkflowType = (item) => {
    if (!item) return 'CUSTOMER_INTAKE';
    if (item.workflow_type) return item.workflow_type;
    
    const status = (item.status || "").toUpperCase();
    if (['QUOTE_NEEDED', 'QUOTE_SENT', 'QUOTED', 'BOOKED', 'ASSIGNED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED'].includes(status)) return 'VISIT_BOOKING';
    if (item.worker_id || item.job_id) return 'VISIT_BOOKING';
    if (item.service_type && item.start_date && ['WALK_30MIN', 'DROPIN_1HR', 'DROPIN_3HR', 'OVERNIGHT'].includes(item.service_type)) return 'VISIT_BOOKING';
    
    return 'CUSTOMER_INTAKE';
  };

  const getStatusLabel = (status = "", item = null) => {
    const s = (status || "").toUpperCase();
    const workflow = determineWorkflowType(item);

    if (s === 'PENDING_REVIEW' || s === 'NEEDS_REVIEW') return workflow === 'VISIT_BOOKING' ? "New Request" : "New Registration";
    if (s === 'MEET_GREET_REQUIRED' || s === 'NEEDS_MG') return "Needs Meet & Greet";
    if (s === 'MG_SCHEDULED') return "M&G Scheduled";
    if (s === 'MG_COMPLETED') return "M&G Completed";
    if (s === 'PROFILE_CREATED') return "Profile Created";
    if (s === 'READY_FOR_APPROVAL' || s === 'NEW_REQUEST') return workflow === 'VISIT_BOOKING' ? "Booking Ready" : "Onboarding Ready";
    if (s === 'QUOTE_NEEDED') return "Needs Price Quote";
    if (s === 'QUOTE_SENT' || s === 'QUOTED') return "Price Quote Sent";
    if (s === 'APPROVED' || s === 'BOOKED') return workflow === 'VISIT_BOOKING' ? "Approved / Ready to Schedule" : "Approved Client";
    if (s === 'ASSIGNED' || s === 'JOB_CREATED' || s === 'SCHEDULED') return "Scheduled with Staff";
    if (s === 'IN_PROGRESS') return "In Progress";
    if (s === 'COMPLETED') return "Visit Completed";
    if (s === 'CANCELLATION_REQUESTED') return "Cancellation Requested";
    if (s === 'CANCELLATION_DENIED') return "Cancel Denied";
    if (s === 'CANCELLED') return "Cancelled";
    if (s === 'ARCHIVED' || s === 'ARCHIVE') return "Saved for Records";
    if (s === 'DELETED' || s === 'DELETE' || s === 'TRASH') return "Trash";
    return s.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()) || "Unknown / Status Missing";
  };
  
  const formatVisitDates = (item) => {
    if (!item) return '';

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

  const getFullVisitDatesList = (item) => {
    if (!item) return '';

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

    if (item.selected_dates && item.selected_dates.length > 0) {
      const sorted = [...item.selected_dates].sort();
      const list = sorted.map(d => formatDate(parseDate(d), false)).join(', ');
      const yr = parseDate(sorted[sorted.length - 1]).getFullYear();
      return `${list}, ${yr}`;
    }

    if (item.start_date && item.end_date) {
      if (item.start_date === item.end_date) {
        return formatDate(parseDate(item.start_date), true);
      }
      return `${formatDate(parseDate(item.start_date), false)} to ${formatDate(parseDate(item.end_date), true)}`;
    } else if (item.start_date) {
      return formatDate(parseDate(item.start_date), true);
    }
    
    return '';
  };

  const getServiceLabel = (serviceType) => {
    if (!serviceType) return 'UNKNOWN SERVICE';
    return SERVICE_TYPES.services[serviceType]?.labelLong || serviceType.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
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
  
  const getAccessStatus = (user) => {
    if (!user) return { label: 'No Data', class: 'status-no-login' };
    
    // Check if backend identity fields exist (Release 22H)
    if (user.identity_state) {
      if (user.identity_state === 'protected') {
        return { label: 'Protected', class: 'status-active' };
      }
      if (user.identity_state === 'orphaned') {
        return { label: 'Orphaned Login', class: 'status-disabled' };
      }
      if (user.identity_state === 'profile_only') {
        return { label: 'No Login', class: 'status-no-login' };
      }
      if (user.identity_state === 'linked_active') {
        return { label: 'Login Active', class: 'status-active' };
      }
      if (user.identity_state === 'linked_invited') {
        return { label: 'Invited', class: 'status-invited' };
      }
      if (user.identity_state === 'linked_disabled') {
        return { label: 'Login Disabled', class: 'status-disabled' };
      }
    }
    
    // Fallback to legacy UI-derived logic
    if (user.is_active === false) return { label: 'Disabled', class: 'status-disabled' };
    
    // 2. No Login (No Cognito link)
    if (!user.cognito_sub && (!user.cognito_status || user.cognito_status === 'not_linked')) {
      // Release 7B Phase 3: Show "Offline Client" if the client has no email address
      if (!user.email) {
        return { label: 'Offline Client', class: 'status-offline' };
      }
      return { label: 'No Login', class: 'status-no-login' };
    }
    
    const cogStat = (user.cognito_status || '').toUpperCase();
    
    // 3. Invited (Pending confirmation/password change)
    if (['FORCE_CHANGE_PASSWORD', 'UNCONFIRMED'].includes(cogStat)) {
      return { label: 'Invited', class: 'status-invited' };
    }
    
    // 4. Password Reset Required
    if (cogStat === 'RESET_REQUIRED') {
      return { label: 'Password Reset Required', class: 'status-reset-req' };
    }
    
    // 5. Active (Confirmed login)
    if (cogStat === 'CONFIRMED' && user.is_active !== false) {
      return { label: 'Active', class: 'status-active' };
    }
 
    // 6. Linked but state unknown
    if (user.cognito_sub) {
        return { label: 'Login Linked', class: 'status-linked' };
    }
    
    return { label: 'Unknown', class: 'status-no-login' };
  };


  const getGoogleStatusConfig = (status) => {
    switch (status) {
      case 'CONNECTED':
        return { label: 'Connected', class: 'status-connected' };
      case 'NOT_CONNECTED':
        return { label: 'Not Connected', class: 'status-disconnected' };
      case 'VALIDATION_FAILED':
        return { label: 'Needs Reconnect', class: 'status-reconnect' };
      case 'CREDENTIALS_MISSING':
        return { label: 'Error', class: 'status-error' };
      default:
        return { label: status || 'Checking...', class: 'status-disconnected' };
    }
  };


  /**
   * Data Fetching Engine
   */
  const fetchGoogleStatus = async () => {
    try {
      const status = await getGoogleStatus();
      setGoogleStatus(status.status);
    } catch (err) {
      console.error("Failed to fetch Google status", err);
    }
  };

  const fetchTenantInfo = async () => {
    try {
      const info = await getTenantInfo(expectedTenantSlug);
      setTenantInfo(info);
    } catch (err) {
      console.error("Failed to fetch tenant info:", err);
    }
  };

  const fetchStaffData = async () => {
    try {
      setStaffLoading(true);
      setStaffError(null);
      const data = await getStaff();
      setStaffList(data.staff || []);
    } catch (err) {
      console.error("Failed to fetch staff list:", err);
      setStaffError(err.message || "Failed to load staff");
    } finally {
      setStaffLoading(false);
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

  const fetchAllData = async (startKey = null) => {
    try {
      setLoading(true);
      if (!startKey) {
        setSelectedIds([]); // Reset selection on fresh fetch
        setAllRequests([]); // Reset list on fresh fetch to prevent stale data mixing
      }
      fetchStaffData();
      fetchClientData();

      if (view === 'SCHEDULER') {
        const data = await getAdminRequests('ALL');
        setAllRequests(prev => {
          const combined = [...prev];
          (data.requests || []).forEach(newItem => {
            const index = combined.findIndex(ex => ex.PK === newItem.PK);
            if (index >= 0) combined[index] = newItem;
            else combined.push(newItem);
          });
          return combined;
        });
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

        let rawItems = data.requests || [];
        setAllRequests(prev => {
          const combined = [...prev];
          rawItems.forEach(newItem => {
            const index = combined.findIndex(ex => ex.PK === newItem.PK);
            if (index >= 0) combined[index] = newItem;
            else combined.push(newItem);
          });
          return combined;
        });

        setLastKey(data.lastKey);
      }
    } catch (err) {
      setError("Failed to fetch data: " + err.message);
    } finally {
      setLoading(false);
    }
  };

  /**
   * Lifecycle Helpers
   * NOTE: Currently the backend uses the 'status' field for both workflow phase and lifecycle state.
   * We treat ARCHIVED and DELETED as lifecycle states while others are active workflow statuses.
   */
  const isArchivedRecord = (item) => (item.status || "").toUpperCase() === 'ARCHIVED' || (item.status || "").toUpperCase() === 'ARCHIVE';
  const isDeletedRecord = (item) => {
    const s = (item.status || "").toUpperCase();
    // Release 6D: Status is the sole source of truth for Trash classification.
    // deleted_at alone does NOT qualify — prevents zombie records (active status + deleted_at)
    // from appearing in Trash. Such records are treated as data integrity issues instead.
    return s === 'DELETED' || s === 'TRASH' || s === 'DELETE';
  };
  const isCancellationPendingRecord = (item) => {
    const s = (item.status || "").toUpperCase();
    return s === 'CANCELLATION_REQUESTED';
  };
  const isCancelledRecord = (item) => {
    const s = (item.status || "").toUpperCase();
    return s === 'CANCELLED' || s === 'DECLINED' || s === 'REJECTED' || s === 'CANCELLATION_DENIED';
  };
  const isCompletedRecord = (item) => (item.status || "").toUpperCase() === 'COMPLETED';
  const isRequestLikeRecord = (item) => {
    if (!item || !item.PK) return false;
    const pk = item.PK.toUpperCase();
    const sk = (item.SK || "").toUpperCase();
    const type = (item.type || "").toUpperCase();

    // Explicitly exclude system/audit prefixes
    const systemPrefixes = [
      'AUDIT#', 'COMPANY#', 'STAFF#', 'CLIENT#', 'CONFIG#', 'PROFILE#', 'LOG#'
    ];
    if (systemPrefixes.some(pref => pk.startsWith(pref))) return false;
    if (type === 'AUDIT' || type === 'SYSTEM') return false;

    // Release 1: Request List shows parent REQ# records only.
    // JOB# records are internal child records for worker assignment/calendar sync.
    // They should not appear as separate rows in the admin request list.
    // This prevents the duplicate-row issue where both REQ and JOB appeared
    // for the same booking in the "Scheduled with Staff" view.
    if (pk.startsWith('JOB#')) return false;

    // Must look like a request (REQ# in PK)
    return pk.includes('REQ#');
  };

  const isDataIssue = (item) => {
    if (!item) return false;
    
    // 1. Must be a request-like record (excludes AUDIT, STAFF, etc.)
    if (!isRequestLikeRecord(item)) return false;

    // Release 1: JOB# records are excluded from Data Issues entirely.
    // They are internal child records managed by the cascade system.
    // Previously, JOB records could land in Data Issues when parent rollback
    // removed worker_id from one side of the relationship.
    if (item.PK && item.PK.toUpperCase().startsWith('JOB#')) return false;

    // 2. If it's already deleted or archived, we don't treat it as a primary "data issue" in the intake/booking queues
    if (isDeletedRecord(item) || isArchivedRecord(item)) return false;

    const status = (item.status || "").toUpperCase();
    const petNames = item.pet_names || item.pet_name || "";
    const clientName = item.client_name || "";
    
    const knownStatuses = [
      'PENDING_REVIEW', 'NEEDS_REVIEW', 'READY_FOR_APPROVAL', 'NEW_REQUEST',
      'MEET_GREET_REQUIRED', 'NEEDS_MG', 'VERIFY_MEET_GREET', 'MG_SCHEDULED', 'MG_COMPLETED',
      'QUOTE_NEEDED', 'QUOTED', 'QUOTE_SENT', 'APPROVED', 'BOOKED',
      'ASSIGNED', 'SCHEDULED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED',
      'REJECTED', 'DECLINED', 'DENIED', 'ARCHIVED', 'ARCHIVE', 'DELETED', 'TRASH',
      'PROFILE_CREATED', 'CANCELLATION_REQUESTED', 'CANCELLATION_DENIED'
    ];

    // Release 6D: Zombie detection — deleted_at exists but status is active.
    // These are data integrity issues, not normal Trash records.
    const activeStatuses = ['APPROVED', 'ASSIGNED', 'SCHEDULED', 'BOOKED', 'JOB_CREATED', 'IN_PROGRESS', 'PENDING_REVIEW', 'NEEDS_REVIEW'];
    if (item.deleted_at && activeStatuses.includes(status)) return true;

    return (
      !status || 
      status === "UNKNOWN" || 
      !petNames.trim() || 
      !clientName.trim() ||
      (petNames === "---" && clientName === "No Client Name") ||
      !knownStatuses.includes(status)
    );
  };

  const isActiveRecord = (item) => {
    if (isDeletedRecord(item) || isArchivedRecord(item) || isCompletedRecord(item) || isCancelledRecord(item) || isDataIssue(item)) return false;
    return true;
  };

  /**
   * Filter Predicate Engine
   * Centralizes filtering logic for both the request list and the sidebar counts.
   */
  const getFilterPredicate = (filterKey) => {
    return (r) => {
      if (!r) return false;
      const stat = (r.status || '').toUpperCase();
      const workflow = determineWorkflowType(r);

      switch (filterKey) {
        case 'DATA_ISSUES':
          return isDataIssue(r);
        case 'ALL': // All Active
          return isActiveRecord(r);
        case 'UNASSIGNED':
          // Release 6D: Dedicated predicate for Needs Assignment — matches stat card count exactly
          if (isDataIssue(r)) return false;
          return (stat === 'APPROVED' || stat === 'BOOKED' || stat === 'JOB_CREATED') && !r.worker_id;
        case 'NEEDS_ACTION':
          if (!isActiveRecord(r)) return false;
          return (
            stat === 'PENDING_REVIEW' || stat === 'NEEDS_REVIEW' ||
            stat === 'MEET_GREET_REQUIRED' || stat === 'NEEDS_MG' ||
            stat === 'QUOTE_NEEDED' ||
            stat === 'APPROVED' || stat === 'BOOKED' ||
            stat === 'CANCELLATION_REQUESTED'
          );
        case 'INTAKE_QUEUE':
          if (!isActiveRecord(r)) return false;
          return workflow === 'CUSTOMER_INTAKE' && (stat === 'PENDING_REVIEW' || stat === 'NEEDS_REVIEW' || stat === 'PROFILE_CREATED');
        case 'MEET_GREET_REQUIRED':
          if (!isActiveRecord(r)) return false;
          return workflow === 'CUSTOMER_INTAKE' && (stat === 'MEET_GREET_REQUIRED' || stat === 'NEEDS_MG' || stat === 'MG_SCHEDULED');
        case 'READY_FOR_APPROVAL':
          if (!isActiveRecord(r)) return false;
          if (workflow === 'CUSTOMER_INTAKE') return stat === 'READY_FOR_APPROVAL' || stat === 'NEW_REQUEST' || stat === 'MG_COMPLETED';
          return stat === 'READY_FOR_APPROVAL' || stat === 'NEW_REQUEST' || stat === 'APPROVED' || stat === 'BOOKED';
        case 'BOOKING_QUEUE':
          if (!isActiveRecord(r)) return false;
          return workflow === 'VISIT_BOOKING' && (stat === 'PENDING_REVIEW' || stat === 'NEEDS_REVIEW' || stat === 'READY_FOR_APPROVAL' || stat === 'NEW_REQUEST' || stat === 'APPROVED' || stat === 'BOOKED');
        case 'QUOTED':
          if (!isActiveRecord(r)) return false;
          return workflow === 'VISIT_BOOKING' && (stat === 'QUOTED' || stat === 'QUOTE_SENT' || stat === 'QUOTE_NEEDED');
        case 'ASSIGNED':
          if (!isActiveRecord(r)) return false;
          return stat === 'ASSIGNED' || stat === 'SCHEDULED' || stat === 'IN_PROGRESS';
        case 'COMPLETED':
          return isCompletedRecord(r);
        case 'CANCELLED':
          return isCancelledRecord(r);
        case 'ARCHIVED':
        case 'ARCHIVE':
          return isArchivedRecord(r);
        case 'DELETED':
        case 'TRASH':
          return isDeletedRecord(r);
        default:
          return stat === filterKey.toUpperCase();
      }
    };
  };

  /**
   * Selection Helpers
   * We use a composite key of PK and SK to ensure uniqueness even for malformed records.
   */
  const getRecordKey = (item) => `${item.PK || 'NO_PK'}|||${item.SK || 'NO_SK'}`;
  const getWorkflowState = (item) => {
    const status = (item.status || 'PENDING_REVIEW').toUpperCase();
    const workflow = determineWorkflowType(item);
    const hasWorker = Boolean(item.worker_id);
    const isInvalidAssigned = status === 'ASSIGNED' && !hasWorker;

    const state = {
      displayStatus: getStatusLabel(status, item),
      statusClass: getStatusClass(status),
      isInvalid: isInvalidAssigned || isDataIssue(item),
      actions: []
    };

    if (isInvalidAssigned) {
      state.displayStatus = "Needs Assignment";
      state.statusClass = "status-chip status-chip--urgent";
      state.actions = ["ASSIGN", "REVERT_TO_APPROVED", "CANCEL"];
      return state;
    }

    if (isDataIssue(item) && !isDeletedRecord(item)) {
      state.displayStatus = "Data Issue";
      state.statusClass = "status-chip status-chip--urgent";
      state.actions = ["DELETE"];
      return state;
    }

    // Lifecycle-based Actions
    if (isArchivedRecord(item)) {
      state.actions = ["UNARCHIVE", "REOPEN_PENDING", "RESTORE_APPROVED", "DELETE"];
      if (item.is_test_booking) {
        state.actions.push("UNMARK_TEST");
      } else {
        state.actions.push("MARK_TEST");
      }
      return state;
    }
    
    if (isDeletedRecord(item)) {
      // Release 6D: PURGE_FOREVER only for records with explicit DELETED/TRASH status.
      // This prevents purge from appearing on zombie records (active status + deleted_at).
      const explicitlyDeleted = ['DELETED', 'TRASH', 'DELETE'].includes(status);
      state.actions = explicitlyDeleted 
        ? ["REOPEN_PENDING", "RESTORE_APPROVED", "PURGE_FOREVER"]
        : ["REOPEN_PENDING", "RESTORE_APPROVED", "DELETE"];
      return state;
    }

    // Contextual Workflow Actions
    if (workflow === 'CUSTOMER_INTAKE') {
      switch (status) {
        case 'PENDING_REVIEW':
        case 'NEEDS_REVIEW':
          state.actions = ["CREATE_PROFILE", "MEET_GREET", "APPROVE", "CANCEL", "DELETE"];
          break;
        case 'PROFILE_CREATED':
          state.actions = ["MOVE_TO_NEW_REQUEST", "MEET_GREET", "APPROVE", "CANCEL"];
          break;
        case 'MEET_GREET_REQUIRED':
        case 'NEEDS_MG':
          state.actions = ["MG_SCHEDULED", "VERIFY_MG", "CANCEL"];
          break;
        case 'MG_SCHEDULED':
          state.actions = ["VERIFY_MG", "MEET_GREET_REQUIRED", "CANCEL"];
          break;
        case 'MG_COMPLETED':
          state.actions = ["APPROVE", "CANCEL"];
          break;
        case 'APPROVED':
          state.actions = ["ARCHIVE", "DELETE"];
          break;
        case 'DECLINED':
        case 'CANCELLED':
          // Release 1: Add RESTORE_APPROVED for controlled recovery.
          state.actions = ["RESTORE_APPROVED", "ARCHIVE", "DELETE"];
          break;
        case 'CANCELLATION_REQUESTED':
          state.actions = ["PROCESS_CANCELLATION", "ARCHIVE", "DELETE"];
          break;
        default:
          state.actions = ["ARCHIVE", "DELETE"];
      }
    } else {
      // VISIT_BOOKING
      switch (status) {
        case 'PENDING_REVIEW':
        case 'NEEDS_REVIEW':
        case 'READY_FOR_APPROVAL':
        case 'NEW_REQUEST':
          state.actions = ["QUOTE", "APPROVE", "CANCEL", "EDIT_PET"];
          break;
        case 'QUOTE_NEEDED':
          state.actions = ["QUOTED", "APPROVE", "CANCEL", "EDIT_PET"];
          break;
        case 'QUOTED':
        case 'QUOTE_SENT':
          state.actions = ["APPROVE", "CANCEL", "EDIT_PET"];
          break;
        case 'APPROVED':
        case 'BOOKED':
        case 'JOB_CREATED':
          state.actions = ["ASSIGN", "CANCEL", "ARCHIVE", "EDIT_PET"];
          break;
        case 'ASSIGNED':
        case 'SCHEDULED':
          state.actions = ["CHANGE_WORKER", "REVERT_TO_APPROVED", "COMPLETE", "CANCEL", "ARCHIVE", "EDIT_PET"];
          break;
        case 'IN_PROGRESS':
          state.actions = ["COMPLETE", "CANCEL", "EDIT_PET"];
          break;
        case 'COMPLETED':
          state.actions = ["REOPEN", "ARCHIVE"];
          break;
        case 'CANCELLED':
        case 'DECLINED':
          // Release 1: Add RESTORE_APPROVED for controlled recovery from accidental cancellation.
          state.actions = ["RESTORE_APPROVED", "ARCHIVE", "DELETE"];
          break;
        case 'CANCELLATION_REQUESTED':
          state.actions = ["PROCESS_CANCELLATION", "ARCHIVE", "DELETE"];
          break;
        default:
          state.actions = ["CANCEL", "ARCHIVE"];
      }
    }

    if (!isDeletedRecord(item) && !isArchivedRecord(item)) {
      if (item.is_test_booking) {
        state.actions.push("UNMARK_TEST");
      } else {
        state.actions.push("MARK_TEST");
      }
    }

    return state;
  };

  const matchesSearch = (item, query) => {
    if (!query) return true;
    const q = query.toLowerCase().trim();
    if (!q) return true;

    const clientName = (item.client_name || '').toLowerCase();
    const petNames = (item.pet_names || item.pet_name || '').toLowerCase();
    const clientEmail = (item.client_email || '').toLowerCase();
    const requestId = (item.request_id || item.PK?.replace('REQ#', '') || '').toLowerCase();
    const serviceType = (item.service_type || '').toLowerCase();
    const status = (item.status || '').toLowerCase();
    const paymentStatus = (item.payment_status || 'unpaid').toLowerCase();

    const serviceLabel = getServiceLabel(item.service_type).toLowerCase();
    const statusLabel = getStatusLabel(item.status, item).toLowerCase();

    return (
      clientName.includes(q) ||
      petNames.includes(q) ||
      clientEmail.includes(q) ||
      requestId.includes(q) ||
      serviceType.includes(q) ||
      serviceLabel.includes(q) ||
      status.includes(q) ||
      statusLabel.includes(q) ||
      paymentStatus.includes(q)
    );
  };

  const matchesPaymentStatus = (item, filter) => {
    if (filter === 'ALL') return true;
    const paymentStatus = (item.payment_status || 'unpaid').toLowerCase();
    if (filter === 'UNPAID') {
      return paymentStatus === 'unpaid' || !item.payment_status;
    }
    return paymentStatus === filter.toLowerCase();
  };

  const renderPaymentStatusChip = (item) => {
    const status = (item.payment_status || 'unpaid').toLowerCase();
    const config = {
      paid: {
        label: 'Paid',
        style: { backgroundColor: '#ecfdf5', color: '#065f46', borderColor: '#a7f3d0' }
      },
      payment_link_sent: {
        label: 'Payment Link Sent',
        style: { backgroundColor: '#eff6ff', color: '#1e40af', borderColor: '#bfdbfe' }
      },
      waived: {
        label: 'Waived',
        style: { backgroundColor: '#fffbeb', color: '#b45309', borderColor: '#fde68a' }
      },
      refunded: {
        label: 'Refunded',
        style: { backgroundColor: '#faf5ff', color: '#6b21a8', borderColor: '#e9d5ff' }
      },
      unpaid: {
        label: 'Unpaid',
        style: { backgroundColor: '#f3f4f6', color: '#374151', borderColor: '#e5e7eb' }
      }
    };
    const current = config[status] || config.unpaid;
    return (
      <span 
        className="status-chip" 
        style={{ 
          minWidth: 'auto', 
          padding: '4px 10px', 
          fontSize: '0.65rem',
          border: '1px solid',
          borderRadius: '4px',
          fontWeight: 'bold',
          textTransform: 'uppercase',
          ...current.style
        }}
      >
        {current.label}
      </span>
    );
  };

  /**
   * Memoized Derived State
   * visibleRecords and filterCounts are always in sync with allRequests pool.
   */
  const visibleRecords = React.useMemo(() => {
    // Exclude lifecycle/removal statuses from the scheduler timeline if in SCHEDULER view
    if (view === 'SCHEDULER') {
        const terminalStatuses = ['ARCHIVED', 'DELETED', 'COMPLETED', 'CANCELLED'];
        return allRequests.filter(r => !terminalStatuses.includes((r.status || '').toUpperCase()));
    }
    // Filter by the current status filter
    let filtered = allRequests.filter(getFilterPredicate(statusFilter));

    // Apply search query
    if (searchQuery) {
      filtered = filtered.filter(r => matchesSearch(r, searchQuery));
    }

    // Apply payment status filter
    if (paymentStatusFilter && paymentStatusFilter !== 'ALL') {
      filtered = filtered.filter(r => matchesPaymentStatus(r, paymentStatusFilter));
    }

    return filtered;
  }, [allRequests, statusFilter, view, searchQuery, paymentStatusFilter]);

  const filterCounts = React.useMemo(() => {
    try {
      const filters = [
          'INTAKE_QUEUE', 'MEET_GREET_REQUIRED', 'READY_FOR_APPROVAL',
          'BOOKING_QUEUE', 'QUOTED', 'ASSIGNED', 'COMPLETED',
          'ALL', 'NEEDS_ACTION', 'DATA_ISSUES', 'UNASSIGNED',
          'CANCELLED', 'ARCHIVED', 'DELETED'
      ];
      const counts = {};
      const reqs = allRequests || [];
      filters.forEach(f => {
          counts[f] = reqs.filter(getFilterPredicate(f)).length;
      });
      return counts;
    } catch (err) {
      console.error("Critical: filterCounts calculation crashed", err);
      return {};
    }
  }, [allRequests]);

  // Clear stale selections when switching filters
  React.useEffect(() => {
    setSelectedIds([]);
  }, [statusFilter]);


  const getGuidedActions = (item) => {
    const workflowItem = { ...item, workflow_type: determineWorkflowType(item) };
    const { actions } = getWorkflowState(item);
    const primaryAction = resolveGuidedWorkflowAction(workflowItem, actions);
    const primary = primaryAction?.id || null;

    const secondary = actions
      .filter(action => action !== primary && !['EDIT_PET', 'ASSIGN', 'CHANGE_WORKER', 'PURGE_FOREVER'].includes(action))
      .map(action => describeGuidedWorkflowAction(workflowItem, action));
    
    return { primary, primaryAction, secondary };
  };

  const [adminNote, setAdminNote] = useState('');

  const completeAuthenticatedBootstrap = async (session, userRole) => {
    if (!['owner', 'admin', 'staff'].includes(userRole)) {
      if (userRole === 'client' && !expectedTenantSlug) {
        window.location.href = '/my-bookings';
      } else {
        setError(expectedTenantSlug ? TENANT_ACCESS_ERROR : "Access denied. You do not have permission to view the Staff Portal.");
        setIsAuthenticated(false);
      }
      return false;
    }

    const payload = session.getIdToken().payload;
    const authorize = async (verifiedTenantInfo = null) => {
      setCurrentUser({
        email: payload.email,
        sub: payload.sub,
        name: payload.name || payload['custom:display_name'] || null
      });
      setRole(userRole);
      if (verifiedTenantInfo) {
        setTenantInfo(verifiedTenantInfo);
        const presentation = deriveTenantPresentation(verifiedTenantInfo);
        updateDocumentTitle(presentation);
      } else {
        updateDocumentTitle(DEFAULT_BRANDING);
      }
      setIsAuthenticated(true);
      fetchAllData();
      fetchGoogleStatus();
      if (!verifiedTenantInfo) {
        fetchTenantInfo();
      }
    };

    if (expectedTenantSlug) {
      try {
        await bootstrapTenantSession({
          session,
          tenantSlug: expectedTenantSlug,
          resolveTenant: getTenantInfo,
          onAuthorized: authorize,
        });
      } catch {
        setError(TENANT_ACCESS_ERROR);
        setIsAuthenticated(false);
        updateDocumentTitle(null);
        return false;
      }
    } else {
      await authorize();
    }

    return true;
  };

  const checkAuth = async () => {
    try {
      const session = await getSession();
      if (session) {
        const userRole = getEffectiveRole(session);
        await completeAuthenticatedBootstrap(session, userRole);
      }
    } catch (err) {
      console.error("Auth check failed", err);
      if (expectedTenantSlug) {
        setError(TENANT_ACCESS_ERROR);
        setIsAuthenticated(false);
        updateDocumentTitle(null);
      }
    }
  };

  useEffect(() => {
    checkAuth();
  }, []);

  useEffect(() => {
    if (role === 'staff' && view !== 'SCHEDULER') {
      setView('SCHEDULER');
    }
  }, [role, view]);

  // Release 4B Hotfix: Reactive data fetching when filters change
  // This ensures the list stays populated when navigating between views.
  useEffect(() => {
    if (isAuthenticated && role) {
      // Small delay to prevent jitter during rapid state changes
      const timer = setTimeout(() => {
        fetchAllData();
      }, 100);
      return () => clearTimeout(timer);
    }
  }, [statusFilter, view, timeframeFilter, isAuthenticated, role]);


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
      await completeAuthenticatedBootstrap(session, userRole);

    } catch (err) {
      setError(err.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  const openPasswordRecovery = () => {
    setError(null);
    setRecoverySuccess(false);
    setRecoveryEmail(loginData.email);
    setRecoveryCode('');
    setRecoveryNewPassword('');
    setRecoveryConfirmPassword('');
    setRecoveryMode('request');
  };

  const returnToLogin = () => {
    const email = recoveryEmail.trim();
    setLoginData((current) => ({ ...current, email: email || current.email, password: '' }));
    setError(null);
    setRecoverySuccess(false);
    setRecoveryCode('');
    setRecoveryNewPassword('');
    setRecoveryConfirmPassword('');
    setRecoveryMode('login');
  };

  const returnToRecoveryRequest = () => {
    setError(null);
    setRecoverySuccess(false);
    setRecoveryCode('');
    setRecoveryNewPassword('');
    setRecoveryConfirmPassword('');
    setRecoveryMode('request');
  };

  const handleRequestPasswordReset = async (e) => {
    e.preventDefault();
    if (loading) return;

    const normalizedEmail = recoveryEmail.trim().toLowerCase();
    if (!normalizedEmail) {
      setError('Please enter your email address.');
      return;
    }

    setLoading(true);
    setError(null);
    try {
      await forgotPassword(normalizedEmail);
      setRecoveryEmail(normalizedEmail);
      setRecoveryMode('confirm');
    } catch {
      setError('Unable to send a reset code right now. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleConfirmPasswordReset = async (e) => {
    e.preventDefault();
    if (loading) return;

    const normalizedEmail = recoveryEmail.trim().toLowerCase();
    const normalizedCode = recoveryCode.trim();
    if (!normalizedCode) {
      setError('Please enter your verification code.');
      return;
    }
    if (!recoveryNewPassword) {
      setError('Please enter a new password.');
      return;
    }
    if (!recoveryConfirmPassword) {
      setError('Please confirm your new password.');
      return;
    }
    if (recoveryNewPassword.length < 8) {
      setError('Password must be at least 8 characters.');
      return;
    }
    if (recoveryNewPassword !== recoveryConfirmPassword) {
      setError('Passwords do not match.');
      return;
    }

    setLoading(true);
    setError(null);
    try {
      await confirmForgotPassword(normalizedEmail, normalizedCode, recoveryNewPassword);
      setRecoveryCode('');
      setRecoveryNewPassword('');
      setRecoveryConfirmPassword('');
      setRecoverySuccess(true);
    } catch (err) {
      const recoveryError = String(err?.code || err?.message || '').toLowerCase();
      if (recoveryError.includes('code mismatch') || recoveryError.includes('codemismatch') || recoveryError.includes('invalid verification code')) {
        setError('Invalid verification code. Please check the code and try again.');
      } else if (recoveryError.includes('expired')) {
        setError('This verification code has expired. Please request a new one.');
      } else {
        setError('Unable to reset your password. Please check your code and try again.');
      }
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
          await completeAuthenticatedBootstrap(session, userRole);
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




  const handleSaveStaff = async (e) => {
    e.preventDefault();

    // Phase 1B.5C-C: Block form submission if edit mode was just activated (double-click guard)
    if (staffEditModeGuardRef.current) {
      return;
    }

    if (!staffForm.display_name.trim()) {
      showNotification("Display name is required", "error");
      return;
    }
    if (staffForm.creation_mode === 'onboard' && !editingStaffId && !staffForm.email.trim()) {
      showNotification("Email is required to create a login account", "error");
      return;
    }

    // Phase 1B.5C-C: No-change detection — skip PATCH if nothing was modified
    if (editingStaffId && initialFormValues) {
      const hasChanges = (
        staffForm.display_name !== initialFormValues.display_name ||
        staffForm.role !== initialFormValues.role ||
        staffForm.is_assignable !== initialFormValues.is_assignable ||
        staffForm.assignment_color !== initialFormValues.assignment_color ||
        staffForm.phone !== initialFormValues.phone ||
        staffForm.notes !== initialFormValues.notes
      );
      if (!hasChanges) {
        showNotification("No changes to save", "info");
        return;
      }
    }
    
    setIsSavingStaff(true);
    try {
      if (editingStaffId) {
        const resp = await updateStaff(editingStaffId, staffForm);
        if (resp && resp._warnings && resp._warnings.length > 0) {
          showNotification("Profile saved, but " + resp._warnings.join(", "), "info");
        } else {
          showNotification("Staff updated successfully", "success");
        }
      } else {
        if (staffForm.creation_mode === 'onboard') {
          await onboardStaff(staffForm);
          showNotification("Staff created and login account set up", "success");
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
      setSelectedStaffForDrawer(null);
      setStaffLinkPrompt(null);
      setIsStaffDrawerOpen(false);
      setIsStaffEditMode(false);
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
    const staff = staffList.find(s => s.staff_id === staffId);
    const staffName = staff?.display_name || 'this staff member';
    if (hasCognito) {
      setConfirmAction({
        type: 'staff',
        id: staffId,
        action: 'disable_with_choice',
        name: staffName,
        message: `Turn off login access for ${staffName}?`,
        consequence: "Click 'Turn Off Both' to disable the profile AND login access, or 'Profile Only' to disable just the profile.",
        variant: 'disable-choice',
        hasCognito: true
      });
      setConfirmTypedInput('');
    } else {
      setConfirmAction({
        type: 'staff',
        id: staffId,
        action: 'disable_profile_only',
        name: staffName,
        message: `Disable ${staffName}'s staff profile?`,
        consequence: "They will no longer appear as assignable. This can be reversed by restoring the profile.",
        variant: 'confirm',
        hasCognito: false
      });
      setConfirmTypedInput('');
    }
  };

  const executeConfirmAction = async () => {
    if (!confirmAction) return;
    const { type, id, action, variant } = confirmAction;

    // Handle the disable-choice variant (staff disable with cognito choice)
    // This is handled by the two buttons in the modal directly
    if (variant === 'disable-choice') return;

    // Handle typed delete confirmation
    if (variant === 'delete-typed') {
      if (confirmTypedInput !== 'DELETE LOGIN ACCOUNT') {
        showNotification("Deletion cancelled. Text did not match.", "info");
        setConfirmAction(null);
        setConfirmTypedInput('');
        return;
      }
    }

    // Handle temp password
    if (variant === 'temp-password') {
      if (!confirmTypedInput.trim()) {
        setConfirmAction(null);
        setConfirmTypedInput('');
        return;
      }
      try {
        if (type === 'staff') {
          await setStaffTempPassword(id, confirmTypedInput.trim());
        } else {
          await setClientTempPassword(id, confirmTypedInput.trim());
        }
        showNotification("Temporary password set successfully", "success");
        if (type === 'staff') await fetchStaffData();
        else await fetchClientData();
      } catch (err) {
        showNotification(err.message || "Failed to set temporary password", "error");
      }
      setConfirmAction(null);
      setConfirmTypedInput('');
      return;
    }

    // Handle link email
    if (variant === 'link-email') {
      if (!confirmTypedInput.trim()) {
        setConfirmAction(null);
        setConfirmTypedInput('');
        return;
      }
      try {
        if (type === 'staff') {
          await linkCognitoUser(id, { username: confirmTypedInput.trim() });
        } else {
          await linkClientCognitoUser(id, { username: confirmTypedInput.trim() });
        }
        showNotification("Login account linked successfully", "success");
        if (type === 'staff') await fetchStaffData();
        else await fetchClientData();
      } catch (err) {
        let errorMsg = err.message || "Failed to link user";
        if (errorMsg === "Failed to fetch") {
          errorMsg = "Link request could not reach the backend. Please verify the API route is deployed and try again.";
        }
        showNotification(errorMsg, "error");
      }
      setConfirmAction(null);
      setConfirmTypedInput('');
      return;
    }

    // Handle disable_profile_only (from handleDisableStaff without cognito)
    if (action === 'disable_profile_only') {
      try {
        await disableStaff(id, null);
        showNotification("Staff disabled successfully", "success");
        await fetchStaffData();
      } catch (err) {
        showNotification(err.message || "Failed to disable staff", "error");
      }
      setConfirmAction(null);
      setConfirmTypedInput('');
      return;
    }

    // Standard confirm actions for staff/client
    try {
      if (type === 'staff') {
        if (action === 'resend-invite') {
          await resendInvite(id);
          showNotification("Invitation resent successfully", "success");
        } else if (action === 'reset-password') {
          await resetStaffPassword(id);
          showNotification("Password reset email triggered", "success");
        } else if (action === 'delete_cognito') {
          await updateStaff(id, { action: 'delete_cognito' });
          showNotification("Staff action 'delete_cognito' completed successfully", "success");
        } else if (action === 'set-protected' || action === 'unset-protected') {
          const updatedStaff = await updateStaff(id, { action });
          showNotification(action === 'set-protected' ? `Protected status granted to ${confirmAction.name}.` : `Protected status removed from ${confirmAction.name}.`, "success");
          if (selectedStaffForDrawer && selectedStaffForDrawer.staff_id === id && updatedStaff) {
            setSelectedStaffForDrawer(updatedStaff);
          }
        } else {
          await updateStaff(id, { action });
          showNotification(`Staff action '${action}' completed successfully`, "success");
        }
        await fetchStaffData();
      } else {
        if (action === 'resend-invite') {
          await resendClientInvite(id);
          showNotification("Invitation resent successfully", "success");
        } else if (action === 'reset-password') {
          await resetClientPassword(id);
          showNotification("Password reset email triggered", "success");
        } else if (action === 'delete_cognito') {
          await updateClient(id, { action: 'delete_cognito' });
          showNotification("Client action 'delete_cognito' completed successfully", "success");
        } else {
          await updateClient(id, { action });
          showNotification(`Client action '${action}' completed successfully`, "success");
        }
        await fetchClientData();
      }
    } catch (err) {
      showNotification(err.message || `Failed to execute ${action}`, "error");
    }
    setConfirmAction(null);
    setConfirmTypedInput('');
  };

  const handleDisableStaffWithCognito = async (disableCognito) => {
    if (!confirmAction) return;
    const { id } = confirmAction;
    try {
      await disableStaff(id, disableCognito ? { disable_cognito: true } : null);
      showNotification("Staff disabled successfully", "success");
      await fetchStaffData();
    } catch (err) {
      showNotification(err.message || "Failed to disable staff", "error");
    }
    setConfirmAction(null);
    setConfirmTypedInput('');
  };
  
  const executeStaffAction = async (staffId, action) => {
    const staff = staffList.find(s => s.staff_id === staffId);
    const staffName = staff?.display_name || 'this staff member';

    // Protected account guardrail — block destructive actions
    const destructiveActions = ['disable', 'delete_cognito', 'delete_profile', 'unlink', 'set-temp-password', 'reset-password'];
    if (destructiveActions.includes(action)) {
      if (isProtectedProfile(staff)) {
        showNotification(`Action blocked: ${staffName} is a protected platform admin and cannot be modified.`, "error");
        return;
      }
      if (isSelf(staff) && ['disable', 'delete_cognito', 'delete_profile'].includes(action)) {
        showNotification(`Action blocked: You cannot ${action === 'disable' ? 'disable' : 'delete'} your own account.`, "error");
        return;
      }
    }

    if (action === 'disable') {
      setConfirmAction({
        type: 'staff', id: staffId, action: 'disable', name: staffName,
        message: `Turn off login access for ${staffName}?`,
        consequence: "This prevents them from signing in, but keeps their records. This can be reversed by restoring login access.",
        variant: 'confirm'
      });
      setConfirmTypedInput('');
      return;
    }
    if (action === 'enable') {
      setConfirmAction({
        type: 'staff', id: staffId, action: 'enable', name: staffName,
        message: `Restore login access for ${staffName}?`,
        consequence: "This allows them to sign in again.",
        variant: 'confirm'
      });
      setConfirmTypedInput('');
      return;
    }
    if (action === 'unlink') {
      setConfirmAction({
        type: 'staff', id: staffId, action: 'unlink', name: staffName,
        message: `Unlink the login account from ${staffName}'s profile?`,
        consequence: "The profile will remain but will no longer be connected to a login. This can be reversed by linking a login account again.",
        variant: 'confirm'
      });
      setConfirmTypedInput('');
      return;
    }
    if (action === 'delete_profile') {
      setConfirmAction({
        type: 'staff', id: staffId, action: 'delete_profile', name: staffName,
        message: `Permanently delete ${staffName}'s profile?`,
        consequence: "This cannot be undone.",
        variant: 'confirm'
      });
      setConfirmTypedInput('');
      return;
    }
    if (action === 'delete_cognito') {
      setConfirmAction({
        type: 'staff', id: staffId, action: 'delete_cognito', name: staffName,
        message: `Delete the login account for ${staffName}?`,
        consequence: "Type 'DELETE LOGIN ACCOUNT' below to confirm. This action permanently removes their login credentials.",
        variant: 'delete-typed'
      });
      setConfirmTypedInput('');
      return;
    }
    if (action === 'set-temp-password') {
      setConfirmAction({
        type: 'staff', id: staffId, action: 'set-temp-password', name: staffName,
        message: `Set a temporary password for ${staffName}`,
        consequence: "Enter the temporary password below. The user will need to change it on next sign-in.",
        variant: 'temp-password'
      });
      setConfirmTypedInput('');
      return;
    }
    if (action === 'reset-password') {
      setConfirmAction({
        type: 'staff', id: staffId, action: 'reset-password', name: staffName,
        message: `Send a password reset email to ${staffName}?`,
        consequence: "They will receive an email with instructions to reset their password.",
        variant: 'confirm'
      });
      setConfirmTypedInput('');
      return;
    }
    if (action === 'set-protected') {
      setConfirmAction({
        type: 'staff', id: staffId, action: 'set-protected', name: staffName,
        message: `Mark ${staffName} as a Protected Platform Admin?`,
        consequence: "Protected platform admins cannot be deleted, disabled, or unlinked.",
        variant: 'confirm'
      });
      setConfirmTypedInput('');
      return;
    }
    if (action === 'unset-protected') {
      if (staff?.is_config_protected) {
        showNotification(`Action blocked: ${staffName} is protected by platform configuration and cannot be unprotected via database flag.`, "error");
        return;
      }
      if (isSelf(staff)) {
        showNotification(`Action blocked: You cannot remove protected status from your own account.`, "error");
        return;
      }
      setConfirmAction({
        type: 'staff', id: staffId, action: 'unset-protected', name: staffName,
        message: `Remove protected status from ${staffName}?`,
        consequence: "This will remove platform protection, allowing account modification or deletion according to standard role permissions.",
        variant: 'confirm'
      });
      setConfirmTypedInput('');
      return;
    }

    // Actions that don't need confirmation (resend-invite)
    try {
      if (action === 'resend-invite') {
        await resendInvite(staffId);
        showNotification("Invitation resent successfully", "success");
      } else {
        await updateStaff(staffId, { action });
        showNotification(`Staff action '${action}' completed successfully`, "success");
      }
      await fetchStaffData();
    } catch (err) {
      showNotification(err.message || `Failed to execute ${action}`, "error");
    }
  };





  const openStaffDetail = (staff, triggerElement) => {
    const el = triggerElement || document.activeElement;
    staffDrawerTriggerRef.current = el;
    handleEditStaff(staff, el);
    setIsStaffEditMode(false);
  };

  const handleEditStaff = (staff, triggerElement) => {
    const formVals = {
      display_name: staff.display_name || '',
      role: staff.role || 'Staff',
      email: staff.email || '',
      is_assignable: staff.is_assignable !== false,
      assignment_color: staff.assignment_color || 'var(--staff-ryan)',
      creation_mode: 'profile_only',
      send_invite: true,
      phone: staff.phone || '',
      notes: staff.notes || ''
    };
    setEditingStaffId(staff.staff_id);
    setStaffForm(formVals);
    setSelectedStaffForDrawer(staff);
    setInitialFormValues(formVals);
    const el = triggerElement || document.activeElement;
    staffDrawerTriggerRef.current = el;
    setIsStaffDrawerOpen(true);
  };

  const handleNewStaff = (triggerElement) => {
    const defaultVals = {
      display_name: '',
      role: 'Staff',
      email: '',
      is_assignable: true,
      assignment_color: 'var(--staff-ryan)',
      creation_mode: 'onboard',
      send_invite: true,
      phone: '',
      notes: ''
    };
    setEditingStaffId(null);
    setStaffForm(defaultVals);
    setSelectedStaffForDrawer(null);
    setInitialFormValues(defaultVals);
    setIsStaffEditMode(true);
    const el = triggerElement || document.activeElement;
    staffDrawerTriggerRef.current = el;
    setIsStaffDrawerOpen(true);
  };

  const closeStaffDrawer = () => {
    const hasUnsavedChanges = isStaffEditMode && initialFormValues && (
      staffForm.display_name !== initialFormValues.display_name ||
      staffForm.role !== initialFormValues.role ||
      staffForm.email !== initialFormValues.email ||
      staffForm.is_assignable !== initialFormValues.is_assignable ||
      staffForm.assignment_color !== initialFormValues.assignment_color ||
      staffForm.phone !== initialFormValues.phone ||
      staffForm.notes !== initialFormValues.notes ||
      staffForm.creation_mode !== initialFormValues.creation_mode ||
      staffForm.send_invite !== initialFormValues.send_invite
    );

    if (hasUnsavedChanges) {
      if (!window.confirm("You have unsaved changes. Are you sure you want to close?")) {
        return;
      }
    }
    setEditingStaffId(null);
    setSelectedStaffForDrawer(null);
    setIsStaffDrawerOpen(false);
    setIsStaffEditMode(false);
  };

  const handleCancelEditStaff = () => {
    if (!editingStaffId) {
      closeStaffDrawer();
    } else {
      setStaffForm(initialFormValues);
      setIsStaffEditMode(false);
    }
  };

  useEffect(() => {
    if (isStaffDrawerOpen) {
      const originalOverflow = document.body.style.overflow;
      const originalOverflowX = document.body.style.overflowX;
      document.body.style.overflow = 'hidden';
      document.body.style.overflowX = 'hidden';
      return () => {
        document.body.style.overflow = originalOverflow;
        document.body.style.overflowX = originalOverflowX;
      };
    }
  }, [isStaffDrawerOpen]);

  const closeStaffDrawerRef = useRef(null);
  useEffect(() => {
    closeStaffDrawerRef.current = closeStaffDrawer;
  });

  // Focus management when staff drawer opens/closes
  useEffect(() => {
    if (isStaffDrawerOpen) {
      setTimeout(() => {
        const firstInput = document.querySelector('.profile-editor-drawer input[type="text"]:not([disabled])');
        if (firstInput) {
          firstInput.focus();
        } else {
          staffDrawerCloseBtnRef.current?.focus();
        }
      }, 50);
    } else {
      const trigger = staffDrawerTriggerRef.current;
      if (trigger && typeof trigger.focus === 'function' && document.body.contains(trigger)) {
        trigger.focus();
      }
      staffDrawerTriggerRef.current = null;
    }
  }, [isStaffDrawerOpen]);

  // Focus trap when staff drawer is open
  useEffect(() => {
    if (!isStaffDrawerOpen) return;

    const drawerEl = document.querySelector('.profile-editor-drawer');
    if (!drawerEl) return;

    const focusableSelector = 'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';
    
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        if (closeStaffDrawerRef.current) {
          closeStaffDrawerRef.current();
        }
        return;
      }
      
      if (e.key !== 'Tab') return;

      const focusables = Array.from(drawerEl.querySelectorAll(focusableSelector))
        .filter(el => !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length));

      if (focusables.length === 0) return;

      const firstEl = focusables[0];
      const lastEl = focusables[focusables.length - 1];

      if (!drawerEl.contains(document.activeElement)) {
        firstEl.focus();
        e.preventDefault();
        return;
      }

      if (e.shiftKey) {
        if (document.activeElement === firstEl) {
          lastEl.focus();
          e.preventDefault();
        }
      } else {
        if (document.activeElement === lastEl) {
          firstEl.focus();
          e.preventDefault();
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [isStaffDrawerOpen]);





  useEffect(() => {
    if (isAuthenticated) {
      if (skipNextDataFetchRef.current) {
        skipNextDataFetchRef.current = false;
        return;
      }
      fetchAllData();
    }
  }, [view, statusFilter, timeframeFilter, isAuthenticated]);

   const toggleSelectAll = () => {
    const currentKeys = visibleRecords.map(r => getRecordKey(r));
    const allSelected = currentKeys.length > 0 && currentKeys.every(key => selectedIds.includes(key));
    
    if (allSelected) {
      setSelectedIds(prev => prev.filter(id => !currentKeys.includes(id)));
    } else {
      setSelectedIds(prev => [...new Set([...prev, ...currentKeys])]);
    }
  };

  const toggleSelectOne = (key) => {
    setSelectedIds(prev => 
      prev.includes(key) ? prev.filter(i => i !== key) : [...prev, key]
    );
  };

  const updateRecordStatus = async (req, action, note = "", extraData = null) => {
    if (action === 'ASSIGN' || action === 'VIEW_CALENDAR') {
      throw new Error(`${action} is a UI workflow action and cannot be submitted as a status transition.`);
    }

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
      // Release 1: MVP recovery action — restores to APPROVED status.
      // Future enhancement: restore to exact previous_status when tracking is available.
      'RESTORE_APPROVED': 'APPROVED',
      'ARCHIVE': 'ARCHIVED',
      'UNARCHIVE': 'UNARCHIVE',
      'MARK_TEST': 'MARK_TEST',
      'UNMARK_TEST': 'UNMARK_TEST',
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
    const isLifecycleAction = ['ARCHIVED', 'DELETED', 'MARK_TEST', 'UNMARK_TEST', 'UNARCHIVE'].includes(targetStatus.toUpperCase());
    
    if (isLifecycleAction && req.PK && req.SK) {
      // Direct record update for terminal record-management states (Archive/Trash/Test flags)
      let finalAction = action;
      if (targetStatus === 'DELETED') finalAction = 'DELETE';
      if (targetStatus === 'ARCHIVED') finalAction = 'ARCHIVE';
      return performAdminAction(req.PK, req.SK, finalAction, null, extraData);
    } else {
      // Workflow transition update — uses reviewRequest to trigger side effects (emails, jobs, etc.)
      const { reqId, clientId } = resolveIds(req);
      if (!reqId || !clientId) throw new Error("Missing IDs for transition");
      return reviewRequest(reqId, clientId, targetStatus, note);
    }
  };

  const handleExportData = async () => {
    try {
      setLoading(true);
      const data = await getExportData();

      // Sanitize any value to a flat string/number/boolean suitable for an Excel cell.
      // DynamoDB records may contain nested objects, arrays, Decimals, or nulls
      // that SheetJS cannot serialize to valid cell values.
      const sanitize = (v) => {
        if (v === null || v === undefined) return "";
        if (typeof v === "string" || typeof v === "number" || typeof v === "boolean") return v;
        if (Array.isArray(v)) return v.map(item => typeof item === "object" ? JSON.stringify(item) : String(item)).join(", ");
        if (typeof v === "object") return JSON.stringify(v);
        return String(v);
      };
      const sanitizeRow = (row) => {
        const clean = {};
        for (const [key, val] of Object.entries(row)) {
          clean[key] = sanitize(val);
        }
        return clean;
      };

      const workbook = XLSX.utils.book_new();

      // A. Daily Sitter Dispatch Sheet (Release 9D)
      const WINDOW_ORDER = { 'MORNING': 1, 'MIDDAY': 2, 'AFTERNOON': 3, 'EVENING': 4, 'ANYTIME': 5 };
      const FRIENDLY_WINDOWS = { 'MORNING': 'Morning (7-10 AM)', 'MIDDAY': 'Midday (10 AM-2 PM)', 'AFTERNOON': 'Afternoon (2-5 PM)', 'EVENING': 'Evening (5-8 PM)', 'ANYTIME': 'Anytime' };
      const getWindowOrder = (win) => {
        const key = (win || '').toUpperCase();
        return WINDOW_ORDER[key] || 99;
      };
      const getFriendlyWindow = (win) => {
        const key = (win || '').toUpperCase();
        return FRIENDLY_WINDOWS[key] || win || 'Anytime';
      };
      const getFriendlyService = (svc) => {
        const key = (svc || '').toUpperCase();
        return SERVICE_TYPES.services[key]?.label || svc || '';
      };
      const formatDateFriendly = (dateStr) => {
        if (!dateStr) return '';
        const parts = dateStr.split('-');
        if (parts.length !== 3) return dateStr;
        const year = parseInt(parts[0], 10);
        const month = parseInt(parts[1], 10) - 1;
        const day = parseInt(parts[2], 10);
        const date = new Date(year, month, day);
        if (isNaN(date.getTime())) return dateStr;
        return date.toLocaleDateString('en-US', {
          weekday: 'short',
          month: 'short',
          day: 'numeric',
          year: 'numeric'
        });
      };
      const getLocalDateString = (d) => {
        const year = d.getFullYear();
        const month = String(d.getMonth() + 1).padStart(2, '0');
        const day = String(d.getDate()).padStart(2, '0');
        return `${year}-${month}-${day}`;
      };

      const today = new Date();
      const todayStr = getLocalDateString(today);
      const maxDate = new Date();
      maxDate.setDate(today.getDate() + 7);
      const maxDateStr = getLocalDateString(maxDate);

      const dispatchJobs = (data.jobs || []).filter(j => {
        // Exclude test bookings by default
        if (j.is_test_booking === true) return false;

        // Exclude archived/deleted/cancelled jobs
        if (isCancelledRecord(j) || isArchivedRecord(j) || isDeletedRecord(j)) return false;

        const date = j.occurrence_date || j.start_date;
        if (!date || date < todayStr || date > maxDateStr) return false;

        // Check parent request to filter by parent status/test booking status
        const parent = (data.requests || []).find(r => r.request_id === j.request_id || r.PK === `REQ#${j.request_id}`);
        if (parent) {
          if (parent.is_test_booking === true) return false;
          if (isCancelledRecord(parent) || isArchivedRecord(parent) || isDeletedRecord(parent)) return false;
        }

        const jobStatus = (j.status || '').toUpperCase();
        if (!['ASSIGNED', 'JOB_CREATED', 'COMPLETED', 'SCHEDULED'].includes(jobStatus)) return false;

        return true;
      });

      // Sort by date ASC, worker name ASC, window order ASC
      dispatchJobs.sort((a, b) => {
        const dateA = a.occurrence_date || a.start_date || '';
        const dateB = b.occurrence_date || b.start_date || '';
        const dateComp = dateA.localeCompare(dateB);
        if (dateComp !== 0) return dateComp;

        const staffA = a.worker_name || 'Unassigned';
        const staffB = b.worker_name || 'Unassigned';
        const staffComp = staffA.localeCompare(staffB);
        if (staffComp !== 0) return staffComp;

        const winA = a.visit_windows?.[0] || a.visit_window || 'ANYTIME';
        const winB = b.visit_windows?.[0] || b.visit_window || 'ANYTIME';
        return getWindowOrder(winA) - getWindowOrder(winB);
      });

      const dispatchRows = dispatchJobs.map(j => {
        const parent = (data.requests || []).find(r => r.request_id === j.request_id || r.PK === `REQ#${j.request_id}`);
        const client = (data.clients || []).find(c => c.client_id === j.client_id || c.PK === `CLIENT#${j.client_id}`);

        const address = parent?.service_location || parent?.address || client?.address || "";
        const phone = parent?.client_phone || parent?.phone || client?.phone || "";
        const instructions = parent?.pet_info || parent?.details || client?.notes || "";

        return sanitizeRow({
          "Visit Date": formatDateFriendly(j.occurrence_date || j.start_date),
          "Staff / Sitter": j.worker_name || 'Unassigned',
          "Visit Window / Time": getFriendlyWindow(j.visit_windows?.[0] || j.visit_window || 'ANYTIME'),
          "Client Name": j.client_name || parent?.client_name || '',
          "Pet Name(s)": j.pet_name || parent?.pet_names || '',
          "Service Type": getFriendlyService(j.service_type),
          "Address / Location": address ? address.substring(0, 100) : '',
          "Phone / Contact": phone,
          "Status": j.status === 'COMPLETED' ? '✅ Done' : '⏳ Pending',
          "Completion State": j.status === 'COMPLETED' ? `Completed by ${j.completed_by || 'Staff'} at ${j.completed_at || ''}` : 'Pending',
          "Notes / Special Instructions": instructions ? instructions.substring(0, 150) : '',
          "Visit Notes / Feedback": j.visit_notes || ''
        });
      });

      if (dispatchRows.length > 0) {
        XLSX.utils.book_append_sheet(workbook, XLSX.utils.json_to_sheet(dispatchRows), "Daily Dispatch");
      } else {
        XLSX.utils.book_append_sheet(workbook, XLSX.utils.aoa_to_sheet([
          ["Daily Sitter Dispatch"],
          ["Generated At", new Date().toLocaleString()],
          [],
          ["No upcoming visits scheduled for the next 7 days."]
        ]), "Daily Dispatch");
      }

      // 1. Export Summary
      const summaryData = [
        ["Tog & Dogs Offline Backup"],
        ["Generated At", new Date().toLocaleString()],
        [],
        ["Entity", "Count"],
        ["Requests", data.requests?.length || 0],
        ["Clients", data.clients?.length || 0],
        ["Pets", data.pets?.length || 0],
        ["Staff", data.staff?.length || 0],
        ["Jobs", data.jobs?.length || 0]
      ];
      XLSX.utils.book_append_sheet(workbook, XLSX.utils.aoa_to_sheet(summaryData), "Export Summary");

      // Helper to map fields for Requests
      const mapRequest = (r) => sanitizeRow({
        "Request ID": r.request_id || r.PK?.replace('REQ#', ''),
        "Status": r.status,
        "Client Name": r.client_name,
        "Client Email": r.client_email,
        "Client Phone": r.client_phone || r.phone,
        "Pet Name(s)": Array.isArray(r.pet_names) ? r.pet_names.join(", ") : r.pet_names,
        "Service Type": r.service_type,
        "Requested Dates": `${r.start_date || ""}${r.end_date ? " to " + r.end_date : ""}`,
        "Scheduled Date/Time": r.scheduled_at || r.preferred_time,
        "Assigned Staff": r.worker_name || r.assigned_worker,
        "Service Location": r.service_location || r.address,
        "Meet & Greet": r.meet_and_greet_completed ? "Completed" : (r.meet_and_greet_required ? "Required" : "N/A"),
        "Quote Status": r.quote_status || (r.quote_sent_date ? "Sent" : "None"),
        "Visits Completed": (r.is_multi_day || (r.selected_dates && r.selected_dates.length > 1)) ? `${r.completed_count || 0}/${r.selected_dates?.length || r.total_occurrences || 1}` : (r.status === "COMPLETED" ? "1/1" : "0/1"),
        "Admin Notes": r.admin_notes || r.notes,
        "Visit Notes": r.visit_notes || "",
        "Completed By": r.completed_by || "",
        "Completed At": r.completed_at || "",
        "Created Date": r.created_at,
        "Last Updated": r.updated_at
      });

      // 2. All Requests
      const allReqs = (data.requests || []).map(mapRequest);
      XLSX.utils.book_append_sheet(workbook, XLSX.utils.json_to_sheet(allReqs.length ? allReqs : [{}]), "All Requests");

      // 3. Active Requests
      const activeReqs = (data.requests || []).filter(r => isActiveRecord(r)).map(mapRequest);
      XLSX.utils.book_append_sheet(workbook, XLSX.utils.json_to_sheet(activeReqs.length ? activeReqs : [{}]), "Active Requests");

      // 4. Scheduled
      const scheduledReqs = (data.requests || []).filter(r => ['ASSIGNED', 'SCHEDULED', 'BOOKED'].includes(r.status?.toUpperCase())).map(mapRequest);
      XLSX.utils.book_append_sheet(workbook, XLSX.utils.json_to_sheet(scheduledReqs.length ? scheduledReqs : [{}]), "Scheduled");

      // 5. Completed
      const completedReqs = (data.requests || []).filter(r => r.status?.toUpperCase() === 'COMPLETED').map(mapRequest);
      XLSX.utils.book_append_sheet(workbook, XLSX.utils.json_to_sheet(completedReqs.length ? completedReqs : [{}]), "Completed");

      // 6. Clients
      const clientRows = (data.clients || []).map(c => sanitizeRow({
        "Client ID": c.client_id || c.SK?.replace('CLIENT#', ''),
        "Name": c.display_name,
        "Email": c.email,
        "Phone": c.phone,
        "Address": c.address,
        "Emergency Contact": c.emergency_contact,
        "Notes": c.notes,
        "Joined At": c.created_at
      }));
      XLSX.utils.book_append_sheet(workbook, XLSX.utils.json_to_sheet(clientRows.length ? clientRows : [{}]), "Clients");

      // 7. Pets
      const petRows = (data.pets || []).map(p => sanitizeRow({
        "Pet ID": p.pet_id || p.PK?.replace('PET#', ''),
        "Client ID": p.client_id,
        "Name": p.name,
        "Breed": p.breed,
        "Age": p.age,
        "Care Instructions": p.care_instructions,
        "Behavior": p.behavior,
        "Health": p.health,
        "Meet & Greet": p.meet_and_greet_completed ? "Completed" : "Pending"
      }));
      XLSX.utils.book_append_sheet(workbook, XLSX.utils.json_to_sheet(petRows.length ? petRows : [{}]), "Pets");

      // 8. Staff Assignments
      const jobRows = (data.jobs || []).map(j => sanitizeRow({
        "Job ID": j.job_id || j.PK?.replace('JOB#', ''),
        "Request ID": j.request_id || j.SK?.replace('REQ#', ''),
        "Status": j.status,
        "Staff Name": j.worker_name,
        "Assigned At": j.assigned_at,
        "Completed At": j.completed_at || "",
        "Completed By": j.completed_by || "",
        "Visit Notes": j.visit_notes || "",
        "Updated At": j.updated_at
      }));
      XLSX.utils.book_append_sheet(workbook, XLSX.utils.json_to_sheet(jobRows.length ? jobRows : [{}]), "Staff Assignments");

      // 9. Cancelled / Archived / Trash
      const junkReqs = (data.requests || []).filter(r => isCancelledRecord(r) || isArchivedRecord(r) || isDeletedRecord(r)).map(mapRequest);
      XLSX.utils.book_append_sheet(workbook, XLSX.utils.json_to_sheet(junkReqs.length ? junkReqs : [{}]), "Cancelled-Archived-Trash");

      // Generate filename with timestamp
      const now = new Date();
      const pad2 = (n) => String(n).padStart(2, '0');
      const exportPrefix = tenantInfo?.company_id || 'TogAndDogs';
      const fileName = `${exportPrefix}_Offline_Backup_${now.getFullYear()}-${pad2(now.getMonth()+1)}-${pad2(now.getDate())}_${pad2(now.getHours())}${pad2(now.getMinutes())}.xlsx`;

      // Write workbook to ArrayBuffer and create Blob
      const wbArrayBuffer = XLSX.write(workbook, { bookType: 'xlsx', type: 'array' });
      const blob = new Blob([wbArrayBuffer], {
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
      });

      // Trigger download via hidden anchor
      const blobUrl = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.style.display = 'none';
      anchor.href = blobUrl;
      anchor.download = fileName;
      document.body.appendChild(anchor);

      // Use requestAnimationFrame to ensure the anchor is in the DOM before clicking
      requestAnimationFrame(() => {
        anchor.click();
        // Delay cleanup so Chrome fully registers the download name and reads the blob
        setTimeout(() => {
          URL.revokeObjectURL(blobUrl);
          anchor.remove();
        }, 1500);
      });

      showNotification("Offline backup generated successfully.", "success");
      setExportModal(false);
    } catch (err) {
      console.error("Export failed:", err);
      showNotification("Export failed: " + err.message, "error");
    } finally {
      setLoading(false);
    }
  };

  const handleBulkUpdate = async () => {
    setError(null);
    if (!bulkAction || selectedIds.length === 0) return;
    
    setIsBulkUpdating(true);
    const selectedRequests = allRequests.filter(r => selectedIds.includes(getRecordKey(r)));
    
    // For terminal lifecycle actions (DELETE/ARCHIVE), use the bulk backend path
    if (['DELETE', 'ARCHIVE'].includes(bulkAction)) {
      try {
        const payload = selectedRequests.map(r => ({ PK: r.PK, SK: r.SK }));
        const response = await performAdminAction(null, null, bulkAction, payload);
        
        if (response.failed > 0 || response.skipped > 0) {
          const reasons = response.failures.map(f => f.reason).join(", ");
          const summary = `Bulk ${bulkAction}: ${response.success} success, ${response.skipped} skipped, ${response.failed} failed.`;
          showNotification(`${summary} Reasons: ${reasons}`, response.success > 0 ? "info" : "error");
        } else {
          showNotification(`Successfully moved ${response.success} records to ${bulkAction === 'DELETE' ? 'Trash' : 'Archive'}.`, "success");
        }
        
        setSelectedIds([]);
        setBulkAction('');
        setBulkConfirmModal(null);
        await fetchAllData();
      } catch (err) {
        showNotification(`Bulk ${bulkAction} failed: ` + err.message, "error");
      } finally {
        setIsBulkUpdating(false);
      }
      return;
    }

    // Standard workflow transitions still use parallel reviewRequest calls for now
    const updates = selectedRequests.map(async (req) => {
      return updateRecordStatus(req, bulkAction, `Bulk update: ${bulkAction}`);
    });

    try {
      const results = { success: 0, failed: 0 };
      const settled = await Promise.allSettled(updates);
      settled.forEach(res => {
        if (res.status === 'fulfilled') results.success++;
        else results.failed++;
      });

      if (results.failed > 0) {
        showNotification(`Bulk update partial: ${results.success} success, ${results.failed} failed.`, "error");
      } else {
        const actionLabel = bulkAction === 'REOPEN_PENDING' ? 'restored to Active' : 
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
      const response = await reviewRequest(reqId, clientId, type === 'APPROVE' ? 'APPROVED' : 'DECLINED', adminNote);
      
      const successMsg = response.message || (type === 'APPROVE' ? 'Approved successfully.' : 'Declined successfully.');
      const notifType = response.notification_result?.success === false ? 'warning' : getCalendarNotificationType(response);
      showNotification(getCalendarWarningMessage(response, successMsg), notifType);
      
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

  // Google Calendar Disconnect is intentionally disabled.
  // The connection is tenant/business-scoped; disconnecting would affect all users.
  // Per-user calendar connections are deferred work.


  const handleConnectGoogle = async () => {
    if (tenantInfo && tenantInfo.calendar_provider !== 'google') {
      return;
    }
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

  const onReviewAction = async (req, action, note = "", extraData = null) => {
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
      'RESTORE_APPROVED':    'Record restored to Approved.',
      'ASSIGN':              'Worker assigned.',
      'CREATE_PROFILE':      'Profile created.',
      'MOVE_TO_NEW_REQUEST': 'Moved to New Request.',
      'MEET_GREET':          'M&G required flag set.',
      'MEET_GREET_REQUIRED': 'M&G required flag set.',
      'UNARCHIVE':           'Record unarchived.',
      'MARK_TEST':           'Record marked as Test.',
      'UNMARK_TEST':         'Record unmarked as Test.',
    };

    let actionSucceeded = false;

    try {
      setLoading(true);
      const response = await updateRecordStatus(req, action, note, extraData);
      actionSucceeded = true;

      const statusMap = {
        'APPROVE': 'APPROVED',
        'DECLINE': 'DECLINED',
        'CANCEL': 'CANCELLED',
        'COMPLETE': 'COMPLETED',
        'ARCHIVE': 'ARCHIVED',
        'DELETE': 'DELETED',
        'UNARCHIVE': 'UNARCHIVE'
      };
      const targetStatus = statusMap[action] || action;

      // Use backend message if available (includes calendar sync results), otherwise fallback to local map
      const successMsg = response?.message || actionSuccessMessages[action] || actionSuccessMessages[targetStatus] || `Status updated to ${getStatusLabel(targetStatus)}.`;
      showNotification(
        getCalendarWarningMessage(response, successMsg),
        getCalendarNotificationType(response)
      );

      // Reconcile local state immediately to prevent stale display while refresh is in flight
      setAllRequests(prev => prev.map(item =>
        (item.PK === req.PK && item.SK === req.SK)
        ? { 
            ...item, 
            status: targetStatus === 'UNARCHIVE' ? (item.worker_id ? 'ASSIGNED' : 'APPROVED') : targetStatus,
            is_test_booking: action === 'MARK_TEST' ? true : (action === 'UNMARK_TEST' ? false : item.is_test_booking)
          }
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
      setAllRequests(prev => prev.filter(r => !(r.PK === pk && r.SK === sk)));
      showNotification("Record permanently deleted.", "success");
      setPurgeModal(null);
    } catch (err) {
      showNotification("Permanent delete failed: " + err.message, "error");
      setPurgeModal(null);
    } finally {
      setLoading(false);
    }
  };

  const handleBulkPurge = async (confirm = false) => {
    setError(null);
    const selectedItems = allRequests.filter(record => selectedIds.includes(getRecordKey(record)));
    
    if (selectedItems.length === 0) return;

    // Release 6D: Pre-filter to only include records with explicit DELETED/TRASH status.
    // Prevents accidental purge of active records that might be selected.
    const purgeableItems = selectedItems.filter(record => {
      const s = (record.status || '').toUpperCase();
      return s === 'DELETED' || s === 'TRASH' || s === 'DELETE';
    });

    if (purgeableItems.length === 0) {
      showNotification("No selected records are in Trash status. Move records to Trash before purging.", "warning");
      return;
    }

    if (purgeableItems.length < selectedItems.length) {
      showNotification(`${selectedItems.length - purgeableItems.length} record(s) skipped — only Trash records can be permanently deleted.`, "info");
    }

    setIsBulkPurging(true);
    try {
      const payload = purgeableItems.map(item => ({ PK: item.PK, SK: item.SK }));
      
      // Step 1: Dry Run Analysis
      if (!confirm) {
        const response = await purgeRecordsBulk(payload, true); // dry_run = true
        setPurgeAnalysis(response);
        setIsBulkPurging(false);
        return;
      }

      // Step 2: Confirmed Purge (only on purgeable records identified by backend)
      const processedItems = purgeAnalysis.processed || [];
      if (processedItems.length === 0) {
        showNotification("No records are eligible for permanent deletion.", "warning");
        setPurgeAnalysis(null);
        setIsBulkPurging(false);
        return;
      }

      const finalPayload = processedItems.map(p => ({ PK: p.PK, SK: p.SK }));
      const response = await purgeRecordsBulk(finalPayload, false); // dry_run = false
      
      const deletedPKs = processedItems.map(item => item.PK);
      setAllRequests(prev => prev.filter(req => !deletedPKs.includes(req.PK)));
      
      showNotification(`Permanently deleted ${response.success} records.`, "success");
      if (response.failed > 0) {
        showNotification(`${response.failed} deletions failed. Check logs.`, "error");
      }

      setSelectedIds([]);
      setPurgeAnalysis(null);
      setBulkConfirmModal(null);
      await fetchAllData();
    } catch (err) {
      showNotification("Bulk purge failed: " + err.message, "error");
      setBulkConfirmModal(null);
    } finally {
      setIsBulkPurging(false);
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
      const resp = await processCancellationDecision(reqId, clientId, decision, note);
      showNotification(resp.message || "Cancellation processed.", "success");
      fetchAllData();
    } catch (err) {
      showNotification("Cancellation process failed: " + err.message, "error");
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
      // Resolve staff name for better tracking/GCal
      const staff = staffList.find(s => (s.email || s.display_name) === workerId);
      const workerName = staff ? staff.display_name : workerId;

      const resp = await assignWorker(jobId || reqId, reqId, clientId, workerId, workerName);
      showNotification(
        getCalendarWarningMessage(resp, resp.message || "Worker assigned."),
        getCalendarNotificationType(resp)
      );
      setAssigningId(null);
      fetchAllData();
    } catch (err) {
      showNotification("Assignment failed: " + err.message, "error");
    } finally {
      setLoading(false);
    }
  };

  const handleSelectPet = async (item) => {
    // Release 4B: Load multiple PET# records when pet_ids array exists.
    // Falls back to single pet_id, then request pets array, then legacy pet_names.
    const petIds = item.pet_ids || (item.pet_id ? [item.pet_id] : []);
    
    if (petIds.length > 0) {
      try {
        setLoading(true);
        // Release 5A Hotfix 1: Fetch all PET# records with reliable fallback.
        // If a fetch fails, include a placeholder with the pet_id so tabs still render.
        const petPromises = petIds.map((pid, idx) => 
          getPet(pid, item.linked_client_profile_id || item.client_id).catch(err => {
            console.warn(`Failed to load PET#${pid}:`, err.message);
            // Return a minimal fallback so the pet tab still appears
            return { pet_id: pid, client_id: item.linked_client_profile_id || item.client_id, name: "Deleted/Unavailable pet record", _fetchFailed: true };
          })
        );
        const petResults = await Promise.all(petPromises);
        // All results are non-null now (failed ones have fallback data)
        const loadedPets = petResults.filter(p => p !== null);
        
        if (loadedPets.length > 0) {
          setSelectedPet({ 
            ...loadedPets.find(p => !p._fetchFailed) || loadedPets[0],
            _allPets: loadedPets,
            _originItem: item 
          });
        } else {
          setSelectedPet(_buildFallbackPet(item));
        }
      } catch (err) {
        alert("Failed to load care card: " + err.message);
      } finally {
        setLoading(false);
      }
    } else {
      // No pet_ids — show preview from request data
      setSelectedPet(_buildFallbackPet(item));
    }
  };

  const _buildFallbackPet = (item) => {
    const petsArr = item.pets || [];
    const firstPetName = (petsArr.length > 0 && petsArr[0].name) ? petsArr[0].name : null;
    
    return {
      ...item, // Preserve original fields
      name: firstPetName || item.pet_names || item.pet_name || item.client_name || 'Pet',
      species: (petsArr.length > 0 ? petsArr[0].species : item.species) || 'DOG',
      breed: (petsArr.length > 0 ? petsArr[0].breed : (item.breed || item.pet_breed)) || 'Unknown',
      age: (petsArr.length > 0 ? petsArr[0].age : (item.age || item.pet_age)) || '?',
      care_instructions: item.pet_info || item.care_instructions || item.pet_names,
      health: { 
        vet_name: item.vet_name || (item.vet_info ? item.vet_info.vet_name : null), 
        vet_phone: item.vet_phone || (item.vet_info ? item.vet_info.clinic_phone : null) 
      },
      _allPets: petsArr.length > 0 ? petsArr.map(p => ({ ...p, _source: 'request' })) : [],
      _originItem: item
    };
  };

  const handleUpdatePet = async (updatedPet) => {
    try {
      setLoading(true);
      const originItem = selectedPet?._originItem;
      const { clientId: resolvedClientId, reqId } = resolveIds(originItem || selectedPet || updatedPet);
      const pid = updatedPet.pet_id || selectedPet?.pet_id || 'NEW';
      // Release 5A: Use the pet's own client_id for the update call (may differ from REQ client_id
      // when PET# records use linked_client_profile_id as their SK).
      const clientId = updatedPet.client_id || resolvedClientId;
      
      if (!clientId) throw new Error("Could not resolve Client ID for pet update.");
      
      await updatePet(pid, clientId, { ...updatedPet, request_id: reqId });

      // Transition workflow if this was an intake record
      const intakeStatuses = ['PENDING_REVIEW', 'MEET_GREET_REQUIRED'];
      if (pid === 'NEW' && reqId && (!originItem?.status || intakeStatuses.includes(originItem.status))) {
        await reviewRequest(reqId, clientId, 'PROFILE_CREATED', "Automated: Profile created.");
      }

      if (pid === 'NEW') {
        setSelectedPet(null);
      } else {
        // Release 5A Hotfix 2: Preserve _allPets and _originItem metadata after save
        // so the multi-pet UI doesn't collapse back to single-pet view.
        setSelectedPet(prev => {
          if (!prev) return null;
          const preservedAllPets = prev._allPets?.map(p => p.pet_id === pid ? { ...p, ...updatedPet } : p);
          return {
            ...prev,
            ...updatedPet,
            _allPets: preservedAllPets || prev._allPets,
            _originItem: prev._originItem  // Always preserve origin
          };
        });
      }
      fetchAllData();
    } catch (err) {
      alert("Failed to update/create pet record: " + err.message);
    } finally {
      setLoading(false);
    }
  };

  // Release 6F: New Visit modal handlers
  const handleCloseNewVisitModal = () => {
    setNewVisitModal(false);
    setNewVisitForm(createInitialNewVisitForm());
    setNewVisitScheduleError('');
    setNewVisitClientPets([]);
    setIsAddingPetInline(false);
    setInlinePetForm({ name: '', species: 'DOG', breed: '', age: '' });
  };

  const handleInlinePetSubmit = async () => {
    if (!inlinePetForm.name.trim()) return;
    const clientId = newVisitForm.client_id;
    if (!clientId) return;

    setIsSavingPetInline(true);
    try {
      const result = await createPet({
        client_id: clientId,
        name: inlinePetForm.name.trim(),
        species: inlinePetForm.species,
        breed: inlinePetForm.breed.trim() || undefined,
        age: inlinePetForm.age ? parseInt(inlinePetForm.age) : undefined,
        is_active: true
      });

      showNotification(`Pet "${inlinePetForm.name}" created successfully!`, "success");

      // Refresh client pets list
      const resp = await listAdminClientPets(clientId);
      const pets = (resp.pets || []).filter(p => p && p.pet_id);
      setNewVisitClientPets(pets);

      // Auto-select the newly created pet ID
      const newPetId = result?.pet_id;
      if (newPetId) {
        setNewVisitForm(prev => {
          const ids = prev.pet_ids.includes(newPetId) ? prev.pet_ids : [...prev.pet_ids, newPetId];
          const names = pets
            .filter(p => ids.includes(p.pet_id))
            .map(p => p.name || 'Unnamed')
            .join(', ');
          return { ...prev, pet_ids: ids, pet_names: names };
        });
      }

      // Reset form
      setInlinePetForm({ name: '', species: 'DOG', breed: '', age: '' });
      setIsAddingPetInline(false);
    } catch (err) {
      showNotification("Failed to create pet inline: " + err.message, "error");
    } finally {
      setIsSavingPetInline(false);
    }
  };

  const handleNewVisitClientSelect = (clientId) => {
    const client = clientList.find(c => c.client_id === clientId);
    if (!client) return;
    setNewVisitForm(prev => ({
      ...prev,
      client_id: client.client_id,
      client_name: client.display_name || '',
      client_email: client.email || '',
      client_phone: client.phone || '',
      pet_names: '', pet_ids: []
    }));
    // Close inline pet addition if active
    setIsAddingPetInline(false);
    setInlinePetForm({ name: '', species: 'DOG', breed: '', age: '' });
    
    // Load pets for this client
    const fetchPets = async () => {
      try {
        const resp = await listAdminClientPets(client.client_id);
        const pets = (resp.pets || []).filter(p => p && p.pet_id);
        setNewVisitClientPets(pets);
      } catch { setNewVisitClientPets([]); }
    };
    fetchPets();
  };

  const handleNewVisitPetToggle = (pet) => {
    setNewVisitForm(prev => {
      const ids = prev.pet_ids.includes(pet.pet_id)
        ? prev.pet_ids.filter(id => id !== pet.pet_id)
        : [...prev.pet_ids, pet.pet_id];
      const names = newVisitClientPets
        .filter(p => ids.includes(p.pet_id))
        .map(p => p.name || 'Unnamed')
        .join(', ');
      return { ...prev, pet_ids: ids, pet_names: names };
    });
  };

  const openAssignmentHandoff = (item) => {
    const { jobId } = resolveIds(item);
    const status = String(item?.status || '').toUpperCase();

    if (!jobId && status === 'APPROVED') {
      alert("Job record is still initializing. Please wait a moment and refresh.");
      fetchAllData();
      return;
    }

    setAssigningId(item.PK);
    setDecisionModal(null);
    setWorkflowDropdownOpen(false);
  };

  const getRequestId = (item) => {
    if (!item) return null;
    if (item.request_id) return item.request_id;

    const pk = String(item.PK || '');
    const sk = String(item.SK || '');
    if (pk.startsWith('REQ#')) return pk.slice(4);
    if (sk.startsWith('REQ#')) return sk.slice(4);
    return null;
  };

  const hasInitializedJob = (item) => (
    Boolean(item?.job_id)
    || (Array.isArray(item?.job_ids) ? item.job_ids.length > 0 : Boolean(item?.job_ids))
  );

  const mergeRefreshedRequest = (requestId, refreshedRequest) => {
    if (!refreshedRequest) return;
    setAllRequests(prev => prev.map(item => (
      getRequestId(item) === requestId
        ? { ...item, ...refreshedRequest }
        : item
    )));
  };

  const navigateToScheduler = () => {
    if (view !== 'SCHEDULER' || statusFilter !== 'ALL') {
      skipNextDataFetchRef.current = true;
    }
    setView('SCHEDULER');
    setStatusFilter('ALL');
    setDecisionModal(null);
    setWorkflowDropdownOpen(false);
    setOpenMenuId(null);
  };

  const refetchUntilJobReady = async (requestId) => {
    let refreshedRequest = null;

    for (let attempt = 0; attempt < APPROVAL_JOB_REFRESH_ATTEMPTS; attempt += 1) {
      const data = await getAdminRequests('ALL');
      refreshedRequest = (data.requests || []).find(item => getRequestId(item) === requestId) || null;
      mergeRefreshedRequest(requestId, refreshedRequest);

      if (hasInitializedJob(refreshedRequest)) {
        return true;
      }

      if (attempt < APPROVAL_JOB_REFRESH_ATTEMPTS - 1) {
        await waitForApprovalJobRefresh();
      }
    }

    return false;
  };

  const handleApprovalSchedulerHandoff = async (item, note = "") => {
    if (approvalSchedulerHandoffRef.current) return;

    const { reqId, clientId } = resolveIds(item);
    if (!reqId || !clientId) {
      showNotification('Action failed: Missing IDs for transition', 'error');
      return;
    }

    approvalSchedulerHandoffRef.current = true;
    setError(null);
    setLoading(true);

    try {
      const response = await reviewRequest(reqId, clientId, 'APPROVED', note);
      const successMsg = response?.message || 'Approved successfully.';
      showNotification(
        getCalendarWarningMessage(response, successMsg),
        getCalendarNotificationType(response)
      );

      setAllRequests(prev => prev.map(request => (
        getRequestId(request) === reqId
          ? { ...request, status: 'APPROVED' }
          : request
      )));
      setSelectedIds([]);
      setDecisionModal(null);
      setWorkflowDropdownOpen(false);
      setOpenMenuId(null);

      let jobReady = false;
      try {
        jobReady = await refetchUntilJobReady(reqId);
      } catch (refreshErr) {
        console.warn('Approved request reconciliation failed:', refreshErr);
      }

      navigateToScheduler();
      if (!jobReady) {
        showNotification(APPROVAL_JOB_INITIALIZATION_WARNING, 'warning');
      }
    } catch (err) {
      console.error('Action failed:', err);
      showNotification('Action failed: ' + err.message, 'error');
    } finally {
      approvalSchedulerHandoffRef.current = false;
      setLoading(false);
    }
  };

  const handleGuidedWorkflowAction = (item, guidedAction, note = "") => {
    if (!guidedAction) return;

    if (guidedAction.semantic === GUIDED_ACTION_SEMANTICS.ASSIGNMENT_HANDOFF) {
      openAssignmentHandoff(item);
      return;
    }

    if (guidedAction.semantic === GUIDED_ACTION_SEMANTICS.CALENDAR_NAVIGATION) {
      navigateToScheduler();
      return;
    }

    if (guidedAction.semantic === GUIDED_ACTION_SEMANTICS.APPROVAL_SCHEDULER_HANDOFF) {
      handleApprovalSchedulerHandoff(item, note);
      return;
    }

    onReviewAction(item, guidedAction.id, note);
  };

  const handleNewVisitServiceChange = (serviceType) => {
    setNewVisitScheduleError('');
    setNewVisitForm(prev => ({
      ...prev,
      service_type: serviceType,
      visits_per_day: null,
      visit_windows: getInitialAdminVisitWindows(serviceType)
    }));
  };

  const handleNewVisitCountChange = (visitsPerDay) => {
    const model = getAdminCheckInModel(newVisitForm.service_type);
    if (!model || !model.service.visitsPerDayOptions.includes(visitsPerDay)) return;

    setNewVisitScheduleError('');
    setNewVisitForm(prev => {
      const selected = model.windows
        .map(window => window.id)
        .filter(id => prev.visit_windows.includes(id));
      return {
        ...prev,
        visits_per_day: visitsPerDay,
        visit_windows: visitsPerDay === model.windows.length
          ? model.windows.map(window => window.id)
          : selected.slice(0, visitsPerDay)
      };
    });
  };

  const handleNewVisitWindowToggle = (windowId) => {
    const model = getAdminCheckInModel(newVisitForm.service_type);
    if (!model || !newVisitForm.visits_per_day) return;

    setNewVisitScheduleError('');
    setNewVisitForm(prev => {
      const selected = prev.visit_windows.includes(windowId)
        ? prev.visit_windows.filter(id => id !== windowId)
        : prev.visit_windows.length < prev.visits_per_day
          ? [...prev.visit_windows, windowId]
          : prev.visit_windows;
      const canonical = model.windows
        .map(window => window.id)
        .filter(id => selected.includes(id));
      return { ...prev, visit_windows: canonical };
    });
  };

  const handleNewVisitExactWindowChange = (windowId) => {
    const model = getAdminCanonicalWindowModel(newVisitForm.service_type);
    if (model?.service.windowSelectionMode !== 'exactly_one') return;
    if (!model.windows.some(window => window.id === windowId)) return;
    setNewVisitScheduleError('');
    setNewVisitForm(prev => ({ ...prev, visits_per_day: null, visit_windows: [windowId] }));
  };

  const handleNewVisitSubmit = async () => {
    if (!newVisitForm.client_id) { showNotification("Please select a client.", "error"); return; }
    if (!newVisitForm.pet_names && newVisitForm.pet_ids.length === 0) { showNotification("Please select at least one pet.", "error"); return; }
    if (newVisitForm.selected_dates.length === 0) {
      showNotification("Please select at least one date.", "error"); return;
    }

    const checkInModel = getAdminCheckInModel(newVisitForm.service_type);
    const canonicalWindowModel = getAdminCanonicalWindowModel(newVisitForm.service_type);
    if (checkInModel) {
      if (!checkInModel.service.visitsPerDayOptions.includes(newVisitForm.visits_per_day)) {
        setNewVisitScheduleError('Choose how many Check-In visits are needed each day.');
        return;
      }
      if (newVisitForm.visit_windows.length !== newVisitForm.visits_per_day) {
        setNewVisitScheduleError(
          `Choose exactly ${newVisitForm.visits_per_day} visit window${newVisitForm.visits_per_day === 1 ? '' : 's'}.`
        );
        return;
      }
    } else if (canonicalWindowModel?.service.windowSelectionMode === 'exactly_one'
      && newVisitForm.visit_windows.length !== 1) {
      setNewVisitScheduleError('Choose exactly one visit window.');
      return;
    }

    const sorted = [...newVisitForm.selected_dates].sort();

    const payload = {
      client_id: newVisitForm.client_id,
      client_name: newVisitForm.client_name,
      client_email: newVisitForm.client_email,
      client_phone: newVisitForm.client_phone,
      pet_names: newVisitForm.pet_names,
      pet_ids: newVisitForm.pet_ids,
      service_type: newVisitForm.service_type,
      details: newVisitForm.details || undefined,
      preferred_sitter: newVisitForm.preferred_sitter || undefined,
      selected_dates: sorted,
      start_date: sorted[0]
    };

    if (checkInModel) {
      payload.visits_per_day = newVisitForm.visits_per_day;
      payload.visit_windows = checkInModel.windows
        .map(window => window.id)
        .filter(id => newVisitForm.visit_windows.includes(id));
    } else if (canonicalWindowModel?.service.windowSelectionMode === 'exactly_one') {
      payload.visit_windows = canonicalWindowModel.windows
        .map(window => window.id)
        .filter(id => newVisitForm.visit_windows.includes(id));
    } else if (SERVICE_TYPES.services[newVisitForm.service_type]?.windowSelectionMode === 'legacy_compatibility') {
      payload.visit_windows = newVisitForm.visit_windows;
    }

    if (sorted.length > 1) {
      payload.end_date = sorted[sorted.length - 1];
    }

    setIsCreatingVisit(true);
    try {
      const resp = await createAdminBooking(payload);
      showNotification(
        getCalendarWarningMessage(resp, resp.message || "Booking created successfully."),
        getCalendarNotificationType(resp)
      );
      handleCloseNewVisitModal();
      fetchAllData();
    } catch (err) {
      showNotification("Failed to create booking: " + err.message, "error");
    } finally {
      setIsCreatingVisit(false);
    }
  };

  const renderStats = () => {
    // Release 6D: Needs Assignment uses a dedicated predicate for count/click alignment
    const unassignedPredicate = (r) => {
      if (!r || isDataIssue(r)) return false;
      const s = (r.status || '').toUpperCase();
      return (s === 'APPROVED' || s === 'BOOKED' || s === 'JOB_CREATED') && !r.worker_id;
    };

    const stats = {
      intake: allRequests.filter(getFilterPredicate('INTAKE_QUEUE')).length,
      unassigned: allRequests.filter(unassignedPredicate).length,
      scheduled: allRequests.filter(getFilterPredicate('ASSIGNED')).length,
      alerts: allRequests.filter(r => r.status === 'CANCELLATION_REQUESTED').length
    };

    return (
      <div className="admin-stats-grid">
        <div
          className="stat-card"
          role="button"
          tabIndex={0}
          aria-label={`Intake Queue: ${stats.intake} new registrations. Click to view.`}
          onClick={() => { setView('LIST'); setStatusFilter('NEEDS_ACTION'); }}
          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setView('LIST'); setStatusFilter('NEEDS_ACTION'); } }}
        >
          <span className="label">Intake Queue</span>
          <span className="value">{stats.intake}</span>
          <span className="trend neutral">New registrations</span>
        </div>
        <div
          className="stat-card"
          role="button"
          tabIndex={0}
          aria-label={`Needs Assignment: ${stats.unassigned} approved with no staff. Click to view.`}
          onClick={() => { setView('LIST'); setStatusFilter('UNASSIGNED'); }}
          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setView('LIST'); setStatusFilter('UNASSIGNED'); } }}
        >
          <span className="label">Needs Assignment</span>
          <span className="value" style={{ color: stats.unassigned > 0 ? 'var(--warning-color)' : 'inherit' }}>
            {stats.unassigned}
          </span>
          <span className="trend">Approved, no staff</span>
        </div>
        <div
          className="stat-card"
          role="button"
          tabIndex={0}
          aria-label={`Scheduled Visits: ${stats.scheduled} total upcoming. Click to view scheduler.`}
          onClick={() => { setView('SCHEDULER'); setStatusFilter('ALL'); }}
          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setView('SCHEDULER'); setStatusFilter('ALL'); } }}
        >
          <span className="label">Scheduled Visits</span>
          <span className="value">{stats.scheduled}</span>
          <span className="trend neutral">Total upcoming</span>
        </div>
        {stats.alerts > 0 && (
          <div
            className="stat-card"
            style={{ borderColor: 'var(--warning-color)' }}
            role="button"
            tabIndex={0}
            aria-label={`Alerts: ${stats.alerts} cancellation requests. Click to view.`}
            onClick={() => { setView('LIST'); setStatusFilter('ALL'); }}
            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setView('LIST'); setStatusFilter('ALL'); } }}
          >
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
                <label htmlFor="challenge-new-password">New Password</label>
                <input 
                  id="challenge-new-password"
                  type="password" 
                  value={newPassword} 
                  onChange={(e) => setNewPassword(e.target.value)} 
                  required 
                />
              </div>
              <div className="field">
                <label htmlFor="challenge-confirm-password">Confirm New Password</label>
                <input 
                  id="challenge-confirm-password"
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

    if (recoveryMode === 'request') {
      return (
        <div className="section auth-section">
          <div className="card auth-card">
            <h1>Forgot Password</h1>
            <p className="subtitle auth-helper">Enter your email address and we&rsquo;ll send you a verification code.</p>
            <form onSubmit={handleRequestPasswordReset} className="premium-form" noValidate>
              <div className="field">
                <label htmlFor="recovery-email">Email Address</label>
                <input
                  id="recovery-email"
                  type="email"
                  value={recoveryEmail}
                  onChange={(e) => setRecoveryEmail(e.target.value)}
                  autoComplete="username"
                  inputMode="email"
                  aria-required="true"
                />
              </div>
              <button type="submit" className="button-primary" disabled={loading}>
                {loading ? 'Sending...' : 'Send Reset Code'}
              </button>
              {error && <p className="auth-message auth-message--error" role="alert">{error}</p>}
              <button type="button" onClick={returnToLogin} className="auth-link-button" disabled={loading}>
                Back to Sign In
              </button>
            </form>
          </div>
        </div>
      );
    }

    if (recoveryMode === 'confirm') {
      return (
        <div className="section auth-section">
          <div className="card auth-card">
            <h1>Enter Reset Code</h1>
            <p className="subtitle auth-helper">Check your email for a verification code, then choose a new password.</p>
            {recoverySuccess ? (
              <div className="auth-success-panel">
                <p className="auth-message auth-message--success" role="status" aria-live="polite">
                  Password reset successfully. You can now sign in with your new password.
                </p>
                <button type="button" onClick={returnToLogin} className="button-primary">
                  Back to Sign In
                </button>
              </div>
            ) : (
              <form onSubmit={handleConfirmPasswordReset} className="premium-form" noValidate>
                <div className="field">
                  <label htmlFor="recovery-code">Verification Code</label>
                  <input
                    id="recovery-code"
                    type="text"
                    value={recoveryCode}
                    onChange={(e) => setRecoveryCode(e.target.value)}
                    autoComplete="one-time-code"
                    inputMode="numeric"
                    aria-required="true"
                  />
                </div>
                <div className="field">
                  <label htmlFor="recovery-new-password">New Password</label>
                  <input
                    id="recovery-new-password"
                    type="password"
                    value={recoveryNewPassword}
                    onChange={(e) => setRecoveryNewPassword(e.target.value)}
                    autoComplete="new-password"
                    aria-describedby="recovery-password-requirement"
                    aria-required="true"
                  />
                  <span id="recovery-password-requirement" className="auth-field-hint">At least 8 characters.</span>
                </div>
                <div className="field">
                  <label htmlFor="recovery-confirm-password">Confirm New Password</label>
                  <input
                    id="recovery-confirm-password"
                    type="password"
                    value={recoveryConfirmPassword}
                    onChange={(e) => setRecoveryConfirmPassword(e.target.value)}
                    autoComplete="new-password"
                    aria-required="true"
                  />
                </div>
                <button type="submit" className="button-primary" disabled={loading}>
                  {loading ? 'Resetting...' : 'Reset Password'}
                </button>
                {error && <p className="auth-message auth-message--error" role="alert">{error}</p>}
                <div className="auth-recovery-actions">
                  <button type="button" onClick={returnToRecoveryRequest} className="auth-link-button" disabled={loading}>
                    Request a New Code
                  </button>
                  <button type="button" onClick={returnToLogin} className="auth-link-button" disabled={loading}>
                    Back to Sign In
                  </button>
                </div>
              </form>
            )}
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
              <label htmlFor="login-email">Email Address</label>
              <input 
                id="login-email"
                type="email" 
                value={loginData.email} 
                onChange={(e) => setLoginData({...loginData, email: e.target.value})} 
                required 
              />
            </div>
            <div className="field">
              <label htmlFor="login-password">Password</label>
              <input 
                id="login-password"
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
            <button type="button" onClick={openPasswordRecovery} className="auth-link-button" disabled={loading}>
              Forgot password?
            </button>
          </form>
        </div>
      </div>
    );
  }


  const closeClientDrawer = () => {
    if (hasClientUnsavedChanges) {
      if (!window.confirm("You have unsaved changes. Are you sure you want to discard them?")) {
        return;
      }
    }
    setClientDetailTarget(null);
    setClientDrawerMode('view');
    setEditingClientId(null);
    clientPetRequestSeqRef.current += 1;
    activeClientDetailIdRef.current = null;
    setIsClientPetsLoading(false);
    const trigger = clientDrawerTriggerRef.current;
    if (trigger && typeof trigger.focus === 'function' && document.body.contains(trigger)) {
      trigger.focus();
    }
    clientDrawerTriggerRef.current = null;
  };

  const openClientDetail = (client, triggerElement) => {
    if (hasClientUnsavedChanges) {
      if (!window.confirm("You have unsaved changes. Are you sure you want to discard them?")) {
        return;
      }
    }
    const el = triggerElement || document.activeElement;
    clientDrawerTriggerRef.current = el;
    handleEditClient(client);
    setClientDetailTarget(client);
    setClientDrawerMode('view');
  };

  const handleNewClient = (triggerElement) => {
    if (hasClientUnsavedChanges) {
      if (!window.confirm("You have unsaved changes. Are you sure you want to discard them?")) {
        return;
      }
    }
    const defaultVals = {
      display_name: '',
      email: '',
      phone: '',
      address: '',
      emergency_contact: '',
      notes: '',
      creation_mode: 'onboard',
      send_invite: true
    };
    setEditingClientId(null);
    setClientForm(defaultVals);
    setClientInitialFormValues(defaultVals);
    setClientDetailTarget({ client_id: 'new', ...defaultVals });
    setClientDrawerMode('create');
    const el = triggerElement || document.activeElement;
    clientDrawerTriggerRef.current = el;
  };

  const handleCancelClientEdit = () => {
    if (hasClientUnsavedChanges) {
      if (!window.confirm("You have unsaved changes. Are you sure you want to discard them?")) {
        return;
      }
    }
    if (clientDrawerMode === 'create') {
      setClientDetailTarget(null);
      setEditingClientId(null);
      setClientDrawerMode('view');
    } else {
      setClientForm(clientInitialFormValues);
      setClientDrawerMode('view');
    }
  };

  const handleLinkEmail = (client) => {
    setConfirmAction({
      type: 'client', id: client.client_id, action: 'link-email', name: client.display_name || 'this client',
      message: `Link a login account to ${client.display_name || 'this client'}`,
      consequence: "Enter the existing email address to link as their login account.",
      variant: 'link-email'
    });
    setConfirmTypedInput('');
  };

  const handleCreateProfileFromVirtual = (client) => {
    const formVals = {
      display_name: client.display_name || '',
      email: client.email || '',
      phone: '',
      address: '',
      emergency_contact: '',
      notes: '',
      creation_mode: 'profile_only',
      send_invite: false
    };
    setEditingClientId(client.client_id);
    setClientForm(formVals);
    setClientInitialFormValues(formVals);
    setClientDetailTarget(client);
    setClientDrawerMode('edit');
  };

  const handleEditClient = (client) => {
    const formVals = {
      display_name: client.display_name || '',
      email: client.email || '',
      phone: client.phone || '',
      address: client.address || '',
      emergency_contact: client.emergency_contact || '',
      notes: client.notes || '',
      creation_mode: 'profile_only',
      send_invite: true
    };
    setEditingClientId(client.client_id);
    setClientForm(formVals);
    setClientInitialFormValues(formVals);

    // Increment sequence and track active client ID
    clientPetRequestSeqRef.current += 1;
    const currentSeq = clientPetRequestSeqRef.current;
    const currentClientId = client.client_id;
    activeClientDetailIdRef.current = currentClientId;

    setClientPets([]);
    setIsClientPetsLoading(false);

    if (currentClientId && currentClientId !== 'new') {
      setIsClientPetsLoading(true);
      // Phase 1B.5B-A: Load all pets (active + archived) for staff pet management
      listAdminClientPets(currentClientId, true)
        .then(resp => {
          if (currentSeq === clientPetRequestSeqRef.current && activeClientDetailIdRef.current === currentClientId) {
            const pets = (resp && Array.isArray(resp.pets) ? resp.pets : []).filter(p => p && p.pet_id);
            setClientPets(pets);
            setIsClientPetsLoading(false);
          }
        })
        .catch(() => {
          if (currentSeq === clientPetRequestSeqRef.current && activeClientDetailIdRef.current === currentClientId) {
            setClientPets([]);
            setIsClientPetsLoading(false);
          }
        });
    }
  };

  // Phase 1B.5B-A: Pet CRUD handlers passed to ClientDetailDrawer
  const handleDrawerPetCreate = async (clientId, petData) => {
    const result = await createPet({ ...petData, client_id: clientId });
    if (!result || !result.pet_id) throw new Error('Invalid response from server');
    // Refresh the pet list in the drawer
    try {
      const resp = await listAdminClientPets(clientId, true);
      const pets = (resp && Array.isArray(resp.pets) ? resp.pets : []).filter(p => p && p.pet_id);
      setClientPets(pets);
    } catch { /* non-fatal — pet was created */ }
    showNotification(`Pet "${result.name || 'New pet'}" created successfully!`, 'success');
    return result;
  };

  const handleDrawerPetUpdate = async (petId, clientId, petData, action = 'update') => {
    const result = await updatePet(petId, clientId, petData);
    if (!result || !result.pet_id) throw new Error('Invalid response from server');
    // Refresh the pet list in the drawer
    try {
      const resp = await listAdminClientPets(clientId, true);
      const pets = (resp && Array.isArray(resp.pets) ? resp.pets : []).filter(p => p && p.pet_id);
      setClientPets(pets);
    } catch { /* non-fatal */ }
    const actionLabel = action === 'archive' ? 'archived' : (action === 'restore' ? 'restored' : 'updated');
    showNotification(`Pet "${result.name || ''}" ${actionLabel}.`, 'success');
    return result;
  };

  const handleSaveClient = async (e) => {
    if (e && e.preventDefault) e.preventDefault();
    const editingClient = editingClientId ? clientList.find(c => c.client_id === editingClientId) : null;
    const isProfileOnly = clientForm.creation_mode === 'profile_only' && (!editingClient || (!editingClient.cognito_sub && editingClient.cognito_status !== 'onboard' && editingClient.cognito_status !== 'linked'));
    
    if (!clientForm.display_name.trim() || (!isProfileOnly && !clientForm.email.trim())) {
      showNotification("Display name and Email are required", "error");
      return;
    }
    setIsSavingClient(true);
    try {
      if (editingClientId) {
        await updateClient(editingClientId, clientForm);
        showNotification("Client profile updated successfully", "success");
        setClientDetailTarget(prev => ({ ...prev, ...clientForm }));
        setClientDrawerMode('view');
        setClientInitialFormValues({ ...clientForm });
      } else {
        if (clientForm.creation_mode === 'onboard') {
          await onboardClient(clientForm);
          showNotification("Client onboarding triggered", "success");
        } else {
          await createClient(clientForm);
          showNotification("Client profile created successfully", "success");
        }
        setClientDetailTarget(null);
        setEditingClientId(null);
        setClientDrawerMode('view');
      }
      await fetchClientData();
    } catch(err) {
      if (err.message && err.message.includes("Cognito user already exists")) {
        setClientLinkPrompt({ ...clientForm });
      } else {
        let errorMsg = err.message || "Failed to save client";
        if (errorMsg === "Failed to fetch") {
          errorMsg = "Client onboarding request could not reach the backend. Please verify the API route is deployed and try again.";
        }
        showNotification(errorMsg, "error");
      }
    } finally {
      setIsSavingClient(false);
    }
  };

  const handleLinkExistingClientOnboard = async () => {
    try {
      setIsSavingClient(true);
      await onboardClient({ ...clientLinkPrompt, mode: 'create_or_link' });
      showNotification("Client profile linked successfully", "success");
      setClientLinkPrompt(null);
      setClientDetailTarget(null);
      setEditingClientId(null);
      setClientDrawerMode('view');
      await fetchClientData();
    } catch (err) {
      showNotification(err.message || "Link failed", "error");
    } finally {
      setIsSavingClient(false);
    }
  };

  const executeClientAction = async (clientId, action) => {
    const client = clientList.find(c => c.client_id === clientId);
    const clientName = client?.display_name || 'this client';

    // Protected account guardrail — block destructive actions
    const destructiveActions = ['disable', 'delete_cognito', 'delete_profile', 'unlink', 'set-temp-password', 'reset-password'];
    if (destructiveActions.includes(action) && isProtectedProfile(client)) {
      showNotification(`Action blocked: ${clientName} is a protected platform admin and cannot be modified.`, "error");
      return;
    }

    if (action === 'disable') {
      setConfirmAction({
        type: 'client', id: clientId, action: 'disable', name: clientName,
        message: `Turn off login access for ${clientName}?`,
        consequence: "This prevents them from signing in, but keeps their records. This can be reversed.",
        variant: 'confirm'
      });
      setConfirmTypedInput('');
      return;
    }
    if (action === 'enable') {
      setConfirmAction({
        type: 'client', id: clientId, action: 'enable', name: clientName,
        message: `Restore login access for ${clientName}?`,
        consequence: "This allows them to sign in again.",
        variant: 'confirm'
      });
      setConfirmTypedInput('');
      return;
    }
    if (action === 'unlink') {
      setConfirmAction({
        type: 'client', id: clientId, action: 'unlink', name: clientName,
        message: `Unlink the login account from ${clientName}'s profile?`,
        consequence: "The profile will remain but will no longer be connected to a login.",
        variant: 'confirm'
      });
      setConfirmTypedInput('');
      return;
    }
    if (action === 'delete_profile') {
      setConfirmAction({
        type: 'client', id: clientId, action: 'delete_profile', name: clientName,
        message: `Permanently delete ${clientName}'s profile?`,
        consequence: "This cannot be undone.",
        variant: 'confirm'
      });
      setConfirmTypedInput('');
      return;
    }
    if (action === 'delete_cognito') {
      setConfirmAction({
        type: 'client', id: clientId, action: 'delete_cognito', name: clientName,
        message: `Delete the login account for ${clientName}?`,
        consequence: "Type 'DELETE LOGIN ACCOUNT' below to confirm. This action permanently removes their login credentials.",
        variant: 'delete-typed'
      });
      setConfirmTypedInput('');
      return;
    }
    if (action === 'set-temp-password') {
      setConfirmAction({
        type: 'client', id: clientId, action: 'set-temp-password', name: clientName,
        message: `Set a temporary password for ${clientName}`,
        consequence: "Enter the temporary password below. The user will need to change it on next sign-in.",
        variant: 'temp-password'
      });
      setConfirmTypedInput('');
      return;
    }
    if (action === 'reset-password') {
      setConfirmAction({
        type: 'client', id: clientId, action: 'reset-password', name: clientName,
        message: `Send a password reset email to ${clientName}?`,
        consequence: "They will receive an email with instructions to reset their password.",
        variant: 'confirm'
      });
      setConfirmTypedInput('');
      return;
    }

    // Actions that don't need confirmation (resend-invite)
    try {
      setIsSavingClient(true);
      if (action === 'resend-invite') {
        await resendClientInvite(clientId);
        showNotification("Invitation resent successfully. A branded welcome email and login credentials have been sent.", "success");
      } else {
        await updateClient(clientId, { action });
        showNotification(`Client action '${action}' completed successfully`, "success");
      }
      await fetchClientData();
    } catch (err) {
      showNotification(err.message || `Failed to execute ${action}`, "error");
    } finally {
      setIsSavingClient(false);
    }
  };

  const renderClientManagement = () => (
    <div className="client-management-container card" style={{ padding: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <h2>Client Access Management</h2>
        <button type="button" className="button-primary" onClick={(e) => handleNewClient(e.currentTarget)}>
          + Add New Client
        </button>
      </div>

      <div>
        {/* Phase 1B.1A: Client search and filter controls */}
        <div style={{ marginTop: '12px', marginBottom: '16px', display: 'flex', flexWrap: 'wrap', gap: '12px', alignItems: 'center' }}>
          <div style={{ position: 'relative', flex: '1 1 300px', maxWidth: '400px' }}>
            <label htmlFor="client-search-input" className="sr-only" style={{ position: 'absolute', width: '1px', height: '1px', overflow: 'hidden', clip: 'rect(0,0,0,0)' }}>Search clients</label>
            <input
              id="client-search-input"
              type="text"
              placeholder="Search by name, email, phone, notes, pets..."
              value={clientSearch}
              onChange={(e) => setClientSearch(e.target.value)}
              style={{ width: '100%', padding: '10px 14px', borderRadius: '8px', border: '1px solid var(--border)', fontSize: '0.9rem' }}
            />
            {clientSearch && (
              <button
                type="button"
                aria-label="Clear search"
                onClick={() => setClientSearch('')}
                style={{ position: 'absolute', right: '10px', top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', fontSize: '1.1rem', color: 'var(--text-muted)', padding: '4px' }}
              >&times;</button>
            )}
          </div>
          <div>
            <label htmlFor="client-filter-select" className="sr-only" style={{ position: 'absolute', width: '1px', height: '1px', overflow: 'hidden', clip: 'rect(0,0,0,0)' }}>Filter clients</label>
            <select
              id="client-filter-select"
              value={clientFilter}
              onChange={(e) => setClientFilter(e.target.value)}
              style={{ padding: '10px 14px', borderRadius: '8px', border: '1px solid var(--border)', fontSize: '0.9rem', backgroundColor: 'var(--card-bg)' }}
            >
              {CLIENT_FILTERS.map(f => (
                <option key={f.value} value={f.value}>{f.label}</option>
              ))}
            </select>
          </div>
          <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }} aria-live="polite">
            Showing {getVisibleClients(clientList, clientSearch, clientFilter).length} of {clientList.length} clients
          </span>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '20px', marginTop: '20px' }}>
          {getVisibleClients(clientList, clientSearch, clientFilter).map(c => {
            const isSelected = c.client_id === editingClientId;
            return (
              <ClientProfileCard
                key={c.client_id}
                client={c}
                isSelected={isSelected}
                openClientDetail={openClientDetail}
                isProtectedProfile={isProtectedProfile}
              />
            );
          })}
        </div>
      </div>
      {/* Phase 1B.1B, 1B.3 & 1B.5B-A: Client detail drawer */}
      {clientDetailTarget && (
        <ClientDetailDrawer
          client={clientDetailTarget}
          mode={clientDrawerMode}
          formValues={clientForm}
          setFormValues={setClientForm}
          onClose={closeClientDrawer}
          onEdit={(c) => {
            handleEditClient(c);
            setClientDrawerMode('edit');
          }}
          onCancel={handleCancelClientEdit}
          onSave={handleSaveClient}
          isSaving={isSavingClient}
          pets={clientPets}
          loadingPets={isClientPetsLoading}
          onExecuteAction={executeClientAction}
          onLinkEmail={handleLinkEmail}
          onCreateProfile={handleCreateProfileFromVirtual}
          isProtectedProfile={isProtectedProfile}
          clientLinkPrompt={clientLinkPrompt}
          setClientLinkPrompt={setClientLinkPrompt}
          onLinkExistingClientOnboard={handleLinkExistingClientOnboard}
          onPetCreate={handleDrawerPetCreate}
          onPetUpdate={handleDrawerPetUpdate}
          userRole={role}
        />
      )}
    </div>
  );

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
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <h1>{tenantInfo?.display_name || "Pet Care Admin"}</h1>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', fontWeight: '500', opacity: 0.8 }}>
              {expectedTenantSlug ? 'Tenant workspace · ' : ''}Powered by usmissionhero
            </span>
          </div>
          <nav className="view-selector">
            {capabilities.canViewScheduler && (
              <button 
                ref={view === 'SCHEDULER' ? activeTabRef : null}
                className={view === 'SCHEDULER' ? 'active' : ''} 
                onClick={() => { setView('SCHEDULER'); setStatusFilter('ALL'); }}
              >
                Scheduler
              </button>
            )}
            {capabilities.canViewRequestList && (
              <button 
                ref={view === 'LIST' ? activeTabRef : null}
                className={view === 'LIST' ? 'active' : ''} 
                onClick={() => setView('LIST')}
              >
                Request List
              </button>
            )}
            {capabilities.canManageStaff && (
              <button 
                ref={view === 'STAFF_MGMT' ? activeTabRef : null}
                className={view === 'STAFF_MGMT' ? 'active' : ''} 
                onClick={() => setView('STAFF_MGMT')}
              >
                Staff Management
              </button>
            )}
            {capabilities.canManageClients && (
              <button 
                ref={view === 'CLIENT_MGMT' ? activeTabRef : null}
                className={view === 'CLIENT_MGMT' ? 'active' : ''} 
                onClick={() => setView('CLIENT_MGMT')}
              >
                Client Management
              </button>
            )}
          </nav>
        </div>
        <div className="header-right">
          {capabilities.canManageClients && (
            <button 
              className="button-primary" 
              style={{ padding: '8px 16px', fontSize: '0.85rem', borderRadius: '8px', marginRight: '12px' }}
              onClick={() => setNewVisitModal(true)}
            >
              + New Visit
            </button>
          )}
          <UserProfile 
            externalCurrentUser={currentUser} 
            staffProfile={staffList.find(s => s.cognito_sub === currentUser?.sub || (s.email && s.email.toLowerCase() === currentUser?.email?.toLowerCase()))}
            tenantInfo={tenantInfo}
          />
        </div>
      </header>

      {/* Render Google Calendar Health Banner if degraded/not connected */}
      {(tenantInfo ? tenantInfo.calendar_provider === 'google' : true) && googleStatus && googleStatus !== 'CONNECTED' && (
        <div className={`google-calendar-health-banner ${googleStatus}`} style={{
          padding: '12px 16px',
          borderRadius: '8px',
          marginBottom: '20px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          boxShadow: '0 2px 4px rgba(0,0,0,0.05)',
          fontSize: '0.9rem',
          fontWeight: '500',
          backgroundColor: googleStatus === 'VALIDATION_FAILED' ? '#fffbeb' : (googleStatus === 'CREDENTIALS_MISSING' ? '#fef2f2' : '#eff6ff'),
          color: googleStatus === 'VALIDATION_FAILED' ? '#b45309' : (googleStatus === 'CREDENTIALS_MISSING' ? '#b91c1c' : '#1d4ed8'),
          border: `1px solid ${googleStatus === 'VALIDATION_FAILED' ? '#fde68a' : (googleStatus === 'CREDENTIALS_MISSING' ? '#fecaca' : '#bfdbfe')}`
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span>
              {googleStatus === 'VALIDATION_FAILED' && '⚠️'}
              {googleStatus === 'CREDENTIALS_MISSING' && '❌'}
              {googleStatus === 'NOT_CONNECTED' && 'ℹ️'}
            </span>
            <span>
              {googleStatus === 'VALIDATION_FAILED' && 'Google Calendar connection needs reconnect. Sitter schedule sync is degraded.'}
              {googleStatus === 'CREDENTIALS_MISSING' && 'Google Client ID/Secret config is missing in Secrets Manager. Please contact support.'}
              {googleStatus === 'NOT_CONNECTED' && 'Google Calendar is not connected. Connect calendar to enable automatic sitter schedule sync.'}
            </span>
          </div>
          {googleStatus !== 'CREDENTIALS_MISSING' && capabilities.canManageGoogleCalendarIntegration && (
            <button 
              onClick={handleConnectGoogle}
              className="btn-small" 
              style={{
                backgroundColor: googleStatus === 'VALIDATION_FAILED' ? '#d97706' : '#2563eb',
                color: '#ffffff',
                border: 'none',
                padding: '6px 12px',
                borderRadius: '6px',
                cursor: 'pointer',
                fontWeight: '600',
                transition: 'background-color 0.2s'
              }}
              onMouseOver={(e) => e.target.style.backgroundColor = googleStatus === 'VALIDATION_FAILED' ? '#b45309' : '#1d4ed8'}
              onMouseOut={(e) => e.target.style.backgroundColor = googleStatus === 'VALIDATION_FAILED' ? '#d97706' : '#2563eb'}
            >
              {googleStatus === 'VALIDATION_FAILED' ? 'Reconnect Calendar' : 'Connect Calendar'}
            </button>
          )}
        </div>
      )}

      {renderStats()}

      <div className="admin-layout">

        <aside className="admin-sidebar card">
          <button
            className="mobile-filter-toggle"
            onClick={() => setMobileFilterOpen(prev => !prev)}
            aria-expanded={mobileFilterOpen}
            aria-controls="filter-panel-content"
          >
            {mobileFilterOpen ? 'Hide Filters' : 'Show Filters'}
            {!mobileFilterOpen && ((statusFilter !== 'PENDING_REVIEW' ? 1 : 0) + (timeframeFilter !== 'ALL' ? 1 : 0)) > 0 && (
              <span className="filter-badge">
                {(statusFilter !== 'PENDING_REVIEW' ? 1 : 0) + (timeframeFilter !== 'ALL' ? 1 : 0)}
              </span>
            )}
          </button>
          <div id="filter-panel-content" className={`filter-panel-content ${mobileFilterOpen ? 'filter-panel-open' : ''}`}>
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
            <div className="sidebar-workflows">
              <div className="filter-group">
                <h4 className="workflow-title">New Customer Intake</h4>
                {[
                  { id: 'INTAKE_QUEUE', label: 'Intake Queue' },
                  { id: 'MEET_GREET_REQUIRED', label: 'Needs Meet & Greet' },
                  { id: 'READY_FOR_APPROVAL', label: 'Ready to Approve' },
                ].map(f => (
                  <button 
                    key={f.id}
                    className={`filter-option ${statusFilter === f.id ? 'active' : ''}`}
                    onClick={() => setStatusFilter(f.id)}
                  >
                    {f.label} <span className="filter-count">({filterCounts[f.id] || 0})</span>
                  </button>
                ))}
              </div>

              <div className="filter-group">
                <h4 className="workflow-title">Visit Requests</h4>
                {[
                  { id: 'BOOKING_QUEUE', label: 'Booking Queue' },
                  { id: 'QUOTED', label: 'Price Quotes' },
                  { id: 'ASSIGNED', label: 'Scheduled with Staff' },
                  { id: 'COMPLETED', label: 'Visit Completed' },
                ].map(f => (
                  <button 
                    key={f.id}
                    className={`filter-option ${statusFilter === f.id ? 'active' : ''}`}
                    onClick={() => setStatusFilter(f.id)}
                  >
                    {f.label} <span className="filter-count">({filterCounts[f.id] || 0})</span>
                  </button>
                ))}
              </div>

              <div className="filter-group">
                <h4>System</h4>
                {[
                  { id: 'ALL', label: 'All Active' },
                  { id: 'NEEDS_ACTION', label: 'Needs Action' },
                  ...(capabilities.canViewRequestList ? [{ id: 'DATA_ISSUES', label: '⚠️ Data Issues' }] : [])
                ].map(f => (
                  <button 
                    key={f.id}
                    className={`filter-option ${statusFilter === f.id ? 'active' : ''}`}
                    onClick={() => setStatusFilter(f.id)}
                  >
                    {f.label} <span className="filter-count">({filterCounts[f.id] || 0})</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {view === 'LIST' && (
            <div className="filter-group">
              <h4>Closed / History</h4>
              {[
                { id: 'CANCELLED', label: 'Cancelled' },
                { id: 'ARCHIVED', label: 'Saved for Records' },
                { id: 'DELETED', label: 'Trash' }
              ].map(f => (
                <button 
                  key={f.id}
                  className={`filter-option ${statusFilter === f.id ? 'active' : ''}`}
                  onClick={() => setStatusFilter(f.id)}
                >
                  {f.label} <span className="filter-count" style={{ float: 'right', opacity: 0.7, fontSize: '11px', fontWeight: 'bold' }}>({filterCounts[f.id] || 0})</span>
                </button>
              ))}

            </div>
          )}

          {capabilities.canExportData && (
            <div className="filter-group">
              <h4>Data Management</h4>
              <button 
                className="filter-option"
                onClick={() => setExportModal(true)}
              >
                📥 Download Offline Backup
              </button>
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
            <h4 style={{ marginBottom: '16px' }}>System Integrations</h4>
            {(() => {
              const isGoogleCalendarSupported = tenantInfo ? tenantInfo.calendar_provider === 'google' : true;
              if (!isGoogleCalendarSupported) {
                return (
                  <div className="google-integration-card">
                    <div className="integration-header">
                      <div className="integration-title-area">
                        <h3>Calendar Integration</h3>
                        <p>Automated scheduling sync</p>
                      </div>
                      <span className="integration-status-badge status-disconnected">
                        NOT CONFIGURED
                      </span>
                    </div>

                    <div style={{ padding: '16px', borderTop: '1px solid var(--border-color, #e5e7eb)' }}>
                      <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-muted, #6b7280)', lineHeight: '1.4' }}>
                        Calendar integration is not configured for this business yet.
                      </p>
                      <p style={{ margin: '8px 0 0 0', fontSize: '0.85rem', color: 'var(--text-light, #9ca3af)', lineHeight: '1.4' }}>
                        Schedule sync can be enabled by the platform owner when this tenant is ready.
                      </p>
                    </div>
                  </div>
                );
              }

              const config = getGoogleStatusConfig(googleStatus);
              return (
                <div className="google-integration-card">
                  <div className="integration-header">
                    <div className="integration-title-area">
                      <h3>Google Calendar</h3>
                      <p>Automated scheduling sync</p>
                    </div>
                    <span className={`integration-status-badge ${config.class}`}>
                      {config.label}
                    </span>
                  </div>

                  <div className="integration-details-list">
                    <div className="detail-item">
                      <span className="detail-label">Connected Account</span>
                      <span className="detail-value">
                        {googleStatus === 'CONNECTED' ? 'Business Account' : 'None'}
                      </span>
                    </div>
                    <div className="detail-item">
                      <span className="detail-label">Last Checked</span>
                      <span className="detail-value">
                        {new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    </div>
                  </div>

                  <div className="integration-actions">
                    {googleStatus === 'CONNECTED' ? (
                      <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-muted, #6b7280)', lineHeight: '1.4', fontStyle: 'italic', textAlign: 'center', padding: '8px 0' }}>
                        Shared business calendar — individual calendar connections are not available yet.
                      </p>
                    ) : (
                      capabilities.canManageGoogleCalendarIntegration && (
                        <button onClick={handleConnectGoogle} className="btn-small primary" style={{ flex: 1 }}>Connect Calendar</button>
                      )
                    )}
                  </div>

                  <details className="technical-details">
                    <summary>Show technical details</summary>
                    <pre>
{JSON.stringify({
  status: googleStatus,
  provider: 'google-oauth2',
  scopes: ['calendar.events'],
  last_check: new Date().toISOString()
}, null, 2)}
                    </pre>
                  </details>
                </div>
              );
            })()}
          </div>
          </div>{/* end filter-panel-content */}
        </aside>

        <main className="admin-main">
          {view === 'SCHEDULER' ? (
            <MasterScheduler 
              items={visibleRecords} 
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
                <h2>Staff & Profile Management</h2>
                <button type="button" className="button-primary" onClick={(e) => handleNewStaff(e.currentTarget)}>
                  + Add New Staff
                </button>
              </div>

              <h2>Active Staff List</h2>
              <div className={`staff-grid${isStaffDrawerOpen ? ' drawer-open' : ''}`} style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '16px' }}>
                {staffList.map(s => {
                  const isSelected = s.staff_id === editingStaffId;
                  return (
                    <StaffProfileCard
                      key={s.staff_id}
                      staff={s}
                      isSelected={isSelected}
                      openStaffDetail={openStaffDetail}
                      isProtectedProfile={isProtectedProfile}
                      isSelf={isSelf}
                      getAccessStatus={getAccessStatus}
                    />
                  );
                })}

                {staffList.length === 0 && (
                  <p style={{ gridColumn: 'span 3', color: 'var(--text-secondary)', textAlign: 'center', padding: '24px' }}>No active staff profiles found.</p>
                )}
              </div>

              {/* Side Drawer Profile Editor Container */}
              {isStaffDrawerOpen && createPortal(
                <div className="profile-editor-drawer-overlay" onClick={(e) => e.stopPropagation()} onMouseDown={(e) => e.stopPropagation()}>
                  <div className="profile-editor-drawer" onClick={(e) => e.stopPropagation()} onMouseDown={(e) => e.stopPropagation()}>
                    <div className="drawer-header">
                      <h3>{editingStaffId ? (isStaffEditMode ? `Edit Staff: ${staffForm.display_name}` : `Staff Profile: ${selectedStaffForDrawer?.display_name}`) : 'Add New Staff Profile'}</h3>
                      <button type="button" ref={staffDrawerCloseBtnRef} className="drawer-close-button" onClick={closeStaffDrawer}>&times;</button>
                    </div>
                    
                    <div className="drawer-content">
                      {/* Section 5: Protected Account Guardrails Banner */}
                      {editingStaffId && selectedStaffForDrawer?.is_protected && (
                        <div className="drawer-guardrail-banner">
                          🛡️ <strong>Protected Platform Account</strong><br />
                          This account is protected to prevent accidental lockout or loss of platform support access.
                        </div>
                      )}

                      {!isStaffEditMode ? (
                        <>
                          {/* Read-Only Profile Details */}
                          <div className="drawer-section">
                            <h4 className="drawer-section-title">Profile Details</h4>
                            <dl className="client-detail-fields">
                              <dt>Display Name</dt>
                              <dd>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                  <span className="dot" style={{ backgroundColor: selectedStaffForDrawer?.assignment_color || 'var(--staff-unassigned)', width: '12px', height: '12px', borderRadius: '50%' }}></span>
                                  {selectedStaffForDrawer?.display_name}
                                </div>
                              </dd>
                              <dt>Role / Access</dt>
                              <dd>{selectedStaffForDrawer?.role || 'Staff'}</dd>
                              <dt>Assignable</dt>
                              <dd>{selectedStaffForDrawer?.is_assignable !== false ? 'Yes' : 'No'}</dd>
                              {selectedStaffForDrawer?.phone && (
                                <>
                                  <dt>Phone</dt>
                                  <dd>{selectedStaffForDrawer.phone}</dd>
                                </>
                              )}
                              {selectedStaffForDrawer?.notes && (
                                <>
                                  <dt>Notes</dt>
                                  <dd style={{ whiteSpace: 'pre-wrap' }}>{selectedStaffForDrawer.notes}</dd>
                                </>
                              )}
                            </dl>
                          </div>

                          {/* Login Identity */}
                          <div className="drawer-section">
                            <h4 className="drawer-section-title">Login Identity</h4>
                            <dl className="client-detail-fields">
                              <dt>Email Address</dt>
                              <dd>{selectedStaffForDrawer?.email || 'N/A'}</dd>
                              <dt>Cognito Username</dt>
                              <dd>{selectedStaffForDrawer?.cognito_username || selectedStaffForDrawer?.email || 'N/A'}</dd>
                              <dt>Access Status</dt>
                              <dd>
                                {(() => {
                                  const status = getAccessStatus(selectedStaffForDrawer);
                                  return <span className={`access-badge ${status.class}`}>{status.label}</span>
                                })()}
                              </dd>
                            </dl>
                            {selectedStaffForDrawer?.is_orphaned_identity && (
                              <div style={{
                                padding: '10px 12px',
                                backgroundColor: 'rgba(244, 67, 54, 0.08)',
                                border: '1px solid var(--danger, #f44336)',
                                borderRadius: '6px',
                                color: 'var(--danger, #f44336)',
                                fontSize: '13px',
                                fontWeight: '600',
                                display: 'flex',
                                alignItems: 'center',
                                gap: '6px',
                                marginTop: '12px'
                              }}>
                                ⚠️ This profile references a login that no longer exists.
                              </div>
                            )}
                          </div>

                          {/* Account Security */}
                          <div className="drawer-section">
                            <h4 className="drawer-section-title">Account Security</h4>
                            <p className="drawer-section-helper">Manage login setup and security credentials.</p>
                            {selectedStaffForDrawer?.cognito_sub ? (
                              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                                <button
                                  type="button"
                                  className="button-secondary btn-small"
                                  onClick={() => executeStaffAction(selectedStaffForDrawer.staff_id, 'resend-invite')}
                                  disabled={!['FORCE_CHANGE_PASSWORD', 'UNCONFIRMED'].includes(selectedStaffForDrawer.cognito_status) || selectedStaffForDrawer.is_orphaned_identity || selectedStaffForDrawer.is_protected}
                                  title={selectedStaffForDrawer.is_protected ? 'Protected accounts cannot be modified' : selectedStaffForDrawer.is_orphaned_identity ? 'This login is orphaned' : undefined}
                                >
                                  Resend Invite
                                </button>
                                <button
                                  type="button"
                                  className="button-secondary btn-small"
                                  onClick={() => executeStaffAction(selectedStaffForDrawer.staff_id, 'reset-password')}
                                  disabled={selectedStaffForDrawer.is_protected || isSelf(selectedStaffForDrawer) || selectedStaffForDrawer.is_orphaned_identity || selectedStaffForDrawer.cognito_status === 'FORCE_CHANGE_PASSWORD' || selectedStaffForDrawer.identity_state === 'linked_invited'}
                                  title={selectedStaffForDrawer.is_protected ? 'This account is protected and cannot be modified' : isSelf(selectedStaffForDrawer) ? 'You cannot modify your own account security settings' : selectedStaffForDrawer.is_orphaned_identity ? 'This login is orphaned' : selectedStaffForDrawer.cognito_status === 'FORCE_CHANGE_PASSWORD' || selectedStaffForDrawer.identity_state === 'linked_invited' ? ['FORCE_CHANGE_PASSWORD', 'UNCONFIRMED'].includes(selectedStaffForDrawer.cognito_status) ? 'This user has not completed their initial login. Use Resend Invite or Set Temporary Password instead.' : 'This user has not completed their initial login. Use Set Temporary Password instead.' : undefined}
                                >
                                  Send Password Reset Email
                                </button>
                                <button
                                  type="button"
                                  className="button-secondary btn-small"
                                  onClick={() => executeStaffAction(selectedStaffForDrawer.staff_id, 'set-temp-password')}
                                  disabled={selectedStaffForDrawer.is_protected || isSelf(selectedStaffForDrawer) || selectedStaffForDrawer.is_orphaned_identity}
                                  title={selectedStaffForDrawer.is_protected ? 'This account is protected and cannot be modified' : isSelf(selectedStaffForDrawer) ? 'You cannot modify your own account security settings' : selectedStaffForDrawer.is_orphaned_identity ? 'This login is orphaned' : undefined}
                                >
                                  Set Temporary Password
                                </button>
                              </div>
                            ) : (
                              <button
                                type="button"
                                className="button-secondary"
                                style={{ width: '100%' }}
                                onClick={() => {
                                  setConfirmAction({
                                    type: 'staff', id: selectedStaffForDrawer.staff_id, action: 'link-email', name: selectedStaffForDrawer.display_name || 'this staff member',
                                    message: `Link a login account to ${selectedStaffForDrawer.display_name || 'this staff member'}`,
                                    consequence: "Enter the existing email address to link as their login account.",
                                    variant: 'link-email'
                                  });
                                  setConfirmTypedInput('');
                                }}
                              >
                                Link Login Account
                              </button>
                            )}
                          </div>

                          {/* Platform Protection */}
                          {(canManageProtectedStatus() || selectedStaffForDrawer?.is_protected) && (
                            <div className="drawer-section">
                              <h4 className="drawer-section-title">Platform Protection</h4>
                              <p className="drawer-section-helper">Protected accounts cannot be deleted, disabled, or unlinked.</p>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginTop: '8px' }}>
                                {canManageProtectedStatus() ? (
                                  <label style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '8px',
                                    cursor: (selectedStaffForDrawer?.is_config_protected || ((selectedStaffForDrawer?.is_protected || selectedStaffForDrawer?.is_platform_protected) && isSelf(selectedStaffForDrawer))) ? 'not-allowed' : 'pointer',
                                    fontWeight: '500'
                                  }}>
                                    <input
                                      type="checkbox"
                                      id="is_platform_protected_toggle_view"
                                      checked={!!(selectedStaffForDrawer?.is_protected || selectedStaffForDrawer?.is_platform_protected)}
                                      disabled={selectedStaffForDrawer?.is_config_protected || ((selectedStaffForDrawer?.is_protected || selectedStaffForDrawer?.is_platform_protected) && isSelf(selectedStaffForDrawer))}
                                      onChange={(e) => {
                                        const nextVal = e.target.checked;
                                        executeStaffAction(selectedStaffForDrawer.staff_id, nextVal ? 'set-protected' : 'unset-protected');
                                      }}
                                    />
                                    Protected Platform Admin
                                  </label>
                                ) : (
                                  <span className="access-badge status-chip--protected" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                                    🔒 Protected Platform Admin
                                  </span>
                                )}
                                {selectedStaffForDrawer?.is_config_protected && (
                                  <span style={{ fontSize: '12px', color: 'var(--text-secondary)', fontStyle: 'italic' }}>
                                    (Locked by system config)
                                  </span>
                                )}
                                {!selectedStaffForDrawer?.is_config_protected && selectedStaffForDrawer?.is_protected && isSelf(selectedStaffForDrawer) && (
                                  <span style={{ fontSize: '12px', color: 'var(--text-secondary)', fontStyle: 'italic' }}>
                                    (Cannot unprotect self)
                                  </span>
                                )}
                              </div>
                            </div>
                          )}

                          {/* Danger Zone */}
                          <div className="drawer-section">
                            <div className="danger-zone-box" style={{ border: '1px solid var(--warning-color, #f44336)', padding: '12px', borderRadius: '8px' }}>
                              <h4 style={{ color: 'var(--warning-color, #f44336)', margin: '0 0 4px 0', fontSize: '0.9rem', fontWeight: 600 }}>Danger Zone</h4>
                              <p style={{ fontSize: '12px', margin: '0 0 12px 0', color: 'var(--text-secondary)' }}>These actions are destructive and cannot be undone.</p>
                              
                              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                                {selectedStaffForDrawer?.is_virtual ? (
                                  <>
                                    {selectedStaffForDrawer?.is_active !== false ? (
                                      <button
                                        type="button"
                                        className="button-danger btn-small"
                                        disabled={selectedStaffForDrawer.is_protected || isSelf(selectedStaffForDrawer)}
                                        title={selectedStaffForDrawer.is_protected ? 'This account is protected and cannot be modified' : isSelf(selectedStaffForDrawer) ? 'You cannot disable your own account' : undefined}
                                        onClick={() => executeStaffAction(selectedStaffForDrawer.staff_id, 'disable')}
                                      >
                                        Turn Off Login Access
                                      </button>
                                    ) : (
                                      <>
                                        <button
                                          type="button"
                                          className="button-primary btn-small"
                                          style={{ backgroundColor: 'var(--accent-teal)', color: 'white' }}
                                          onClick={() => executeStaffAction(selectedStaffForDrawer.staff_id, 'enable')}
                                        >
                                          Restore Login Access
                                        </button>
                                        <button
                                          type="button"
                                          className="button-danger btn-small"
                                          disabled={selectedStaffForDrawer.is_protected || isSelf(selectedStaffForDrawer)}
                                          title={selectedStaffForDrawer.is_protected ? 'This account is protected and cannot be modified' : isSelf(selectedStaffForDrawer) ? 'You cannot delete your own account' : undefined}
                                          onClick={() => executeStaffAction(selectedStaffForDrawer.staff_id, 'delete_cognito')}
                                        >
                                          Delete Login Account
                                        </button>
                                      </>
                                    )}
                                  </>
                                ) : (
                                  <>
                                    {selectedStaffForDrawer?.is_active !== false ? (
                                      <button
                                        type="button"
                                        className="button-danger btn-small"
                                        disabled={selectedStaffForDrawer.is_protected || isSelf(selectedStaffForDrawer)}
                                        title={selectedStaffForDrawer.is_protected ? 'This account is protected and cannot be modified' : isSelf(selectedStaffForDrawer) ? 'You cannot disable your own account' : undefined}
                                        onClick={() => executeStaffAction(selectedStaffForDrawer.staff_id, 'disable')}
                                      >
                                        Turn Off Login Access
                                      </button>
                                    ) : (
                                      <button
                                        type="button"
                                        className="button-primary btn-small"
                                        style={{ backgroundColor: 'var(--accent-teal)', color: 'white' }}
                                        onClick={() => executeStaffAction(selectedStaffForDrawer.staff_id, 'enable')}
                                      >
                                        Restore Login Access
                                      </button>
                                    )}
                                    {selectedStaffForDrawer?.cognito_sub && (
                                      <button
                                        type="button"
                                        className="button-danger btn-small"
                                        disabled={selectedStaffForDrawer.is_protected || isSelf(selectedStaffForDrawer) || selectedStaffForDrawer.is_orphaned_identity}
                                        title={selectedStaffForDrawer.is_protected ? 'This account is protected and cannot be modified' : isSelf(selectedStaffForDrawer) ? 'You cannot modify your own account' : selectedStaffForDrawer.is_orphaned_identity ? 'This login is orphaned' : undefined}
                                        onClick={() => executeStaffAction(selectedStaffForDrawer.staff_id, 'unlink')}
                                      >
                                        Unlink Login
                                      </button>
                                    )}
                                    {selectedStaffForDrawer?.is_active === false && (
                                      <button
                                        type="button"
                                        className="button-danger btn-small"
                                        disabled={selectedStaffForDrawer.is_protected || isSelf(selectedStaffForDrawer)}
                                        title={selectedStaffForDrawer.is_protected ? 'This account is protected and cannot be modified' : isSelf(selectedStaffForDrawer) ? 'You cannot delete your own account' : undefined}
                                        onClick={() => executeStaffAction(selectedStaffForDrawer.staff_id, 'delete_profile')}
                                      >
                                        Delete Profile
                                      </button>
                                    )}
                                  </>
                                )}
                              </div>
                            </div>
                          </div>
                        </>
                      ) : (
                        <>
                          {/* Section 1: Profile Details Form */}
                          <div className="drawer-section">
                            <h4 className="drawer-section-title">Profile Details</h4>
                            <p className="drawer-section-helper">Public-facing information and internal metadata.</p>
                            
                            <form id="staff-profile-form" onSubmit={handleSaveStaff}>
                              {!editingStaffId && (
                                <div className="field" style={{ display: 'flex', gap: '20px', marginBottom: '16px' }}>
                                  <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                                    <input 
                                      type="radio" 
                                      name="creation_mode" 
                                      value="onboard" 
                                      checked={staffForm.creation_mode === 'onboard'} 
                                      onChange={(e) => setStaffForm({ ...staffForm, creation_mode: e.target.value })}
                                    />
                                    Create Login & Profile
                                  </label>
                                  <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                                    <input 
                                      type="radio" 
                                      name="creation_mode" 
                                      value="profile_only" 
                                      checked={staffForm.creation_mode === 'profile_only'} 
                                      onChange={(e) => setStaffForm({ ...staffForm, creation_mode: e.target.value })}
                                    />
                                    Create Profile Only
                                  </label>
                                </div>
                              )}

                              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                                <div className="field">
                                  <label>Display Name *</label>
                                  <input 
                                    type="text" 
                                    value={staffForm.display_name} 
                                    onChange={(e) => setStaffForm({ ...staffForm, display_name: e.target.value })} 
                                    placeholder="e.g. Ryan"
                                    required 
                                    style={{ width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid var(--border-color)' }}
                                  />
                                </div>

                                {!editingStaffId && (
                                  <div className="field">
                                    <label>Email Address {staffForm.creation_mode === 'onboard' ? '*' : '(Optional)'}</label>
                                    <input 
                                      type="email" 
                                      value={staffForm.email} 
                                      onChange={(e) => setStaffForm({ ...staffForm, email: e.target.value })}
                                      required={staffForm.creation_mode === 'onboard'}
                                      placeholder={staffForm.creation_mode === 'onboard' ? "Required for login account" : "Optional for profile-only"}
                                      aria-label="Staff email address"
                                      style={{ width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid var(--border-color)' }}
                                    />
                                  </div>
                                )}

                                <div className="field">
                                  <label>Phone (Optional)</label>
                                  <input 
                                    type="text" 
                                    value={staffForm.phone} 
                                    onChange={(e) => setStaffForm({ ...staffForm, phone: e.target.value })} 
                                    placeholder="e.g. 555-0199"
                                    style={{ width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid var(--border-color)' }}
                                  />
                                </div>

                                <div className="field">
                                  <label>Role</label>
                                  <select 
                                    value={staffForm.role} 
                                    onChange={(e) => setStaffForm({ ...staffForm, role: e.target.value })}
                                    style={{ width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid var(--border-color)' }}
                                  >
                                    <option value="Staff">Staff</option>
                                    <option value="Admin">Admin</option>
                                    <option value="Owner">Owner</option>
                                  </select>
                                </div>

                                <div className="field" style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '6px' }}>
                                  <input 
                                    type="checkbox" 
                                    id="is_assignable" 
                                    checked={staffForm.is_assignable !== false} 
                                    onChange={(e) => setStaffForm({ ...staffForm, is_assignable: e.target.checked })}
                                  />
                                  <label htmlFor="is_assignable" style={{ cursor: 'pointer' }}>Assignable to Jobs</label>
                                </div>

                                {editingStaffId && canManageProtectedStatus() && (
                                  <div className="field" style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '6px' }}>
                                    <input
                                      type="checkbox"
                                      id="edit_is_platform_protected"
                                      checked={!!(selectedStaffForDrawer?.is_protected || selectedStaffForDrawer?.is_platform_protected)}
                                      disabled={selectedStaffForDrawer?.is_config_protected || ((selectedStaffForDrawer?.is_protected || selectedStaffForDrawer?.is_platform_protected) && isSelf(selectedStaffForDrawer))}
                                      onChange={(e) => {
                                        const nextVal = e.target.checked;
                                        executeStaffAction(selectedStaffForDrawer.staff_id, nextVal ? 'set-protected' : 'unset-protected');
                                      }}
                                    />
                                    <label htmlFor="edit_is_platform_protected" style={{ cursor: (selectedStaffForDrawer?.is_config_protected || (selectedStaffForDrawer?.is_protected && isSelf(selectedStaffForDrawer))) ? 'not-allowed' : 'pointer', fontWeight: '500' }}>
                                      Protected Platform Admin
                                      {selectedStaffForDrawer?.is_config_protected ? ' (Locked by system config)' : selectedStaffForDrawer?.is_protected && isSelf(selectedStaffForDrawer) ? ' (Cannot unprotect self)' : ''}
                                    </label>
                                  </div>
                                )}

                                <div className="field">
                                  <label>Sitter Color (For calendar visualization)</label>
                                  <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', marginTop: '8px' }}>
                                    {[
                                      { color: 'var(--staff-ryan, #4a90e2)', label: 'Ryan (Blue)' },
                                      { color: 'var(--staff-sarah, #e25a8e)', label: 'Sarah (Pink)' },
                                      { color: 'var(--staff-michael, #50e3c2)', label: 'Michael (Teal)' },
                                      { color: 'var(--staff-emily, #f5a623)', label: 'Emily (Orange)' },
                                      { color: '#b8e986', label: 'Lime' },
                                      { color: '#bd10e0', label: 'Purple' },
                                      { color: '#4a4a4a', label: 'Dark Grey' }
                                    ].map(col => (
                                      <button 
                                        key={col.color}
                                        type="button" 
                                        onClick={() => setStaffForm({ ...staffForm, assignment_color: col.color })}
                                        style={{ 
                                          backgroundColor: col.color, 
                                          width: '32px', 
                                          height: '32px', 
                                          borderRadius: '50%', 
                                          border: staffForm.assignment_color === col.color ? '3px solid var(--text-primary)' : '1px solid var(--border-color)',
                                          cursor: 'pointer',
                                          boxShadow: staffForm.assignment_color === col.color ? '0 0 4px rgba(0,0,0,0.5)' : 'none'
                                        }}
                                        title={col.label}
                                      />
                                    ))}
                                  </div>
                                </div>

                                <div className="field">
                                  <label>Internal Notes (Optional)</label>
                                  <textarea 
                                    value={staffForm.notes} 
                                    onChange={(e) => setStaffForm({ ...staffForm, notes: e.target.value })} 
                                    placeholder="Add any internal admin notes about this staff member..."
                                    style={{ width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid var(--border-color)', minHeight: '80px', fontFamily: 'inherit' }}
                                  />
                                </div>
                              </div>
                            </form>
                          </div>
                        </>
                      )}

                      <div className="drawer-section">
                        <h4 className="drawer-section-title">Audit History</h4>
                        <p style={{ fontSize: '13px', color: 'var(--text-muted)', fontStyle: 'italic', margin: '8px 0 0 0' }}>
                          Audit history will appear here in a future release.
                        </p>
                      </div>
                    </div>

                    {/* Footer */}
                    {!isStaffEditMode ? (
                      <div className="drawer-footer">
                        <button type="button" className="button-secondary" onClick={closeStaffDrawer}>
                          Close
                        </button>
                        <button type="button" className="button-primary" onClick={() => {
                          staffEditModeGuardRef.current = true;
                          setIsStaffEditMode(true);
                          setTimeout(() => { staffEditModeGuardRef.current = false; }, 300);
                        }}>
                          Edit Profile
                        </button>
                      </div>
                    ) : (
                      <div className="drawer-footer">
                        <button type="button" className="button-secondary" onClick={handleCancelEditStaff}>
                          Cancel
                        </button>
                        <button type="submit" form="staff-profile-form" className="button-primary" disabled={isSavingStaff}>
                          {isSavingStaff ? 'Saving...' : editingStaffId ? 'Save Changes' : 'Create Profile'}
                        </button>
                      </div>
                    )}
                  </div>
                </div>,
                document.body
              )}
            </div>
          ) : view === 'CLIENT_MGMT' && ['owner', 'admin'].includes(role) ? (
            renderClientManagement()
          ) : (

            <div className="list-view-container card">

              <div className="list-header-bar">
                <h2>Request List — {(() => {
                  const filter = [
                    { id: 'NEEDS_ACTION', label: 'Needs Action' },
                    { id: 'INTAKE_QUEUE', label: 'Intake Queue' },
                    { id: 'READY_FOR_APPROVAL', label: 'Ready for Approval' },
                    { id: 'MEET_GREET_REQUIRED', label: 'Needs Meet & Greet' },
                    { id: 'BOOKING_QUEUE', label: 'Booking Queue' },
                    { id: 'QUOTED', label: 'Price Quotes' },
                    { id: 'APPROVED', label: 'Approved' },
                    { id: 'ASSIGNED', label: 'Scheduled with Staff' },
                    { id: 'COMPLETED', label: 'Visit Completed' },
                    { id: 'CANCELLED', label: 'Cancelled' },
                    { id: 'ARCHIVED', label: 'Saved for Records' },
                    { id: 'DELETED', label: 'Trash' },
                    { id: 'DATA_ISSUES', label: 'Data Integrity Issues' },
                    { id: 'ALL', label: 'All Active' }
                  ].find(f => f.id === statusFilter);

                  return filter ? filter.label : 'Items';
                })()}</h2>
                <span className="micro-text">Showing records requiring action in the {statusFilter.replace(/_/g, ' ')} phase</span>
              </div>
              <div className="list-controls-bar">
                <div className="search-wrapper">
                  <input
                    type="text"
                    placeholder="Search client, pet, email, ID..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    style={{
                      padding: '10px 14px 10px 36px',
                      borderRadius: '8px',
                      border: '1px solid var(--border)',
                      backgroundColor: 'var(--bg-input, rgba(255, 255, 255, 0.05))',
                      color: 'var(--text-main)',
                      fontSize: '0.9rem'
                    }}
                  />
                  <span style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', opacity: 0.5 }}>🔍</span>
                  {searchQuery && (
                    <button 
                      onClick={() => setSearchQuery('')}
                      style={{
                        position: 'absolute',
                        right: '12px',
                        top: '50%',
                        transform: 'translateY(-50%)',
                        background: 'none',
                        border: 'none',
                        cursor: 'pointer',
                        fontSize: '1rem',
                        color: 'var(--text-muted)',
                        padding: '4px'
                      }}
                      title="Clear search"
                      aria-label="Clear search"
                    >
                      ✕
                    </button>
                  )}
                </div>
                <div className="payment-filter-wrapper">
                  <label style={{ fontSize: '0.85rem', fontWeight: 'bold', color: 'var(--text-secondary)' }}>Payment Status:</label>
                  <select
                    value={paymentStatusFilter}
                    onChange={(e) => setPaymentStatusFilter(e.target.value)}
                    className="staff-select"
                    style={{ padding: '8px 12px', borderRadius: '8px', border: '1px solid var(--border)', minWidth: '180px' }}
                  >
                    <option value="ALL">All Payment Statuses</option>
                    <option value="UNPAID">Unpaid / Not Set</option>
                    <option value="PAYMENT_LINK_SENT">Payment Link Sent</option>
                    <option value="PAID">Paid</option>
                    <option value="WAIVED">Waived</option>
                    <option value="REFUNDED">Refunded</option>
                  </select>
                </div>
                {((searchQuery !== '') || (paymentStatusFilter !== 'ALL')) && (
                  <button
                    onClick={() => {
                      setSearchQuery('');
                      setPaymentStatusFilter('ALL');
                    }}
                    className="button-secondary btn-small"
                    style={{ height: '38px', borderRadius: '8px' }}
                  >
                    Reset Filters
                  </button>
                )}
              </div>
              {selectedIds.length > 0 && (
                <div className="bulk-toolbar">
                  <div className="bulk-info">
                    <span className="count">{selectedIds.length}</span>
                    <span>visits selected</span>
                  </div>
                  <div className="bulk-actions">
                    {/* Bulk purge — only shown in Trash/Deleted view */}
                    {(statusFilter === 'DELETED' || statusFilter === 'TRASH') && (
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
                      <option value="">Choose action...</option>
                      {/* Context-aware bulk actions */}
                      {statusFilter === 'DATA_ISSUES' ? (
                        <>
                          <option value="DELETE">Move to Trash</option>
                        </>
                      ) : statusFilter === 'DELETED' || statusFilter === 'TRASH' ? (
                        <>
                          <option value="REOPEN_PENDING">Restore to Active</option>
                          <option value="RESTORE_APPROVED">Restore to Approved</option>
                          <option value="__PURGE__">Delete Permanently</option>
                        </>
                      ) : statusFilter === 'ARCHIVED' ? (
                        <>
                          <option value="REOPEN_PENDING">Restore to Active</option>
                          <option value="RESTORE_APPROVED">Restore to Approved</option>
                          <option value="DELETE">Move to Trash</option>
                        </>
                      ) : statusFilter === 'CANCELLED' ? (
                        <>
                          <option value="ARCHIVED">Archive</option>
                          <option value="REOPEN_PENDING">Restore to Active</option>
                          <option value="RESTORE_APPROVED">Restore to Approved</option>
                          <option value="DELETE">Move to Trash</option>
                        </>
                      ) : statusFilter === 'COMPLETED' ? (
                        <>
                          <option value="ARCHIVED">Archive</option>
                          <option value="DELETE">Move to Trash</option>
                        </>
                      ) : (
                        <>
                          {/* Active record transitions */}
                          <option value="PENDING_REVIEW">Set to Pending Review</option>
                          <option value="READY_FOR_APPROVAL">Set to New Request</option>
                          <option value="MEET_GREET_REQUIRED">Set to M&G Required</option>
                          <option value="VERIFY_MG">Mark M&G Completed</option>
                          <option value="QUOTED">Mark as Quoted</option>
                          <option value="APPROVED">Approve All</option>
                          <option value="ASSIGNED">Mark as Scheduled</option>
                          <option value="COMPLETED">Mark as Completed</option>
                          <option value="CANCELLED">Cancel Requests</option>
                          <option value="ARCHIVED">Archive</option>
                          <option value="DELETE">Move to Trash</option>
                        </>
                      )}
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
                        ref={el => {
                          if (el) {
                            const currentKeys = visibleRecords.map(r => getRecordKey(r));
                            const some = currentKeys.some(key => selectedIds.includes(key));
                            const all = currentKeys.length > 0 && currentKeys.every(key => selectedIds.includes(key));
                            el.indeterminate = some && !all;
                          }
                        }}
                        checked={visibleRecords.length > 0 && visibleRecords.map(r => getRecordKey(r)).every(key => selectedIds.includes(key))}
                        onChange={toggleSelectAll}
                        disabled={visibleRecords.length === 0}
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
                  {visibleRecords.map(item => {
                    const recordKey = getRecordKey(item);
                    const isExpanded = !!expandedRequestIds[recordKey];
                    return (
                      <React.Fragment key={recordKey}>
                        <tr className={`${selectedIds.includes(recordKey) ? 'selected-row' : ''} ${item.is_test_booking ? 'test-row' : ''}`} style={item.is_test_booking ? { borderLeft: '4px solid var(--info, #0284c7)', backgroundColor: 'var(--bg-test, #f0f9ff)' } : {}}>
                          <td data-label="Select">
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                              <input 
                                type="checkbox" 
                                checked={selectedIds.includes(recordKey)}
                                onChange={() => toggleSelectOne(recordKey)}
                                aria-label={`Select ${item.pet_names || item.client_name || 'this record'}`}
                              />
                              <button
                                type="button"
                                style={{
                                  background: 'none',
                                  border: 'none',
                                  cursor: 'pointer',
                                  fontSize: '0.85rem',
                                  color: 'var(--text-muted, #6c757d)',
                                  padding: '2px',
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  justifyContent: 'center',
                                  transition: 'transform 0.15s ease',
                                  transform: isExpanded ? 'rotate(90deg)' : 'rotate(0deg)'
                                }}
                                onClick={() => toggleRequestExpanded(recordKey)}
                                title={isExpanded ? "Collapse Details" : "Expand Details"}
                                aria-label={isExpanded ? `Collapse details for ${item.pet_names || item.client_name || 'this record'}` : `Expand details for ${item.pet_names || item.client_name || 'this record'}`}
                                aria-expanded={isExpanded}
                              >
                                ▶
                              </button>
                            </div>
                          </td>
                      <td data-label="Customer / Service" onClick={() => handleSelectPet(item)} className="clickable-cell">
                        <span className="mobile-only-label">Customer / Service: </span>
                        <div className="info-stack">
                          <span className="bold" style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                            {item.is_test_booking && (
                              <span className="status-chip" style={{ padding: '2px 6px', fontSize: '0.65rem', background: '#e0f2fe', color: '#0369a1', border: '1px solid #bae6fd', borderRadius: '4px', textTransform: 'uppercase', fontWeight: 'bold', whiteSpace: 'nowrap' }}>
                                Test Data
                              </span>
                            )}
                            {(() => {
                              const pets = item.pet_names || item.pet_name;
                              const client = item.client_name;
                              if (!pets && !client) return (
                                <span style={{ color: 'var(--error-color)', fontWeight: 'bold' }}>
                                  ⚠️ DATA ISSUE: Missing Names {item.request_id ? `(${item.request_id.slice(0,8)})` : ''}
                                </span>
                              );
                              if (!pets) return `(No Pet Names) — ${client}`;
                              if (!client) return `${pets} — (No Client Name)`;
                              return `${pets} (${client})`;
                            })()}
                          </span>
                          <span className="micro-text">{getServiceLabel(item.service_type)}</span>
                        </div>
                      </td>
                      <td data-label="Dates / Window">
                        <span className="mobile-only-label">Dates / Window: </span>
                        <div className="info-stack">
                          <span className="small" title={getFullVisitDatesList(item)}>
                            {formatVisitDates(item)}
                            {(item.is_multi_day || (item.selected_dates && item.selected_dates.length > 1) ||
                              (item.end_date && item.start_date && item.end_date !== item.start_date)) && (
                              <span style={{
                                fontSize: '0.65rem', fontWeight: 700,
                                background: 'var(--bg-muted)', color: 'var(--text-muted)',
                                padding: '2px 6px', borderRadius: '4px', marginLeft: '6px',
                                display: 'inline-block', verticalAlign: 'middle', border: '1px solid var(--border-soft)'
                              }}>
                                Multi-Day
                              </span>
                            )}
                          </span>
                          {/* Release 2: Display multi-select visit windows with backward compat */}
                          <span className="badge-window">
                            {(item.visit_windows || [item.visit_window || 'ANYTIME'])
                              .map(w => getVisitWindowLabel(w)).join(', ')}
                          </span>
                          {/* Release 2: Preferred sitter badge (informational) */}
                          {item.preferred_sitter_name && (
                            <span className="badge-preferred" style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontStyle: 'italic' }}>
                              Prefers: {item.preferred_sitter_name}
                            </span>
                          )}
                          {/* Release 8Z: per-visit completion badge */}
                          {(item.is_multi_day || (item.selected_dates && item.selected_dates.length > 1) || (item.total_occurrences && item.total_occurrences > 1)) && (
                            <span style={{
                              fontSize: '0.65rem',
                              fontWeight: 700,
                              background: (item.completed_count || 0) >= (item.selected_dates?.length || item.total_occurrences || 1) ? '#ecfdf5' : '#eff6ff',
                              color: (item.completed_count || 0) >= (item.selected_dates?.length || item.total_occurrences || 1) ? '#065f46' : '#1e40af',
                              padding: '2px 6px',
                              borderRadius: '4px',
                              marginTop: '4px',
                              display: 'inline-block',
                              width: 'fit-content',
                              border: (item.completed_count || 0) >= (item.selected_dates?.length || item.total_occurrences || 1) ? '1px solid #a7f3d0' : '1px solid #bfdbfe'
                            }}>
                              {item.completed_count || 0}/{(item.selected_dates?.length || item.total_occurrences || 1)} visits done
                            </span>
                          )}
                        </div>
                      </td>
                      <td data-label="Status" style={{ width: '180px' }}>
                        <span className="mobile-only-label">Status: </span>
                        {(() => {
                          const state = getWorkflowState(item);
                          return (
                            <div className="status-cell">
                              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                                <span className={`${state.statusClass} ${state.isInvalid ? 'status-chip--urgent' : ''}`}>
                                  {state.isInvalid ? "Needs Assignment" : getStatusLabel(item.status)}
                                </span>
                                {renderPaymentStatusChip(item)}
                                {item.status === 'COMPLETED' && item.visit_notes && (
                                  <span title="Completion Notes Available" style={{ fontSize: '1rem', cursor: 'help' }}>📝</span>
                                )}
                              </div>
                              {state.isInvalid && <div className="micro-text urgent-text">Missing worker assignment!</div>}
                              {/* Release 7B Phase 3: Admin Created badge */}
                              {item.source === 'admin_created' && (
                                <span className="status-chip status-chip--admin-created" style={{ fontSize: '9px', padding: '2px 8px', minWidth: 'auto', marginTop: '4px' }}>Admin Created</span>
                              )}
                            </div>
                          );
                        })()}
                      </td>
                      <td data-label="Staff">
                        <span className="mobile-only-label">Staff: </span>
                        {(() => {
                          const state = getWorkflowState(item);
                          const { primaryAction } = getGuidedActions(item);
                          const isAssignmentHandoff = primaryAction?.semantic === GUIDED_ACTION_SEMANTICS.ASSIGNMENT_HANDOFF;
                          if (isAssignmentHandoff || state.actions.includes("CHANGE_WORKER")) {
                            return (
                              <div className="assignment-wrapper">
                                {assigningId === item.PK ? (
                                  <select 
                                    autoFocus
                                    className="staff-select"
                                    onChange={(e) => handleAssignAction(item, e.target.value)}
                                    onBlur={() => setAssigningId(null)}
                                    disabled={staffLoading}
                                  >
                                    {staffLoading ? (
                                      <option>Loading staff...</option>
                                    ) : staffError ? (
                                      <option>Error loading staff</option>
                                    ) : staffList.length === 0 ? (
                                      <option>No staff users found</option>
                                    ) : (
                                      <>
                                        <option value="">Select Staff...</option>
                                        {staffList.filter(s => s.is_assignable !== false && s.is_active !== false).map(s => (
                                          <option key={s.email || s.display_name} value={s.email || s.display_name}>
                                            {s.display_name} {s.email ? `<${s.email}>` : ''}
                                          </option>
                                        ))}
                                      </>
                                    )}
                                  </select>
                                ) : (
                                  <button 
                                    onClick={() => openAssignmentHandoff(item)}
                                    className={`btn-small ${item.worker_id ? 'success' : 'primary-outline'}`}
                                    disabled={!resolveIds(item).jobId && String(item.status || '').toUpperCase() === 'APPROVED'}
                                  >
                                    {item.worker_id || (String(item.status || '').toUpperCase() === 'APPROVED' && !resolveIds(item).jobId ? 'Initializing...' : primaryAction?.label || 'Change Sitter')}
                                  </button>
                                )}
                              </div>
                            );
                          }
                          const resolvedName = staffList.find(s => (s.email || s.display_name) === item.worker_id)?.display_name || item.worker_id;
                          return resolvedName || '---';
                        })()}
                      </td>
                      <td data-label="Actions">
                        <div className="action-menu-container">
                          {(() => {
                            const { primaryAction } = getGuidedActions(item);
                            if (primaryAction?.semantic !== GUIDED_ACTION_SEMANTICS.CALENDAR_NAVIGATION) return null;
                            return (
                              <button
                                className="btn-small primary"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleGuidedWorkflowAction(item, primaryAction);
                                }}
                              >
                                {primaryAction.label}
                              </button>
                            );
                          })()}
                          <button 
                            className="button-secondary btn-small dropdown-trigger" 
                            onClick={(e) => {
                              e.stopPropagation();
                              setOpenMenuId(openMenuId === item.PK ? null : item.PK);
                            }}
                            aria-haspopup="true"
                            aria-expanded={openMenuId === item.PK}
                            aria-label={`Actions for ${item.pet_names || item.client_name || 'this record'}`}
                          >
                            Actions <span className="chevron">▾</span>
                          </button>
                          
                          {openMenuId === item.PK && (
                            <div className="action-dropdown-menu card shadow-lg">
                               {(() => {
                                 const state = getWorkflowState(item);
                                 const availableActions = state.actions.filter(a => !['EDIT_PET', 'ASSIGN', 'CHANGE_WORKER'].includes(a));
                                 
                                 if (availableActions.length === 0) {
                                   return <div className="dropdown-item empty">No actions available</div>;
                                 }

                                 return availableActions.map(action => {
                                   // PURGE_FOREVER: distinct logic
                                   if (action === 'PURGE_FOREVER') {
                                     return (
                                       <button
                                         key="PURGE_FOREVER"
                                         onClick={(e) => { e.stopPropagation(); setPurgeModal({ item }); setOpenMenuId(null); }}
                                         className="dropdown-item dangerous"
                                         title="Permanently delete this record — cannot be undone"
                                       >
                                         Delete Permanently
                                       </button>
                                     );
                                   }
                                   
                                   const labels = {
                                     'APPROVE': 'Approve', 'QUOTE': 'Quote', 'QUOTED': 'Mark Quoted',
                                     'CANCEL': 'Cancel Request', 'VERIFY_MG': 'Verify M&G',
                                     'REVERT_TO_APPROVED': 'Back to Approved', 'COMPLETE': 'Complete',
                                     'REOPEN': 'Reopen', 'REOPEN_PENDING': 'Restore to Active',
                                     'RESTORE_APPROVED': 'Restore to Approved',
                                     'ARCHIVE': 'Archive', 'CREATE_PROFILE': 'Create Profile',
                                     'MOVE_TO_NEW_REQUEST': 'To New Request', 'DELETE': 'Move to Trash',
                                     'UNARCHIVE': 'Unarchive', 'MARK_TEST': 'Mark as Test', 'UNMARK_TEST': 'Unmark Test',
                                     'PROCESS_CANCELLATION': 'Review Cancellation'
                                   };
                                   
                                   const isDangerous = ['DELETE', 'CANCEL'].includes(action);
                                   const workflowItem = { ...item, workflow_type: determineWorkflowType(item) };
                                   const guidedAction = describeGuidedWorkflowAction(workflowItem, action);
                                   
                                   return (
                                     <button 
                                       key={action}
                                       onClick={(e) => { 
                                         e.stopPropagation(); 
                                         setOpenMenuId(null);
                                         if (action === 'ARCHIVE') {
                                           setArchiveConfirmModal({ item });
                                         } else if (action === 'PROCESS_CANCELLATION') {
                                           handleProcessCancellation(item);
                                         } else if (guidedAction.semantic === GUIDED_ACTION_SEMANTICS.APPROVAL_SCHEDULER_HANDOFF) {
                                           handleGuidedWorkflowAction(item, guidedAction);
                                         } else {
                                           onReviewAction(item, action); 
                                         }
                                       }} 
                                       className={`dropdown-item ${isDangerous ? 'dangerous' : ''}`}
                                     >
                                       {guidedAction.label || labels[action] || action}
                                     </button>
                                   );
                                 });
                               })()}
                            </div>
                          )}
                        </div>
                      </td>
                    </tr>
                    {isExpanded && (
                      <tr className="expanded-row-details" style={{ backgroundColor: 'var(--bg-muted, #f8f9fa)' }}>
                        <td colSpan={6} style={{ padding: '16px 24px', borderTop: 'none' }}>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                            <div className="expanded-details-grid">
                              <div>
                                <strong style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Service Details:</strong>
                                <p style={{ margin: '4px 0 0 0' }}>{getServiceLabel(item.service_type)} for {item.pet_names || item.pet_name || 'Pet'}</p>
                              </div>
                              <div>
                                <strong style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Client Contact:</strong>
                                <p style={{ margin: '4px 0 0 0' }}>{item.client_name} ({item.client_email || 'No email'}) {item.client_phone || item.phone || ''}</p>
                              </div>
                            </div>
                            {item.status === 'COMPLETED' && (
                              <div style={{ borderTop: '1px solid var(--border-soft, #e9ecef)', paddingTop: '12px', marginTop: '4px' }}>
                                <strong style={{ fontSize: '0.85rem', color: 'var(--text-muted)', display: 'block', marginBottom: '8px' }}>Visit Completion Info:</strong>
                                <div style={{ display: 'flex', gap: '24px', marginBottom: '8px', fontSize: '0.9rem' }}>
                                  <span><strong>Completed By:</strong> {item.completed_by || 'Unknown'}</span>
                                  <span><strong>Completed At:</strong> {item.completed_at ? new Date(item.completed_at).toLocaleString('en-US', {
                                    month: 'short', day: 'numeric', year: 'numeric',
                                    hour: 'numeric', minute: '2-digit', hour12: true
                                  }) : 'N/A'}</span>
                                </div>
                                <div style={{ 
                                  whiteSpace: 'pre-wrap', 
                                  padding: '12px', 
                                  background: 'var(--bg-card, #ffffff)', 
                                  borderRadius: '6px', 
                                  border: '1px solid var(--border-soft, #e9ecef)',
                                  fontStyle: item.visit_notes ? 'normal' : 'italic',
                                  color: item.visit_notes ? 'var(--text-main, #212529)' : 'var(--text-muted, #6c757d)'
                                }}>
                                  {item.visit_notes || 'No completion notes provided'}
                                </div>
                              </div>
                            )}
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })}
                  {visibleRecords.length === 0 && !loading && (
                    <tr>
                      <td colSpan={6} style={{ textAlign: 'center', padding: '48px 24px', color: 'var(--text-muted)' }}>
                        <p style={{ fontSize: '1.1rem', fontWeight: 600, margin: 0 }}>
                          {(searchQuery || paymentStatusFilter !== 'ALL') 
                            ? 'No requests match the current filters.' 
                            : 'No records in this view'}
                        </p>
                        <p style={{ fontSize: '0.85rem', marginTop: '8px', margin: '8px 0 0' }}>
                          {(searchQuery || paymentStatusFilter !== 'ALL') ? (
                            <>
                              Try adjusting your search query or payment status filter, or{' '}
                              <button 
                                onClick={() => { setSearchQuery(''); setPaymentStatusFilter('ALL'); }}
                                style={{ background: 'none', border: 'none', color: 'var(--accent-color, #2563eb)', textDecoration: 'underline', cursor: 'pointer', padding: 0, font: 'inherit' }}
                              >
                                clear filters
                              </button> to see all requests.
                            </>
                          ) : (
                            statusFilter === 'DATA_ISSUES' ? 'No data integrity issues found. ✓' :
                            statusFilter === 'DELETED' || statusFilter === 'TRASH' ? 'Trash is empty.' :
                            statusFilter === 'COMPLETED' ? 'No completed visits yet.' :
                            statusFilter === 'CANCELLED' ? 'No cancelled records.' :
                            statusFilter === 'ARCHIVED' ? 'No archived records.' :
                            'No records match the current filter.'
                          )}
                        </p>
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>

              <div className="pagination-footer">
                <span className="small text-muted">Showing {visibleRecords.length} records</span>
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
            <button
              className="modal-close-btn"
              onClick={() => { setDecisionModal(null); setModalError(null); setWorkflowDropdownOpen(false); }}
              aria-label="Close dialog"
            >
              ✕
            </button>
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

            <div className="modal-footer" style={{ justifyContent: 'space-between' }}>
              <button 
                onClick={() => { setDecisionModal(null); setModalError(null); setWorkflowDropdownOpen(false); }} 
                className="btn-secondary"
              >
                Close
              </button>
              
              {decisionModal.type === 'APPROVE' ? (
                <button onClick={submitDecision} className="btn-small success">Approve & Notify</button>
              ) : decisionModal.type === 'DECLINE' ? (
                <button onClick={submitDecision} className="btn-small danger">Decline & Notify</button>
              ) : decisionModal.type === 'WORKFLOW_REVIEW' ? (
                <div className="workflow-guided-actions" style={{ display: 'flex', gap: '12px', alignItems: 'center', position: 'relative' }}>
                  {(() => {
                    const { primaryAction, secondary } = getGuidedActions(decisionModal.item);
                    const labels = {
                      'APPROVE': 'Approve', 'QUOTE': 'Quote Needed', 'QUOTED': 'Mark Quoted',
                      'CANCEL': 'Cancel Request', 'VERIFY_MG': 'Mark M&G Complete',
                      'REVERT_TO_APPROVED': 'Back to Approved', 'COMPLETE': 'Complete',
                      'REOPEN': 'Reopen', 'REOPEN_PENDING': 'Restore to Active',
                      'RESTORE_APPROVED': 'Restore to Approved',
                      'ARCHIVE': 'Archive', 'CREATE_PROFILE': 'Create Profile',
                      'MOVE_TO_NEW_REQUEST': 'To New Request', 'DELETE': 'Move to Trash',
                      'MEET_GREET': 'Require Meet & Greet', 'MG_SCHEDULED': 'M&G Scheduled',
                      'ASSIGN': 'Assign Sitter', 'VIEW_CALENDAR': 'View in Calendar'
                    };

                    const getButtonClass = (act) => {
                      if (act === 'DELETE' || act === 'CANCEL') return 'btn-small danger';
                      if (['APPROVE', 'VERIFY_MG', 'QUOTED'].includes(act)) return 'btn-small success';
                      if (['QUOTE', 'MEET_GREET', 'MG_SCHEDULED'].includes(act)) return 'btn-small highlight';
                      return 'btn-small primary';
                    };

                    return (
                      <>
                        {secondary.length > 0 && (
                          <div className="secondary-actions-wrapper" style={{ position: 'relative' }}>
                            <button 
                              className="btn-secondary btn-small"
                              onClick={() => setWorkflowDropdownOpen(!workflowDropdownOpen)}
                              aria-haspopup="true"
                              aria-expanded={workflowDropdownOpen}
                            >
                              More Actions ▾
                            </button>
                            {workflowDropdownOpen && (
                              <div className="action-dropdown-menu card shadow-lg" style={{ bottom: '100%', top: 'auto', marginBottom: '8px' }}>
                                {secondary.map(guidedAction => (
                                  <button
                                    key={guidedAction.id}
                                    className={`dropdown-item ${['DELETE', 'CANCEL'].includes(guidedAction.id) ? 'dangerous' : ''}`}
                                    onClick={() => {
                                      if (guidedAction.semantic === GUIDED_ACTION_SEMANTICS.APPROVAL_SCHEDULER_HANDOFF) {
                                        handleGuidedWorkflowAction(decisionModal.item, guidedAction, adminNote);
                                      } else {
                                        onReviewAction(decisionModal.item, guidedAction.id, adminNote);
                                        setDecisionModal(null);
                                        setWorkflowDropdownOpen(false);
                                      }
                                    }}
                                  >
                                    {guidedAction.label || labels[guidedAction.id] || guidedAction.id}
                                  </button>
                                ))}
                              </div>
                            )}
                          </div>
                        )}
                        
                        {primaryAction && (
                          <button 
                            key={primaryAction.id}
                            onClick={() => {
                              handleGuidedWorkflowAction(decisionModal.item, primaryAction, adminNote);
                            }} 
                            className={getButtonClass(primaryAction.id)}
                            disabled={loading}
                          >
                            {primaryAction.label || labels[primaryAction.id] || primaryAction.id}
                          </button>
                        )}
                      </>
                    );
                  })()}
                </div>
              ) : null}
            </div>
          </div>
        </div>
      )}

      {archiveConfirmModal && (
        <div className="modal-overlay">
          <div className="modal-content" style={{ maxWidth: '500px' }}>
            <button
              className="modal-close-btn"
              onClick={() => { setArchiveConfirmModal(null); setArchiveReasonText(''); }}
              aria-label="Close dialog"
            >
              ✕
            </button>
            <div className="modal-header">
               <h2>Archive Booking</h2>
               <p className="text-muted">
                 Confirm archiving for: <strong>{archiveConfirmModal.item.pet_names || archiveConfirmModal.item.pet_name || 'Pet'} ({archiveConfirmModal.item.client_name})</strong>
               </p>
            </div>

            <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginTop: '16px' }}>
              <div style={{ background: 'var(--bg-muted, #f8f9fa)', padding: '12px 16px', borderRadius: '6px', fontSize: '0.85rem' }}>
                <p style={{ margin: '0 0 8px 0' }}><strong>Parent Request ID:</strong> {archiveConfirmModal.item.request_id || archiveConfirmModal.item.PK?.replace('REQ#', '')}</p>
                {(() => {
                  const summary = archiveConfirmModal.item.job_completion_summary;
                  if (summary) {
                    const jobs = summary.jobs || [];
                    const completedJobsCount = jobs.filter(j => j.status === 'COMPLETED').length;
                    return (
                      <>
                        <p style={{ margin: '0 0 8px 0' }}><strong>Total Visits:</strong> {summary.total || jobs.length}</p>
                        <p style={{ margin: '0 0 8px 0' }}><strong>Completed Visits:</strong> {completedJobsCount}</p>
                        {completedJobsCount > 0 && (
                          <div style={{ color: 'var(--warning, #f59e0b)', fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: '6px', marginTop: '8px' }}>
                            ⚠️ Warning: This booking has completed visits. Archiving preserves completed visits/sitter notes but soft-archives active child visits.
                          </div>
                        )}
                      </>
                    );
                  }
                  return <p style={{ margin: 0 }}>No child visits associated with this request.</p>;
                })()}
              </div>

              <div className="field">
                <label style={{ fontWeight: 'bold' }}>Archive Reason (Required)</label>
                <input 
                  type="text" 
                  placeholder="e.g. Validation complete, Customer cancelled, Duplicate..."
                  value={archiveReasonText}
                  onChange={(e) => setArchiveReasonText(e.target.value)}
                  className="form-control"
                  style={{ width: '100%', padding: '8px 12px', marginTop: '6px', borderRadius: '4px', border: '1px solid var(--border-soft, #e9ecef)' }}
                />
              </div>
            </div>

            <div className="modal-footer" style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: '24px' }}>
              <button 
                onClick={() => { setArchiveConfirmModal(null); setArchiveReasonText(''); }} 
                className="btn-secondary btn-small"
              >
                Cancel
              </button>
              <button 
                onClick={() => {
                  if (!archiveReasonText.trim()) {
                    alert('Please enter a reason for archiving.');
                    return;
                  }
                  onReviewAction(archiveConfirmModal.item, 'ARCHIVE', '', { archive_reason: archiveReasonText });
                  setArchiveConfirmModal(null);
                  setArchiveReasonText('');
                }} 
                className="btn-small dangerous"
                disabled={!archiveReasonText.trim()}
              >
                Confirm Archive
              </button>
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
          staffList={staffList}
          onPaymentSessionCreated={async (updatedOriginItem) => {
            if (updatedOriginItem) {
              try {
                await fetchAllData();
                await handleSelectPet(updatedOriginItem);
              } catch(e) {
                console.error("Failed to refresh request details:", e);
              }
            }
          }}
          onAssign={async (originItem, workerId) => {
            // Release 4E: Inline staff assignment from CareCard
            await handleAssignAction(originItem, workerId);
            // Refresh CareCard with updated worker data.
            // handleAssignAction already called fetchAllData() which refreshes the list/scheduler.
            // Now reload the CareCard with the updated origin item.
            if (originItem) {
              try {
                const staff = staffList.find(s => (s.email || s.display_name) === workerId);
                const updatedOrigin = {...originItem, worker_id: workerId, worker_name: staff?.display_name || workerId, status: 'ASSIGNED'};
                await handleSelectPet(updatedOrigin);
              } catch(e) { /* CareCard refresh failed — list is still updated */ }
            }
          }}
          onAddPet={async (clientId, petData) => {
            // Release 5B Hotfix 3: Create new pet and persistently link to parent request.
            // Pass request_id so backend appends to pet_ids array on the REQ record.
            try {
              const originItem = selectedPet?._originItem;
              const { reqId } = resolveIds(originItem || {});
              const result = await createPet({ ...petData, client_id: clientId, request_id: reqId || undefined });
              showNotification("Pet created successfully!", "success");
              
              // Fetch all pets for this client to get the complete list including the new one
              const allPetIds = [...(originItem?.pet_ids || [])];
              const newPetId = result?.pet_id;
              if (newPetId && !allPetIds.includes(newPetId)) {
                allPetIds.push(newPetId);
              }
              
              // Re-fetch all PET# records using the updated ID list
              if (allPetIds.length > 0) {
                const petPromises = allPetIds.map((pid, idx) =>
                  getPet(pid, clientId).catch(() => ({ pet_id: pid, name: "Deleted/Unavailable pet record", _fetchFailed: true }))
                );
                const petResults = await Promise.all(petPromises);
                const loadedPets = petResults.filter(p => p !== null);
                
                setSelectedPet(prev => {
                  if (!prev) return null;
                  return {
                    ...prev,
                    _allPets: loadedPets,
                    _originItem: { ...(prev._originItem || {}), pet_ids: allPetIds },
                    _newPetIndex: loadedPets.length - 1
                  };
                });
              }
              // Also refresh the main request list so pet_names display updates
              fetchAllData();
            } catch (err) {
              showNotification("Failed to create pet: " + err.message, "error");
              throw err;
            }
          }}
        />

      )}

      {bulkConfirmModal && (
        <div className="modal-overlay">
          <div className="modal-content bulk-confirm-modal">
            <button
              className="modal-close-btn"
              onClick={() => { setBulkConfirmModal(null); setPurgeAnalysis(null); }}
              aria-label="Close dialog"
            >
              ✕
            </button>
            <div className="modal-header">
              <h2>Confirm Bulk Update</h2>
              <p>You are about to update <strong>{bulkConfirmModal.count}</strong> selected records.</p>
            </div>
            
            <div className="bulk-confirm-details">
              {bulkConfirmModal.target === '__PURGE__' ? (
                <>
                  <p className="purge-warning-text">You are about to <strong>permanently delete {bulkConfirmModal.count} record(s)</strong> from the Trash.</p>
                  
                  {purgeAnalysis ? (
                    <div className="purge-analysis-summary">
                      <div className="analysis-item success">
                        <span>Purgeable:</span> <strong>{purgeAnalysis.success}</strong>
                      </div>
                      <div className="analysis-item warning">
                        <span>Blocked/Skipped:</span> <strong>{purgeAnalysis.skipped}</strong>
                      </div>
                      <div className="analysis-item error">
                        <span>Failed to Resolve:</span> <strong>{purgeAnalysis.failed}</strong>
                      </div>
                      
                      {purgeAnalysis.failures?.length > 0 && (
                        <div className="analysis-reasons">
                          <p>Reasons for blocked records:</p>
                          <ul>
                            {purgeAnalysis.failures.slice(0, 3).map((f, i) => (
                              <li key={i}>{f.reason}</li>
                            ))}
                            {purgeAnalysis.failures.length > 3 && <li>... and {purgeAnalysis.failures.length - 3} more</li>}
                          </ul>
                        </div>
                      )}
                      
                      {purgeAnalysis.success > 0 ? (
                        <p className="final-confirmation-text">Only the {purgeAnalysis.success} purgeable records will be removed.</p>
                      ) : (
                        <p className="final-confirmation-text error">None of the selected records are eligible for permanent deletion.</p>
                      )}
                    </div>
                  ) : (
                    <div className="safety-notice">
                      <p>● Only records currently in DELETED / Trash status will be purged.</p>
                      <p>● <strong>This cannot be undone.</strong> Records will be removed from the database entirely.</p>
                      <p>● Clicking 'Analyze Selection' will verify record eligibility before deletion.</p>
                    </div>
                  )}
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
                onClick={() => { setBulkConfirmModal(null); setPurgeAnalysis(null); }}
                disabled={isBulkUpdating || isBulkPurging}
              >
                Cancel
              </button>
              {bulkConfirmModal.target === '__PURGE__' ? (
                <button
                  className={`btn-small purge ${!purgeAnalysis ? 'button-secondary' : ''}`}
                  onClick={() => handleBulkPurge(!!purgeAnalysis)}
                  disabled={isBulkPurging || (purgeAnalysis && purgeAnalysis.success === 0)}
                >
                  {isBulkPurging ? (purgeAnalysis ? 'Purging...' : 'Analyzing...') : (purgeAnalysis ? 'Confirm & Purge Permanently' : 'Analyze Selection')}
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
              <button
                className="modal-close-btn"
                onClick={() => { setPurgeModal(null); setPurgeConfirmText(''); }}
                aria-label="Close dialog"
              >
                ✕
              </button>
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

      {/* Staff/Client Action Confirmation Modal */}
      {confirmAction && (
        <div className="modal-overlay">
          <div className="modal-content" style={{ maxWidth: '480px' }}>
            <button
              className="modal-close-btn"
              onClick={() => { setConfirmAction(null); setConfirmTypedInput(''); }}
              aria-label="Close dialog"
            >
              ✕
            </button>
            <div className="modal-header">
              <h2>{confirmAction.message}</h2>
              <p style={{ color: 'var(--text-secondary)', marginTop: '8px', lineHeight: '1.5' }}>
                {confirmAction.consequence}
              </p>
            </div>

            {/* Typed input for delete-typed, temp-password, and link-email variants */}
            {(confirmAction.variant === 'delete-typed' || confirmAction.variant === 'temp-password' || confirmAction.variant === 'link-email') && (
              <div className="field" style={{ margin: '16px 0 0 0' }}>
                <label style={{ fontWeight: 700, fontSize: '0.85rem' }}>
                  {confirmAction.variant === 'delete-typed' && "Type 'DELETE LOGIN ACCOUNT' to confirm:"}
                  {confirmAction.variant === 'temp-password' && "Temporary password:"}
                  {confirmAction.variant === 'link-email' && "Email address:"}
                </label>
                <input
                  type={confirmAction.variant === 'temp-password' ? 'text' : confirmAction.variant === 'link-email' ? 'email' : 'text'}
                  value={confirmTypedInput}
                  onChange={(e) => setConfirmTypedInput(e.target.value)}
                  placeholder={
                    confirmAction.variant === 'delete-typed' ? 'DELETE LOGIN ACCOUNT' :
                    confirmAction.variant === 'temp-password' ? 'Enter temporary password' :
                    'e.g. user@example.com'
                  }
                  autoFocus
                  style={{ marginTop: '8px', width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid var(--border)' }}
                />
              </div>
            )}

            <div className="modal-footer" style={{ marginTop: '20px' }}>
              <button
                className="btn-secondary"
                onClick={() => { setConfirmAction(null); setConfirmTypedInput(''); }}
              >
                Cancel
              </button>

              {/* Disable-choice variant: two action buttons */}
              {confirmAction.variant === 'disable-choice' ? (
                <>
                  <button
                    className="button-secondary"
                    onClick={() => handleDisableStaffWithCognito(false)}
                  >
                    Profile Only
                  </button>
                  <button
                    className="button-primary"
                    style={{ backgroundColor: 'var(--error, #d32f2f)', borderColor: 'var(--error, #d32f2f)' }}
                    onClick={() => handleDisableStaffWithCognito(true)}
                  >
                    Turn Off Both
                  </button>
                </>
              ) : confirmAction.variant === 'delete-typed' ? (
                <button
                  className="button-primary"
                  style={{ backgroundColor: 'var(--error, #d32f2f)', borderColor: 'var(--error, #d32f2f)' }}
                  onClick={executeConfirmAction}
                  disabled={confirmTypedInput !== 'DELETE LOGIN ACCOUNT'}
                >
                  Confirm Delete
                </button>
              ) : confirmAction.variant === 'temp-password' ? (
                <button
                  className="button-primary"
                  onClick={executeConfirmAction}
                  disabled={!confirmTypedInput.trim()}
                >
                  Set Password
                </button>
              ) : confirmAction.variant === 'link-email' ? (
                <button
                  className="button-primary"
                  onClick={executeConfirmAction}
                  disabled={!confirmTypedInput.trim()}
                >
                  Link Account
                </button>
              ) : (
                <button
                  className="button-primary"
                  style={
                    ['disable', 'delete_profile', 'delete_cognito', 'disable_profile_only'].includes(confirmAction.action)
                      ? { backgroundColor: 'var(--error, #d32f2f)', borderColor: 'var(--error, #d32f2f)' }
                      : {}
                  }
                  onClick={executeConfirmAction}
                >
                  Confirm
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Export Confirmation Modal */}
      {exportModal && (
        <div className="modal-overlay">
          <div className="modal-content card" style={{ maxWidth: '450px' }}>
            <div className="modal-header">
              <h2 className="modal-title">Download Offline Backup</h2>
              <button className="btn-close" onClick={() => setExportModal(false)}>×</button>
            </div>
            <div className="modal-body">
              <p style={{ color: 'var(--text-secondary)', marginBottom: '15px' }}>
                You are about to download a complete offline backup of all operational records, including:
              </p>
              <ul style={{ paddingLeft: '20px', marginBottom: '15px', color: 'var(--text-secondary)' }}>
                <li>All Client contact information</li>
                <li>All Pet care records</li>
                <li>All Service requests and schedules</li>
                <li>Staff assignment history</li>
              </ul>
              <div className="alert alert-warning" style={{ 
                backgroundColor: 'rgba(255, 152, 0, 0.1)', 
                border: '1px solid rgba(255, 152, 0, 0.3)',
                padding: '12px',
                borderRadius: '8px',
                display: 'flex',
                gap: '10px'
              }}>
                <span style={{ fontSize: '20px' }}>⚠️</span>
                <p style={{ margin: 0, fontSize: '13px', lineHeight: '1.4' }}>
                  <strong>Security Reminder:</strong> This file contains sensitive private information. 
                  Ensure it is stored securely and handled in compliance with privacy guidelines.
                </p>
              </div>
            </div>
            <div className="modal-footer" style={{ marginTop: '20px' }}>
              <button className="btn-secondary" onClick={() => setExportModal(false)}>Cancel</button>
              <button 
                className="button-primary" 
                onClick={handleExportData}
                disabled={loading}
              >
                {loading ? 'Preparing Backup...' : 'Confirm & Download'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Release 6F: New Visit Modal */}
      {newVisitModal && (
        <div className="modal-overlay">
          <div className="modal-content card" style={{ maxWidth: '550px', maxHeight: '85vh', overflow: 'auto' }}>
            <div className="modal-header">
              <h2 className="modal-title">Create Visit for Client</h2>
              <button className="btn-close" onClick={handleCloseNewVisitModal}>×</button>
            </div>
            <div className="modal-body" style={{ padding: '24px' }}>
              {/* Client Selector */}
              <div className="field" style={{ marginBottom: '16px' }}>
                <label>Client *</label>
                <select
                  value={newVisitForm.client_id}
                  onChange={(e) => handleNewVisitClientSelect(e.target.value)}
                  style={{ width: '100%', padding: '10px', borderRadius: '8px', border: '1px solid var(--border-soft)' }}
                >
                  <option value="">— Select a client —</option>
                  {clientList.filter(c => c.is_active !== false).map(c => (
                    <option key={c.client_id} value={c.client_id}>
                      {c.display_name || 'Unnamed'} ({c.email || 'no email'})
                    </option>
                  ))}
                </select>
              </div>

              {/* Pet Selector */}
              {newVisitForm.client_id && (
                <div className="field" style={{ marginBottom: '16px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                    <label style={{ margin: 0 }}>Pet(s) *</label>
                    {!isAddingPetInline && (
                      <button 
                        type="button" 
                        onClick={() => setIsAddingPetInline(true)}
                        style={{ background: 'none', border: 'none', color: 'var(--primary)', cursor: 'pointer', fontSize: '0.85rem', fontWeight: 600, padding: 0 }}
                      >
                        + Add Pet Inline
                      </button>
                    )}
                  </div>

                  {isAddingPetInline ? (
                    <div style={{ 
                      marginTop: '8px', 
                      padding: '14px', 
                      borderRadius: '8px', 
                      border: '1px solid rgba(76, 175, 80, 0.2)', 
                      backgroundColor: 'rgba(76, 175, 80, 0.03)',
                      boxShadow: 'inset 0 1px 2px rgba(0,0,0,0.02)'
                    }}>
                      <h4 style={{ margin: '0 0 10px 0', fontSize: '0.85rem', color: 'var(--text-primary)' }}>Create Pet Inline</h4>
                      
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                        <div className="field-compact" style={{ display: 'flex', flexDirection: 'column' }}>
                          <label style={{ fontSize: '0.75rem', marginBottom: '4px' }}>Name *</label>
                          <input 
                            type="text" 
                            placeholder="e.g. Luna"
                            value={inlinePetForm.name} 
                            onChange={e => setInlinePetForm({ ...inlinePetForm, name: e.target.value })}
                            style={{ width: '100%', padding: '6px 10px', fontSize: '0.85rem', borderRadius: '6px', border: '1px solid var(--border-soft)' }} 
                          />
                        </div>
                        
                        <div className="field-compact" style={{ display: 'flex', flexDirection: 'column' }}>
                          <label style={{ fontSize: '0.75rem', marginBottom: '4px' }}>Species</label>
                          <select 
                            value={inlinePetForm.species} 
                            onChange={e => setInlinePetForm({ ...inlinePetForm, species: e.target.value })}
                            style={{ width: '100%', padding: '6px 10px', fontSize: '0.85rem', borderRadius: '6px', border: '1px solid var(--border-soft)', height: '31px' }}
                          >
                            <option value="DOG">Dog</option>
                            <option value="CAT">Cat</option>
                            <option value="OTHER">Other</option>
                          </select>
                        </div>
                        
                        <div className="field-compact" style={{ display: 'flex', flexDirection: 'column' }}>
                          <label style={{ fontSize: '0.75rem', marginBottom: '4px' }}>Breed</label>
                          <input 
                            type="text" 
                            placeholder="e.g. Poodle"
                            value={inlinePetForm.breed} 
                            onChange={e => setInlinePetForm({ ...inlinePetForm, breed: e.target.value })}
                            style={{ width: '100%', padding: '6px 10px', fontSize: '0.85rem', borderRadius: '6px', border: '1px solid var(--border-soft)' }} 
                          />
                        </div>
                        
                        <div className="field-compact" style={{ display: 'flex', flexDirection: 'column' }}>
                          <label style={{ fontSize: '0.75rem', marginBottom: '4px' }}>Age (Years)</label>
                          <input 
                            type="number" 
                            min="0" 
                            max="30"
                            placeholder="e.g. 3"
                            value={inlinePetForm.age} 
                            onChange={e => {
                              const val = e.target.value;
                              if (val === '' || (parseInt(val) >= 0 && parseInt(val) <= 30)) {
                                setInlinePetForm({ ...inlinePetForm, age: val });
                              }
                            }}
                            style={{ width: '100%', padding: '6px 10px', fontSize: '0.85rem', borderRadius: '6px', border: '1px solid var(--border-soft)' }} 
                          />
                        </div>
                      </div>

                      <div style={{ display: 'flex', gap: '8px', marginTop: '12px', justifyContent: 'flex-end' }}>
                        <button 
                          type="button" 
                          className="btn-secondary"
                          onClick={() => setIsAddingPetInline(false)}
                          style={{ padding: '4px 10px', fontSize: '0.8rem', cursor: 'pointer', border: '1px solid var(--border-soft)', borderRadius: '4px', background: 'none' }}
                          disabled={isSavingPetInline}
                        >
                          Cancel
                        </button>
                        <button 
                          type="button" 
                          className="button-primary"
                          onClick={handleInlinePetSubmit}
                          disabled={!inlinePetForm.name.trim() || isSavingPetInline}
                          style={{ padding: '4px 12px', fontSize: '0.8rem', cursor: 'pointer', backgroundColor: 'var(--primary)', color: '#fff', border: 'none', borderRadius: '4px' }}
                        >
                          {isSavingPetInline ? 'Creating...' : 'Save & Select'}
                        </button>
                      </div>
                    </div>
                  ) : (
                    <>
                      {newVisitClientPets.length === 0 ? (
                        <div style={{ padding: '10px', border: '1px dashed var(--warning-color)', borderRadius: '8px', backgroundColor: 'rgba(255, 152, 0, 0.02)', marginTop: '4px' }}>
                          <p style={{ color: 'var(--warning-color)', fontSize: '0.85rem', margin: 0 }}>
                            This client has no pets on file. Click <strong>+ Add Pet Inline</strong> above to create one immediately.
                          </p>
                        </div>
                      ) : (
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginTop: '4px' }}>
                          {newVisitClientPets.map(pet => (
                            <label key={pet.pet_id} style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '6px 12px', borderRadius: '8px', border: newVisitForm.pet_ids.includes(pet.pet_id) ? '2px solid var(--primary)' : '1px solid var(--border-soft)', cursor: 'pointer', fontSize: '0.9rem' }}>
                              <input
                                type="checkbox"
                                checked={newVisitForm.pet_ids.includes(pet.pet_id)}
                                onChange={() => handleNewVisitPetToggle(pet)}
                              />
                              {pet.name || 'Unnamed'} {pet.breed ? `(${pet.breed})` : ''}
                            </label>
                          ))}
                        </div>
                      )}
                    </>
                  )}
                </div>
              )}

              {/* Service Type */}
              <div className="field" style={{ marginBottom: '16px' }}>
                <label>Service Type *</label>
                <select
                  value={newVisitForm.service_type}
                  onChange={(e) => handleNewVisitServiceChange(e.target.value)}
                  style={{ width: '100%', padding: '10px', borderRadius: '8px', border: '1px solid var(--border-soft)' }}
                >
                  {adminServiceTypes.map(([identifier, service]) => (
                    <option key={identifier} value={identifier}>{service.labelLong}</option>
                  ))}
                </select>
              </div>

              {/* Dates */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginBottom: '16px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                  <label style={{ fontSize: '0.85rem', fontWeight: '700', color: 'var(--text-main)' }}>Visit Dates *</label>
                </div>

                <div className="intake-date-picker-card">
                  
                  {/* Quick Range Helper */}
                  <div className="range-helper-container range-helper-row" style={{ paddingBottom: '12px', borderBottom: '1px solid var(--border-soft)' }}>
                    <div className="field range-helper-field">
                      <label style={{ fontSize: '0.75rem' }}>Auto-select from</label>
                      <input
                        type="date"
                        value={newVisitForm.range_start}
                        onChange={(e) => setNewVisitForm(prev => ({ ...prev, range_start: e.target.value }))}
                        className="range-helper-input"
                      />
                    </div>
                    <div className="field range-helper-field">
                      <label style={{ fontSize: '0.75rem' }}>to</label>
                      <input
                        type="date"
                        value={newVisitForm.range_end}
                        onChange={(e) => setNewVisitForm(prev => ({ ...prev, range_end: e.target.value }))}
                        className="range-helper-input"
                      />
                    </div>
                    <button 
                      className="button-secondary btn-range-autofill" 
                      onClick={(e) => {
                        e.preventDefault();
                        if (!newVisitForm.range_start || !newVisitForm.range_end) return;
                        const start = new Date(newVisitForm.range_start + 'T00:00:00');
                        const end = new Date(newVisitForm.range_end + 'T00:00:00');
                        if (end < start) return;
                        const dates = [];
                        let curr = new Date(start);
                        while (curr <= end && dates.length < 14) {
                          const y = curr.getFullYear();
                          const m = String(curr.getMonth() + 1).padStart(2, '0');
                          const d = String(curr.getDate()).padStart(2, '0');
                          dates.push(`${y}-${m}-${d}`);
                          curr.setDate(curr.getDate() + 1);
                        }
                        setNewVisitForm(prev => {
                          const existing = new Set(prev.selected_dates);
                          dates.forEach(d => existing.add(d));
                          return { ...prev, selected_dates: Array.from(existing).sort().slice(0, 14), range_start: '', range_end: '' };
                        });
                      }}
                    >
                      Apply
                    </button>
                  </div>

                  <DatePickerGrid
                    selectedDates={newVisitForm.selected_dates}
                    onDateToggle={(dateStr) => {
                      setNewVisitForm(prev => {
                        const current = prev.selected_dates || [];
                        if (current.includes(dateStr)) {
                          return { ...prev, selected_dates: current.filter(d => d !== dateStr) };
                        }
                        if (current.length >= 14) return prev;
                        return { ...prev, selected_dates: [...current, dateStr] };
                      });
                    }}
                    maxSelections={14}
                  />

                  <div className="date-picker-summary-container">
                    <div className="date-picker-summary-header">
                      <span className="date-picker-summary-title">
                        {newVisitForm.selected_dates.length}/14 days selected
                      </span>
                      {newVisitForm.selected_dates.length > 0 && (
                        <button 
                          onClick={(e) => { e.preventDefault(); setNewVisitForm(prev => ({ ...prev, selected_dates: [] })); }}
                          className="btn-clear-dates"
                        >
                          Clear All
                        </button>
                      )}
                    </div>
                    {newVisitForm.selected_dates.length > 0 && (
                      <div className="date-chip-list">
                        {[...newVisitForm.selected_dates].sort().map(d => {
                          const dateObj = new Date(d + 'T00:00:00');
                          const shortStr = dateObj.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
                          return <span key={d} className="date-chip">{shortStr}</span>;
                        })}
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {newVisitForm.service_type === checkInServiceId && (() => {
                const model = getAdminCheckInModel(newVisitForm.service_type);
                if (!model) return null;
                const exactCountReached = newVisitForm.visit_windows.length >= newVisitForm.visits_per_day;
                return (
                  <div className="admin-check-in-schedule">
                    <fieldset className="admin-check-in-fieldset">
                      <legend>Visits per day *</legend>
                      <div className="admin-check-in-options">
                        {model.service.visitsPerDayOptions.map(visits => (
                          <label key={visits} className="admin-check-in-option">
                            <input
                              type="radio"
                              name="admin-visits-per-day"
                              value={visits}
                              checked={newVisitForm.visits_per_day === visits}
                              onChange={() => handleNewVisitCountChange(visits)}
                              aria-describedby={newVisitScheduleError ? 'admin-check-in-schedule-error' : undefined}
                            />
                            {visits}
                          </label>
                        ))}
                      </div>
                    </fieldset>

                    <fieldset
                      className="admin-check-in-fieldset"
                      aria-describedby={newVisitScheduleError ? 'admin-check-in-schedule-error' : undefined}
                    >
                      <legend>Visit windows *</legend>
                      <div className="admin-check-in-options admin-check-in-window-options">
                        {model.windows.map(window => {
                          const checked = newVisitForm.visit_windows.includes(window.id);
                          const disabled = (
                            !newVisitForm.visits_per_day
                            || newVisitForm.visits_per_day === model.windows.length
                            || (!checked && exactCountReached)
                          );
                          return (
                            <label key={window.id} className={`admin-check-in-option admin-check-in-window ${disabled ? 'disabled' : ''}`}>
                              <input
                                type="checkbox"
                                checked={checked}
                                disabled={disabled}
                                onChange={() => handleNewVisitWindowToggle(window.id)}
                                aria-label={`${window.label}, ${formatCanonicalTime(window.start)} to ${formatCanonicalTime(window.end)}`}
                              />
                              <span>
                                <strong>{window.label}</strong>
                                <small>{formatCanonicalTime(window.start)}–{formatCanonicalTime(window.end)}</small>
                              </span>
                            </label>
                          );
                        })}
                      </div>
                    </fieldset>
                    {newVisitScheduleError && (
                      <p id="admin-check-in-schedule-error" className="admin-check-in-error" role="alert">
                        {newVisitScheduleError}
                      </p>
                    )}
                  </div>
                );
              })()}

              {SERVICE_TYPES.services[newVisitForm.service_type]?.windowSelectionMode === 'exactly_one' && (() => {
                const model = getAdminCanonicalWindowModel(newVisitForm.service_type);
                if (!model) return null;
                return (
                  <div className="admin-check-in-schedule">
                    <fieldset
                      className="admin-check-in-fieldset"
                      aria-describedby={newVisitScheduleError ? 'admin-walk-schedule-error' : 'admin-walk-schedule-hint'}
                    >
                      <legend>Visit window *</legend>
                      <p id="admin-walk-schedule-hint">Choose one window for every selected date.</p>
                      <div className="admin-check-in-options admin-check-in-window-options">
                        {model.windows.map(window => {
                          const checked = newVisitForm.visit_windows[0] === window.id;
                          return (
                            <label key={window.id} className="admin-check-in-option admin-check-in-window">
                              <input
                                type="radio"
                                name="admin-walk-window"
                                value={window.id}
                                checked={checked}
                                onChange={() => handleNewVisitExactWindowChange(window.id)}
                                aria-label={`${window.label}, ${formatCanonicalTime(window.start)} to ${formatCanonicalTime(window.end)}`}
                              />
                              <span>
                                <strong>{window.label}</strong>
                                <small>{formatCanonicalTime(window.start)}–{formatCanonicalTime(window.end)}</small>
                              </span>
                            </label>
                          );
                        })}
                      </div>
                    </fieldset>
                    {newVisitScheduleError && (
                      <p id="admin-walk-schedule-error" className="admin-check-in-error" role="alert">
                        {newVisitScheduleError}
                      </p>
                    )}
                  </div>
                );
              })()}

              {SERVICE_TYPES.services[newVisitForm.service_type]?.scheduleMode === 'fixed' && (
                <div className="admin-check-in-schedule" role="note" aria-label="Fixed Overnight schedule">
                  <strong>{getAdminFixedScheduleLabel(newVisitForm.service_type)}</strong>
                  <p>Each selected date is the night service starts. It ends the following morning.</p>
                </div>
              )}

              {SERVICE_TYPES.services[newVisitForm.service_type]?.windowSelectionMode === 'legacy_compatibility' && (
                <div className="field" style={{ marginBottom: '16px' }}>
                  <label>Visit Window</label>
                  <select
                    value={newVisitForm.visit_windows[0] || 'ANYTIME'}
                    onChange={(e) => setNewVisitForm(prev => ({ ...prev, visit_windows: [e.target.value] }))}
                    style={{ width: '100%', padding: '10px', borderRadius: '8px', border: '1px solid var(--border-soft)' }}
                  >
                    <option value="ANYTIME">Anytime</option>
                    <option value="MORNING">Morning</option>
                    <option value="MIDDAY">Midday</option>
                    <option value="AFTERNOON">Afternoon</option>
                    <option value="EVENING">Evening</option>
                  </select>
                </div>
              )}

              {/* Notes */}
              <div className="field" style={{ marginBottom: '16px' }}>
                <label>Notes / Details</label>
                <textarea
                  value={newVisitForm.details}
                  onChange={(e) => setNewVisitForm(prev => ({ ...prev, details: e.target.value }))}
                  placeholder="Access codes, special instructions, etc."
                  rows={3}
                  style={{ width: '100%', padding: '10px', borderRadius: '8px', border: '1px solid var(--border-soft)', resize: 'vertical' }}
                />
              </div>

              {/* Preferred Sitter */}
              <div className="field" style={{ marginBottom: '16px' }}>
                <label>Preferred Sitter</label>
                <select
                  value={newVisitForm.preferred_sitter}
                  onChange={(e) => setNewVisitForm(prev => ({ ...prev, preferred_sitter: e.target.value }))}
                  style={{ width: '100%', padding: '10px', borderRadius: '8px', border: '1px solid var(--border-soft)' }}
                >
                  <option value="">No preference</option>
                  {staffList.filter(s => s.is_active && s.is_assignable).map(s => (
                    <option key={s.staff_id} value={s.email || s.display_name}>{s.display_name}</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="modal-footer" style={{ padding: '16px 24px', borderTop: '1px solid var(--border-soft)', display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
              <button className="button-secondary" onClick={handleCloseNewVisitModal} disabled={isCreatingVisit}>Cancel</button>
              <button
                className="button-primary"
                onClick={handleNewVisitSubmit}
                disabled={
                  isCreatingVisit || 
                  !newVisitForm.client_id || 
                  (!newVisitForm.pet_names && newVisitForm.pet_ids.length === 0) ||
                  (newVisitForm.selected_dates.length === 0)
                }
              >
                {isCreatingVisit ? 'Creating...' : 'Create Visit'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AdminDashboard;
