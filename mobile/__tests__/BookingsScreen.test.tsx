/**
 * Phase 24A-3: BookingsScreen Baseline Smoke Test
 *
 * Tests existing client bookings screen behavior with mocked API and auth.
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
  it('shows loading state initially', () => {
    mockGetClientRequests.mockReturnValue(new Promise(() => {})); // Never resolves
    render(<BookingsScreen />);
    expect(screen.getByText('Loading your appointments...')).toBeTruthy();
  });

  it('shows empty state when no bookings exist', async () => {
    mockGetClientRequests.mockResolvedValue([]);
    render(<BookingsScreen />);

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
    render(<BookingsScreen />);

    await waitFor(() => {
      expect(screen.getByText(/Buddy/)).toBeTruthy();
    });
  });

  it('shows error state on API failure', async () => {
    mockGetClientRequests.mockRejectedValue(new Error('Network error'));
    render(<BookingsScreen />);

    await waitFor(() => {
      expect(screen.getByText('Network error')).toBeTruthy();
      expect(screen.getByText('Retry')).toBeTruthy();
    });
  });
});
