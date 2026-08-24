const TENANT_SLUG_PATTERN = /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/;

export const TENANT_ACCESS_ERROR = 'This sign-in does not have access to the requested tenant workspace.';

export const shouldExposePlatformAdminNavigation = (isTenantRoute, isPlatformAdmin) => (
  !isTenantRoute && isPlatformAdmin
);

export class TenantContextError extends Error {
  constructor() {
    super(TENANT_ACCESS_ERROR);
    this.name = 'TenantContextError';
  }
}

const getCompanyClaim = (session) => {
  const claim = session?.getIdToken?.()?.payload?.['custom:company_id'];
  return typeof claim === 'string' ? claim.trim() : '';
};

/**
 * Verify route context before any tenant operational fetch is scheduled.
 * The server response is authoritative; the client-side comparison is an
 * additional fail-closed bootstrap check, not a source of tenant authority.
 */
export const verifyTenantAgreement = async (session, tenantSlug, resolveTenant) => {
  if (!session || !TENANT_SLUG_PATTERN.test(tenantSlug || '')) {
    throw new TenantContextError();
  }

  const claimCompanyId = getCompanyClaim(session);
  if (!claimCompanyId) {
    throw new TenantContextError();
  }

  let tenantInfo;
  try {
    tenantInfo = await resolveTenant(tenantSlug);
  } catch {
    throw new TenantContextError();
  }

  if (
    !tenantInfo ||
    tenantInfo.company_id !== claimCompanyId ||
    tenantInfo.is_access_allowed !== true ||
    tenantInfo.is_blocked === true
  ) {
    throw new TenantContextError();
  }

  return tenantInfo;
};

/**
 * Run the authenticated bootstrap only after route/claim agreement succeeds.
 * Tests use this boundary to prove mismatches cannot schedule data loading.
 */
export const bootstrapTenantSession = async ({
  session,
  tenantSlug,
  resolveTenant,
  onAuthorized,
}) => {
  const tenantInfo = await verifyTenantAgreement(session, tenantSlug, resolveTenant);
  await onAuthorized(tenantInfo);
  return tenantInfo;
};
