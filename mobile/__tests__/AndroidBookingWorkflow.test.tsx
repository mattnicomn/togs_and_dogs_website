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
  return { ConfirmationModal: ({ visible, title, message, onConfirm, onCancel }: any) => visible ? <><Text>{message}</Text><TouchableOpacity onPress={onConfirm}><Text>{`Confirm ${title}`}</Text></TouchableOpacity><TouchableOpacity onPress={onCancel}><Text>{`Cancel ${title}`}</Text></TouchableOpacity></> : null };
});
import { RequestDetailScreen } from '../src/screens/RequestDetailScreen';
const booking = (extra: any = {}) => ({ request_id: 'req-test', client_id: 'client-test', status: 'ASSIGNED', service_type: 'DROPIN_1HR', selected_dates: ['2026-10-29', '2026-10-30'], pet_names: ['Test Pet'], ...extra });
const child = (id: string, extra: any = {}) => ({ job_id: id, request_id: 'req-test', occurrence_date: '2026-10-29', occurrence_window: 'ANYTIME', status: 'ASSIGNED', ...extra });
const screen = (request: any, extra: any = {}) => render(<RequestDetailScreen route={{ params: { request, ...extra } }} navigation={{ goBack: jest.fn() }} />);
beforeEach(() => { jest.clearAllMocks(); mockRole = 'owner'; mockReview.mockReset().mockResolvedValue({}); mockRead.mockReset(); mockStart.mockReset().mockResolvedValue({ started_at: '2026-10-29T10:00:00Z' }); mockComplete.mockReset().mockResolvedValue({}); });

const hydratedVisits = async (started: boolean, role: string | null = 'staff') => {
  mockRole = role;
  mockRead.mockResolvedValue(booking({ job_ids: ['a', 'b'], job_completion_summary: { jobs: [
    child('a', started ? { started_at: '2026-10-29T09:00:00Z' } : {}),
    child('b', { occurrence_date: '2026-10-30', ...(started ? { started_at: '2026-10-29T09:00:00Z' } : {}) }),
  ] } }));
  const v = await screen(booking({ job_ids: ['a', 'b'] }));
  if (role === 'staff' || role === 'owner' || role === 'admin') {
    await fireEvent.press(v.getByText('Load / refresh visits'));
    await waitFor(() => expect(v.getByText(/^Visit 1:/)).toBeTruthy());
  }
  return v;
};
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
  it.each([[1, 2], [2, 1]])('isolates drafts when switching Visit %s to Visit %s and back', async (from, to) => {
    const v = await hydratedVisits(true);
    await fireEvent.press(v.getByText(new RegExp(`^Visit ${from}:`)));
    await fireEvent.changeText(v.getByPlaceholderText('How did the visit go? Any observations...'), `Draft ${from}`);
    await fireEvent.press(v.getByText(new RegExp(`^Visit ${to}:`)));
    expect(v.getByPlaceholderText('How did the visit go? Any observations...').props.value).toBe('');
    await fireEvent.changeText(v.getByPlaceholderText('How did the visit go? Any observations...'), `Draft ${to}`);
    await fireEvent.press(v.getByText(new RegExp(`^Visit ${from}:`)));
    expect(v.getByPlaceholderText('How did the visit go? Any observations...').props.value).toBe(`Draft ${from}`);
    await fireEvent.press(v.getByText(new RegExp(`^Visit ${to}:`)));
    await fireEvent.press(v.getByText('Complete Visit'));
    expect(v.getByText(new RegExp(`Selected Visit Date: 2026-10-${to === 1 ? '29' : '30'}`))).toBeTruthy();
    expect(v.getByText(/Selected Window: ANYTIME/)).toBeTruthy();
    await fireEvent.press(v.getByText('Confirm Mark Visit Completed?'));
    await waitFor(() => expect(mockComplete).toHaveBeenCalledWith(to === 1 ? 'a' : 'b', 'req-test', `Draft ${to}`));
  });
  it('preserves per-child drafts across successful and failed refresh without moving them', async () => {
    const v = await hydratedVisits(true);
    await fireEvent.press(v.getByText(/^Visit 1:/));
    await fireEvent.changeText(v.getByPlaceholderText('How did the visit go? Any observations...'), 'Only A');
    mockRead.mockRejectedValueOnce(new Error('Offline'));
    await fireEvent.press(v.getByText('Load / refresh visits'));
    expect(await v.findByText('Offline')).toBeTruthy();
    expect(v.getByPlaceholderText('How did the visit go? Any observations...').props.editable).toBe(false);
    await fireEvent.press(v.getByText('Load / refresh visits'));
    await fireEvent.press(await v.findByText(/^Visit 2:/));
    expect(v.getByPlaceholderText('How did the visit go? Any observations...').props.value).toBe('');
    await fireEvent.press(v.getByText(/^Visit 1:/));
    expect(v.getByPlaceholderText('How did the visit go? Any observations...').props.value).toBe('Only A');
  });
  it('keeps a failed completion draft on A and never submits it for B', async () => {
    const v = await hydratedVisits(true);
    mockComplete.mockRejectedValueOnce(new Error('Completion unavailable'));
    await fireEvent.press(v.getByText(/^Visit 1:/));
    await fireEvent.changeText(v.getByPlaceholderText('How did the visit go? Any observations...'), 'A retained');
    await fireEvent.press(v.getByText('Complete Visit'));
    await fireEvent.press(v.getByText('Confirm Mark Visit Completed?'));
    await waitFor(() => expect(v.getByText(/Completion unavailable/)).toBeTruthy());
    await fireEvent.press(v.getByText('Cancel Mark Visit Completed?'));
    expect(v.getByPlaceholderText('How did the visit go? Any observations...').props.value).toBe('A retained');
    await fireEvent.press(v.getByText(/^Visit 2:/));
    expect(v.getByPlaceholderText('How did the visit go? Any observations...').props.value).toBe('');
    await fireEvent.press(v.getByText('Complete Visit'));
    await fireEvent.press(v.getByText('Confirm Mark Visit Completed?'));
    await waitFor(() => expect(mockComplete.mock.calls).toEqual([['a', 'req-test', 'A retained'], ['b', 'req-test', '']]));
  });
  it('does not retain an unmounted screen draft in another visit screen', async () => {
    const v = await hydratedVisits(true);
    await fireEvent.press(v.getByText(/^Visit 1:/));
    await fireEvent.changeText(v.getByPlaceholderText('How did the visit go? Any observations...'), 'Discard on leave');
    await v.unmount();
    const next = await screen(booking({ job_ids: ['a', 'b'] }), { occurrence: child('b', { started_at: '2026-10-29T10:00:00Z' }) });
    expect(next.getByPlaceholderText('How did the visit go? Any observations...').props.value).toBe('');
    expect(mockComplete).not.toHaveBeenCalled();
  });
  it('keeps authoritative Start state when reselecting A across multiple children', async () => {
    const v = await hydratedVisits(false);
    await fireEvent.press(v.getByText(/^Visit 1:/));
    await fireEvent.press(v.getByText('Start Visit'));
    await waitFor(() => expect(v.getByText('Complete Visit')).toBeTruthy());
    await fireEvent.press(v.getByText(/^Visit 1:/));
    expect(v.getByText('Complete Visit')).toBeTruthy();
    expect(v.queryByText('Start Visit')).toBeNull();
    await fireEvent.press(v.getByText(/^Visit 2:/));
    expect(v.getByText('Start Visit')).toBeTruthy();
    await fireEvent.press(v.getByText(/^Visit 1:/));
    expect(v.getByText('Complete Visit')).toBeTruthy();
    expect(v.queryByText('Start Visit')).toBeNull();
    expect(mockStart.mock.calls).toEqual([['a', 'req-test']]);
    expect(v.getByText(/Started .*2026/)).toBeTruthy();
  });
  it('blocks refresh during an active visit mutation, including immediate handler calls', async () => {
    const v = await hydratedVisits(false);
    await fireEvent.press(v.getByText(/^Visit 1:/));
    const handler = (text: string) => {
      let fiber = v.getByText(text).unstable_fiber;
      while (fiber && typeof fiber.memoizedProps?.onPress !== 'function') fiber = fiber.return;
      if (!fiber) throw new Error('Missing handler');
      return fiber.memoizedProps.onPress;
    };
    const refresh = handler('Load / refresh visits');
    const start = handler('Start Visit');
    let finish!: (value: any) => void;
    mockStart.mockReturnValueOnce(new Promise(resolve => { finish = resolve; }));
    let pending!: Promise<void>;
    await act(async () => { pending = start(); await refresh(); });
    expect(mockRead).toHaveBeenCalledTimes(1);
    await act(async () => { finish({ started_at: '2026-10-29T10:00:00Z', status: 'ASSIGNED' }); await pending; });
    expect(v.getByText('Complete Visit')).toBeTruthy();
    expect(mockRead).toHaveBeenCalledTimes(1);
  });
  it('offers READY_FOR_APPROVAL as a separate owner action and keeps server validation', async () => {
    const v = await screen(booking({ status: 'READY_FOR_APPROVAL' }));
    await fireEvent.press(v.getByText('Approve Booking'));
    expect(mockReview).not.toHaveBeenCalled();
    await fireEvent.press(v.getByText('Confirm Approve Pet Booking?'));
    await waitFor(() => expect(mockReview).toHaveBeenCalledWith('req-test', 'client-test', 'APPROVED'));
  });
  it.each(['owner', 'admin', 'client', 'unknown', null])('never exposes staff execution to %s after child selection', async role => {
    const v = await hydratedVisits(true, role);
    if (role === 'owner' || role === 'admin') await fireEvent.press(v.getByText(/^Visit 1:/));
    expect(v.queryByText('Start Visit')).toBeNull();
    expect(v.queryByText('Complete Visit')).toBeNull();
    expect(mockStart).not.toHaveBeenCalled(); expect(mockComplete).not.toHaveBeenCalled();
  });
});