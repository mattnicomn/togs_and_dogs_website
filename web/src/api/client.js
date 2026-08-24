import CONFIG from './config';
import { getIdToken } from './auth';
import { API_PATHS, buildPath } from '../generated/contracts.js';



export const request = async (path, method = 'GET', data = null, isProtected = false) => {
  const options = {
    method,
    headers: {
      'Content-Type': 'application/json'
    }
  };

  if (isProtected) {
    const token = await getIdToken();
    if (token) {
      options.headers['Authorization'] = token;
    }
  }

  if (data) {
    options.body = JSON.stringify(data);
  }

  const response = await fetch(`${CONFIG.API_URL}${path}`, options);
  
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const errorMessage = errorData.error || errorData.message || `Request failed with status ${response.status}`;
    throw new Error(errorMessage);
  }
  
  return response.json();
};

export const submitRequest = (data) => request(API_PATHS.public.submitRequest, 'POST', data);

// Release 6F: Admin-created booking (authenticated, owner/admin only)
export const createAdminBooking = (data) => request(API_PATHS.client.submitRequest, 'POST', { ...data, source: 'admin_created' }, true);

// Release 6F / 1B.5B-A: List pets for a specific client.
// includeInactive=true returns both active and archived pets (staff/admin only).
export const listAdminClientPets = (clientId, includeInactive = false) => {
  const base = `${API_PATHS.admin.getPets}?clientId=${encodeURIComponent(clientId)}`;
  return request(includeInactive ? `${base}&includeInactive=true` : base, 'GET', null, true);
};

// Release 2: Public staff-options endpoint for preferred sitter selection.
// Returns only sanitized display names — no sensitive data exposed.
export const getStaffOptions = () => request(API_PATHS.public.staffOptions, 'POST', { action: 'staff-options' });

// Authenticated Client Portal Calls
export const getClientRequests = () => request(API_PATHS.client.getRequests, 'GET', null, true);
export const submitClientRequest = (data) => request(API_PATHS.client.submitRequest, 'POST', data, true);
export const getClientPets = () => request(API_PATHS.client.getPets, 'GET', null, true);
export const updateClientPet = (petId, data) => request(buildPath(API_PATHS.client.updatePet, { petId }), 'PUT', data, true);

// Protected Admin Calls
export const getAdminRequests = (status = 'PENDING_REVIEW', startKey = null, timeframe = null) => {
  let url = `${API_PATHS.admin.getRequests}?status=${status}`;
  if (startKey) url += `&startKey=${encodeURIComponent(startKey)}`;
  if (timeframe) url += `&timeframe=${timeframe}`;
  return request(url, 'GET', null, true);
};


export const reviewRequest = (requestId, clientId, status, reason = "") => 
  request(API_PATHS.admin.review, 'POST', { 
    request_id: requestId, 
    client_id: clientId, 
    status, 
    reason 
  }, true);

export const assignWorker = (jobId, reqId, clientId, workerId, workerName) => 
  request(API_PATHS.admin.assign, 'POST', { 
    job_id: jobId, 
    req_id: reqId, 
    client_id: clientId,
    worker_id: workerId,
    worker_name: workerName
  }, true);

export const getGoogleStatus = () => request('/admin/auth/status', 'GET', null, true);

export const initiateGoogleAuth = () => request('/admin/auth/google', 'GET', null, true);

export const getStaff = () => request(API_PATHS.admin.getStaff, 'GET', null, true);
export const createStaff = (data) => request(API_PATHS.admin.getStaff, 'POST', data, true);
export const updateStaff = (staffId, data) => request(`/admin/staff/${staffId}`, 'PATCH', data, true);
export const disableStaff = (staffId, data = null) => request(`/admin/staff/${staffId}`, 'DELETE', data, true);

export const onboardStaff = (data) => request('/admin/staff/onboard', 'POST', data, true);
export const linkCognitoUser = (staffId, data) => request(`/admin/staff/${staffId}/link-cognito`, 'POST', data, true);
export const resendInvite = (staffId) => request(`/admin/staff/${staffId}/resend-invite`, 'POST', null, true);
export const resetStaffPassword = (staffId) => request(`/admin/staff/${staffId}/reset-password`, 'POST', null, true);
export const setStaffTempPassword = (staffId, password) => request(`/admin/staff/${staffId}/set-temp-password`, 'POST', { password }, true);

export const getClients = () => request(API_PATHS.admin.getClients, 'GET', null, true);
export const createClient = (data) => request(API_PATHS.admin.getClients, 'POST', data, true);
export const updateClient = (clientId, data) => request(`/admin/clients/${clientId}`, 'PATCH', data, true);
export const disableClient = (clientId) => request(`/admin/clients/${clientId}/disable`, 'POST', null, true);

export const onboardClient = (data) => request('/admin/clients/onboard', 'POST', data, true);
export const resendClientInvite = (clientId) => request(`/admin/clients/${clientId}/resend-invite`, 'POST', null, true);
export const resetClientPassword = (clientId) => request(`/admin/clients/${clientId}/reset-password`, 'POST', null, true);
export const setClientTempPassword = (clientId, password) => request(`/admin/clients/${clientId}/set-temp-password`, 'POST', { password }, true);
export const linkClientCognitoUser = (clientId, data) => request(`/admin/clients/${clientId}/link-cognito`, 'POST', data, true);






export const completeGoogleAuth = (code, state) => 
  request(`/admin/auth/callback?code=${encodeURIComponent(code)}&state=${encodeURIComponent(state)}`, 'GET', null, false);

// Care Card / Pet Operations
export const getPet = (petId, clientId) => 
  request(`${buildPath(API_PATHS.admin.getPetById, { petId })}?clientId=${clientId}`, 'GET', null, true);

export const updatePet = (petId, clientId, data) => 
  request(buildPath(API_PATHS.admin.updatePet, { petId }), 'PUT', { ...data, client_id: clientId }, true);

export const createPet = (data) => 
  request(API_PATHS.admin.createPet, 'POST', data, true);

// Booking Change Management
export const requestCancellation = (requestId, clientId, reason) =>
  request(API_PATHS.client.requestCancellation, 'POST', { request_id: requestId, client_id: clientId, reason }, true);

export const processCancellationDecision = (requestId, clientId, decision, note) =>
  request(API_PATHS.admin.cancelDecision, 'PUT', { request_id: requestId, client_id: clientId, decision, note }, true);

// Operational Management
export const performAdminAction = (pk, sk, action, records = null, extraData = null) => {
  const payload = { action, ...extraData };
  if (records) {
    payload.records = records;
  } else if (pk && sk) {
    payload.PK = pk;
    payload.SK = sk;
  }
  return request(API_PATHS.admin.postAction, 'POST', payload, true);
};

// Permanent purge — backend enforces DELETED status guard before removing from DynamoDB
export const purgeRecord = (pk, sk) =>
  request(API_PATHS.admin.postAction, 'POST', { PK: pk, SK: sk, action: 'PURGE' }, true);

export const purgeRecordsBulk = (records, dryRun = false) =>
  request(API_PATHS.admin.postAction, 'POST', { records, action: 'PURGE', dry_run: dryRun }, true);

export const disconnectGoogle = () => 
  request('/admin/auth/google', 'DELETE', null, true);

export const getExportData = () => request(API_PATHS.admin.exportData, 'GET', null, true);

// Release 12R: Stripe Payment Session Creation / Retrieval
export const createPaymentSession = (requestId, clientId, amountCents) =>
  request(`/admin/requests/${requestId}/payment-session`, 'POST', {
    client_id: clientId,
    amount_cents: amountCents
  }, true);

// Release 12V: Send payment-link email
export const sendPaymentEmail = (requestId, clientId) =>
  request(`/admin/requests/${requestId}/send-payment-email`, 'POST', {
    client_id: clientId
  }, true);

// Release 19L: Fetch safe tenant display metadata
export const getTenantInfo = (expectedTenantSlug = null) => {
  const suffix = expectedTenantSlug
    ? `?expectedTenantSlug=${encodeURIComponent(expectedTenantSlug)}`
    : '';
  return request(`${API_PATHS.admin.tenantInfo}${suffix}`, 'GET', null, true);
};


