import { CONFIG } from './config';
import { getIdToken } from '../auth/storage';

const request = async (path: string, method = 'GET', data: any = null, isProtected = false) => {
  const options: RequestInit = {
    method,
    headers: {
      'Content-Type': 'application/json',
    },
  };

  if (isProtected) {
    const token = await getIdToken();
    if (token) {
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
