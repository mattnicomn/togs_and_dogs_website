import CONFIG from './config';
import { getIdToken } from './auth';

const request = async (path, method = 'GET', data = null, isProtected = false) => {
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

export const submitRequest = (data) => request('/requests', 'POST', data);

// Protected Admin Calls
export const getAdminRequests = (status = 'PENDING_REVIEW', startKey = null, timeframe = null) => {
  let url = `/admin/requests?status=${status}`;
  if (startKey) url += `&startKey=${encodeURIComponent(startKey)}`;
  if (timeframe) url += `&timeframe=${timeframe}`;
  return request(url, 'GET', null, true);
};

export const reviewRequest = (requestId, clientId, status, reason = "") => 
  request('/admin/review', 'POST', { 
    request_id: requestId, 
    client_id: clientId, 
    status, 
    reason 
  }, true);

export const assignWorker = (jobId, reqId, clientId, workerId) => 
  request('/admin/assign', 'POST', { 
    job_id: jobId, 
    req_id: reqId, 
    client_id: clientId,
    worker_id: workerId 
  }, true);

export const getGoogleStatus = () => request('/admin/auth/status', 'GET', null, true);

export const initiateGoogleAuth = () => request('/admin/auth/google', 'GET', null, true);

export const getStaff = () => request('/admin/staff', 'GET', null, true);
export const createStaff = (data) => request('/admin/staff', 'POST', data, true);
export const updateStaff = (staffId, data) => request(`/admin/staff/${staffId}`, 'PATCH', data, true);
export const disableStaff = (staffId, data = null) => request(`/admin/staff/${staffId}`, 'DELETE', data, true);

export const onboardStaff = (data) => request('/admin/staff/onboard', 'POST', data, true);
export const linkCognitoUser = (staffId, data) => request(`/admin/staff/${staffId}/link-cognito`, 'POST', data, true);
export const resendInvite = (staffId) => request(`/admin/staff/${staffId}/resend-invite`, 'POST', null, true);




export const completeGoogleAuth = (code, state) => 
  request(`/admin/auth/callback?code=${encodeURIComponent(code)}&state=${encodeURIComponent(state)}`, 'GET', null, false);

// Care Card / Pet Operations
export const getPet = (petId, clientId) => 
  request(`/admin/pets/${petId}?clientId=${clientId}`, 'GET', null, true);

export const updatePet = (petId, clientId, data) => 
  request(`/admin/pets/${petId}`, 'PUT', { ...data, client_id: clientId }, true);

export const createPet = (data) => 
  request(`/admin/pets`, 'POST', data, true);

// Booking Change Management
export const requestCancellation = (requestId, clientId, reason) =>
  request('/client/cancel', 'POST', { request_id: requestId, client_id: clientId, reason }, true);

export const processCancellationDecision = (requestId, clientId, decision, note) =>
  request('/admin/cancel/decision', 'PUT', { request_id: requestId, client_id: clientId, decision, note }, true);

// Operational Management
export const performAdminAction = (pk, sk, action) => 
  request('/admin/requests', 'POST', { PK: pk, SK: sk, action }, true);

// Permanent purge — backend enforces DELETED status guard before removing from DynamoDB
export const purgeRecord = (pk, sk) =>
  request('/admin/requests', 'POST', { PK: pk, SK: sk, action: 'PURGE' }, true);

export const disconnectGoogle = () => 
  request('/admin/auth/google', 'DELETE', null, true);

