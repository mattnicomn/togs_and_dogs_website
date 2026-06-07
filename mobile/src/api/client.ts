import { CONFIG } from './config';
import { getIdToken, isTokenExpired } from '../auth/storage';
import { refreshSession } from '../auth/cognito';

const request = async (path: string, method = 'GET', data: any = null, isProtected = false) => {
  const options: RequestInit = {
    method,
    headers: {
      'Content-Type': 'application/json',
    },
  };

  if (isProtected) {
    let token = await getIdToken();
    if (token) {
      // Validate expiration before request
      if (isTokenExpired(token)) {
        console.log('Token expired prior to API call, attempting silent refresh...');
        const newToken = await refreshSession();
        if (newToken) {
          token = newToken;
          console.log('Silent token refresh succeeded before API call.');
        } else {
          console.warn('Silent refresh failed before API call, forcing session expiration.');
          throw new Error('Your session expired. Please sign in again.');
        }
      }
      
      options.headers = {
        ...options.headers,
        'Authorization': token,
      };
    }
  }

  if (data) {
    options.body = JSON.stringify(data);
  }

  const response = await fetch(`${CONFIG.API_URL}${path}`, options);
  
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const errorMessage = errorData.error || errorData.message || `Request failed with status ${response.status}`;
    // 401 = token expired or invalid → surface as session expiry so auth layer can log out
    if (
      response.status === 401 ||
      errorMessage.toLowerCase().includes('expired') ||
      errorMessage.toLowerCase().includes('unauthorized')
    ) {
      throw new Error('Your session expired. Please sign in again.');
    }
    // 403 = valid token but insufficient role → surface as a plain permission error (do NOT trigger logout)
    if (response.status === 403) {
      throw new Error(errorMessage || 'You do not have permission to perform this action.');
    }
    throw new Error(errorMessage);
  }
  
  return response.json();
};

// Mirror key API mutations from the web client for future integration
export const getAdminRequests = (status = 'PENDING_REVIEW', startKey: string | null = null, timeframe: string | null = null) => {
  let url = `/admin/requests?status=${status}`;
  if (startKey) url += `&startKey=${encodeURIComponent(startKey)}`;
  if (timeframe) url += `&timeframe=${timeframe}`;
  return request(url, 'GET', null, true);
};

export const getStaff = () => request('/admin/staff', 'GET', null, true);
export const getClients = () => request('/admin/clients', 'GET', null, true);

// Public staffing options
export const getStaffOptions = () => request('/requests', 'POST', { action: 'staff-options' });
export const submitRequest = (data: any) => request('/requests', 'POST', data);

// reviewRequest mutations
export const reviewRequest = (requestId: string, clientId: string, status: string, reason = "", visitNotes = "") => 
  request('/admin/review', 'POST', { 
    request_id: requestId, 
    client_id: clientId, 
    status, 
    reason,
    ...(visitNotes ? { visit_notes: visitNotes } : {})
  }, true);

export const assignWorker = (jobId: string, reqId: string, clientId: string, workerId: string, workerName: string) => 
  request('/admin/assign', 'POST', { 
    job_id: jobId, 
    req_id: reqId, 
    client_id: clientId,
    worker_id: workerId,
    worker_name: workerName
  }, true);

export const completeJob = (jobId: string, requestId: string, visitNotes = "") =>
  request('/admin/job/complete', 'POST', {
    job_id: jobId,
    request_id: requestId,
    visit_notes: visitNotes
  }, true);


