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

  // ---- W4 Option A: workflow-summary badge regression ----
  describe('W4 workflow-summary status badges', () => {
    const renderWithStatus = async (status: string) => {
      mockGetClientRequests.mockResolvedValue([
        {
          request_id: `req-${status}`,
          pet_name: 'Rex',
          service_type: 'PET_SITTING',
          status,
          selected_dates: ['2026-10-10'],
          created_at: '2026-10-01',
        },
      ]);
      await render(<BookingsScreen />);
      await screen.findByText(/Rex/);
    };

    it.each(['QUOTE_NEEDED', 'QUOTE_SENT', 'QUOTED'])(
      'does not render raw %s enum on the card badge',
      async (status) => {
        await renderWithStatus(status);
        expect(screen.queryByText(status)).toBeNull();
        expect(screen.queryByText(/QUOTE/)).toBeNull();
        // Collapses to neutral workflow-summary wording.
        expect(screen.getByText('In Review')).toBeTruthy();
      }
    );

    it('does not synthesize commercial quote wording from RequestStatus', async () => {
      await renderWithStatus('QUOTE_SENT');
      expect(screen.queryByText(/quote/i)).toBeNull();
      expect(screen.queryByText(/payment/i)).toBeNull();
      expect(screen.queryByText(/accepted/i)).toBeNull();
      expect(screen.queryByText(/declined/i)).toBeNull();
    });

    it('known non-quote status still renders a sensible label', async () => {
      await renderWithStatus('APPROVED');
      expect(screen.getByText('Approved')).toBeTruthy();
    });

    it('terminal DECLINED request renders "Declined", not the neutral "In Review"', async () => {
      await renderWithStatus('DECLINED');
      expect(screen.getByText('Declined')).toBeTruthy();
      expect(screen.queryByText('In Review')).toBeNull();
      // Request-oriented wording only: no commercial quote claim on the list card.
      expect(screen.queryByText(/quote/i)).toBeNull();
    });

    it('unknown status does not render raw enum text', async () => {
      await renderWithStatus('SOME_FUTURE_STATUS');
      expect(screen.queryByText('SOME_FUTURE_STATUS')).toBeNull();
      expect(screen.getByText('In Review')).toBeTruthy();
    });

    it('does NOT fetch per-row canonical quote data for the list', async () => {
      // The quote-detail endpoint module is not imported/mocked here; the bookings
      // screen must rely solely on getClientRequests. Assert no quote fetch helper
      // was wired into the list path.
      await renderWithStatus('QUOTE_SENT');
      expect(mockGetClientRequests).toHaveBeenCalledTimes(1);
      // getClientRequests is the ONLY client API the screen imports; there is no
      // getClientQuote call per row (the detail screen owns that fetch).
    });
  });
});
