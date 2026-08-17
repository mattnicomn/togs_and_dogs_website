import React from 'react';
import { act, fireEvent, render, waitFor } from '@testing-library/react-native';

const mockGetAdminRequests = jest.fn();
const mockSetParams = jest.fn();
const mockNavigation = { setParams: mockSetParams };
let mockRouteParams: { initialFilter?: 'PENDING_REVIEW' | 'APPROVED' } | undefined;
let mockFocusCleanup: (() => void) | undefined;

jest.mock('@react-navigation/native', () => {
  const React = require('react');
  return {
    useNavigation: () => mockNavigation,
    useRoute: () => ({ params: mockRouteParams }),
    useFocusEffect: (callback: () => void | (() => void)) => {
      React.useEffect(() => {
        const cleanup = callback();
        mockFocusCleanup = typeof cleanup === 'function' ? cleanup : undefined;
      }, [callback]);
    },
  };
});

jest.mock('../src/api/client', () => ({
  getAdminRequests: (...args: unknown[]) => mockGetAdminRequests(...args),
}));

jest.mock('../src/auth/useAuth', () => ({
  useAuth: () => ({ logout: jest.fn() }),
}));

jest.mock('../src/hooks/useStaff', () => ({
  useStaff: () => ({
    staff: [],
    isLoading: false,
    error: null,
    refresh: jest.fn(),
  }),
}));

jest.mock('../src/components/RequestCard', () => ({
  RequestCard: () => null,
}));

jest.mock('../src/components/ContentContainer', () => ({
  ContentContainer: ({ children }: { children: React.ReactNode }) => children,
}));

import { RequestListScreen } from '../src/screens/RequestListScreen';

beforeEach(() => {
  jest.clearAllMocks();
  mockRouteParams = undefined;
  mockFocusCleanup = undefined;
  mockGetAdminRequests.mockResolvedValue([]);
});

describe('RequestListScreen dashboard filter integration', () => {
  it('preserves ordinary Requests-tab behavior without route parameters', async () => {
    const view = await render(<RequestListScreen />);

    await waitFor(() => {
      expect(mockGetAdminRequests).toHaveBeenCalledWith('PENDING_REVIEW');
      expect(view.getByText('All Caught Up')).toBeTruthy();
    });
  });

  it('applies the approved filter from dashboard navigation and clears the route param on blur', async () => {
    mockRouteParams = { initialFilter: 'APPROVED' };
    const view = await render(<RequestListScreen />);

    await waitFor(() => {
      expect(mockGetAdminRequests).toHaveBeenCalledWith('APPROVED');
      expect(view.getByText('Fully Handled')).toBeTruthy();
    });

    await act(async () => mockFocusCleanup?.());
    expect(mockSetParams).toHaveBeenCalledWith({ initialFilter: undefined });
  });

  it('keeps ordinary filter-pill changes working after a normal tab entry', async () => {
    const view = await render(<RequestListScreen />);
    await waitFor(() => expect(view.getByText('All Caught Up')).toBeTruthy());

    await fireEvent.press(view.getByText('Approved'));

    await waitFor(() => {
      expect(mockGetAdminRequests).toHaveBeenLastCalledWith('APPROVED');
      expect(view.getByText('Fully Handled')).toBeTruthy();
    });
  });
});
