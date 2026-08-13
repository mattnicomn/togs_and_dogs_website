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

/**
 * Validate onboarding fields for a proposed new tenant.
 * Returns { valid, errors, warnings, validated_fields, no_writes }.
 * Never writes to the database.
 */
export const validateOnboardingTenant = (data) =>
  request('/platform/onboarding/validate', 'POST', data, true);

/**
 * Generate a full preview of the proposed tenant provisioning.
 * Returns proposed_metadata, proposed_audit, tier_limits, approval_checklist,
 * preview_hash, and no_writes: true.
 * Never writes to the database.
 */
export const previewOnboardingTenant = (data) =>
  request('/platform/onboarding/preview', 'POST', data, true);
