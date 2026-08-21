import React from 'react';
import { act, fireEvent, render, waitFor } from '@testing-library/react-native';

const mockStartJob = jest.fn();
const mockCompleteJob = jest.fn();
const mockGetAdminRequest = jest.fn();
const mockReviewRequest = jest.fn();

jest.mock('../src/api/client', () => ({
  startJob: (...args: any[]) => mockStartJob(...args),
  completeJob: (...args: any[]) => mockCompleteJob(...args),
  getAdminRequest: (...args: any[]) => mockGetAdminRequest(...args),
  reviewRequest: (...args: any[]) => mockReviewRequest(...args),
  assignWorker: jest.fn(),
}));
jest.mock('../src/auth/useAuth', () => ({ useAuth: () => ({ role: 'staff', logout: jest.fn() }) }));
jest.mock('../src/hooks/useStaff', () => ({ useStaff: () => ({ staff: [], isLoading: false, error: null, refresh: jest.fn() }) }));
jest.mock('../src/components/StatusBadge', () => ({ StatusBadge: () => null }));
jest.mock('../src/components/StaffPickerSheet', () => ({ StaffPickerSheet: () => null }));
jest.mock('../src/components/ContentContainer', () => ({ ContentContainer: ({ children }: any) => children }));
jest.mock('../src/components/ConfirmationModal', () => {
  const React = require('react');
  const { Text, TouchableOpacity } = require('react-native');
  return { ConfirmationModal: ({ visible, title, onConfirm }: any) => visible ? (
    <TouchableOpacity onPress={onConfirm}><Text>{`Confirm ${title}`}</Text></TouchableOpacity>
  ) : null };
});

import { RequestDetailScreen } from '../src/screens/RequestDetailScreen';

const request = (extra: any = {}) => ({
  request_id: 'req-1', client_id: 'client-1', pet_name: 'Pet', client_name: 'Client',
  service_type: 'CHECK_IN', selected_dates: ['2026-09-01'], status: 'ASSIGNED', created_at: 'x',
  worker_id: 'staff@example.test', ...extra,
});
const occurrence = (extra: any = {}) => ({
  job_id: 'job-a', request_id: 'req-1', occurrence_date: '2026-09-01',
  occurrence_window: 'MORNING', status: 'ASSIGNED', ...extra,
});
const renderDetail = (params: any) => render(<RequestDetailScreen route={{ params }} navigation={{ goBack: jest.fn() }} />);
const pressHandler = (node: any) => {
  let fiber = node.unstable_fiber;
  while (fiber && typeof fiber.memoizedProps?.onPress !== 'function') fiber = fiber.return;
  if (!fiber) throw new Error('No press handler found');
  return fiber.memoizedProps.onPress as () => Promise<void>;
};

beforeEach(() => {
  jest.clearAllMocks();
  mockStartJob.mockReset();
  mockCompleteJob.mockReset();
  mockGetAdminRequest.mockReset();
  mockReviewRequest.mockReset();
  mockStartJob.mockResolvedValue({ started_at: '2026-09-01T12:00:00Z', started_by: 'staff@example.test' });
  mockCompleteJob.mockResolvedValue({ status: 'COMPLETED' });
});

describe('E3B.1 RequestDetail visit-action safety', () => {
  it('starts the authoritative occurrence and uses the server timestamp', async () => {
    const view = await renderDetail({ request: request({ job_ids: ['job-a', 'job-b'] }), occurrence: occurrence() });
    await fireEvent.press(view.getByText('Start Visit'));
    await waitFor(() => expect(mockStartJob).toHaveBeenCalledWith('job-a', 'req-1'));
    expect(mockStartJob.mock.calls[0]).toHaveLength(2);
    expect(JSON.stringify(mockStartJob.mock.calls)).not.toContain('IN_PROGRESS');
    expect(view.queryByText('IN_PROGRESS')).toBeNull();
    expect(await view.findByText(/Started .*2026/)).toBeTruthy();
    expect(view.getByText('Complete Visit')).toBeTruthy();
  });

  it('blocks route disagreement for Start and Complete', async () => {
    const unstarted = await renderDetail({ request: request(), occurrence: occurrence(), jobId: 'job-b' });
    expect(unstarted.getByText('Visit details changed. Refresh before continuing.')).toBeTruthy();
    expect(unstarted.queryByText('Start Visit')).toBeNull();
    await unstarted.unmount();
    const started = await renderDetail({ request: request(), occurrence: occurrence({ started_at: '2026-09-01T12:00:00Z' }), jobId: 'job-b' });
    expect(started.queryByText('Complete Visit')).toBeNull();
    expect(mockStartJob).not.toHaveBeenCalled();
    expect(mockCompleteJob).not.toHaveBeenCalled();
  });

  it('uses singular legacy identity without a route ID for Start and Complete', async () => {
    const startView = await renderDetail({ request: request({ job_id: 'legacy' }), occurrence: occurrence({ job_id: 'legacy', legacy: true }) });
    await fireEvent.press(startView.getByText('Complete Visit'));
    await fireEvent.press(await startView.findByText('Confirm Mark Visit Completed?'));
    await waitFor(() => expect(mockCompleteJob).toHaveBeenCalledWith('legacy', 'req-1', ''));
    await startView.unmount();

    const unstarted = await renderDetail({ request: request({ job_id: 'legacy' }) });
    await fireEvent.press(unstarted.getByText('Start Visit'));
    await waitFor(() => expect(mockStartJob).toHaveBeenCalledWith('legacy', 'req-1'));
  });

  it('blocks ambiguous multi-child actions', async () => {
    const view = await renderDetail({ request: request({ job_ids: ['a', 'b'] }) });
    expect(view.getByText('An exact visit could not be identified safely. Refresh and retry.')).toBeTruthy();
    expect(view.queryByText('Start Visit')).toBeNull();
    expect(view.queryByText('Complete Visit')).toBeNull();
  });

  it('allows only one immediate Start request', async () => {
    let resolve!: (value: any) => void;
    mockStartJob.mockReturnValue(new Promise(r => { resolve = r; }));
    const view = await renderDetail({ request: request(), occurrence: occurrence() });
    const onPress = pressHandler(view.getByText('Start Visit'));
    let first!: Promise<void>;
    let second!: Promise<void>;
    await act(async () => {
      first = onPress();
      second = onPress();
    });
    expect(mockStartJob).toHaveBeenCalledTimes(1);
    await act(async () => {
      resolve({ started_at: '2026-09-01T12:00:00Z', started_by: 'staff@example.test' });
      await Promise.all([first, second]);
    });
    await waitFor(() => expect(view.getByText('Complete Visit')).toBeTruthy());
  });

  it('reconciles one ambiguous failure from authoritative state', async () => {
    mockStartJob.mockRejectedValue(new Error('timeout'));
    mockGetAdminRequest.mockResolvedValue({
      ...request(), job_completion_summary: { jobs: [occurrence({ started_at: '2026-09-01T12:00:00Z' })] },
    });
    const view = await renderDetail({ request: request(), occurrence: occurrence() });
    await fireEvent.press(view.getByText('Start Visit'));
    await waitFor(() => expect(mockGetAdminRequest).toHaveBeenCalledTimes(1));
    expect(await view.findByText('Complete Visit')).toBeTruthy();
    expect(mockStartJob).toHaveBeenCalledTimes(1);
  });

  it('keeps failed reconciliation retryable without fake Started state', async () => {
    mockStartJob.mockRejectedValue(new Error('offline'));
    mockGetAdminRequest.mockRejectedValue(new Error('offline'));
    const view = await renderDetail({ request: request(), occurrence: occurrence() });
    await fireEvent.press(view.getByText('Start Visit'));
    expect(await view.findByText(/offline/)).toBeTruthy();
    expect(view.queryByText(/^Started /)).toBeNull();
    expect(view.getByText('Start Visit')).toBeTruthy();
  });

  it('completes only the authoritative child with notes and never parent review', async () => {
    const view = await renderDetail({ request: request({ job_ids: ['job-a', 'job-b'] }), occurrence: occurrence({ started_at: '2026-09-01T12:00:00Z' }) });
    await fireEvent.changeText(view.getByPlaceholderText('How did the visit go? Any observations...'), 'All good');
    await fireEvent.press(view.getByText('Complete Visit'));
    await fireEvent.press(await view.findByText('Confirm Mark Visit Completed?'));
    await waitFor(() => expect(mockCompleteJob).toHaveBeenCalledWith('job-a', 'req-1', 'All good'));
    expect(mockReviewRequest).not.toHaveBeenCalled();
    expect(mockCompleteJob).not.toHaveBeenCalledWith('job-b', expect.anything(), expect.anything());
  });

  it('renders a completed occurrence read-only', async () => {
    const view = await renderDetail({ request: request(), occurrence: occurrence({ status: 'COMPLETED', completed_at: 'done' }) });
    expect(view.queryByText('Start Visit')).toBeNull();
    expect(view.queryByText('Complete Visit')).toBeNull();
  });

  it('does not apply a late Start result after unmount', async () => {
    let resolve!: (value: any) => void;
    mockStartJob.mockReturnValue(new Promise(r => { resolve = r; }));
    const view = await renderDetail({ request: request(), occurrence: occurrence() });
    const onPress = pressHandler(view.getByText('Start Visit'));
    let pending!: Promise<void>;
    await act(async () => {
      pending = onPress();
    });
    await view.unmount();
    await act(async () => {
      resolve({ started_at: '2026-09-01T12:00:00Z' });
      await pending;
    });
    expect(mockStartJob).toHaveBeenCalledTimes(1);
  });
});
