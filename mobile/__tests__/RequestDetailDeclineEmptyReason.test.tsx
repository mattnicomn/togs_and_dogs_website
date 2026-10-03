/**
 * OPS-2A Mobile Request Processing — Decline with no reason entered.
 *
 * Isolated in its own file: under jest-expo + React 19 a single async-mutating
 * render of RequestDetailScreen leaves the shared renderer in a state that
 * breaks the next render in the same file, so each async-mutating decline test
 * lives in a dedicated file. See RequestDetailDecline.test.tsx for the rationale.
 *
 * Reason is optional: declining with an empty reason still calls reviewRequest
 * with status DECLINED and an empty-string reason. No new RequestStatus, no
 * NEEDS_CLIENT_INFO, no logout.
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

describe('OPS-2A Decline — empty reason', () => {
  it('declines with an empty reason when none is entered', async () => {
    mockRole = 'owner';
    const view = await renderDetail({ request: request() });
    fireEvent.changeText(view.getByPlaceholderText(/Why is this request being declined/), '');
    fireEvent.press(view.getByText('Decline Booking'));
    await fireEvent.press(await view.findByText('Confirm Decline Pet Booking?'));
    await waitFor(() => expect(mockReviewRequest).toHaveBeenCalledWith('req-1', 'client-1', 'DECLINED', ''));
    expect(mockLogout).not.toHaveBeenCalled();
  });
});
