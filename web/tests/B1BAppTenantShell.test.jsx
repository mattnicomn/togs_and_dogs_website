/**
 * B1-B regression coverage: the App shell's tenant presentation is cleared during render
 * on routes that do not use it, so stale tenant identity can never be shown on
 * (re-)entry to an admin route — including when a tenant read resolves late.
 */
import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, useNavigate } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { AppContent } from '../src/App';
import { getSession } from '../src/api/auth';
import { getTenantInfo } from '../src/api/client';

vi.mock('../src/api/auth', () => ({
  getSession: vi.fn(),
  getEffectiveRole: vi.fn(),
}));

vi.mock('../src/api/client', () => ({
  getTenantInfo: vi.fn(),
}));

vi.mock('../src/components/AdminDashboard', () => ({ default: () => <div>Admin dashboard</div> }));
vi.mock('../src/components/PortalGateway', () => ({ default: () => <div>Portal gateway route</div> }));
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

const ownerSession = {
  getIdToken: () => ({
    payload: { email: 'owner@example.test', 'custom:company_id': 'tenant_alpha', 'cognito:groups': ['owner'] },
  }),
};

const deferred = () => {
  let resolve;
  const promise = new Promise((res) => { resolve = res; });
  return { promise, resolve };
};

const Nav = () => {
  const navigate = useNavigate();
  return (
    <>
      <button onClick={() => navigate('/')}>nav-home</button>
      <button onClick={() => navigate('/admin')}>nav-admin</button>
    </>
  );
};

const renderAt = (path) => render(
  <MemoryRouter initialEntries={[path]}>
    <Nav />
    <AppContent />
  </MemoryRouter>
);

const DEFAULT_BRAND = 'Pet Care Admin: A Pet Business Platform';

// jsdom has no matchMedia; App's responsive-drawer effect needs a minimal stand-in.
if (!window.matchMedia) {
  window.matchMedia = (query) => ({
    matches: false,
    media: query,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
  });
}

describe('App shell tenant presentation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getSession.mockResolvedValue(ownerSession);
  });

  it('shows the tenant name on an admin route', async () => {
    getTenantInfo.mockResolvedValue({ display_name: 'Alpha Pets' });
    renderAt('/admin');
    expect(await screen.findByText('Alpha Pets: A Pet Business Platform')).toBeInTheDocument();
  });

  it('a tenant read that resolves after leaving the admin route is never shown on re-entry', async () => {
    const lateRead = deferred();
    const secondRead = deferred();
    getTenantInfo
      .mockReturnValueOnce(lateRead.promise)
      .mockReturnValueOnce(secondRead.promise);
    renderAt('/admin');
    await waitFor(() => expect(getTenantInfo).toHaveBeenCalledTimes(1));

    // Leave the admin route, then let the first (now stale) read resolve.
    fireEvent.click(screen.getByRole('button', { name: 'nav-home' }));
    await act(async () => { lateRead.resolve({ display_name: 'Stale Tenant' }); });

    // Re-enter the admin route while the fresh read is still pending.
    fireEvent.click(screen.getByRole('button', { name: 'nav-admin' }));
    await waitFor(() => expect(getTenantInfo).toHaveBeenCalledTimes(2));
    expect(screen.queryByText(/Stale Tenant/)).toBeNull();
    expect(screen.getAllByText(DEFAULT_BRAND).length).toBeGreaterThan(0);

    await act(async () => { secondRead.resolve({ display_name: 'Fresh Tenant' }); });
    expect(await screen.findByText('Fresh Tenant: A Pet Business Platform')).toBeInTheDocument();
    expect(screen.queryByText(/Stale Tenant/)).toBeNull();
  });

  it('does not read tenant info on a non-admin route', async () => {
    renderAt('/');
    expect(await screen.findByText('Portal gateway route')).toBeInTheDocument();
    await act(async () => { for (let i = 0; i < 10; i += 1) await Promise.resolve(); });
    expect(getTenantInfo).not.toHaveBeenCalled();
  });
});
