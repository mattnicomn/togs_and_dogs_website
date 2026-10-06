import { CONFIG } from './config';
import { getIdToken, isTokenExpired } from '../auth/storage';
import { refreshSession } from '../auth/cognito';
import { API_PATHS, buildPath } from '../contracts/generatedContracts';
import type {
  ClientQuote,
  ClientQuoteAcceptResponse,
  ClientQuoteDeclineResponse,
} from '../types';

/**
 * OPS-3A.3A: Error carrying the HTTP status so callers can branch on it
 * (e.g. 409 conflict reconciliation in OPS-3A.3C) without parsing message text.
 * Preserves the existing message behavior; exposes only the numeric status, no
 * raw response/body/session/auth data.
 */
export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

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
    // 401 = token expired or invalid → surface as session expiry so auth layer can log out.
    // Message text is preserved exactly so existing session-recovery checks continue to match.
    if (
      response.status === 401 ||
      errorMessage.toLowerCase().includes('expired') ||
      errorMessage.toLowerCase().includes('unauthorized')
    ) {
      throw new ApiError('Your session expired. Please sign in again.', response.status || 401);
    }
    // 403 = valid token but insufficient role → surface as a plain permission error (do NOT trigger logout)
    if (response.status === 403) {
      throw new ApiError(errorMessage || 'You do not have permission to perform this action.', 403);
    }
    // All other non-OK responses preserve the HTTP status (e.g. 409 conflict) for callers.
    throw new ApiError(errorMessage, response.status);
  }
  
  return response.json();
};

// Mirror key API mutations from the web client for future integration
export const getAdminRequests = (status = 'PENDING_REVIEW', startKey: string | null = null, timeframe: string | null = null) => {
  let url = `${API_PATHS.admin.getRequests}?status=${status}`;
  if (startKey) url += `&startKey=${encodeURIComponent(startKey)}`;
  if (timeframe) url += `&timeframe=${timeframe}`;
  return request(url, 'GET', null, true);
};

export const getAdminRequest = (requestId: string, clientId: string) =>
  request(`${buildPath(API_PATHS.admin.getRequest, { requestId })}?clientId=${encodeURIComponent(clientId)}`, 'GET', null, true);

// Client portal: fetch appointments for the logged-in client
export const getClientRequests = () => request(API_PATHS.client.getRequests, 'GET', null, true);

export const getStaff = () => request(API_PATHS.admin.getStaff, 'GET', null, true);
export const getClients = () => request(API_PATHS.admin.getClients, 'GET', null, true);

// Public staffing options
export const getStaffOptions = () => request(API_PATHS.public.staffOptions, 'POST', { action: 'staff-options' });
export const submitRequest = (data: any) => request(API_PATHS.public.submitRequest, 'POST', data);

// reviewRequest mutations
export const reviewRequest = (requestId: string, clientId: string, status: string, reason = "", visitNotes = "") => 
  request(API_PATHS.admin.review, 'POST', { 
    request_id: requestId, 
    client_id: clientId, 
    status, 
    reason,
    ...(visitNotes ? { visit_notes: visitNotes } : {})
  }, true);

export const assignWorker = (jobId: string, reqId: string, clientId: string, workerId: string, workerName: string) => 
  request(API_PATHS.admin.assign, 'POST', { 
    job_id: jobId, 
    req_id: reqId, 
    client_id: clientId,
    worker_id: workerId,
    worker_name: workerName
  }, true);

export const completeJob = (jobId: string, requestId: string, visitNotes = "") =>
  request(API_PATHS.admin.jobComplete, 'POST', {
    job_id: jobId,
    request_id: requestId,
    visit_notes: visitNotes
  }, true);

export const startJob = (jobId: string, requestId: string) =>
  request(API_PATHS.admin.jobStart, 'POST', { job_id: jobId, request_id: requestId }, true);

// Phase 24A-4: Client pets listing (read-only)
export const getClientPets = () => request(API_PATHS.client.getPets, 'GET', null, true);

// Phase 24A-5: Client pet update
export const updateClientPet = (petId: string, data: any) =>
  request(buildPath(API_PATHS.client.updatePet, { petId }), 'PUT', data, true);

// Phase 24A-6: Client care request submission
export const submitClientRequest = (data: any) => request(API_PATHS.client.submitRequest, 'POST', data, true);

// OPS-3A.3A: Client quote read + Accept/Decline mutations.
// Consumes the already-live OPS-3A.2 client quote API. No UI logic, no retries,
// no optimistic behavior, and no offline queuing — mutations are server-confirmed.

// GET /client/quotes/{requestId} — client-safe quote projection.
export const getClientQuote = (requestId: string): Promise<ClientQuote> =>
  request(buildPath(API_PATHS.client.getQuote, { requestId }), 'GET', null, true);

// POST /client/quotes/{requestId}/accept — accept the current SENT quote.
// Body is strictly the server contract shape: { expected_revision }.
export const acceptClientQuote = (
  requestId: string,
  expectedRevision: number
): Promise<ClientQuoteAcceptResponse> =>
  request(
    buildPath(API_PATHS.client.acceptQuote, { requestId }),
    'POST',
    { expected_revision: expectedRevision },
    true
  );

// POST /client/quotes/{requestId}/decline — decline the current SENT quote.
// Body: { expected_revision, decline_reason? }. The reason is trimmed at this
// boundary and omitted entirely when blank; the helper never fabricates a value.
export const declineClientQuote = (
  requestId: string,
  expectedRevision: number,
  declineReason?: string
): Promise<ClientQuoteDeclineResponse> => {
  const trimmed = typeof declineReason === 'string' ? declineReason.trim() : '';
  const body: { expected_revision: number; decline_reason?: string } = {
    expected_revision: expectedRevision,
  };
  if (trimmed) {
    body.decline_reason = trimmed;
  }
  return request(
    buildPath(API_PATHS.client.declineQuote, { requestId }),
    'POST',
    body,
    true
  );
};
