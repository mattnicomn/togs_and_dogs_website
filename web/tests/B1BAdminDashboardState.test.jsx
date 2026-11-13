/**
 * B1-B regression coverage for AdminDashboard state that moved out of effects:
 * - staff RBAC presentation: a staff role always ends on the Scheduler;
 * - stale selections are cleared when the status filter changes, independently of
 *   (and before) the refresh triggered by that change;
 * - the mount-only auth check runs once and keeps the tenant-mismatch error path.
 */
import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import AdminDashboard from '../src/components/AdminDashboard';
import { getEffectiveRole, getSession } from '../src/api/auth';
import {
  getAdminRequests,
  getClients,
  getGoogleStatus,
  getStaff,
  getTenantInfo,
} from '../src/api/client';
import { TENANT_ACCESS_ERROR } from '../src/utils/tenantContext';

vi.mock('../src/api/auth', () => ({
  signIn: vi.fn(),
  forgotPassword: vi.fn(),
  confirmForgotPassword: vi.fn(),
  getSession: vi.fn(),
  getEffectiveRole: vi.fn()
}));

vi.mock('../src/api/client', () => ({
  getAdminRequests: vi.fn(),
  reviewRequest: vi.fn(),
  assignWorker: vi.fn(),
  getGoogleStatus: vi.fn(),
  initiateGoogleAuth: vi.fn(),
  getPet: vi.fn(),
  updatePet: vi.fn(),
  createPet: vi.fn(),
  processCancellationDecision: vi.fn(),
  performAdminAction: vi.fn(),
  purgeRecord: vi.fn(),
  purgeRecordsBulk: vi.fn(),
  getStaff: vi.fn(),
  createStaff: vi.fn(),
  updateStaff: vi.fn(),
  disableStaff: vi.fn(),
  onboardStaff: vi.fn(),
  linkCognitoUser: vi.fn(),
  resendInvite: vi.fn(),
  resetStaffPassword: vi.fn(),
  setStaffTempPassword: vi.fn(),
  getClients: vi.fn(),
  createClient: vi.fn(),
  updateClient: vi.fn(),
  disableClient: vi.fn(),
  onboardClient: vi.fn(),
  resendClientInvite: vi.fn(),
  resetClientPassword: vi.fn(),
  setClientTempPassword: vi.fn(),
  linkClientCognitoUser: vi.fn(),
  getExportData: vi.fn(),
  createAdminBooking: vi.fn(),
  listAdminClientPets: vi.fn(),
  getTenantInfo: vi.fn()
}));

window.HTMLElement.prototype.scrollIntoView = vi.fn();
window.alert = vi.fn();

const sessionFor = (email, companyId) => ({
  getIdToken: () => ({
    payload: { email, sub: `${email}-sub`, name: 'B1B Test User', 'custom:company_id': companyId }
  })
});

const booking = {
  PK: 'JOB#job-approved',
  SK: 'REQ#req-approved',
  entity_type: 'JOB',
  workflow_type: 'VISIT_BOOKING',
  job_id: 'job-approved',
  request_id: 'req-approved',
  client_id: 'client-1',
  status: 'APPROVED',
  client_name: 'Selection Client',
  pet_name: 'Selection Pet',
  pet_names: 'Selection Pet',
  service_type: 'WALK_20MIN',
  start_date: new Date().toLocaleDateString('sv-SE')
};

const deferred = () => {
  let resolve;
  const promise = new Promise((res) => { resolve = res; });
  return { promise, resolve };
};

beforeEach(() => {
  vi.clearAllMocks();
  getGoogleStatus.mockResolvedValue({ status: 'CONNECTED' });
  getTenantInfo.mockResolvedValue({ display_name: 'Synthetic Test Company', calendar_enabled: true });
  getStaff.mockResolvedValue({ staff: [] });
  getClients.mockResolvedValue({ clients: [] });
  getAdminRequests.mockResolvedValue({ requests: [booking] });
});

describe('AdminDashboard staff RBAC presentation', () => {
  it('keeps a staff user on the Scheduler even when a stat card requests the Request List', async () => {
    getSession.mockResolvedValue(sessionFor('sitter@example.test', 'tog_and_dogs'));
    getEffectiveRole.mockReturnValue('staff');
    render(<AdminDashboard />);
    expect(await screen.findByRole('heading', { name: 'Master Scheduler' })).toBeInTheDocument();

    fireEvent.click(await screen.findByRole('button', { name: /Intake Queue:/ }));

    expect(screen.getByRole('heading', { name: 'Master Scheduler' })).toBeInTheDocument();
    expect(document.querySelector('.request-table')).toBeNull();
  });

  it('lets an owner open the Request List from the same stat card', async () => {
    getSession.mockResolvedValue(sessionFor('owner@example.test', 'tog_and_dogs'));
    getEffectiveRole.mockReturnValue('owner');
    render(<AdminDashboard />);
    expect(await screen.findByRole('heading', { name: 'Master Scheduler' })).toBeInTheDocument();

    fireEvent.click(await screen.findByRole('button', { name: /Intake Queue:/ }));
    await waitFor(() => expect(document.querySelector('.request-table')).not.toBeNull());
    expect(screen.queryByRole('heading', { name: 'Master Scheduler' })).toBeNull();
  });
});

describe('AdminDashboard selection reset on filter change', () => {
  it('clears selected visits as soon as the status filter changes, before the new data arrives', async () => {
    getSession.mockResolvedValue(sessionFor('owner@example.test', 'tog_and_dogs'));
    getEffectiveRole.mockReturnValue('owner');
    render(<AdminDashboard />);
    fireEvent.click(await screen.findByRole('button', { name: 'Request List' }));
    fireEvent.click(await screen.findByRole('button', { name: /All Active/ }));
    await screen.findByText(/Selection Client/);
    // Let the All Active click's debounced refresh complete before selecting.
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 250)); });

    fireEvent.click(screen.getByRole('checkbox', { name: 'Select Selection Pet' }));
    expect(await screen.findByText('visits selected')).toBeInTheDocument();

    // Hold the refresh caused by the filter change, so only the filter-keyed reset can
    // clear the selection (the fetch-completion reset cannot run yet).
    const pending = deferred();
    getAdminRequests.mockImplementation(() => pending.promise);
    fireEvent.click(screen.getByRole('button', { name: /Needs Assignment:/ }));
    expect(screen.queryByText('visits selected')).toBeNull();

    await act(async () => { pending.resolve({ requests: [booking] }); });
  });
});

describe('AdminDashboard mount-only auth check', () => {
  it('runs the session check once on mount', async () => {
    getSession.mockResolvedValue(sessionFor('owner@example.test', 'tog_and_dogs'));
    getEffectiveRole.mockReturnValue('owner');
    render(<AdminDashboard />);
    expect(await screen.findByRole('heading', { name: 'Master Scheduler' })).toBeInTheDocument();
    await act(async () => { for (let i = 0; i < 10; i += 1) await Promise.resolve(); });
    expect(getSession).toHaveBeenCalled();
    const sessionReadsAfterMount = getSession.mock.calls.length;
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 150)); });
    expect(getSession.mock.calls.length).toBe(sessionReadsAfterMount);
  });

  it('keeps the tenant access error when the session read fails on a tenant route', async () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    getSession.mockRejectedValue(new Error('session unavailable'));
    render(<AdminDashboard expectedTenantSlug="test-tenant-alpha" />);
    expect(await screen.findByText(TENANT_ACCESS_ERROR)).toBeInTheDocument();
    expect(getAdminRequests).not.toHaveBeenCalled();
    errorSpy.mockRestore();
  });
});
