import React from 'react';
import { act, fireEvent, render, waitFor } from '@testing-library/react-native';
const mockReview = jest.fn();
const mockRead = jest.fn();
const mockStart = jest.fn();
const mockComplete = jest.fn();
let mockRole: string | null = 'owner';
jest.mock('../src/api/client', () => ({ reviewRequest: (...a: any[]) => mockReview(...a), getAdminRequest: (...a: any[]) => mockRead(...a), startJob: (...a: any[]) => mockStart(...a), completeJob: (...a: any[]) => mockComplete(...a), assignWorker: jest.fn() }));
jest.mock('../src/auth/useAuth', () => ({ useAuth: () => ({ role: mockRole, logout: jest.fn() }) }));
jest.mock('../src/hooks/useStaff', () => ({ useStaff: () => ({ staff: [], isLoading: false, error: null, refresh: jest.fn() }) }));
jest.mock('../src/components/StatusBadge', () => ({ StatusBadge: () => null }));
jest.mock('../src/components/StaffPickerSheet', () => ({ StaffPickerSheet: () => null }));
jest.mock('../src/components/ContentContainer', () => ({ ContentContainer: ({ children }: any) => children }));
jest.mock('../src/components/ConfirmationModal', () => {
  const React = require('react'); const { Text, TouchableOpacity } = require('react-native');
  return { ConfirmationModal: ({ visible, title, message, onConfirm }: any) => visible ? <><Text>{message}</Text><TouchableOpacity onPress={onConfirm}><Text>{`Confirm ${title}`}</Text></TouchableOpacity></> : null };
});
import { RequestDetailScreen } from '../src/screens/RequestDetailScreen';
const booking = (extra: any = {}) => ({ request_id: 'req-test', client_id: 'client-test', status: 'ASSIGNED', service_type: 'DROPIN_1HR', selected_dates: ['2026-10-29', '2026-10-30'], pet_names: ['Test Pet'], ...extra });
const child = (id: string, extra: any = {}) => ({ job_id: id, request_id: 'req-test', occurrence_date: '2026-10-29', occurrence_window: 'ANYTIME', status: 'ASSIGNED', ...extra });
const screen = (request: any, extra: any = {}) => render(<RequestDetailScreen route={{ params: { request, ...extra } }} navigation={{ goBack: jest.fn() }} />);
beforeEach(() => { jest.clearAllMocks(); mockRole = 'owner'; mockReview.mockReset().mockResolvedValue({}); mockRead.mockReset(); mockStart.mockReset().mockResolvedValue({ started_at: '2026-10-29T10:00:00Z' }); mockComplete.mockReset().mockResolvedValue({}); });

describe('Android booking workflow remediation', () => {
  it('continues verified M&G through a separate approval, with no automatic mutation', async () => {
    const v = await screen(booking({ status: 'MEET_GREET_REQUIRED' }));
    await fireEvent.press(v.getByText('Verify Meet & Greet'));
    await fireEvent.press(v.getByText('Confirm Verify Meet & Greet?'));
    await waitFor(() => expect(v.getByText('Approve Booking')).toBeTruthy());
    expect(mockReview.mock.calls).toEqual([['req-test', 'client-test', 'VERIFY_MEET_GREET']]);
    await fireEvent.press(v.getByText('Approve Booking'));
    expect(v.getByText(/Submit approval for Test Pet/)).toBeTruthy();
    expect(v.queryByText(/undefined/)).toBeNull();
    await fireEvent.press(v.getByText('Confirm Approve Pet Booking?'));
    await waitFor(() => expect(mockReview).toHaveBeenLastCalledWith('req-test', 'client-test', 'APPROVED'));
    expect(v.getByText('Assign Staff')).toBeTruthy();
  });
  it('offers prerequisite verification after backend rejects pending approval, without optimistic approval', async () => {
    mockReview.mockRejectedValueOnce(new Error('Meet & Greet must be marked completed before this request can move forward to Approved.'));
    const v = await screen(booking({ status: 'PENDING_REVIEW' }));
    await fireEvent.press(v.getByText('Approve Booking'));
    await fireEvent.press(v.getByText('Confirm Approve Pet Booking?'));
    await waitFor(() => expect(v.getByText('Verify Meet & Greet')).toBeTruthy());
    expect(v.queryByText('Assign Staff')).toBeNull();
    expect(mockReview).toHaveBeenCalledTimes(1);
  });
  it('keeps a quote prerequisite rejection blocked and does not fabricate verification', async () => {
    mockReview.mockRejectedValueOnce(new Error('Quote must be accepted and payment status updated before this request can move forward to Approved.'));
    const v = await screen(booking({ status: 'MG_COMPLETED' }));
    await fireEvent.press(v.getByText('Approve Booking'));
    await fireEvent.press(v.getByText('Confirm Approve Pet Booking?'));
    expect(await v.findByText(/Quote must be accepted/)).toBeTruthy();
    expect(v.queryByText('Assign Staff')).toBeNull();
    expect(v.queryByText('Verify Meet & Greet')).toBeNull();
  });
  it.each(['staff', 'client', 'unknown', null])('does not expose MG approval to %s', async role => {
    mockRole = role;
    const v = await screen(booking({ status: 'MG_COMPLETED' }));
    expect(v.queryByText('Approve Booking')).toBeNull();
    expect(v.queryByText('Verify Meet & Greet')).toBeNull();
    expect(mockReview).not.toHaveBeenCalled();
  });
  it.each(['QUOTE_SENT', 'QUOTED'])('explains %s without treating status as accepted', async status => {
    const v = await screen(booking({ status }));
    expect(v.getByText(/This booking status alone does not prove acceptance/)).toBeTruthy();
    expect(v.queryByText('Approve Booking')).toBeNull();
    expect(v.queryByText('Assign Staff')).toBeNull();
    expect(mockReview).not.toHaveBeenCalled();
  });
  it('makes onboarding limits truthful without creating profiles or accounts', async () => {
    const v = await screen(booking({ status: 'PROFILE_CREATED' }));
    expect(v.getByText(/not proof of a client account or invitation/)).toBeTruthy();
    expect(v.queryByText('Approve Booking')).toBeNull();
    expect(mockReview).not.toHaveBeenCalled();
  });
  it('hydrates visits without mutation and keeps owner execution unavailable', async () => {
    mockRead.mockResolvedValue(booking({ job_ids: ['a', 'b'], job_completion_summary: { jobs: [child('a'), child('b', { occurrence_date: '2026-10-30' })] } }));
    const v = await screen(booking());
    expect(v.getByText('Change Staff')).toBeTruthy();
    await fireEvent.press(v.getByText('Load / refresh visits'));
    await fireEvent.press(await v.findByText('Visit 2: 2026-10-30 · ANYTIME · ASSIGNED'));
    expect(v.getByText('Selected visit: 2026-10-30 · ANYTIME · ASSIGNED')).toBeTruthy();
    expect(v.queryByText('Start Visit')).toBeNull();
    expect(v.queryByText('Complete Visit')).toBeNull();
    expect(mockStart).not.toHaveBeenCalled(); expect(mockComplete).not.toHaveBeenCalled();
  });
  it('selects and starts only the authoritative second child as staff', async () => {
    mockRole = 'staff';
    mockRead.mockResolvedValue(booking({ job_ids: ['a', 'b'], job_completion_summary: { jobs: [child('a'), child('b', { occurrence_date: '2026-10-30' })] } }));
    const v = await screen(booking({ job_ids: ['a', 'b'] }));
    await fireEvent.press(v.getByText('Load / refresh visits'));
    await fireEvent.press(await v.findByText('Visit 2: 2026-10-30 · ANYTIME · ASSIGNED'));
    await fireEvent.press(v.getByText('Start Visit'));
    await waitFor(() => expect(mockStart).toHaveBeenCalledWith('b', 'req-test'));
    await fireEvent.press(v.getByText('Complete Visit'));
    expect(v.getByText(/Only the exact selected visit is submitted/)).toBeTruthy();
    expect(v.queryByText(/ALL dates/)).toBeNull();
    await fireEvent.press(v.getByText('Confirm Mark Visit Completed?'));
    await waitFor(() => expect(mockComplete).toHaveBeenCalledWith('b', 'req-test', ''));
    expect(mockReview).not.toHaveBeenCalled();
  });
  it('fails closed on cross-parent child identity', async () => {
    mockRole = 'staff';
    mockRead.mockResolvedValue(booking({ job_completion_summary: { jobs: [child('a', { request_id: 'different-parent' })] } }));
    const v = await screen(booking({ job_ids: ['a', 'b'] }));
    await fireEvent.press(v.getByText('Load / refresh visits'));
    expect(await v.findByText('Refresh required: exact visit identity unavailable.')).toBeTruthy();
    expect(v.queryByText('Start Visit')).toBeNull();
    expect(mockStart).not.toHaveBeenCalled();
  });
  it('keeps failed hydration retryable and never falls back to a guessed child', async () => {
    mockRole = 'staff'; mockRead.mockRejectedValueOnce(new Error('Offline')).mockResolvedValueOnce(booking({ job_ids: ['a', 'b'] }));
    const v = await screen(booking({ job_ids: ['a', 'b'] }));
    await fireEvent.press(v.getByText('Load / refresh visits'));
    expect(await v.findByText('Offline')).toBeTruthy();
    expect(v.queryByText('Start Visit')).toBeNull();
    await fireEvent.press(v.getByText('Load / refresh visits'));
    expect(await v.findByText('Refresh required: exact visit identity unavailable.')).toBeTruthy();
    expect(mockRead).toHaveBeenCalledTimes(2); expect(mockStart).not.toHaveBeenCalled();
  });
  it('does not offer terminal or intermediate blocked transitions', async () => {
    for (const status of ['COMPLETED', 'CANCELLED', 'QUOTE_NEEDED', 'MG_SCHEDULED']) {
      const v = await screen(booking({ status }));
      expect(v.queryByText('Approve Booking')).toBeNull();
      await v.unmount();
    }
    expect(mockReview).not.toHaveBeenCalled();
  });
  it('ignores a late hydration response after leaving the screen', async () => {
    let finish!: (value: any) => void;
    mockRead.mockReturnValueOnce(new Promise(resolve => { finish = resolve; }));
    const v = await screen(booking());
    let fiber = v.getByText('Load / refresh visits').unstable_fiber;
    while (fiber && typeof fiber.memoizedProps?.onPress !== 'function') fiber = fiber.return;
    if (!fiber) throw new Error('Missing refresh handler');
    const onPress = fiber.memoizedProps.onPress;
    let pending!: Promise<void>;
    await act(async () => { pending = onPress(); });
    await v.unmount();
    await act(async () => { finish(booking({ job_completion_summary: { jobs: [child('a')] } })); await pending; });
    expect(mockStart).not.toHaveBeenCalled(); expect(mockComplete).not.toHaveBeenCalled();
  });
  it('rejects a mismatched refreshed parent', async () => {
    mockRead.mockResolvedValue(booking({ request_id: 'different-parent' }));
    const v = await screen(booking());
    await fireEvent.press(v.getByText('Load / refresh visits'));
    expect(await v.findByText(/Booking identity changed/)).toBeTruthy();
    expect(mockReview).not.toHaveBeenCalled();
  });
});