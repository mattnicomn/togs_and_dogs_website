import React from 'react';
import { fireEvent, render, waitFor } from '@testing-library/react-native';

const mockGetAdminRequests = jest.fn();
const mockGetAdminRequest = jest.fn();
const mockNavigate = jest.fn();

jest.mock('../src/api/client', () => ({
  getAdminRequests: (...args: any[]) => mockGetAdminRequests(...args),
  getAdminRequest: (...args: any[]) => mockGetAdminRequest(...args),
}));
jest.mock('../src/auth/useAuth', () => ({ useAuth: () => ({ role: 'owner', logout: jest.fn() }) }));
jest.mock('@react-navigation/native', () => {
  const React = require('react');
  return {
    useNavigation: () => ({ navigate: mockNavigate }),
    useFocusEffect: (callback: any) => React.useEffect(() => callback(), [callback]),
  };
});
jest.mock('../src/components/StatusBadge', () => ({ StatusBadge: () => null }));
jest.mock('../src/components/ContentContainer', () => ({ ContentContainer: ({ children }: any) => children }));

import { ScheduleScreen } from '../src/screens/ScheduleScreen';

const parent = {
  request_id: 'req', client_id: 'client', client_name: 'Client', pet_name: 'Pet', service_type: 'CHECK_IN',
  selected_dates: ['2099-09-01', '2099-09-02'], visit_windows: ['MORNING', 'MIDDAY', 'EVENING'],
  status: 'ASSIGNED', created_at: 'x', job_ids: ['wrong-a', 'wrong-b'],
};

beforeEach(() => {
  jest.clearAllMocks();
  mockGetAdminRequests.mockResolvedValue([parent]);
});

describe('E3B.1 Schedule occurrence hydration safety', () => {
  it('renders six distinct authoritative Check-In children and navigates with exact IDs', async () => {
    const jobs = parent.selected_dates.flatMap((date, di) => parent.visit_windows.map((window, wi) => ({
      job_id: `job-${di}-${wi}`, request_id: 'req', occurrence_date: date,
      occurrence_window: window, occurrence_index: di * 3 + wi, status: 'ASSIGNED',
    })));
    mockGetAdminRequest.mockResolvedValue({ ...parent, job_completion_summary: { jobs: [...jobs].reverse() } });
    const view = await render(<ScheduleScreen />);
    await waitFor(() => expect(view.getAllByText('MORNING')).toHaveLength(2));
    expect(view.getAllByText('MIDDAY')).toHaveLength(2);
    expect(view.getAllByText('EVENING')).toHaveLength(2);
    await fireEvent.press(view.getAllByText('MORNING')[0]);
    expect(mockNavigate).toHaveBeenCalledWith('RequestDetail', expect.objectContaining({
      jobId: 'job-0-0', occurrence: expect.objectContaining({ job_id: 'job-0-0' }),
    }));
  });

  it('renders truthful non-actionable date-window placeholders when hydration fails', async () => {
    mockGetAdminRequest.mockRejectedValue(new Error('route unavailable'));
    const view = await render(<ScheduleScreen />);
    await waitFor(() => expect(view.getAllByText('Refresh required to identify this visit safely.')).toHaveLength(6));
    expect(view.getAllByText('MORNING')).toHaveLength(2);
    await fireEvent.press(view.getAllByText('MORNING')[0]);
    expect(mockNavigate).toHaveBeenCalledWith('RequestDetail', expect.objectContaining({
      jobId: undefined,
      occurrence: expect.objectContaining({ job_id: '', actionBlocked: true }),
    }));
    expect(mockNavigate.mock.calls[0][1].jobId).toBeUndefined();
  });

  it('preserves a singular legacy identity without guessing', async () => {
    mockGetAdminRequest.mockResolvedValue({
      ...parent,
      job_id: 'legacy-job',
      job_ids: undefined,
      visit_windows: undefined,
      timeframe: 'Anytime',
    });
    const view = await render(<ScheduleScreen />);
    await waitFor(() => expect(view.getByText('Anytime')).toBeTruthy());
    await fireEvent.press(view.getByText('Anytime'));
    expect(mockNavigate).toHaveBeenCalledWith('RequestDetail', expect.objectContaining({
      jobId: 'legacy-job',
      occurrence: expect.objectContaining({ job_id: 'legacy-job', legacy: true }),
    }));
  });
});
