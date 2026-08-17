import React from 'react';
import { fireEvent, render, waitFor, within } from '@testing-library/react-native';

const mockGetAdminRequests = jest.fn();
const mockNavigate = jest.fn();

jest.mock('@react-navigation/native', () => {
  const React = require('react');
  return {
    useNavigation: () => ({ navigate: mockNavigate }),
    useFocusEffect: (callback: () => void) => {
      React.useEffect(() => callback(), [callback]);
    },
  };
});

jest.mock('../src/api/client', () => ({
  getAdminRequests: (...args: unknown[]) => mockGetAdminRequests(...args),
}));

jest.mock('../src/auth/useAuth', () => ({
  useAuth: () => ({
    logout: jest.fn(),
    role: 'owner',
    user: 'owner@example.test',
  }),
}));

jest.mock('../src/components/ContentContainer', () => ({
  ContentContainer: ({ children }: { children: React.ReactNode }) => children,
}));

import { DashboardScreen } from '../src/screens/DashboardScreen';

const getLocalDateString = (date: Date) => {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
};

const dateFromToday = (days: number) => {
  const date = new Date();
  date.setDate(date.getDate() + days);
  return getLocalDateString(date);
};

beforeEach(() => {
  jest.clearAllMocks();
  mockGetAdminRequests.mockResolvedValue([
    { request_id: 'pending', status: 'PENDING_REVIEW', selected_dates: [dateFromToday(0)] },
    { request_id: 'approved-today', status: 'APPROVED', selected_dates: [dateFromToday(0)] },
    { request_id: 'approved-later', status: 'APPROVED', selected_dates: [dateFromToday(7)] },
    { request_id: 'assigned', status: 'ASSIGNED', selected_dates: [dateFromToday(0)] },
    { request_id: 'scheduled', status: 'SCHEDULED', selected_dates: [dateFromToday(0)] },
    { request_id: 'job-created', status: 'JOB_CREATED', selected_dates: [dateFromToday(6)] },
  ]);
});

describe('DashboardScreen navigation cards', () => {
  it('preserves the existing API call and displayed operational counts', async () => {
    const view = await render(<DashboardScreen />);

    await waitFor(() => {
      expect(mockGetAdminRequests).toHaveBeenCalledWith('ALL');
      expect(within(view.getByRole('button', { name: 'Pending Review' })).getByText('1')).toBeTruthy();
      expect(within(view.getByRole('button', { name: 'Needs Sitter' })).getByText('2')).toBeTruthy();
      expect(within(view.getByRole('button', { name: 'Scheduled' })).getByText('3')).toBeTruthy();
      expect(within(view.getByRole('button', { name: "Today's Visits" })).getByText('4')).toBeTruthy();
      expect(within(view.getByRole('button', { name: "This Week's Visits" })).getByText('5')).toBeTruthy();
    });
  });

  it('exposes meaningful button semantics and navigates with supported route contracts', async () => {
    const view = await render(<DashboardScreen />);

    await waitFor(() => expect(view.getByText('1')).toBeTruthy());

    const pending = view.getByRole('button', { name: 'Pending Review' });
    const needsSitter = view.getByRole('button', { name: 'Needs Sitter' });
    const scheduled = view.getByRole('button', { name: 'Scheduled' });
    const today = view.getByRole('button', { name: "Today's Visits" });
    const week = view.getByRole('button', { name: "This Week's Visits" });

    expect(pending.props.accessibilityHint).toBe('Opens requests filtered to pending review');
    expect(needsSitter.props.accessibilityHint).toBe('Opens approved requests that need assignment');

    await fireEvent.press(pending);
    await fireEvent.press(needsSitter);
    await fireEvent.press(scheduled);
    await fireEvent.press(today);
    await fireEvent.press(week);

    expect(mockNavigate.mock.calls).toEqual([
      ['Requests', { initialFilter: 'PENDING_REVIEW' }],
      ['Requests', { initialFilter: 'APPROVED' }],
      ['Schedule'],
      ['Schedule'],
      ['Schedule'],
    ]);
  });
});
