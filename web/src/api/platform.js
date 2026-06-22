import { request } from './client';

/**
 * Retrieve a summary list of all tenants registered in the system.
 * Returns company_id, display_name, subscription_tier, subscription_status, created_at.
 */
export const getPlatformTenants = () => request('/platform/tenants', 'GET', null, true);

/**
 * Retrieve detailed metadata, entitlement limits, and usage counts for a single tenant.
 */
export const getPlatformTenant = (companyId) => request(`/platform/tenants/${companyId}`, 'GET', null, true);

/**
 * Update tenant subscription metadata (tier, status, display name, override time, notes).
 */
export const updatePlatformTenant = (companyId, data) => request(`/platform/tenants/${companyId}`, 'PATCH', data, true);

/**
 * Fetch platform-wide audit log events (up to 50, pagination supported).
 */
export const getPlatformAudit = () => request('/platform/audit', 'GET', null, true);
