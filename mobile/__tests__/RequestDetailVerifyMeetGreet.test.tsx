/**
 * OPS-2B Mobile Request Processing — Verify Meet & Greet (RequestDetailScreen).
 *
 * Verify reuses the existing `/admin/review` VERIFY_MEET_GREET pseudo-status via
 * the existing `reviewRequest` API client. The backend marks the client (and pet)
 * meet_and_greet_completed and, when a request_id is supplied, transitions the
 * request to MG_COMPLETED (src/backend/handlers/review_handler.py). No new
 * RequestStatus, no backend change, no notification/calendar side effect.
 *
 * RBAC: VERIFY_MEET_GREET is NOT a backend sensitive transition, so the backend
 * also permits staff. The mobile UI intentionally remains owner/admin-only
 * (explicit fail-closed allowlist) to match the web product intent and OPS-0
 * ("do not broaden UI permissions merely because the backend permits it").
 *
 * This suite covers visibility/RBAC gating plus the happy-path verify call. The
 * error-path variants live in dedicated sibling files
 * (RequestDetailVerifyMeetGreet401/403) because under jest-expo + React 19 a
 * single async-mutating render leaves the shared renderer in a state that breaks
 * the next render in the same file; one async-mutating test per file is the only
 * reliable isolation boundary. render(...) is awaited to obtain the query-bound
 * result (matching the passing RequestDetailE3B1 / Decline suites).
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
  service_type: 'DROPIN_1HR', selected_dates: ['2026-09-01'], status: 'MEET_GREET_REQUIRED', created_at: 'x',
  ...extra,
});
const renderDetail = (params: any) => render(<RequestDetailScreen route={{ params }} navigation={{ goBack: jest.fn() }} />);

beforeEach(() => {
  jest.clearAllMocks();
  mockRole = 'owner';
  mockReviewRequest.mockResolvedValue({ message: 'Meet & Greet status updated successfully', meet_and_greet_completed: true });
});

describe('OPS-2B Verify M&G — visibility and RBAC gating', () => {
  it('owner sees Verify Meet & Greet on a MEET_GREET_REQUIRED request', async () => {
    mockRole = 'owner';
    const view = await renderDetail({ request: request() });
    expect(view.getByText('Verify Meet & Greet')).toBeTruthy();
  });

  it('owner sees Verify Meet & Greet on an MG_SCHEDULED request', async () => {
    mockRole = 'owner';
    const view = await renderDetail({ request: request({ status: 'MG_SCHEDULED' }) });
    expect(view.getByText('Verify Meet & Greet')).toBeTruthy();
  });

  it('admin sees Verify Meet & Greet on a MEET_GREET_REQUIRED request', async () => {
    mockRole = 'admin';
    const view = await renderDetail({ request: request() });
    expect(view.getByText('Verify Meet & Greet')).toBeTruthy();
  });

  it('does NOT show Verify Meet & Greet for staff (fail closed)', async () => {
    mockRole = 'staff';
    const view = await renderDetail({ request: request() });
    expect(view.queryByText('Verify Meet & Greet')).toBeNull();
  });

  it('does NOT show Verify Meet & Greet for client (fail closed)', async () => {
    mockRole = 'client';
    const view = await renderDetail({ request: request() });
    expect(view.queryByText('Verify Meet & Greet')).toBeNull();
  });

  it('does NOT show Verify Meet & Greet for an unknown role (fail closed)', async () => {
    mockRole = 'unknown';
    const view = await renderDetail({ request: request() });
    expect(view.queryByText('Verify Meet & Greet')).toBeNull();
  });

  it('does NOT show Verify Meet & Greet when role is null during bootstrap (fail closed)', async () => {
    mockRole = null;
    const view = await renderDetail({ request: request() });
    expect(view.queryByText('Verify Meet & Greet')).toBeNull();
  });

  it('does NOT show Verify Meet & Greet on a PENDING_REVIEW request', async () => {
    mockRole = 'owner';
    const view = await renderDetail({ request: request({ status: 'PENDING_REVIEW' }) });
    expect(view.queryByText('Verify Meet & Greet')).toBeNull();
  });

  it('does NOT show Verify Meet & Greet on an APPROVED request', async () => {
    mockRole = 'owner';
    const view = await renderDetail({ request: request({ status: 'APPROVED' }) });
    expect(view.queryByText('Verify Meet & Greet')).toBeNull();
  });

  it('does NOT show Verify Meet & Greet once already MG_COMPLETED', async () => {
    mockRole = 'owner';
    const view = await renderDetail({ request: request({ status: 'MG_COMPLETED' }) });
    expect(view.queryByText('Verify Meet & Greet')).toBeNull();
  });
});

describe('OPS-2B Verify M&G — action behavior', () => {
  it('verifies via reviewRequest with VERIFY_MEET_GREET and does not log out; no new status introduced', async () => {
    mockRole = 'owner';
    const view = await renderDetail({ request: request() });
    fireEvent.press(view.getByText('Verify Meet & Greet'));
    await fireEvent.press(await view.findByText('Confirm Verify Meet & Greet?'));

    await waitFor(() => expect(mockReviewRequest).toHaveBeenCalledWith('req-1', 'client-1', 'VERIFY_MEET_GREET'));
    const calls = JSON.stringify(mockReviewRequest.mock.calls);
    expect(calls).not.toContain('IN_PROGRESS');
    expect(calls).not.toContain('NEEDS_CLIENT_INFO');
    expect(mockLogout).not.toHaveBeenCalled();
  });
});
