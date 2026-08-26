import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { Link, MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { AppContent, TenantAdminRoute } from '../src/App';
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

vi.mock('../src/components/AdminDashboard', () => {
  const MockAdminDashboard = ({ expectedTenantSlug }) => {
    const [operationalState, setOperationalState] = React.useState('empty');
    const workspace = expectedTenantSlug || 'compatibility';

    return (
      <div>
        <div data-testid="tenant-admin">Tenant admin: {workspace}</div>
        <div data-testid="operational-state">{operationalState}</div>
        <button type="button" onClick={() => setOperationalState(`loaded:${workspace}`)}>
          Load operational state
        </button>
      </div>
    );
  };

  return { default: MockAdminDashboard };
});

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

  it.each([
    ['401', Object.assign(new Error('unauthorized'), { status: 401 })],
    ['403', Object.assign(new Error('forbidden'), { status: 403 })],
    ['network failure', new TypeError('network unavailable')],
  ])('maps resolver %s failures to the generic tenant error', async (_category, resolverError) => {
    const onAuthorized = vi.fn();

    await expect(bootstrapTenantSession({
      session: sessionFor('test_tenant_alpha'),
      tenantSlug: 'test-tenant-alpha',
      resolveTenant: vi.fn().mockRejectedValue(resolverError),
      onAuthorized,
    })).rejects.toThrow(TENANT_ACCESS_ERROR);

    expect(onAuthorized).not.toHaveBeenCalled();
  });

  it('rejects malformed slugs before resolving or authorizing tenant data', async () => {
    const resolveTenant = vi.fn();
    const onAuthorized = vi.fn();

    await expect(bootstrapTenantSession({
      session: sessionFor('test_tenant_alpha'),
      tenantSlug: '../test-tenant-alpha',
      resolveTenant,
      onAuthorized,
    })).rejects.toThrow(TENANT_ACCESS_ERROR);

    expect(resolveTenant).not.toHaveBeenCalled();
    expect(onAuthorized).not.toHaveBeenCalled();
  });

  it('does not authorize invalid, wrong-tenant, or unknown B after valid tenant A', async () => {
    const onAuthorized = vi.fn();
    const session = sessionFor('test_tenant_alpha');
    const activeTenantA = {
      company_id: 'test_tenant_alpha',
      is_access_allowed: true,
      is_blocked: false,
    };

    await bootstrapTenantSession({
      session,
      tenantSlug: 'test-tenant-alpha',
      resolveTenant: vi.fn().mockResolvedValue(activeTenantA),
      onAuthorized,
    });

    const negativeTenantBResolvers = [
      vi.fn().mockResolvedValue({ ...activeTenantA, is_access_allowed: false, is_blocked: true }),
      vi.fn().mockResolvedValue({ ...activeTenantA, company_id: 'other_company' }),
      vi.fn().mockRejectedValue(new Error('unknown tenant')),
    ];

    for (const resolveTenant of negativeTenantBResolvers) {
      await expect(bootstrapTenantSession({
        session,
        tenantSlug: 'tenant-b',
        resolveTenant,
        onAuthorized,
      })).rejects.toThrow(TENANT_ACCESS_ERROR);
    }

    expect(onAuthorized).toHaveBeenCalledTimes(1);
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

  it('clears mounted operational state on tenant changes and tenant-to-normal navigation', async () => {
    render(
      <MemoryRouter initialEntries={['/t/test-tenant-alpha/admin']}>
        <Link to="/t/tenant-b/admin">Tenant B</Link>
        <Link to="/admin">Compatibility admin</Link>
        <Routes>
          <Route path="/t/:tenantSlug/admin" element={<TenantAdminRoute />} />
          <Route path="/admin" element={<TenantAdminRoute />} />
        </Routes>
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Load operational state' }));
    expect(screen.getByTestId('operational-state')).toHaveTextContent('loaded:test-tenant-alpha');

    fireEvent.click(screen.getByRole('link', { name: 'Tenant B' }));
    expect(await screen.findByTestId('tenant-admin')).toHaveTextContent('tenant-b');
    expect(screen.getByTestId('operational-state')).toHaveTextContent('empty');

    fireEvent.click(screen.getByRole('button', { name: 'Load operational state' }));
    expect(screen.getByTestId('operational-state')).toHaveTextContent('loaded:tenant-b');

    fireEvent.click(screen.getByRole('link', { name: 'Compatibility admin' }));
    expect(await screen.findByTestId('tenant-admin')).toHaveTextContent('compatibility');
    expect(screen.getByTestId('operational-state')).toHaveTextContent('empty');
  });
});
