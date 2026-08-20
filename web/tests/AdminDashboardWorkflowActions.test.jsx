import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import AdminDashboard from '../src/components/AdminDashboard';
import { getEffectiveRole, getSession } from '../src/api/auth';
import {
  assignWorker,
  createAdminBooking,
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
  describeGuidedWorkflowAction,
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

const makeCustomerIntake = (status = 'MG_COMPLETED', overrides = {}) => ({
  PK: 'REQ#intake-request-1',
  SK: 'CLIENT#client-1',
  entity_type: 'REQUEST',
  workflow_type: 'CUSTOMER_INTAKE',
  request_id: 'intake-request-1',
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

const getApprovalHandoffRefreshCalls = () => getAdminRequests.mock.calls.filter(
  args => args.length === 1 && args[0] === 'ALL'
);

const mockApprovalHandoffRefreshes = (originalRequest, refreshedRequests) => {
  let refreshIndex = 0;
  getAdminRequests.mockImplementation((...args) => {
    if (args.length !== 1) {
      return Promise.resolve({ requests: [originalRequest] });
    }

    const responseIndex = Math.min(refreshIndex, refreshedRequests.length - 1);
    refreshIndex += 1;
    return Promise.resolve({ requests: [refreshedRequests[responseIndex]] });
  });
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

  it('describes customer-intake approval as an approval-to-Scheduler handoff', () => {
    const item = makeCustomerIntake('MG_COMPLETED');

    expect(resolveGuidedWorkflowAction(item, ['APPROVE', 'CANCEL'])).toEqual({
      id: 'APPROVE',
      label: 'Approve & Open Scheduler',
      semantic: GUIDED_ACTION_SEMANTICS.APPROVAL_SCHEDULER_HANDOFF,
      target: 'SCHEDULER'
    });
    expect(describeGuidedWorkflowAction(item, 'APPROVE').label).toBe('Approve & Open Scheduler');
  });

  it('keeps visit-booking approval as the standard status transition', () => {
    expect(describeGuidedWorkflowAction(makeBooking('PENDING_REVIEW'), 'APPROVE')).toEqual({
      id: 'APPROVE',
      semantic: GUIDED_ACTION_SEMANTICS.STATUS_TRANSITION
    });
  });
});

describe('AdminDashboard E1 and E2 workflow handoffs', () => {
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

  it('preserves the existing standard visit-booking approval transition', async () => {
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

  it.each([
    ['job_id', { job_id: 'job-intake-1' }],
    ['job_ids', { job_ids: ['job-intake-1', 'job-intake-2'] }]
  ])('approves once and opens Scheduler when %s is immediately ready', async (_field, readyFields) => {
    const request = makeCustomerIntake();
    await renderRequestList(request);
    getAdminRequests.mockClear();
    createAdminBooking.mockClear();
    mockApprovalHandoffRefreshes(request, [
      { ...request, status: 'APPROVED', pet_name: 'Refreshed Workflow Pet', pet_names: 'Refreshed Workflow Pet', ...readyFields }
    ]);

    fireEvent.click(screen.getByRole('button', { name: /Actions for Workflow Pet/ }));
    fireEvent.click(await screen.findByRole('button', { name: 'Approve & Open Scheduler' }));

    expect(await screen.findByRole('heading', { name: 'Master Scheduler' })).toBeInTheDocument();
    expect(await screen.findByText(/Refreshed Workflow Pet/)).toBeInTheDocument();
    expect(reviewRequest).toHaveBeenCalledTimes(1);
    expect(reviewRequest).toHaveBeenCalledWith(
      request.request_id,
      request.client_id,
      'APPROVED',
      ''
    );
    expect(getApprovalHandoffRefreshCalls().length).toBeGreaterThanOrEqual(1);
    expect(getAdminRequests).toHaveBeenCalledWith('ALL');
    expect(createAdminBooking).not.toHaveBeenCalled();
    expect(reviewRequest.mock.calls.flat()).not.toContain('APPROVE_AND_SCHEDULE');
  });

  it('boundedly refetches the same request until delayed job readiness appears', async () => {
    const request = makeCustomerIntake();
    await renderRequestList(request);
    getAdminRequests.mockClear();
    mockApprovalHandoffRefreshes(request, [
      { ...request, status: 'APPROVED' },
      { ...request, status: 'APPROVED', job_id: 'job-intake-1' }
    ]);

    fireEvent.click(screen.getByRole('button', { name: /Actions for Workflow Pet/ }));
    const action = await screen.findByRole('button', { name: 'Approve & Open Scheduler' });
    vi.useFakeTimers();
    try {
      await act(async () => {
        fireEvent.click(action);
        await Promise.resolve();
      });
      expect(getApprovalHandoffRefreshCalls()).toHaveLength(1);

      await act(async () => {
        await vi.advanceTimersByTimeAsync(500);
      });

      expect(screen.getByRole('heading', { name: 'Master Scheduler' })).toBeInTheDocument();
      expect(getApprovalHandoffRefreshCalls()).toHaveLength(2);
      expect(reviewRequest).toHaveBeenCalledTimes(1);
      expect(createAdminBooking).not.toHaveBeenCalled();
    } finally {
      vi.useRealTimers();
    }
  });

  it('opens Scheduler with a warning after the bounded job-initialization timeout', async () => {
    const request = makeCustomerIntake();
    await renderRequestList(request);
    getAdminRequests.mockClear();
    mockApprovalHandoffRefreshes(request, [{ ...request, status: 'APPROVED' }]);

    fireEvent.click(screen.getByRole('button', { name: /Actions for Workflow Pet/ }));
    const action = await screen.findByRole('button', { name: 'Approve & Open Scheduler' });
    vi.useFakeTimers();
    try {
      await act(async () => {
        fireEvent.click(action);
        await Promise.resolve();
      });
      await act(async () => {
        await vi.advanceTimersByTimeAsync(2000);
      });

      expect(screen.getByRole('heading', { name: 'Master Scheduler' })).toBeInTheDocument();
      expect(screen.getByText('Approved successfully; job setup is still initializing. Refresh before assigning.')).toBeInTheDocument();
      expect(getApprovalHandoffRefreshCalls()).toHaveLength(5);
      expect(reviewRequest).toHaveBeenCalledTimes(1);
      expect(createAdminBooking).not.toHaveBeenCalled();
    } finally {
      vi.useRealTimers();
    }
  });

  it('does not poll or navigate when canonical approval fails', async () => {
    const request = makeCustomerIntake();
    await renderRequestList(request);
    getAdminRequests.mockClear();
    reviewRequest.mockRejectedValueOnce(new Error('Approval rejected by backend'));

    fireEvent.click(screen.getByRole('button', { name: /Actions for Workflow Pet/ }));
    fireEvent.click(await screen.findByRole('button', { name: 'Approve & Open Scheduler' }));

    expect(await screen.findByText('Action failed: Approval rejected by backend')).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Master Scheduler' })).not.toBeInTheDocument();
    expect(getApprovalHandoffRefreshCalls()).toHaveLength(0);
    expect(reviewRequest).toHaveBeenCalledTimes(1);
    expect(createAdminBooking).not.toHaveBeenCalled();
  });

  it('guards an in-flight approval handoff against repeated clicks', async () => {
    const request = makeCustomerIntake();
    let resolveApproval;
    reviewRequest.mockImplementationOnce(() => new Promise(resolve => {
      resolveApproval = resolve;
    }));
    await renderRequestList(request);
    getAdminRequests.mockClear();
    mockApprovalHandoffRefreshes(request, [
      { ...request, status: 'APPROVED', job_id: 'job-intake-1' }
    ]);

    fireEvent.click(screen.getByRole('button', { name: /Actions for Workflow Pet/ }));
    const action = await screen.findByRole('button', { name: 'Approve & Open Scheduler' });
    fireEvent.click(action);
    fireEvent.click(action);

    expect(reviewRequest).toHaveBeenCalledTimes(1);
    expect(getApprovalHandoffRefreshCalls()).toHaveLength(0);

    resolveApproval({ message: 'Approved successfully.' });
    expect(await screen.findByRole('heading', { name: 'Master Scheduler' })).toBeInTheDocument();
    expect(reviewRequest).toHaveBeenCalledTimes(1);
    expect(createAdminBooking).not.toHaveBeenCalled();
  });
});
