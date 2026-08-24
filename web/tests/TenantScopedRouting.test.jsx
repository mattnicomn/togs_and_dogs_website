import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { AppContent } from '../src/App';
import {
  bootstrapTenantSession,
  shouldExposePlatformAdminNavigation,
  TENANT_ACCESS_ERROR,
  verifyTenantAgreement,
} from '../src/utils/tenantContext';
import { getSession } from '../src/api/auth';
import { getTenantInfo } from '../src/api/client';


vi.mock('../src/api/auth', () => ({
  getSession: vi.fn(),
  getEffectiveRole: vi.fn(),
}));

vi.mock('../src/api/client', () => ({
  getTenantInfo: vi.fn(),
}));

vi.mock('../src/components/AdminDashboard', () => ({
  default: ({ expectedTenantSlug }) => (
    <div data-testid="tenant-admin">Tenant admin: {expectedTenantSlug || 'compatibility'}</div>
  ),
}));

vi.mock('../src/components/PortalGateway', () => ({ default: () => <div>Portal</div> }));
vi.mock('../src/components/About', () => ({ default: () => <div>About</div> }));
vi.mock('../src/components/Services', () => ({ default: () => <div>Services</div> }));
vi.mock('../src/components/IntakeForm', () => ({ default: () => <div>Intake</div> }));
vi.mock('../src/components/ClientPortal', () => ({ default: () => <div>Bookings</div> }));
vi.mock('../src/components/MyPets', () => ({ default: () => <div>Pets</div> }));
vi.mock('../src/components/GoogleCallback', () => ({ default: () => <div>Callback</div> }));
vi.mock('../src/components/ThemeToggle', () => ({ default: () => <button>Theme</button> }));
vi.mock('../src/components/TermsOfUse', () => ({ default: () => <div>Terms</div> }));
vi.mock('../src/components/PrivacyPolicy', () => ({ default: () => <div>Privacy</div> }));
vi.mock('../src/components/PaymentSuccess', () => ({ default: () => <div>Success</div> }));
vi.mock('../src/components/PaymentCancel', () => ({ default: () => <div>Cancel</div> }));
vi.mock('../src/components/PlatformAdmin', () => ({ default: () => <div>Platform console</div> }));
vi.mock('../src/components/PlatformTenantDetail', () => ({ default: () => <div>Tenant detail</div> }));
vi.mock('../src/components/PlatformAuditLog', () => ({ default: () => <div>Audit</div> }));
vi.mock('../src/components/PlatformAdminOnboarding', () => ({ default: () => <div>Onboarding</div> }));


const sessionFor = (companyId, groups = ['owner']) => ({
  getIdToken: () => ({
    payload: {
      email: 'owner@example.com',
      'custom:company_id': companyId,
      'cognito:groups': groups,
    },
  }),
});


describe('tenant agreement bootstrap', () => {
  it('allows exact slug/claim/server agreement', async () => {
    const session = sessionFor('test_tenant_alpha');
    const resolver = vi.fn().mockResolvedValue({
      company_id: 'test_tenant_alpha',
      display_name: 'Test Tenant Alpha',
      is_access_allowed: true,
      is_blocked: false,
    });

    await expect(
      verifyTenantAgreement(session, 'test-tenant-alpha', resolver),
    ).resolves.toMatchObject({ display_name: 'Test Tenant Alpha' });
    expect(resolver).toHaveBeenCalledWith('test-tenant-alpha');
  });

  it('denies a wrong tenant claim and never schedules operational loading', async () => {
    const onAuthorized = vi.fn();
    const resolver = vi.fn().mockResolvedValue({
      company_id: 'test_tenant_alpha',
      is_access_allowed: true,
      is_blocked: false,
    });

    await expect(bootstrapTenantSession({
      session: sessionFor('tog_and_dogs'),
      tenantSlug: 'test-tenant-alpha',
      resolveTenant: resolver,
      onAuthorized,
    })).rejects.toThrow(TENANT_ACCESS_ERROR);

    expect(onAuthorized).not.toHaveBeenCalled();
  });

  it('denies missing claims before any tenant or operational request', async () => {
    const resolver = vi.fn();
    const onAuthorized = vi.fn();

    await expect(bootstrapTenantSession({
      session: sessionFor(undefined),
      tenantSlug: 'test-tenant-alpha',
      resolveTenant: resolver,
      onAuthorized,
    })).rejects.toThrow(TENANT_ACCESS_ERROR);

    expect(resolver).not.toHaveBeenCalled();
    expect(onAuthorized).not.toHaveBeenCalled();
  });

  it('denies unknown or inactive server results with one generic error', async () => {
    const unknown = vi.fn().mockRejectedValue(new Error('unknown'));
    const inactive = vi.fn().mockResolvedValue({
      company_id: 'test_tenant_alpha',
      is_access_allowed: false,
      is_blocked: true,
    });

    await expect(
      verifyTenantAgreement(sessionFor('test_tenant_alpha'), 'unknown-tenant', unknown),
    ).rejects.toThrow(TENANT_ACCESS_ERROR);
    await expect(
      verifyTenantAgreement(sessionFor('test_tenant_alpha'), 'test-tenant-alpha', inactive),
    ).rejects.toThrow(TENANT_ACCESS_ERROR);
  });
});


describe('tenant-scoped Web routes', () => {
  beforeEach(() => {
    window.matchMedia = vi.fn().mockImplementation(() => ({
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }));
    getTenantInfo.mockReset();
  });

  it('maps /t/:tenantSlug and refresh-safe /admin routing to the tenant dashboard', async () => {
    getSession.mockResolvedValue(null);

    render(
      <MemoryRouter initialEntries={['/t/test-tenant-alpha']}>
        <AppContent />
      </MemoryRouter>,
    );

    expect(await screen.findByTestId('tenant-admin')).toHaveTextContent('test-tenant-alpha');
    expect(getTenantInfo).not.toHaveBeenCalled();
  });

  it('does not expose Platform Admin navigation or prefetch tenant data on a tenant route', async () => {
    getSession.mockResolvedValue(sessionFor('test_tenant_alpha', ['owner', 'platform_admin']));

    render(
      <MemoryRouter initialEntries={['/t/test-tenant-alpha/admin']}>
        <AppContent />
      </MemoryRouter>,
    );

    expect(await screen.findByTestId('tenant-admin')).toHaveTextContent('test-tenant-alpha');
    await waitFor(() => expect(getSession).toHaveBeenCalled());
    expect(screen.queryByRole('link', { name: 'Platform Admin' })).not.toBeInTheDocument();
    expect(getTenantInfo).not.toHaveBeenCalled();
  });

  it('preserves Platform Admin navigation eligibility only on compatibility routes', () => {
    expect(shouldExposePlatformAdminNavigation(false, true)).toBe(true);
    expect(shouldExposePlatformAdminNavigation(true, true)).toBe(false);
    expect(shouldExposePlatformAdminNavigation(false, false)).toBe(false);
  });
});
