import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import AdminDashboard from '../src/components/AdminDashboard';
import { getEffectiveRole, getSession } from '../src/api/auth';
import {
  getAdminRequest,
  getAdminRequests,
  getClients,
  getGoogleStatus,
  getStaff,
  getTenantInfo,
  performAdminAction,
  processCancellationDecision,
  reviewRequest
} from '../src/api/client';

vi.mock('../src/api/auth', () => ({
  signIn: vi.fn(), forgotPassword: vi.fn(), confirmForgotPassword: vi.fn(),
  getSession: vi.fn(), getEffectiveRole: vi.fn()
}));

vi.mock('../src/api/client', () => ({
  getAdminRequests: vi.fn(), getAdminRequest: vi.fn(), reviewRequest: vi.fn(), assignWorker: vi.fn(),
  getGoogleStatus: vi.fn(), initiateGoogleAuth: vi.fn(), getPet: vi.fn(), updatePet: vi.fn(),
  createPet: vi.fn(), processCancellationDecision: vi.fn(), performAdminAction: vi.fn(),
  purgeRecord: vi.fn(), purgeRecordsBulk: vi.fn(), getStaff: vi.fn(), createStaff: vi.fn(),
  updateStaff: vi.fn(), disableStaff: vi.fn(), onboardStaff: vi.fn(), linkCognitoUser: vi.fn(),
  resendInvite: vi.fn(), resetStaffPassword: vi.fn(), setStaffTempPassword: vi.fn(),
  getClients: vi.fn(), createClient: vi.fn(), updateClient: vi.fn(), disableClient: vi.fn(),
  onboardClient: vi.fn(), resendClientInvite: vi.fn(), resetClientPassword: vi.fn(),
  setClientTempPassword: vi.fn(), linkClientCognitoUser: vi.fn(), getExportData: vi.fn(),
  createAdminBooking: vi.fn(), listAdminClientPets: vi.fn(), getTenantInfo: vi.fn()
}));

window.HTMLElement.prototype.scrollIntoView = vi.fn();
window.alert = vi.fn();

const CYCLE = '6f1c2a3b-4d5e-4f60-8a7b-9c0d1e2f3a4b';
const mockSession = {
  getIdToken: () => ({ payload: { email: 'owner@example.test', sub: 'owner-sub', name: 'Owner' } })
};

const pendingRow = (overrides = {}) => ({
  PK: 'REQ#req-cancel-1', SK: 'CLIENT#client-1', entity_type: 'REQUEST',
  workflow_type: 'VISIT_BOOKING', request_id: 'req-cancel-1', client_id: 'client-1',
  status: 'CANCELLATION_REQUESTED', cancellation_request_id: CYCLE,
  client_name: 'Cancel Client', pet_name: 'Cancel Pet', pet_names: 'Cancel Pet',
  service_type: 'WALK_20MIN', start_date: new Date().toLocaleDateString('sv-SE'),
  ...overrides
});

const openRowMenu = async (row) => {
  getAdminRequests.mockResolvedValue({ requests: [row] });
  render(<AdminDashboard />);
  fireEvent.click(await screen.findByRole('button', { name: 'Request List' }));
  fireEvent.click(await screen.findByRole('button', { name: /All Active/ }));
  await screen.findByText(/Cancel Client/);
  fireEvent.click(await screen.findByRole('button', { name: 'Actions for Cancel Pet' }));
};

describe('AdminDashboard WEB-CANCEL-1 cancellation decision workflow', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.confirm = vi.fn(() => true);
    window.prompt = vi.fn(() => 'note');
    getSession.mockResolvedValue(mockSession);
    getGoogleStatus.mockResolvedValue({ status: 'CONNECTED' });
    getTenantInfo.mockResolvedValue({ display_name: 'Synthetic Co', calendar_provider: 'google', calendar_enabled: true });
    getStaff.mockResolvedValue({ staff: [] });
    getClients.mockResolvedValue({ clients: [] });
    reviewRequest.mockResolvedValue({ message: 'Status updated.' });
    performAdminAction.mockResolvedValue({ message: 'Action complete.' });
  });

  it.each(['owner', 'admin'])('%s opens the explicit decision modal, never window.confirm/prompt', async (role) => {
    getEffectiveRole.mockReturnValue(role);
    getAdminRequest.mockResolvedValue(pendingRow());
    await openRowMenu(pendingRow());
    fireEvent.click(await screen.findByRole('button', { name: 'Review Cancellation' }));
    expect(await screen.findByRole('button', { name: 'Approve Cancellation' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Deny Cancellation' })).toBeInTheDocument();
    expect(window.confirm).not.toHaveBeenCalled();
    expect(window.prompt).not.toHaveBeenCalled();
    expect(processCancellationDecision).not.toHaveBeenCalled();
  });

  it('Dismiss sends nothing and closes the modal', async () => {
    getEffectiveRole.mockReturnValue('owner');
    getAdminRequest.mockResolvedValue(pendingRow());
    await openRowMenu(pendingRow());
    fireEvent.click(await screen.findByRole('button', { name: 'Review Cancellation' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Dismiss' }));
    await waitFor(() => expect(screen.queryByTestId('cancellation-decision-modal')).toBeNull());
    expect(processCancellationDecision).not.toHaveBeenCalled();
    expect(reviewRequest).not.toHaveBeenCalled();
  });

  it('a confirmed decision goes to the cancellation endpoint, never /admin/review', async () => {
    getEffectiveRole.mockReturnValue('owner');
    getAdminRequest.mockResolvedValue(pendingRow());
    processCancellationDecision.mockResolvedValue({ message: 'Cancellation request denied.', warnings: [] });
    await openRowMenu(pendingRow());
    fireEvent.click(await screen.findByRole('button', { name: 'Review Cancellation' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Deny Cancellation' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Confirm Deny Cancellation' }));
    await waitFor(() => expect(processCancellationDecision).toHaveBeenCalledWith(
      'req-cancel-1', 'client-1', 'DENY', '', CYCLE));
    expect(reviewRequest).not.toHaveBeenCalled();
  });

  it('pending rows offer no review-status transitions; archive stays a lifecycle action', async () => {
    getEffectiveRole.mockReturnValue('owner');
    await openRowMenu(pendingRow());
    expect(screen.queryByRole('button', { name: 'Cancel Request' })).toBeNull();
    expect(screen.getByRole('button', { name: 'Review Cancellation' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Archive' })).toBeInTheDocument();
    expect(reviewRequest).not.toHaveBeenCalled();
  });

  it('an ordinary row keeps its existing review transition', async () => {
    getEffectiveRole.mockReturnValue('owner');
    const row = pendingRow({ status: 'PENDING_REVIEW', cancellation_request_id: undefined });
    await openRowMenu(row);
    fireEvent.click(await screen.findByRole('button', { name: 'Quote' }));
    await waitFor(() => expect(reviewRequest).toHaveBeenCalledWith('req-cancel-1', 'client-1', 'QUOTE_NEEDED', ''));
    expect(processCancellationDecision).not.toHaveBeenCalled();
  });
});
