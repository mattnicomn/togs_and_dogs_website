/**
 * Phase 24A-2C.1C: Mobile Request-Status Display Compatibility Tests
 *
 * Verifies contract-backed request status label rendering in StatusBadge and BookingsScreen
 * while asserting customer contextual overrides and alias behavior preservation.
 */
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react-native';
import { StatusBadge } from '../src/components/StatusBadge';
import { BookingsScreen } from '../src/screens/BookingsScreen';
import { REQUEST_STATUSES } from '../src/contracts/generatedContracts';

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

beforeEach(() => {
  jest.clearAllMocks();
});

describe('Phase 24A-2C.1C Mobile Request-Status Display Compatibility', () => {

  describe('StatusBadge Uppercase Display & Alias Compatibility', () => {
    it('renders contract-backed PENDING_REVIEW label', async () => {
      const { getByText } = await render(<StatusBadge status="PENDING_REVIEW" />);
      expect(getByText(REQUEST_STATUSES.statuses.PENDING_REVIEW.label.toUpperCase())).toBeTruthy();
    });

    it('renders contract-backed MEET_GREET_REQUIRED label', async () => {
      const { getByText } = await render(<StatusBadge status="MEET_GREET_REQUIRED" />);
      expect(getByText(REQUEST_STATUSES.statuses.MEET_GREET_REQUIRED.label.toUpperCase())).toBeTruthy();
    });

    it('renders contract-backed APPROVED label', async () => {
      const { getByText } = await render(<StatusBadge status="APPROVED" />);
      expect(getByText(REQUEST_STATUSES.statuses.APPROVED.label.toUpperCase())).toBeTruthy();
    });

    it('renders contract-backed COMPLETED label', async () => {
      const { getByText } = await render(<StatusBadge status="COMPLETED" />);
      expect(getByText(REQUEST_STATUSES.statuses.COMPLETED.label.toUpperCase())).toBeTruthy();
    });

    it('renders contract-backed CANCELLED label', async () => {
      const { getByText } = await render(<StatusBadge status="CANCELLED" />);
      expect(getByText(REQUEST_STATUSES.statuses.CANCELLED.label.toUpperCase())).toBeTruthy();
    });

    it('preserves alias badge mapping for JOB_CREATED', async () => {
      const { getByText } = await render(<StatusBadge status="JOB_CREATED" />);
      expect(getByText('ASSIGNED')).toBeTruthy();
    });

    it('preserves alias badge mapping for SCHEDULED', async () => {
      const { getByText } = await render(<StatusBadge status="SCHEDULED" />);
      expect(getByText('SCHEDULED')).toBeTruthy();
    });

    it('falls back to humanized status text for unmapped status strings', async () => {
      const { getByText } = await render(<StatusBadge status="CUSTOM_MOBILE_STATUS" />);
      expect(getByText('CUSTOM MOBILE STATUS')).toBeTruthy();
    });
  });

  describe('BookingsScreen Customer Status Label Wiring', () => {
    it('renders canonical contract labels for exact-match customer statuses', async () => {
      mockGetClientRequests.mockResolvedValue([
        { request_id: 'req-1', pet_name: 'Buddy', service_type: 'PET_SITTING', status: 'PENDING_REVIEW', selected_dates: ['2026-08-10'] },
        { request_id: 'req-2', pet_name: 'Max', service_type: 'PET_SITTING', status: 'APPROVED', selected_dates: ['2026-08-11'] },
        { request_id: 'req-3', pet_name: 'Bella', service_type: 'PET_SITTING', status: 'COMPLETED', selected_dates: ['2026-08-12'] },
        { request_id: 'req-4', pet_name: 'Charlie', service_type: 'PET_SITTING', status: 'CANCELLED', selected_dates: ['2026-08-13'] },
      ]);

      await render(<BookingsScreen />);

      await waitFor(() => {
        expect(screen.getByText('Pending Review')).toBeTruthy();
        expect(screen.getByText('Approved')).toBeTruthy();
        expect(screen.getByText('Completed')).toBeTruthy();
        expect(screen.getByText('Cancelled')).toBeTruthy();
      });
    });

    it('strictly preserves customer-facing "Scheduled" contextual override for ASSIGNED and JOB_CREATED', async () => {
      mockGetClientRequests.mockResolvedValue([
        { request_id: 'req-5', pet_name: 'Daisy', service_type: 'PET_SITTING', status: 'ASSIGNED', selected_dates: ['2026-08-14'] },
        { request_id: 'req-6', pet_name: 'Rocky', service_type: 'PET_SITTING', status: 'JOB_CREATED', selected_dates: ['2026-08-15'] },
      ]);

      await render(<BookingsScreen />);

      await waitFor(() => {
        const scheduledBadges = screen.getAllByText('Scheduled');
        expect(scheduledBadges.length).toBe(2);
      });
    });
  });

});
