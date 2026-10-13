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

vi.mock('../src/api/auth', () => ({
  signIn: vi.fn(),
  forgotPassword: vi.fn(),
  confirmForgotPassword: vi.fn(),
  getSession: vi.fn(),
  getEffectiveRole: vi.fn(),
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
  getTenantInfo: vi.fn(),
}));

window.HTMLElement.prototype.scrollIntoView = vi.fn();
window.alert = vi.fn();

const mockSession = (email = 'user@example.test', sub = 'sub-1') => ({
  getIdToken: () => ({ payload: { email, sub, name: 'Test User' } }),
});

const schedulerTab = () => screen.getByRole('button', { name: 'Scheduler' });
const isActive = (btn) => btn.className.split(/\s+/).includes('active');

describe('AdminDashboard staff-view enforcement (Gate C3b.2n Batch 4C-1)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getSession.mockResolvedValue(mockSession());
    getGoogleStatus.mockResolvedValue({ status: 'CONNECTED' });
    getTenantInfo.mockResolvedValue({ display_name: 'Synthetic Co', calendar_enabled: true });
    getStaff.mockResolvedValue({ staff: [] });
    getClients.mockResolvedValue({ clients: [] });
    getAdminRequests.mockResolvedValue({ requests: [] });
  });

  it('1. staff users initially see the Scheduler view', async () => {
    getEffectiveRole.mockReturnValue('staff');
    render(<AdminDashboard />);

    const tab = await screen.findByRole('button', { name: 'Scheduler' });
    expect(isActive(tab)).toBe(true);
  });

  it('2. staff cannot remain on Request List after a stat card attempts to select LIST', async () => {
    getEffectiveRole.mockReturnValue('staff');
    render(<AdminDashboard />);
    await screen.findByRole('button', { name: 'Scheduler' });

    // The Intake Queue stat card calls setView('LIST'). The staff clamp must
    // return the view to SCHEDULER, so no LIST-only content appears.
    const intakeCard = screen.getByRole('button', { name: /Intake Queue/i });
    fireEvent.click(intakeCard);

    await waitFor(() => expect(isActive(schedulerTab())).toBe(true));
    // LIST-only sidebar section must never render for staff.
    expect(screen.queryByText('Staff Quick View')).not.toBeInTheDocument();
  });

  it('3. staff cannot access Staff Management or Client Management tabs', async () => {
    getEffectiveRole.mockReturnValue('staff');
    render(<AdminDashboard />);
    await screen.findByRole('button', { name: 'Scheduler' });

    expect(screen.queryByRole('button', { name: 'Request List' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Staff Management' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Client Management' })).not.toBeInTheDocument();
  });

  it('4. owner users can navigate to permitted administrative views', async () => {
    getEffectiveRole.mockReturnValue('owner');
    render(<AdminDashboard />);

    const listTab = await screen.findByRole('button', { name: 'Request List' });
    fireEvent.click(listTab);
    await waitFor(() => expect(isActive(screen.getByRole('button', { name: 'Request List' }))).toBe(true));
    // Owner is NOT clamped back to Scheduler.
    expect(isActive(schedulerTab())).toBe(false);

    const staffMgmt = screen.getByRole('button', { name: 'Staff Management' });
    fireEvent.click(staffMgmt);
    await waitFor(() => expect(isActive(screen.getByRole('button', { name: 'Staff Management' }))).toBe(true));
  });

  it('5. admin users can navigate to permitted administrative views', async () => {
    getEffectiveRole.mockReturnValue('admin');
    render(<AdminDashboard />);

    const listTab = await screen.findByRole('button', { name: 'Request List' });
    fireEvent.click(listTab);
    await waitFor(() => expect(isActive(screen.getByRole('button', { name: 'Request List' }))).toBe(true));
    expect(isActive(schedulerTab())).toBe(false);

    const clientMgmt = screen.getByRole('button', { name: 'Client Management' });
    fireEvent.click(clientMgmt);
    await waitFor(() => expect(isActive(screen.getByRole('button', { name: 'Client Management' }))).toBe(true));
  });

  it('6. staff-view enforcement does not cause runaway re-renders or repeated fetches', async () => {
    getEffectiveRole.mockReturnValue('staff');
    render(<AdminDashboard />);
    await screen.findByRole('button', { name: 'Scheduler' });

    // Allow any clamp/settle to run, then record the fetch count.
    await act(async () => { await new Promise((r) => setTimeout(r, 200)); });
    const afterSettle = getAdminRequests.mock.calls.length;

    // A stat-card click that attempts LIST triggers one clamp back to SCHEDULER.
    // The view-driven debounced fetch effect fires a small, BOUNDED number of
    // times (view -> LIST, clamp -> SCHEDULER); it must never loop unbounded.
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /Intake Queue/i }));
      await new Promise((r) => setTimeout(r, 400));
    });
    const afterClick = getAdminRequests.mock.calls.length;

    // Bounded enforcement cycle, never runaway growth (a true loop would be dozens).
    expect(afterClick - afterSettle).toBeLessThanOrEqual(3);
    // And the view ended back on SCHEDULER.
    expect(isActive(schedulerTab())).toBe(true);
  });

  it('7. unauthenticated users see the login form (session behavior unchanged)', async () => {
    getSession.mockResolvedValue(null);
    render(<AdminDashboard />);

    // No authenticated nav; a password field is present on the login screen.
    await waitFor(() => {
      expect(document.querySelector('input[type="password"]')).toBeTruthy();
    });
    expect(getEffectiveRole).not.toHaveBeenCalled();
  });
});
