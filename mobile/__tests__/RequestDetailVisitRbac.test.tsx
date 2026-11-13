/**
 * S1-VISIT-RBAC-A1 — visit execution role policy on RequestDetailScreen.
 *
 * Policy (mobile presentation): Start, Complete and visit notes are offered to an
 * explicit allowlist — owner, admin and staff. Client, unknown, empty and null roles
 * never receive them. The backend is the authority (source contract, deployed Lambda
 * UNVERIFIED): staff must be the assigned worker (403 otherwise); owner/admin may act
 * without being the assigned worker. Exact job_id/occurrence selection, Start before
 * Complete (except the existing legacy path), confirmations, notes, reconciliation and
 * duplicate-action locks are unchanged and are exercised here for owner/admin.
 */
import React from 'react';
import { act, fireEvent, render, waitFor } from '@testing-library/react-native';

const mockStartJob = jest.fn();
const mockCompleteJob = jest.fn();
const mockGetAdminRequest = jest.fn();
const mockReviewRequest = jest.fn();
const mockLogout = jest.fn();
let mockRole: string | null | undefined = 'owner';

jest.mock('../src/api/client', () => ({
  startJob: (...args: any[]) => mockStartJob(...args),
  completeJob: (...args: any[]) => mockCompleteJob(...args),
  getAdminRequest: (...args: any[]) => mockGetAdminRequest(...args),
  reviewRequest: (...args: any[]) => mockReviewRequest(...args),
  assignWorker: jest.fn(),
}));
jest.mock('../src/auth/useAuth', () => ({ useAuth: () => ({ role: mockRole, logout: mockLogout }) }));
jest.mock('../src/hooks/useStaff', () => ({ useStaff: () => ({ staff: [], isLoading: false, error: null, refresh: jest.fn() }) }));
jest.mock('../src/components/StatusBadge', () => ({ StatusBadge: () => null }));
jest.mock('../src/components/StaffPickerSheet', () => ({ StaffPickerSheet: () => null }));
jest.mock('../src/components/ContentContainer', () => ({ ContentContainer: ({ children }: any) => children }));
// The S1 quote editor is covered by its own suites; isolate visit behavior here.
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

// Assigned worker is a staff member, NOT the owner/admin signed in for owner/admin cases.
const request = (extra: any = {}) => ({
  request_id: 'req-1', client_id: 'client-1', pet_name: 'Pet', client_name: 'Client',
  service_type: 'CHECK_IN', selected_dates: ['2026-09-01', '2026-09-02'], status: 'ASSIGNED', created_at: 'x',
  worker_id: 'staff@example.test', job_ids: ['job-a', 'job-b'], ...extra,
});
const occurrence = (extra: any = {}) => ({
  job_id: 'job-b', request_id: 'req-1', occurrence_date: '2026-09-02',
  occurrence_window: 'MORNING', status: 'ASSIGNED', ...extra,
});
const NOTES = 'How did the visit go? Any observations...';
const renderDetail = (params: any) => render(<RequestDetailScreen route={{ params }} navigation={{ goBack: jest.fn() }} />);
const pressHandler = (node: any) => {
  let fiber = node.unstable_fiber;
  while (fiber && typeof fiber.memoizedProps?.onPress !== 'function') fiber = fiber.return;
  if (!fiber) throw new Error('No press handler found');
  return fiber.memoizedProps.onPress as () => Promise<void>;
};

beforeEach(() => {
  jest.clearAllMocks();
  mockRole = 'owner';
  mockStartJob.mockReset().mockResolvedValue({ started_at: '2026-09-02T12:00:00Z', started_by: 'owner@example.test', status: 'ASSIGNED' });
  mockCompleteJob.mockReset().mockResolvedValue({ status: 'COMPLETED' });
  mockGetAdminRequest.mockReset();
  mockReviewRequest.mockReset();
  mockLogout.mockReset();
});

describe.each(['owner', 'admin'])('S1-VISIT-RBAC-A1: %s visit execution', role => {
  beforeEach(() => { mockRole = role; });

  it('can Start the exact routed occurrence (not the assigned worker) and uses the server timestamp', async () => {
    const view = await renderDetail({ request: request(), occurrence: occurrence() });
    expect(view.queryByText('Complete Visit')).toBeNull(); // Start precedes Complete
    await fireEvent.press(view.getByText('Start Visit'));
    await waitFor(() => expect(mockStartJob).toHaveBeenCalledWith('job-b', 'req-1'));
    expect(mockStartJob).toHaveBeenCalledTimes(1);
    expect(mockStartJob).not.toHaveBeenCalledWith('job-a', expect.anything());
    expect(await view.findByText(/Started .*2026/)).toBeTruthy();
    expect(view.getByText('Complete Visit')).toBeTruthy();
    expect(view.queryByText('Start Visit')).toBeNull();
    expect(mockReviewRequest).not.toHaveBeenCalled();
  });

  it('can Complete a started occurrence with notes after confirmation, submitting only that child', async () => {
    const view = await renderDetail({ request: request(), occurrence: occurrence({ started_at: '2026-09-02T12:00:00Z' }) });
    await fireEvent.changeText(view.getByPlaceholderText(NOTES), `${role} observed all good`);
    await fireEvent.press(view.getByText('Complete Visit'));
    expect(mockCompleteJob).not.toHaveBeenCalled(); // confirmation required
    expect(view.getByText(/Selected Visit Date: 2026-09-02/)).toBeTruthy();
    expect(view.getByText(/Only the exact selected visit is submitted/)).toBeTruthy();
    await fireEvent.press(view.getByText('Confirm Mark Visit Completed?'));
    await waitFor(() => expect(mockCompleteJob).toHaveBeenCalledWith('job-b', 'req-1', `${role} observed all good`));
    expect(mockCompleteJob).toHaveBeenCalledTimes(1);
    expect(mockReviewRequest).not.toHaveBeenCalled();
  });

  it('cancelling the completion confirmation submits nothing', async () => {
    const view = await renderDetail({ request: request(), occurrence: occurrence({ started_at: '2026-09-02T12:00:00Z' }) });
    await fireEvent.press(view.getByText('Complete Visit'));
    await fireEvent.press(view.getByText('Cancel Mark Visit Completed?'));
    expect(mockCompleteJob).not.toHaveBeenCalled();
  });

  it('keeps the existing legacy path: singular legacy identity can Complete without a Start', async () => {
    const view = await renderDetail({ request: request({ job_id: 'legacy', job_ids: undefined }), occurrence: occurrence({ job_id: 'legacy', legacy: true }) });
    expect(view.queryByText('Start Visit')).toBeNull();
    await fireEvent.press(view.getByText('Complete Visit'));
    await fireEvent.press(view.getByText('Confirm Mark Visit Completed?'));
    await waitFor(() => expect(mockCompleteJob).toHaveBeenCalledWith('legacy', 'req-1', ''));
  });

  it('blocks ambiguous multi-child actions and route disagreement (no guessed job_id)', async () => {
    const ambiguous = await renderDetail({ request: request() });
    expect(ambiguous.getByText('An exact visit could not be identified safely. Refresh and retry.')).toBeTruthy();
    expect(ambiguous.queryByText('Start Visit')).toBeNull();
    expect(ambiguous.queryByText('Complete Visit')).toBeNull();
    await ambiguous.unmount();
    const disagree = await renderDetail({ request: request(), occurrence: occurrence(), jobId: 'job-a' });
    expect(disagree.getByText('Visit details changed. Refresh before continuing.')).toBeTruthy();
    expect(disagree.queryByText('Start Visit')).toBeNull();
    expect(mockStartJob).not.toHaveBeenCalled();
  });

  it('renders a completed occurrence read-only', async () => {
    const view = await renderDetail({ request: request(), occurrence: occurrence({ status: 'COMPLETED', completed_at: 'done' }) });
    expect(view.queryByText('Start Visit')).toBeNull();
    expect(view.queryByText('Complete Visit')).toBeNull();
    expect(view.queryByPlaceholderText(NOTES)).toBeNull();
  });

  it('allows only one immediate Start request (duplicate-action lock)', async () => {
    let resolve!: (value: any) => void;
    mockStartJob.mockReturnValue(new Promise(r => { resolve = r; }));
    const view = await renderDetail({ request: request(), occurrence: occurrence() });
    const onPress = pressHandler(view.getByText('Start Visit'));
    let first!: Promise<void>;
    let second!: Promise<void>;
    await act(async () => { first = onPress(); second = onPress(); });
    expect(mockStartJob).toHaveBeenCalledTimes(1);
    await act(async () => { resolve({ started_at: '2026-09-02T12:00:00Z', started_by: `${role}@example.test` }); await Promise.all([first, second]); });
    await waitFor(() => expect(view.getByText('Complete Visit')).toBeTruthy());
  });

  it('reconciles an ambiguous Start failure from authoritative state without retrying', async () => {
    mockStartJob.mockRejectedValue(new Error('timeout'));
    mockGetAdminRequest.mockResolvedValue({ ...request(), job_completion_summary: { jobs: [occurrence({ started_at: '2026-09-02T12:00:00Z' })] } });
    const view = await renderDetail({ request: request(), occurrence: occurrence() });
    await fireEvent.press(view.getByText('Start Visit'));
    expect(await view.findByText('Complete Visit')).toBeTruthy();
    expect(mockStartJob).toHaveBeenCalledTimes(1);
  });

  it('a failed Start with failed reconciliation stays retryable without fake Started state', async () => {
    mockStartJob.mockRejectedValue(new Error('offline'));
    mockGetAdminRequest.mockRejectedValue(new Error('offline'));
    const view = await renderDetail({ request: request(), occurrence: occurrence() });
    await fireEvent.press(view.getByText('Start Visit'));
    expect(await view.findByText(/offline/)).toBeTruthy();
    expect(view.queryByText(/^Started /)).toBeNull();
    expect(view.getByText('Start Visit')).toBeTruthy();
    expect(mockLogout).not.toHaveBeenCalled();
  });

  it('a backend 403 on Start is shown in-screen and does not log out', async () => {
    mockStartJob.mockRejectedValue(new Error('Forbidden'));
    mockGetAdminRequest.mockRejectedValue(new Error('Forbidden'));
    const view = await renderDetail({ request: request(), occurrence: occurrence() });
    await fireEvent.press(view.getByText('Start Visit'));
    expect(await view.findByText(/Forbidden/)).toBeTruthy();
    expect(mockLogout).not.toHaveBeenCalled();
    expect(view.getByText('Start Visit')).toBeTruthy();
  });

  it('a failed Complete keeps the note draft and does not navigate as success', async () => {
    mockCompleteJob.mockRejectedValueOnce(new Error('Completion unavailable'));
    const view = await renderDetail({ request: request(), occurrence: occurrence({ started_at: '2026-09-02T12:00:00Z' }) });
    await fireEvent.changeText(view.getByPlaceholderText(NOTES), 'keep me');
    await fireEvent.press(view.getByText('Complete Visit'));
    await fireEvent.press(view.getByText('Confirm Mark Visit Completed?'));
    expect(await view.findByText(/Completion unavailable/)).toBeTruthy();
    await fireEvent.press(view.getByText('Cancel Mark Visit Completed?'));
    expect(view.getByPlaceholderText(NOTES).props.value).toBe('keep me');
    expect(mockLogout).not.toHaveBeenCalled();
  });

  it('a 401 during Complete triggers session recovery', async () => {
    mockCompleteJob.mockRejectedValue(new Error('Your session expired. Please sign in again.'));
    const view = await renderDetail({ request: request(), occurrence: occurrence({ started_at: '2026-09-02T12:00:00Z' }) });
    await fireEvent.press(view.getByText('Complete Visit'));
    await fireEvent.press(view.getByText('Confirm Mark Visit Completed?'));
    await waitFor(() => expect(mockLogout).toHaveBeenCalledTimes(1));
  });

  it('still keeps owner/admin booking management actions (Change Staff) alongside execution', async () => {
    const view = await renderDetail({ request: request(), occurrence: occurrence() });
    expect(view.getByText('Change Staff')).toBeTruthy();
    expect(view.getByText('Start Visit')).toBeTruthy();
  });
});

describe('S1-VISIT-RBAC-A1: staff remains backend-authorized', () => {
  beforeEach(() => { mockRole = 'staff'; });

  it('assigned staff can Start and then Complete the exact occurrence', async () => {
    mockStartJob.mockResolvedValue({ started_at: '2026-09-02T12:00:00Z', started_by: 'staff@example.test' });
    const view = await renderDetail({ request: request(), occurrence: occurrence() });
    await fireEvent.press(view.getByText('Start Visit'));
    await waitFor(() => expect(mockStartJob).toHaveBeenCalledWith('job-b', 'req-1'));
    await fireEvent.press(await view.findByText('Complete Visit'));
    await fireEvent.press(view.getByText('Confirm Mark Visit Completed?'));
    await waitFor(() => expect(mockCompleteJob).toHaveBeenCalledWith('job-b', 'req-1', ''));
  });

  it('unassigned staff: the backend 403 on Start is displayed and no Started state is faked', async () => {
    mockStartJob.mockRejectedValue(new Error('You can only start visits assigned to you.'));
    mockGetAdminRequest.mockRejectedValue(new Error('You can only start visits assigned to you.'));
    const view = await renderDetail({ request: request({ worker_id: 'someone-else@example.test' }), occurrence: occurrence() });
    await fireEvent.press(view.getByText('Start Visit'));
    expect(await view.findByText(/You can only start visits assigned to you\./)).toBeTruthy();
    expect(view.queryByText(/^Started /)).toBeNull();
    expect(mockLogout).not.toHaveBeenCalled();
  });

  it('unassigned staff: the backend 403 on Complete is displayed and does not log out', async () => {
    mockCompleteJob.mockRejectedValue(new Error('You can only complete visits assigned to you.'));
    const view = await renderDetail({ request: request({ worker_id: 'someone-else@example.test' }), occurrence: occurrence({ started_at: '2026-09-02T12:00:00Z' }) });
    await fireEvent.press(view.getByText('Complete Visit'));
    await fireEvent.press(view.getByText('Confirm Mark Visit Completed?'));
    expect(await view.findByText(/You can only complete visits assigned to you\./)).toBeTruthy();
    expect(mockLogout).not.toHaveBeenCalled();
  });

  it('staff do not gain owner/admin booking management actions', async () => {
    const view = await renderDetail({ request: request(), occurrence: occurrence() });
    expect(view.queryByText('Change Staff')).toBeNull();
    expect(view.queryByText('Approve Booking')).toBeNull();
  });
});

describe.each(['client', 'unknown', null, undefined, '', 'Owner', 'STAFF'])('S1-VISIT-RBAC-A1: role %p is denied', role => {
  beforeEach(() => { mockRole = role as any; });

  it('gets no Start, Complete or visit-notes controls, even for an exact started occurrence', async () => {
    const unstarted = await renderDetail({ request: request(), occurrence: occurrence() });
    expect(unstarted.queryByText('Start Visit')).toBeNull();
    expect(unstarted.queryByText('Complete Visit')).toBeNull();
    expect(unstarted.queryByPlaceholderText(NOTES)).toBeNull();
    await unstarted.unmount();
    const started = await renderDetail({ request: request(), occurrence: occurrence({ started_at: '2026-09-02T12:00:00Z' }) });
    expect(started.queryByText('Complete Visit')).toBeNull();
    expect(started.queryByPlaceholderText(NOTES)).toBeNull();
    await started.unmount();
    const legacy = await renderDetail({ request: request({ job_id: 'legacy', job_ids: undefined }), occurrence: occurrence({ job_id: 'legacy', legacy: true }) });
    expect(legacy.queryByText('Complete Visit')).toBeNull();
    expect(mockStartJob).not.toHaveBeenCalled();
    expect(mockCompleteJob).not.toHaveBeenCalled();
  });
});
