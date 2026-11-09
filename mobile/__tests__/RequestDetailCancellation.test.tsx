/**
 * S2: cancellation decision mounted in RequestDetailScreen.
 * After a decision the screen adopts the authoritative REQUEST (exact identity) and
 * re-resolves the exact routed visit, so visit actions follow the server's child-job
 * state (APPROVE -> jobs CANCELLED, DENY -> jobs ASSIGNED). PR #67's quote editor is
 * mocked out here (covered by its own suites).
 */
import React from 'react';
import { fireEvent, render, waitFor } from '@testing-library/react-native';

const mockRead = jest.fn();
const mockDecide = jest.fn();
const mockStart = jest.fn();
const mockComplete = jest.fn();
const mockReview = jest.fn();
const mockLogout = jest.fn();
let mockRole: string | null = 'owner';

jest.mock('../src/api/client', () => ({
  getAdminRequest: (...a: any[]) => mockRead(...a),
  processCancellationDecision: (...a: any[]) => mockDecide(...a),
  startJob: (...a: any[]) => mockStart(...a),
  completeJob: (...a: any[]) => mockComplete(...a),
  reviewRequest: (...a: any[]) => mockReview(...a),
  assignWorker: jest.fn(),
}));
jest.mock('../src/auth/useAuth', () => ({ useAuth: () => ({ role: mockRole, logout: mockLogout }) }));
jest.mock('../src/hooks/useStaff', () => ({ useStaff: () => ({ staff: [], isLoading: false, error: null, refresh: jest.fn() }) }));
jest.mock('../src/components/StatusBadge', () => ({ StatusBadge: ({ status }: any) => { const { Text } = require('react-native'); return <Text>{`badge:${status}`}</Text>; } }));
jest.mock('../src/components/StaffPickerSheet', () => ({ StaffPickerSheet: () => null }));
jest.mock('../src/components/ContentContainer', () => ({ ContentContainer: ({ children }: any) => children }));
jest.mock('../src/components/AdminQuoteEditor', () => ({ AdminQuoteEditor: () => null, mergeQuoteRefresh: (p: any) => p }));
jest.mock('../src/components/ConfirmationModal', () => {
  const { Text, TouchableOpacity } = require('react-native');
  return {
    ConfirmationModal: ({ visible, title, message, onConfirm, onCancel }: any) => visible ? (
      <>
        <Text>{message}</Text>
        <TouchableOpacity onPress={onConfirm}><Text>{`Confirm ${title}`}</Text></TouchableOpacity>
        <TouchableOpacity onPress={onCancel}><Text>{`Cancel ${title}`}</Text></TouchableOpacity>
      </>
    ) : null,
  };
});

import { RequestDetailScreen } from '../src/screens/RequestDetailScreen';

const child = (extra: any = {}) => ({ job_id: 'job-b', request_id: 'req-1', occurrence_date: '2026-09-02', occurrence_window: 'MORNING', status: 'ASSIGNED', ...extra });
const booking = (extra: any = {}) => ({
  request_id: 'req-1', client_id: 'client-1', pet_name: 'Pet', client_name: 'Client',
  service_type: 'CHECK_IN', selected_dates: ['2026-09-01', '2026-09-02'], created_at: 'x',
  worker_id: 'staff@example.test', job_ids: ['job-a', 'job-b'],
  status: 'CANCELLATION_REQUESTED', cancellation_reason: 'Trip cancelled', cancellation_requested_at: '2026-11-08T10:00:00Z',
  sync_failures: [], ...extra,
});
const withJobs = (status: string, jobStatus: string) => booking({ status, job_completion_summary: { jobs: [child({ job_id: 'job-a', occurrence_date: '2026-09-01', status: jobStatus }), child({ status: jobStatus })] } });
const screen = (request: any, extra: any = {}) => render(<RequestDetailScreen route={{ params: { request, ...extra } }} navigation={{ goBack: jest.fn() }} />);

beforeEach(() => {
  jest.clearAllMocks();
  mockRole = 'owner';
  mockRead.mockReset();
  mockDecide.mockReset();
  mockStart.mockReset();
  mockComplete.mockReset();
  mockReview.mockReset();
});

describe('S2: cancellation decision in RequestDetailScreen', () => {
  it.each(['owner', 'admin'])('%s sees the decision panel after hydration for CANCELLATION_REQUESTED', async role => {
    mockRole = role;
    mockRead.mockResolvedValueOnce(booking());
    const v = await screen(booking());
    expect(await v.findByLabelText('Approve Cancellation')).toBeTruthy();
    expect(v.getByText('Reason: Trip cancelled')).toBeTruthy();
    expect(mockRead).toHaveBeenCalledTimes(1);
  });

  it.each(['staff', 'client', 'unknown', null])('role %p sees no decision controls and triggers no read', async role => {
    mockRole = role as any;
    const v = await screen(booking());
    expect(v.queryByLabelText('Approve Cancellation')).toBeNull();
    expect(v.queryByLabelText('Deny Cancellation')).toBeNull();
    expect(mockRead).not.toHaveBeenCalled();
    expect(mockDecide).not.toHaveBeenCalled();
  });

  it('APPROVE: screen adopts CANCELLED and the routed visit can no longer be started', async () => {
    mockRead
      .mockResolvedValueOnce(booking()) // hydration
      .mockResolvedValueOnce(booking()) // pre-submit guard
      .mockResolvedValueOnce(withJobs('CANCELLED', 'CANCELLED')); // post-decision refresh
    mockDecide.mockResolvedValueOnce({ message: 'Cancellation request approved.', new_status: 'CANCELLED' });
    const v = await screen(booking(), { occurrence: child() });
    expect(v.getByText('Start Visit')).toBeTruthy(); // routed exact ASSIGNED child before the decision
    await fireEvent.press(await v.findByLabelText('Approve Cancellation'));
    await fireEvent.press(v.getByText('Confirm Approve cancellation?'));
    await waitFor(() => expect(mockDecide).toHaveBeenCalledWith('req-1', 'client-1', 'APPROVE', ''));
    expect(await v.findByText(/Cancellation request approved\./)).toBeTruthy();
    expect(v.getByText('badge:CANCELLED')).toBeTruthy();
    expect(v.queryByText('Start Visit')).toBeNull();
    expect(v.queryByText('Complete Visit')).toBeNull();
    expect(v.queryByLabelText('Approve Cancellation')).toBeNull();
    expect(mockStart).not.toHaveBeenCalled();
    expect(mockReview).not.toHaveBeenCalled(); // never touches booking approval
  });

  it('DENY: screen adopts CANCELLATION_DENIED and the exact routed visit follows the server (ASSIGNED)', async () => {
    mockRead
      .mockResolvedValueOnce(booking())
      .mockResolvedValueOnce(booking())
      .mockResolvedValueOnce(withJobs('CANCELLATION_DENIED', 'ASSIGNED'));
    mockDecide.mockResolvedValueOnce({ message: 'Cancellation request denied.', new_status: 'CANCELLATION_DENIED' });
    const v = await screen(booking(), { occurrence: child() });
    await fireEvent.press(await v.findByLabelText('Deny Cancellation'));
    await fireEvent.press(v.getByText('Confirm Deny cancellation?'));
    await waitFor(() => expect(mockDecide).toHaveBeenCalledWith('req-1', 'client-1', 'DENY', ''));
    expect(await v.findByText(/stays active as Cancellation Denied/)).toBeTruthy();
    expect(v.getByText('badge:CANCELLATION_DENIED')).toBeTruthy();
    expect(v.getByText('Start Visit')).toBeTruthy(); // owner may still execute the exact ASSIGNED child (PR #68)
    expect(mockStart).not.toHaveBeenCalled();
  });

  it('a stale request at submit time is refused and the screen shows the real status', async () => {
    mockRead
      .mockResolvedValueOnce(booking())
      .mockResolvedValueOnce(withJobs('CANCELLED', 'CANCELLED'));
    const v = await screen(booking());
    await fireEvent.press(await v.findByLabelText('Approve Cancellation'));
    await fireEvent.press(v.getByText('Confirm Approve cancellation?'));
    expect(await v.findByText(/No decision was submitted/)).toBeTruthy();
    expect(mockDecide).not.toHaveBeenCalled();
    expect(v.getByText('badge:CANCELLED')).toBeTruthy();
  });

  it('hydration that reveals a different status updates the screen and offers no decision', async () => {
    mockRead.mockResolvedValueOnce(withJobs('CANCELLATION_DENIED', 'ASSIGNED'));
    const v = await screen(booking());
    await waitFor(() => expect(v.getByText('badge:CANCELLATION_DENIED')).toBeTruthy());
    expect(v.queryByLabelText('Approve Cancellation')).toBeNull();
  });

  it('existing owner booking actions are unaffected on non-cancellation bookings (no extra reads)', async () => {
    const v = await screen(booking({ status: 'PENDING_REVIEW' }));
    expect(v.getByText('Approve Booking')).toBeTruthy();
    expect(v.queryByLabelText('Approve Cancellation')).toBeNull();
    expect(mockRead).not.toHaveBeenCalled();
  });
});
