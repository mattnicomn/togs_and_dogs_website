/**
 * Server-authoritative Tenant Presentation & Branding Utilities (PTM-3D & PTM-3D.1).
 *
 * Presentation is derived ONLY after canonical server-authoritative tenant bootstrap
 * and identity agreement succeed. Mismatched, unauthenticated, or invalid tenant contexts
 * fall back safely to neutral platform presentation without exposing private metadata or
 * defaulting to unrelated primary tenant branding.
 */

/**
 * Neutral Platform Presentation for unauthenticated, invalid, or tenant-less contexts (PTM-3D.1).
 * Used when no valid business tenant authorization exists.
 */
export const NEUTRAL_PLATFORM_PRESENTATION = Object.freeze({
  company_id: null,
  display_name: 'USMissionHero',
  brand_name: 'USMissionHero',
  document_title: 'Pet Care Operations Platform | USMissionHero',
  portal_title: 'Pet Care Portal',
  client_portal_label: 'Client Portal',
  staff_portal_label: 'Staff Portal',
  intake_label: 'Request Pet Care',
  team_label: 'Pet Care Operations Team',
  support_email: null,
  is_default_tenant: false,
  is_neutral_platform: true,
});

/**
 * Explicit Togs & Dogs Tenant Presentation (Ryan's business tenant).
 * Used ONLY when canonical tenant company_id is 'tog_and_dogs'.
 */
export const TOG_AND_DOGS_BRANDING = Object.freeze({
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
  is_neutral_platform: false,
});

// Backward-compatible alias for explicit Togs & Dogs tenant branding
export const DEFAULT_BRANDING = TOG_AND_DOGS_BRANDING;

/**
 * Derive tenant presentation metadata from authoritative tenantInfo.
 *
 * @param {Object|null} tenantInfo - Authoritative tenant metadata returned by GET /admin/tenant-info
 * @returns {Object} Canonical presentation contract object
 */
export const deriveTenantPresentation = (tenantInfo) => {
  if (!tenantInfo || !tenantInfo.company_id) {
    return NEUTRAL_PLATFORM_PRESENTATION;
  }

  if (tenantInfo.company_id === 'tog_and_dogs') {
    return TOG_AND_DOGS_BRANDING;
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
    is_neutral_platform: false,
  });
};

/**
 * Update browser document title dynamically based on active tenant presentation.
 * Resets cleanly to neutral platform title when presentation is cleared/null.
 *
 * @param {Object|null} presentation - Derived presentation metadata or null
 */
export const updateDocumentTitle = (presentation) => {
  if (typeof document !== 'undefined') {
    document.title = presentation?.document_title || NEUTRAL_PLATFORM_PRESENTATION.document_title;
  }
};
