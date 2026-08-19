import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import AdminDashboard from '../src/components/AdminDashboard';
import { getEffectiveRole, getSession } from '../src/api/auth';
import {
  assignWorker,
  getAdminRequests,
  getClients,
  getGoogleStatus,
  getStaff,
  getTenantInfo,
  initiateGoogleAuth,
  performAdminAction,
  reviewRequest
} from '../src/api/client';
import {
  GUIDED_ACTION_SEMANTICS,
  resolveGuidedWorkflowAction
} from '../src/utils/workflowActions';

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

const mockSession = {
  getIdToken: () => ({
    payload: {
      email: 'owner@example.test',
      sub: 'owner-e1-test',
      name: 'Owner E1 Test'
    }
  })
};

const makeBooking = (status, overrides = {}) => ({
  PK: `JOB#job-${status.toLowerCase()}`,
  SK: `REQ#req-${status.toLowerCase()}`,
  entity_type: 'JOB',
  workflow_type: 'VISIT_BOOKING',
  job_id: `job-${status.toLowerCase()}`,
  request_id: `req-${status.toLowerCase()}`,
  client_id: 'client-1',
  status,
  client_name: 'Workflow Client',
  pet_name: 'Workflow Pet',
  pet_names: 'Workflow Pet',
  service_type: 'WALK_20MIN',
  start_date: new Date().toLocaleDateString('sv-SE'),
  ...overrides
});

const renderRequestList = async (request) => {
  getAdminRequests.mockResolvedValue({ requests: [request] });
  render(<AdminDashboard />);
  fireEvent.click(await screen.findByRole('button', { name: 'Request List' }));
  fireEvent.click(await screen.findByRole('button', { name: /All Active/ }));
  await screen.findByText(/Workflow Client/);
};

describe('guided workflow action resolver', () => {
  it.each(['APPROVED', 'BOOKED', 'JOB_CREATED'])('%s resolves to the assignment UI handoff', status => {
    expect(resolveGuidedWorkflowAction({ status }, ['ASSIGN'])).toEqual({
      id: 'ASSIGN',
      label: 'Assign Sitter',
      semantic: GUIDED_ACTION_SEMANTICS.ASSIGNMENT_HANDOFF
    });
  });

  it.each(['ASSIGNED', 'SCHEDULED'])('%s resolves to local calendar navigation', status => {
    expect(resolveGuidedWorkflowAction({ status, worker_id: 'sitter@example.test' }, ['COMPLETE'])).toEqual({
      id: 'VIEW_CALENDAR',
      label: 'View in Calendar',
      semantic: GUIDED_ACTION_SEMANTICS.CALENDAR_NAVIGATION,
      target: 'SCHEDULER'
    });
  });

  it('preserves case compatibility and treats an assigned record without a worker as needing assignment', () => {
    expect(resolveGuidedWorkflowAction({ status: 'booked' }, ['ASSIGN'])?.id).toBe('ASSIGN');
    expect(resolveGuidedWorkflowAction({ status: 'scheduled', worker_id: 'sitter@example.test' }, ['COMPLETE'])?.id).toBe('VIEW_CALENDAR');
    expect(resolveGuidedWorkflowAction({ status: 'assigned' }, ['ASSIGN'])?.id).toBe('ASSIGN');
  });

  it('preserves existing status-transition semantics and rejects unavailable transition actions', () => {
    expect(resolveGuidedWorkflowAction({ status: 'READY_FOR_APPROVAL' }, ['APPROVE'])).toEqual({
      id: 'APPROVE',
      semantic: GUIDED_ACTION_SEMANTICS.STATUS_TRANSITION
    });
    expect(resolveGuidedWorkflowAction({ status: 'APPROVED' }, ['CANCEL'])).toBeNull();
  });
});

describe('AdminDashboard E1 workflow handoffs', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getSession.mockResolvedValue(mockSession);
    getEffectiveRole.mockReturnValue('owner');
    getGoogleStatus.mockResolvedValue({ status: 'CONNECTED' });
    getTenantInfo.mockResolvedValue({
      display_name: 'Synthetic Test Company',
      calendar_provider: 'google',
      calendar_enabled: true
    });
    getStaff.mockResolvedValue({
      staff: [{
        email: 'sitter@example.test',
        display_name: 'Sitter One',
        is_active: true,
        is_assignable: true
      }]
    });
    getClients.mockResolvedValue({ clients: [] });
    reviewRequest.mockResolvedValue({ message: 'Status updated.' });
    assignWorker.mockResolvedValue({ message: 'Worker assigned.' });
    performAdminAction.mockResolvedValue({ message: 'Action complete.' });
  });

  it.each(['APPROVED', 'BOOKED', 'JOB_CREATED'])('surfaces Assign Sitter for %s', async status => {
    await renderRequestList(makeBooking(status));
    expect(await screen.findByRole('button', { name: 'Assign Sitter' })).toBeInTheDocument();
  });

  it('opens the existing selector and completes assignment through assignWorker without an ASSIGN review transition', async () => {
    const request = makeBooking('APPROVED');
    await renderRequestList(request);

    fireEvent.click(await screen.findByRole('button', { name: 'Assign Sitter' }));
    const sitterOption = await screen.findByRole('option', { name: 'Sitter One <sitter@example.test>' });
    fireEvent.change(sitterOption.closest('select'), { target: { value: 'sitter@example.test' } });

    await waitFor(() => {
      expect(assignWorker).toHaveBeenCalledWith(
        request.job_id,
        request.request_id,
        request.client_id,
        'sitter@example.test',
        'Sitter One'
      );
    });
    expect(reviewRequest).not.toHaveBeenCalledWith(
      expect.anything(),
      expect.anything(),
      'ASSIGN',
      expect.anything()
    );
  });

  it.each(['ASSIGNED', 'SCHEDULED'])('navigates %s locally to the scheduler without API or status mutation', async status => {
    await renderRequestList(makeBooking(status, { worker_id: 'sitter@example.test' }));

    getAdminRequests.mockClear();
    getStaff.mockClear();
    getClients.mockClear();
    reviewRequest.mockClear();
    assignWorker.mockClear();
    performAdminAction.mockClear();
    initiateGoogleAuth.mockClear();

    fireEvent.click(await screen.findByRole('button', { name: 'View in Calendar' }));
    expect(await screen.findByRole('heading', { name: 'Master Scheduler' })).toBeInTheDocument();

    await waitFor(() => {
      expect(getAdminRequests).not.toHaveBeenCalled();
      expect(getStaff).not.toHaveBeenCalled();
      expect(getClients).not.toHaveBeenCalled();
      expect(reviewRequest).not.toHaveBeenCalled();
      expect(assignWorker).not.toHaveBeenCalled();
      expect(performAdminAction).not.toHaveBeenCalled();
      expect(initiateGoogleAuth).not.toHaveBeenCalled();
    });
  });

  it('preserves the existing Complete transition behavior', async () => {
    const request = makeBooking('ASSIGNED', { worker_id: 'sitter@example.test' });
    await renderRequestList(request);

    fireEvent.click(screen.getByRole('button', { name: /Actions for Workflow Pet/ }));
    fireEvent.click(await screen.findByRole('button', { name: 'Complete' }));

    await waitFor(() => {
      expect(reviewRequest).toHaveBeenCalledWith(
        request.request_id,
        request.client_id,
        'COMPLETED',
        ''
      );
    });
  });

  it('preserves the existing Cancel transition', async () => {
    const booking = makeBooking('BOOKED');
    await renderRequestList(booking);
    fireEvent.click(screen.getByRole('button', { name: /Actions for Workflow Pet/ }));
    fireEvent.click(await screen.findByRole('button', { name: 'Cancel Request' }));
    await waitFor(() => expect(reviewRequest).toHaveBeenCalledWith(
      booking.request_id,
      booking.client_id,
      'CANCELLED',
      ''
    ));
  });

  it('preserves the existing intake approval transition', async () => {
    const request = makeBooking('PENDING_REVIEW');
    await renderRequestList(request);
    fireEvent.click(screen.getByRole('button', { name: /Actions for Workflow Pet/ }));
    fireEvent.click(await screen.findByRole('button', { name: 'Approve' }));
    await waitFor(() => expect(reviewRequest).toHaveBeenCalledWith(
      request.request_id,
      request.client_id,
      'APPROVED',
      ''
    ));
  });
});
