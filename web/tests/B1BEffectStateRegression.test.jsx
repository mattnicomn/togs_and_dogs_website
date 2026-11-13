/**
 * B1-B regression coverage: the React effect/state restructuring done to clear
 * `react-hooks/set-state-in-effect` and `react-hooks/immutability` must preserve the
 * previous behaviour (OAuth callback validation and once-only exchange, Platform-page
 * loading/retry and tenant identity, ClientPortal session/booking initialization,
 * CareCard payment/cooldown/pet-switch state).
 */
import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useNavigate } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { completeGoogleAuth, getClientRequests } from '../src/api/client';
import { getPlatformAudit, getPlatformTenant, getPlatformTenants } from '../src/api/platform';
import { getEffectiveRole, getSession } from '../src/api/auth';
import GoogleCallback from '../src/components/GoogleCallback';
import PlatformAdmin from '../src/components/PlatformAdmin';
import PlatformAuditLog from '../src/components/PlatformAuditLog';
import PlatformTenantDetail from '../src/components/PlatformTenantDetail';
import ClientPortal from '../src/components/ClientPortal';
import CareCard from '../src/components/CareCard';

vi.mock('../src/api/client', () => ({
  completeGoogleAuth: vi.fn(),
  getClientRequests: vi.fn(),
  requestCancellation: vi.fn(),
  createPaymentSession: vi.fn(),
  sendPaymentEmail: vi.fn(),
  updateAdminRequestQuote: vi.fn(),
  sendAdminRequestQuote: vi.fn(),
}));

vi.mock('../src/api/platform', () => ({
  getPlatformTenants: vi.fn(),
  getPlatformAudit: vi.fn(),
  getPlatformTenant: vi.fn(),
  updatePlatformTenant: vi.fn(),
}));

vi.mock('../src/api/auth', () => ({
  getSession: vi.fn(),
  getEffectiveRole: vi.fn(),
  signIn: vi.fn(),
  signOut: vi.fn(),
}));

vi.mock('../src/components/UserProfile', () => ({ default: () => <div>Profile</div> }));

const deferred = () => {
  let resolve;
  let reject;
  const promise = new Promise((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
};

// Lets every pending microtask/effect settle without relying on a timing window.
const settle = () => act(async () => {
  for (let i = 0; i < 10; i += 1) await Promise.resolve();
});

beforeEach(() => {
  vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// GoogleCallback (OAuth)
// ---------------------------------------------------------------------------
describe('GoogleCallback OAuth completion', () => {
  const renderCallback = (search) => render(
    <MemoryRouter initialEntries={[`/admin/auth/callback${search}`]}>
      <Routes>
        <Route path="/admin/auth/callback" element={<GoogleCallback />} />
        <Route path="/admin" element={<div>Admin dashboard</div>} />
      </Routes>
    </MemoryRouter>
  );

  it.each([
    ['no parameters', ''],
    ['code only', '?code=abc'],
    ['state only', '?state=xyz'],
    ['empty values', '?code=&state='],
  ])('shows the error state and never exchanges a token with %s', async (_label, search) => {
    renderCallback(search);
    expect(screen.getByText('Connection Failed')).toBeInTheDocument();
    expect(screen.queryByText('Finishing Connection...')).toBeNull();
    await settle();
    expect(completeGoogleAuth).not.toHaveBeenCalled();
  });

  it('exchanges the code exactly once, shows success, then returns to the dashboard', async () => {
    completeGoogleAuth.mockResolvedValue({});
    renderCallback('?code=abc&state=xyz');
    expect(screen.getByText('Finishing Connection...')).toBeInTheDocument();

    expect(await screen.findByText('Successfully Linked!')).toBeInTheDocument();
    await settle();
    expect(completeGoogleAuth).toHaveBeenCalledTimes(1);
    expect(completeGoogleAuth).toHaveBeenCalledWith('abc', 'xyz');

    expect(await screen.findByText('Admin dashboard', {}, { timeout: 4000 })).toBeInTheDocument();
    expect(completeGoogleAuth).toHaveBeenCalledTimes(1);
  });

  it('shows the error state when the exchange fails, after exactly one attempt', async () => {
    completeGoogleAuth.mockRejectedValue(new Error('invalid_grant'));
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    renderCallback('?code=abc&state=xyz');

    expect(await screen.findByText('Connection Failed')).toBeInTheDocument();
    await settle();
    expect(completeGoogleAuth).toHaveBeenCalledTimes(1);
    expect(screen.queryByText('Successfully Linked!')).toBeNull();
    errorSpy.mockRestore();
  });
});

// ---------------------------------------------------------------------------
// Platform pages
// ---------------------------------------------------------------------------
describe('PlatformAdmin tenant list loading', () => {
  const renderPage = () => render(<MemoryRouter><PlatformAdmin /></MemoryRouter>);

  it('loads tenants exactly once on mount and shows them', async () => {
    getPlatformTenants.mockResolvedValue({ tenants: [{ company_id: 'tenant_one', display_name: 'Tenant One' }] });
    renderPage();
    expect(await screen.findByText('Tenant One')).toBeInTheDocument();
    await settle();
    expect(getPlatformTenants).toHaveBeenCalledTimes(1);
  });

  it('shows the error, then Retry resets the error and reloads successfully', async () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    getPlatformTenants.mockRejectedValueOnce(new Error('Platform unavailable'));
    renderPage();
    expect(await screen.findByText(/Platform unavailable/)).toBeInTheDocument();

    const retry = deferred();
    getPlatformTenants.mockReturnValueOnce(retry.promise);
    fireEvent.click(screen.getByRole('button', { name: /Retry Fetching Data/ }));
    // Retry immediately clears the stale error and shows loading again.
    await waitFor(() => expect(screen.queryByText(/Platform unavailable/)).toBeNull());
    expect(document.querySelector('.platform-loading-container')).not.toBeNull();

    await act(async () => { retry.resolve({ tenants: [{ company_id: 'tenant_two', display_name: 'Tenant Two' }] }); });
    expect(await screen.findByText('Tenant Two')).toBeInTheDocument();
    expect(getPlatformTenants).toHaveBeenCalledTimes(2);
    errorSpy.mockRestore();
  });
});

describe('PlatformAuditLog loading', () => {
  const renderPage = () => render(<MemoryRouter><PlatformAuditLog /></MemoryRouter>);

  it('loads audit history exactly once on mount', async () => {
    getPlatformAudit.mockResolvedValue({ audits: [] });
    renderPage();
    await waitFor(() => expect(getPlatformAudit).toHaveBeenCalledTimes(1));
    await settle();
    expect(getPlatformAudit).toHaveBeenCalledTimes(1);
  });

  it('Retry after a failure clears the error and loads again', async () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    getPlatformAudit.mockRejectedValueOnce(new Error('Audit unavailable'));
    renderPage();
    expect(await screen.findByText(/Audit unavailable/)).toBeInTheDocument();

    getPlatformAudit.mockResolvedValueOnce({ audits: [] });
    fireEvent.click(screen.getByRole('button', { name: /Retry Fetching Logs/ }));
    await waitFor(() => expect(screen.queryByText(/Audit unavailable/)).toBeNull());
    expect(getPlatformAudit).toHaveBeenCalledTimes(2);
    errorSpy.mockRestore();
  });
});

describe('PlatformTenantDetail tenant identity', () => {
  const tenantRecord = (companyId, name) => ({
    company_id: companyId,
    profile: { display_name: name },
    subscription: { tier: 'starter', status: 'active' },
  });

  const Nav = () => {
    const navigate = useNavigate();
    return (
      <>
        <button onClick={() => navigate('/platform-admin/tenants/tenant_b')}>Go to B</button>
      </>
    );
  };

  const renderAt = (companyId) => render(
    <MemoryRouter initialEntries={[`/platform-admin/tenants/${companyId}`]}>
      <Nav />
      <Routes>
        <Route path="/platform-admin/tenants/:companyId" element={<PlatformTenantDetail />} />
      </Routes>
    </MemoryRouter>
  );

  it('never shows the previous tenant while the next tenant is loading', async () => {
    getPlatformTenant.mockImplementation((id) => (
      id === 'tenant_a' ? Promise.resolve(tenantRecord('tenant_a', 'Alpha Pets')) : pendingB.promise
    ));
    const pendingB = deferred();
    renderAt('tenant_a');
    expect(await screen.findByRole('heading', { name: 'Alpha Pets' })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Go to B' }));
    // Same component instance, new route param: Alpha must disappear immediately.
    expect(screen.queryByRole('heading', { name: 'Alpha Pets' })).toBeNull();
    expect(screen.getByText(/Retrieving tenant metadata/)).toBeInTheDocument();

    await act(async () => { pendingB.resolve(tenantRecord('tenant_b', 'Bravo Pets')); });
    expect(await screen.findByRole('heading', { name: 'Bravo Pets' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Alpha Pets' })).toBeNull();
    expect(getPlatformTenant.mock.calls).toEqual([['tenant_a'], ['tenant_b']]);
  });

  it('Retry after a load failure clears the error and loads the same tenant again', async () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    getPlatformTenant.mockRejectedValueOnce(new Error('Tenant read failed'));
    renderAt('tenant_a');
    expect(await screen.findByText('Tenant read failed')).toBeInTheDocument();

    getPlatformTenant.mockResolvedValueOnce(tenantRecord('tenant_a', 'Alpha Pets'));
    fireEvent.click(screen.getByRole('button', { name: /Retry Fetching Details/ }));
    expect(await screen.findByRole('heading', { name: 'Alpha Pets' })).toBeInTheDocument();
    expect(screen.queryByText('Tenant read failed')).toBeNull();
    expect(getPlatformTenant.mock.calls).toEqual([['tenant_a'], ['tenant_a']]);
    errorSpy.mockRestore();
  });
});

// ---------------------------------------------------------------------------
// ClientPortal session and booking initialization
// ---------------------------------------------------------------------------
describe('ClientPortal session initialization', () => {
  const session = { getIdToken: () => ({ payload: { email: 'client@example.test' } }) };
  const booking = {
    PK: 'REQ#r1', request_id: 'r1', client_id: 'c1', status: 'APPROVED',
    start_date: '2026-12-01', pet_names: 'Portal Pet', service_type: 'WALK_20MIN',
  };

  it('loads bookings exactly once for a client session', async () => {
    getSession.mockResolvedValue(session);
    getEffectiveRole.mockReturnValue('client');
    getClientRequests.mockResolvedValue({ requests: [booking] });
    render(<ClientPortal />);
    expect(await screen.findByText(/Portal Pet/)).toBeInTheDocument();
    await settle();
    expect(getClientRequests).toHaveBeenCalledTimes(1);
  });

  it('denies a staff session without loading any bookings', async () => {
    getSession.mockResolvedValue(session);
    getEffectiveRole.mockReturnValue('staff');
    render(<ClientPortal />);
    expect(await screen.findByText(/Access denied. Staff members must use the Staff Portal./)).toBeInTheDocument();
    await settle();
    expect(getClientRequests).not.toHaveBeenCalled();
  });

  it('shows the login form and loads nothing without a session', async () => {
    getSession.mockResolvedValue(null);
    render(<ClientPortal />);
    expect(await screen.findByText('Client Login')).toBeInTheDocument();
    await settle();
    expect(getClientRequests).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// CareCard payment / cooldown / pet-switch state
// ---------------------------------------------------------------------------
describe('CareCard state derived from the pet prop', () => {
  const baseProps = {
    onClose: vi.fn(),
    onUpdate: vi.fn().mockResolvedValue(undefined),
    onStatusUpdate: vi.fn().mockResolvedValue(undefined),
    userRole: 'owner',
  };
  const paymentPet = (cents, overrides = {}) => ({
    pet_id: 'pet-1',
    name: 'Buddy',
    client_id: 'client-1',
    status: 'APPROVED',
    _originItem: {
      request_id: 'req-1',
      client_id: 'client-1',
      client_email: 'client@example.test',
      status: 'APPROVED',
      payment_amount_cents: cents,
      ...overrides,
    },
  });
  const openQuoteTab = () => fireEvent.click(screen.getByText('Meet & Greet / Quote'));
  // The Stripe "Amount to Charge" input (the quote editor has its own text amount field).
  const amountInput = () => {
    const input = document.querySelector('input[type="number"][step="0.01"][placeholder="0.00"]');
    expect(input).not.toBeNull();
    return input;
  };

  it('starts with the persisted payment amount and keeps edits until the pet changes', () => {
    const pet = paymentPet(1500);
    const { rerender } = render(<CareCard {...baseProps} pet={pet} />);
    openQuoteTab();
    expect(amountInput()).toHaveValue(15);

    fireEvent.change(amountInput(), { target: { value: '20' } });
    // Same pet object: an unrelated re-render must not discard the edit.
    rerender(<CareCard {...baseProps} pet={pet} />);
    expect(amountInput()).toHaveValue(20);

    // A different pet record resets the amount to that record's persisted value.
    rerender(<CareCard {...baseProps} pet={paymentPet(2500)} />);
    expect(amountInput()).toHaveValue(25);
  });

  it('clears the email cooldown when the sent timestamp is removed', () => {
    const linkFields = { payment_status: 'payment_link_sent', stripe_payment_url: 'https://example.test/pay', stripe_checkout_session_id: 'cs_test_1' };
    const sentPet = paymentPet(1500, { ...linkFields, payment_email_sent_at: new Date(Date.now() - 30000).toISOString() });
    const { rerender } = render(<CareCard {...baseProps} pet={sentPet} />);
    openQuoteTab();
    expect(screen.getByRole('button', { name: /Send Payment Email \(Wait \d+s\)/ })).toBeDisabled();

    rerender(<CareCard {...baseProps} pet={paymentPet(1500, linkFields)} />);
    const button = screen.getByRole('button', { name: 'Send Payment Email' });
    expect(button).not.toBeDisabled();
  });

  it('auto-selects the newly added pet on first render and edits that pet', () => {
    const household = {
      pet_id: 'pet-1',
      name: 'Household',
      client_id: 'client-1',
      status: 'APPROVED',
      _allPets: [
        { pet_id: 'pet-1', name: 'Rex', species: 'DOG' },
        { pet_id: 'pet-2', name: 'Bella', species: 'CAT' },
      ],
      _newPetIndex: 1,
      _originItem: { request_id: 'req-1', client_id: 'client-1', status: 'APPROVED' },
    };
    render(<CareCard {...baseProps} pet={household} />);
    expect(screen.getByRole('heading', { level: 1, name: 'Bella' })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Edit Record' }));
    expect(screen.getByDisplayValue('Bella')).toBeInTheDocument();
  });

  it('re-initializes the edit form for the pet selected via its chip', () => {
    const household = {
      pet_id: 'pet-1',
      name: 'Household',
      client_id: 'client-1',
      status: 'APPROVED',
      _allPets: [
        { pet_id: 'pet-1', name: 'Rex', species: 'DOG' },
        { pet_id: 'pet-2', name: 'Bella', species: 'CAT' },
      ],
      _originItem: { request_id: 'req-1', client_id: 'client-1', status: 'APPROVED' },
    };
    render(<CareCard {...baseProps} pet={household} />);
    expect(screen.getByRole('heading', { level: 1, name: 'Rex' })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Bella' }));
    expect(screen.getByRole('heading', { level: 1, name: 'Bella' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Edit Record' }));
    expect(screen.getByDisplayValue('Bella')).toBeInTheDocument();
    expect(screen.queryByDisplayValue('Rex')).toBeNull();
  });
});
