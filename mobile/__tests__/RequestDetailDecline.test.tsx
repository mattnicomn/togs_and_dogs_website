/**
 * OPS-2A Mobile Request Processing — Decline action (RequestDetailScreen).
 *
 * Decline reuses the existing `/admin/review` transition via the existing
 * `reviewRequest` API client (status 'DECLINED'). Backend treats DECLINED as an
 * owner/admin-only sensitive transition (src/backend/handlers/review_handler.py);
 * the mobile UI mirrors that by exposing Decline only for role !== 'staff' on a
 * PENDING_REVIEW request. No new RequestStatus, no NEEDS_CLIENT_INFO, no backend
 * change. Error handling: 401/session-expiry -> logout; 403/permission and 400
 * backend validation -> inline error, no logout.
 *
 * This suite covers Decline visibility/RBAC gating plus the happy-path decline
 * call. The error-path and empty-reason variants live in dedicated sibling files
 * (RequestDetailDecline401/403/EmptyReason) because under jest-expo + React 19 a
 * single async-mutating render leaves the shared renderer in a state that breaks
 * the next render in the same file; one async-mutating test per file is the only
 * reliable isolation boundary. render(...) is awaited to obtain the query-bound
 * result (matching the passing RequestDetailE3B1 suite).
 */
import React from 'react';
import { fireEvent, render, waitFor } from '@testing-library/react-native';

const mockReviewRequest = jest.fn();
const mockLogout = jest.fn();
let mockRole: string | null = 'owner';

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

describe('OPS-2A Decline — visibility and RBAC gating', () => {
  it('shows Decline for owner on a PENDING_REVIEW request alongside Approve', async () => {
    mockRole = 'owner';
    const view = await renderDetail({ request: request() });
    expect(view.getByText('Approve Booking')).toBeTruthy();
    expect(view.getByText('Decline Booking')).toBeTruthy();
  });

  it('shows Decline for admin on a PENDING_REVIEW request', async () => {
    mockRole = 'admin';
    const view = await renderDetail({ request: request() });
    expect(view.getByText('Decline Booking')).toBeTruthy();
  });

  it('does NOT show Decline for staff', async () => {
    mockRole = 'staff';
    const view = await renderDetail({ request: request() });
    expect(view.queryByText('Decline Booking')).toBeNull();
    expect(view.queryByText('Approve Booking')).toBeNull();
  });

  it('does NOT show Decline/Approve for client (fail closed)', async () => {
    mockRole = 'client';
    const view = await renderDetail({ request: request() });
    expect(view.queryByText('Decline Booking')).toBeNull();
    expect(view.queryByText('Approve Booking')).toBeNull();
  });

  it('does NOT show Decline/Approve for an unknown role (fail closed)', async () => {
    mockRole = 'unknown';
    const view = await renderDetail({ request: request() });
    expect(view.queryByText('Decline Booking')).toBeNull();
    expect(view.queryByText('Approve Booking')).toBeNull();
  });

  it('does NOT show Decline/Approve when role is null during bootstrap (fail closed)', async () => {
    mockRole = null;
    const view = await renderDetail({ request: request() });
    expect(view.queryByText('Decline Booking')).toBeNull();
    expect(view.queryByText('Approve Booking')).toBeNull();
  });

  it('does NOT show Decline once the request is no longer PENDING_REVIEW', async () => {
    mockRole = 'owner';
    const view = await renderDetail({ request: request({ status: 'APPROVED' }) });
    expect(view.queryByText('Decline Booking')).toBeNull();
  });
});

describe('OPS-2A Decline — action behavior', () => {
  it('declines via reviewRequest with DECLINED and the optional reason; no IN_PROGRESS / NEEDS_CLIENT_INFO; no logout', async () => {
    mockRole = 'owner';
    const view = await renderDetail({ request: request() });
    fireEvent.changeText(view.getByPlaceholderText(/Why is this request being declined/), 'Out of area');
    fireEvent.press(view.getByText('Decline Booking'));
    await fireEvent.press(await view.findByText('Confirm Decline Pet Booking?'));

    await waitFor(() => expect(mockReviewRequest).toHaveBeenCalledWith('req-1', 'client-1', 'DECLINED', 'Out of area'));
    const calls = JSON.stringify(mockReviewRequest.mock.calls);
    expect(calls).not.toContain('IN_PROGRESS');
    expect(calls).not.toContain('NEEDS_CLIENT_INFO');
    expect(mockLogout).not.toHaveBeenCalled();
  });

});
