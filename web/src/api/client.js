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
    throw new Error(errorData.message || `Request failed with status ${response.status}`);
  }
  
  return response.json();
};

export const submitRequest = (data) => request('/requests', 'POST', data);

// Protected Admin Calls
export const getAdminRequests = (status = 'PENDING_REVIEW') => 
  request(`/admin/requests?status=${status}`, 'GET', null, true);

export const reviewRequest = (requestId, clientId, status, reason = "") => 
  request('/admin/review', 'POST', { 
    request_id: requestId, 
    client_id: clientId, 
    status, 
    reason 
  }, true);

export const assignWorker = (jobId, reqId, workerId) => 
  request('/admin/assign', 'POST', { 
    job_id: jobId, 
    req_id: reqId, 
    worker_id: workerId 
  }, true);

export const getGoogleStatus = () => request('/admin/auth/status', 'GET', null, true);

export const initiateGoogleAuth = () => request('/admin/auth/google', 'GET', null, true);

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
