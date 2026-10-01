/**
 * OPS-1 Mobile Visit Operations MVP — visit-action error handling.
 *
 * Scope: how RequestDetailScreen handles backend errors for Start/Complete.
 *
 * Error classification (confirmed from source):
 *   A. Authentication/session failure — HTTP 401, or expired/invalid session.
 *      The mobile API client (src/api/client.ts) centrally normalizes 401 (and any
 *      "expired"/"unauthorized" message) to the single error
 *      "Your session expired. Please sign in again." The screen then decides
 *      whether to log out.
 *   B. Authorization/permission failure — HTTP 403 (authenticated user lacks
 *      permission / is not the assigned worker). The API client throws the
 *      backend's permission message verbatim (e.g. "You can only start visits
 *      assigned to you."), which contains no "expired"/"unauthorized" substring.
 *
 * Intended behavioral principle:
 *   - 401/auth failure  -> consistent session-recovery behavior (logout).
 *   - 403/authz failure -> show a permission error in-screen WITHOUT logout.
 *
 * The 403 tests are the stable OPS-1 authorization contract. The 401 tests verify
 * consistent session recovery across Start and Complete.
 *
 * OPS-1 auth-handling fix (2026-09-30): handleStart previously lacked the
 * auth-session logout branch that handleMarkCompleted / handleApprove /
 * handleConfirmAssignment have, so an expired session during Start was shown inline
 * instead of recovering the session. The bounded fix in RequestDetailScreen.handleStart
 * now inspects the original Start error after reconciliation fails and logs out on a
 * normalized session failure. See
 * docs/planning/petcare-hero-operational-workflow-mobile-first.md (OPS-1 auth fix).
 */
import React from 'react';
import { fireEvent, render, waitFor } from '@testing-library/react-native';

const mockStartJob = jest.fn();
const mockCompleteJob = jest.fn();
const mockGetAdminRequest = jest.fn();
const mockReviewRequest = jest.fn();
const mockLogout = jest.fn();

jest.mock('../src/api/client', () => ({
  startJob: (...args: any[]) => mockStartJob(...args),
  completeJob: (...args: any[]) => mockCompleteJob(...args),
  getAdminRequest: (...args: any[]) => mockGetAdminRequest(...args),
  reviewRequest: (...args: any[]) => mockReviewRequest(...args),
  assignWorker: jest.fn(),
}));
jest.mock('../src/auth/useAuth', () => ({ useAuth: () => ({ role: 'staff', logout: mockLogout }) }));
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

// The signed-in staff member in these tests is staff@example.test (see useAuth mock).
const request = (extra: any = {}) => ({
  request_id: 'req-1', client_id: 'client-1', pet_name: 'Pet', client_name: 'Client',
  service_type: 'CHECK_IN', selected_dates: ['2026-09-01'], status: 'ASSIGNED', created_at: 'x',
  worker_id: 'staff@example.test', ...extra,
});
const occurrence = (extra: any = {}) => ({
  job_id: 'job-a', request_id: 'req-1', occurrence_date: '2026-09-01',
  occurrence_window: 'MORNING', status: 'ASSIGNED', ...extra,
});
const renderDetail = (params: any) => render(<RequestDetailScreen route={{ params }} navigation={{ goBack: jest.fn() }} />);

// The mobile API client maps a 403 permission failure to the backend message verbatim.
const START_PERMISSION_ERROR = 'You can only start visits assigned to you.';
const COMPLETE_PERMISSION_ERROR = 'You can only complete visits assigned to you.';
const SESSION_EXPIRED = 'Your session expired. Please sign in again.';

beforeEach(() => {
  jest.clearAllMocks();
  mockStartJob.mockReset();
  mockCompleteJob.mockReset();
  mockGetAdminRequest.mockReset();
  mockReviewRequest.mockReset();
  mockLogout.mockReset();
});

describe('OPS-1 visit-action authorization (403) handling — stable contract', () => {
  it('Start: 403 permission failure shows the error in-screen and does NOT log out', async () => {
    mockStartJob.mockRejectedValue(new Error(START_PERMISSION_ERROR));
    // Reconciliation refetch also denies (403), so no fake Started state is applied.
    mockGetAdminRequest.mockRejectedValue(new Error(START_PERMISSION_ERROR));
    const view = await renderDetail({ request: request(), occurrence: occurrence() });

    await fireEvent.press(view.getByText('Start Visit'));

    await waitFor(() => expect(mockStartJob).toHaveBeenCalledWith('job-a', 'req-1'));
    expect(await view.findByText(new RegExp(START_PERMISSION_ERROR))).toBeTruthy();
    expect(mockLogout).not.toHaveBeenCalled();
    // Action remains retryable; no fake Started state.
    expect(view.queryByText(/^Started /)).toBeNull();
    expect(view.getByText('Start Visit')).toBeTruthy();
  });

  it('Complete: 403 permission failure shows the error in-screen and does NOT log out', async () => {
    mockCompleteJob.mockRejectedValue(new Error(COMPLETE_PERMISSION_ERROR));
    const view = await renderDetail({ request: request(), occurrence: occurrence({ started_at: '2026-09-01T12:00:00Z' }) });

    await fireEvent.press(view.getByText('Complete Visit'));
    await fireEvent.press(await view.findByText('Confirm Mark Visit Completed?'));

    await waitFor(() => expect(mockCompleteJob).toHaveBeenCalledWith('job-a', 'req-1', ''));
    expect(mockLogout).not.toHaveBeenCalled();
    expect(mockReviewRequest).not.toHaveBeenCalled();
  });
});

describe('OPS-1 visit-action authentication (401) handling — session recovery', () => {
  it('Complete: 401/session-expiry triggers session recovery (logout)', async () => {
    mockCompleteJob.mockRejectedValue(new Error(SESSION_EXPIRED));
    const view = await renderDetail({ request: request(), occurrence: occurrence({ started_at: '2026-09-01T12:00:00Z' }) });

    await fireEvent.press(view.getByText('Complete Visit'));
    await fireEvent.press(await view.findByText('Confirm Mark Visit Completed?'));

    await waitFor(() => expect(mockLogout).toHaveBeenCalledTimes(1));
  });

  // OPS-1 auth-handling fix (2026-09-30): handleStart now applies the same
  // auth-session branch as its sibling handlers. A 401/session-expiry during Start,
  // when reconciliation does not prove the visit started, triggers session recovery.
  it('Start: 401/session-expiry triggers session recovery (logout) for consistency', async () => {
    mockStartJob.mockRejectedValue(new Error(SESSION_EXPIRED));
    // Reconciliation refetch also fails with the same session error (does not prove started).
    mockGetAdminRequest.mockRejectedValue(new Error(SESSION_EXPIRED));
    const view = await renderDetail({ request: request(), occurrence: occurrence() });

    await fireEvent.press(view.getByText('Start Visit'));

    // Reconciliation is attempted first, then the original 401 drives session recovery.
    await waitFor(() => expect(mockGetAdminRequest).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(mockLogout).toHaveBeenCalledTimes(1));
    // Session recovery replaces an inline session-expired message.
    expect(view.queryByText(/^Started /)).toBeNull();
  });
});
