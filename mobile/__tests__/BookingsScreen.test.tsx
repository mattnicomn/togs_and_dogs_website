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
    });
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
});
