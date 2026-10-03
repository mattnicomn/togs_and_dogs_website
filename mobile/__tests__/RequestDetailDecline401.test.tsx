/**
 * OPS-2A Mobile Request Processing — Decline 401 session-expiry failure.
 *
 * Isolated in its own file (see RequestDetailDecline.test.tsx for the jest-expo +
 * React 19 renderer-isolation rationale).
 *
 * A 401/session-expiry error must log the user out (consistent with the other
 * review handlers). We assert the behavioral contract via the logout side
 * effect, which the awaited catch continuation performs.
 */
import React from 'react';
import { fireEvent, render, waitFor } from '@testing-library/react-native';

const mockReviewRequest = jest.fn();
const mockLogout = jest.fn();
let mockRole = 'owner';

jest.mock('../src/api/client', () => ({
  reviewRequest: (...args: any[]) => mockReviewRequest(...args),
  assignWorker: jest.fn(),
  completeJob: jest.fn(),
  startJob: jest.fn(),
  getAdminRequest: jest.fn(),
}));
jest.mock('../src/auth/useAuth', () => ({ useAuth: () => ({ role: mockRole, logout: mockLogout }) }));
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
  service_type: 'DROPIN_1HR', selected_dates: ['2026-09-01'], status: 'PENDING_REVIEW', created_at: 'x',
  ...extra,
});
const renderDetail = (params: any) => render(<RequestDetailScreen route={{ params }} navigation={{ goBack: jest.fn() }} />);

beforeEach(() => {
  jest.clearAllMocks();
  mockRole = 'owner';
  mockReviewRequest.mockResolvedValue({ status: 'DECLINED' });
});

describe('OPS-2A Decline — 401 session-expiry failure', () => {
  it('logs out on a 401/session-expiry failure', async () => {
    mockRole = 'owner';
    mockReviewRequest.mockRejectedValue(new Error('Your session expired. Please sign in again.'));
    const view = await renderDetail({ request: request() });
    fireEvent.changeText(view.getByPlaceholderText(/Why is this request being declined/), 'x');
    fireEvent.press(view.getByText('Decline Booking'));
    await fireEvent.press(await view.findByText('Confirm Decline Pet Booking?'));

    await waitFor(() => expect(mockLogout).toHaveBeenCalledTimes(1));
  });
});
