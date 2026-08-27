/**
 * Server-authoritative Tenant Presentation & Branding Utilities (PTM-3D).
 *
 * Presentation is derived ONLY after canonical server-authoritative tenant bootstrap
 * and identity agreement succeed. Mismatched, unauthenticated, or invalid tenant contexts
 * fall back safely to default platform presentation without exposing private metadata.
 */

export const DEFAULT_BRANDING = Object.freeze({
  company_id: 'tog_and_dogs',
  display_name: 'Tog and Dogs',
  brand_name: 'Tog and Dogs',
  document_title: 'Tog and Dogs | Premium Pet Care & Dog Walking',
  portal_title: 'Tog and Dogs Portal',
  client_portal_label: 'Client Portal',
  staff_portal_label: 'Staff Portal',
  intake_label: 'Request Pet Care',
  team_label: 'Tog & Dogs Team',
  support_email: 'hello@toganddogs.com',
  is_default_tenant: true,
});

/**
 * Derive tenant presentation metadata from authoritative tenantInfo.
 *
 * @param {Object|null} tenantInfo - Authoritative tenant metadata returned by GET /admin/tenant-info
 * @returns {Object} Canonical presentation contract object
 */
export const deriveTenantPresentation = (tenantInfo) => {
  if (!tenantInfo || !tenantInfo.company_id || tenantInfo.company_id === 'tog_and_dogs') {
    return DEFAULT_BRANDING;
  }

  const displayName = tenantInfo.display_name && tenantInfo.display_name.trim() !== ''
    ? tenantInfo.display_name.trim()
    : tenantInfo.company_id;

  return Object.freeze({
    company_id: tenantInfo.company_id,
    display_name: displayName,
    brand_name: displayName,
    document_title: `${displayName} | Pet Care Portal`,
    portal_title: `${displayName} Portal`,
    client_portal_label: `${displayName} Client Portal`,
    staff_portal_label: `${displayName} Staff Portal`,
    intake_label: `Request Care - ${displayName}`,
    team_label: `${displayName} Team`,
    support_email: tenantInfo.support_email || null,
    is_default_tenant: false,
  });
};

/**
 * Update browser document title dynamically based on active tenant presentation.
 * Resets cleanly to default title when presentation is cleared/null.
 *
 * @param {Object|null} presentation - Derived presentation metadata or null
 */
export const updateDocumentTitle = (presentation) => {
  if (typeof document !== 'undefined') {
    document.title = presentation?.document_title || DEFAULT_BRANDING.document_title;
  }
};
