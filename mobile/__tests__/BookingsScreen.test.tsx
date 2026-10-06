/**
 * Phase 24A-3: BookingsScreen Baseline Tests (RNTL v14)
 *
 * Tests existing client bookings screen with mocked API and auth.
 * All state updates are awaited — no act() warnings expected.
 */
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react-native';

// Mock auth
jest.mock('../src/auth/useAuth', () => ({
  useAuth: () => ({
    login: jest.fn(),
    logout: jest.fn(),
    user: 'test@example.com',
    role: 'client',
    isAuthenticated: true,
    isLoading: false,
  }),
}));

// Mock API
const mockGetClientRequests = jest.fn();
jest.mock('../src/api/client', () => ({
  getClientRequests: (...args: any[]) => mockGetClientRequests(...args),
}));

// Mock navigation (OPS-3A.3B: card tap navigates to ClientRequestDetail)
const mockNavigate = jest.fn();
jest.mock('@react-navigation/native', () => ({
  useNavigation: () => ({ navigate: mockNavigate }),
  useFocusEffect: (cb: () => void | (() => void)) => {
    const React = require('react');
    React.useEffect(() => {
      const cleanup = cb();
      return typeof cleanup === 'function' ? cleanup : undefined;
    }, []);
  },
}));

import { fireEvent } from '@testing-library/react-native';
import { BookingsScreen } from '../src/screens/BookingsScreen';

beforeEach(() => {
  jest.clearAllMocks();
});

describe('BookingsScreen', () => {
  it('shows loading then empty state when no bookings exist', async () => {
    mockGetClientRequests.mockResolvedValue([]);
    await render(<BookingsScreen />);
    await waitFor(() => {
      expect(screen.getByText('No Appointments Yet')).toBeTruthy();
    });
  });

  it('renders booking cards when data exists', async () => {
    mockGetClientRequests.mockResolvedValue([
      {
        request_id: 'req-1',
        pet_name: 'Buddy',
        service_type: 'PET_SITTING',
        status: 'APPROVED',
        selected_dates: ['2026-08-01'],
        created_at: '2026-07-20',
      },
    ]);
    await render(<BookingsScreen />);
    await waitFor(() => {
      expect(screen.getByText(/Buddy/)).toBeTruthy();
      expect(screen.getByText('Pet Sitting')).toBeTruthy();
    });
    expect(mockGetClientRequests).toHaveBeenCalledWith();
  });

  it('shows error state on API failure', async () => {
    mockGetClientRequests.mockRejectedValue(new Error('Network error'));
    await render(<BookingsScreen />);
    await waitFor(() => {
      expect(screen.getByText('Network error')).toBeTruthy();
      expect(screen.getByText('Retry')).toBeTruthy();
    });
  });

  it('shows title header', async () => {
    mockGetClientRequests.mockResolvedValue([]);
    await render(<BookingsScreen />);
    expect(screen.getByText('My Appointments')).toBeTruthy();
  });

  it('navigates to ClientRequestDetail with the requestId when a card is tapped', async () => {
    mockGetClientRequests.mockResolvedValue([
      {
        request_id: 'req-42',
        pet_name: 'Buddy',
        service_type: 'WALK_20MIN',
        status: 'QUOTE_SENT',
        selected_dates: ['2026-10-10'],
        created_at: '2026-10-01',
      },
    ]);
    await render(<BookingsScreen />);
    const card = await screen.findByLabelText(/View booking details for Buddy/);
    fireEvent.press(card);
    expect(mockNavigate).toHaveBeenCalledWith('ClientRequestDetail', { requestId: 'req-42' });
  });
});
