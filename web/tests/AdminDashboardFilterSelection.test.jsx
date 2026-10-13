import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import AdminDashboard from '../src/components/AdminDashboard';
import { getEffectiveRole, getSession } from '../src/api/auth';
import {
  getAdminRequests,
  getClients,
  getGoogleStatus,
  getStaff,
  getTenantInfo,
} from '../src/api/client';

vi.mock('../src/api/auth', () => ({
  signIn: vi.fn(),
  forgotPassword: vi.fn(),
  confirmForgotPassword: vi.fn(),
  getSession: vi.fn(),
  getEffectiveRole: vi.fn(),
}));

vi.mock('../src/api/client', () => ({
  getAdminRequests: vi.fn(),
  reviewRequest: vi.fn(),
  assignWorker: vi.fn(),
  getGoogleStatus: vi.fn(),
  initiateGoogleAuth: vi.fn(),
  getPet: vi.fn(),
  updatePet: vi.fn(),
  createPet: vi.fn(),
  processCancellationDecision: vi.fn(),
  performAdminAction: vi.fn(),
  purgeRecord: vi.fn(),
  purgeRecordsBulk: vi.fn(),
  getStaff: vi.fn(),
  createStaff: vi.fn(),
  updateStaff: vi.fn(),
  disableStaff: vi.fn(),
  onboardStaff: vi.fn(),
  linkCognitoUser: vi.fn(),
  resendInvite: vi.fn(),
  resetStaffPassword: vi.fn(),
  setStaffTempPassword: vi.fn(),
  getClients: vi.fn(),
  createClient: vi.fn(),
  updateClient: vi.fn(),
  disableClient: vi.fn(),
  onboardClient: vi.fn(),
  resendClientInvite: vi.fn(),
  resetClientPassword: vi.fn(),
  setClientTempPassword: vi.fn(),
  linkClientCognitoUser: vi.fn(),
  getExportData: vi.fn(),
  createAdminBooking: vi.fn(),
  listAdminClientPets: vi.fn(),
  getTenantInfo: vi.fn(),
}));

window.HTMLElement.prototype.scrollIntoView = vi.fn();
window.alert = vi.fn();

const mockSession = {
  getIdToken: () => ({
    payload: { email: 'owner@example.test', sub: 'owner-test', name: 'Owner Test' },
  }),
};

// A VISIT_BOOKING request awaiting approval (appears under All Active + Booking Queue).
const bookingReq = (id, overrides = {}) => ({
  PK: `REQ#${id}`,
  SK: `CLIENT#client-${id}`,
  entity_type: 'REQUEST',
  workflow_type: 'VISIT_BOOKING',
  request_id: id,
  client_id: `client-${id}`,
  status: 'READY_FOR_APPROVAL',
  client_name: `Client ${id}`,
  pet_name: `Pet ${id}`,
  pet_names: `Pet ${id}`,
  service_type: 'WALK_20MIN',
  payment_status: 'unpaid',
  start_date: new Date().toLocaleDateString('sv-SE'),
  ...overrides,
});

// The row renders the name as a single combined string: "<pet_names> (<client_name>)".
const rowText = (req) => `${req.pet_names} (${req.client_name})`;

const renderWithRequests = async (requests) => {
  getAdminRequests.mockResolvedValue({ requests });
  render(<AdminDashboard />);
  fireEvent.click(await screen.findByRole('button', { name: 'Request List' }));
  fireEvent.click(await screen.findByRole('button', { name: /All Active/ }));
  // Wait for the first request's combined pet/client label to render.
  await screen.findByText(rowText(requests[0]));
};

describe('AdminDashboard filtering + selection (Gate C3b.2f Batch 3A)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getSession.mockResolvedValue(mockSession);
    getEffectiveRole.mockReturnValue('owner');
    getGoogleStatus.mockResolvedValue({ status: 'CONNECTED' });
    getTenantInfo.mockResolvedValue({ display_name: 'Synthetic Co', calendar_enabled: true });
    getStaff.mockResolvedValue({ staff: [] });
    getClients.mockResolvedValue({ clients: [] });
  });

  it('1. All Active shows active requests; payment/search filtering narrows them', async () => {
    const alpha = bookingReq('alpha', { client_name: 'Alpha Client', pet_names: 'Alpha Pet' });
    const beta = bookingReq('beta', { client_name: 'Beta Client', pet_names: 'Beta Pet', payment_status: 'paid' });
    await renderWithRequests([alpha, beta]);

    expect(screen.getByText(rowText(alpha))).toBeInTheDocument();
    expect(screen.getByText(rowText(beta))).toBeInTheDocument();

    // Text search narrows to the matching client.
    const search = screen.getByPlaceholderText(/search/i);
    fireEvent.change(search, { target: { value: 'Alpha' } });
    await waitFor(() => {
      expect(screen.getByText(rowText(alpha))).toBeInTheDocument();
      expect(screen.queryByText(rowText(beta))).not.toBeInTheDocument();
    });
  });

  it('2. selecting a row then changing the status filter clears the selection', async () => {
    await renderWithRequests([bookingReq('alpha', { client_name: 'Alpha Client', pet_names: 'Alpha Pet' })]);

    // Select the row via its checkbox (aria-label uses pet_names first).
    const checkbox = screen.getByLabelText('Select Alpha Pet', { selector: 'input[type="checkbox"]' });
    fireEvent.click(checkbox);
    // Bulk toolbar appears, confirming one row is selected.
    await waitFor(() => expect(screen.getByText(/visits selected/i)).toBeInTheDocument());
    expect(screen.getByRole('checkbox', { name: 'Select Alpha Pet' })).toBeChecked();

    // Change the status filter -> selection must clear (render-phase reset).
    fireEvent.click(screen.getByRole('button', { name: /Booking Queue/i }));
    await waitFor(() => {
      expect(screen.queryByText(/visits selected/i)).not.toBeInTheDocument();
    });
  });

  it('3. selecting a row then an unrelated change (search text) preserves the selection', async () => {
    const alpha = bookingReq('alpha', { client_name: 'Alpha Client', pet_names: 'Alpha Pet' });
    const beta = bookingReq('beta', { client_name: 'Beta Client', pet_names: 'Beta Pet' });
    await renderWithRequests([alpha, beta]);

    const alphaCheckbox = screen.getByLabelText('Select Alpha Pet', { selector: 'input[type="checkbox"]' });
    fireEvent.click(alphaCheckbox);
    await waitFor(() => expect(screen.getByText(/visits selected/i)).toBeInTheDocument());

    // Unrelated state change: typing in search does NOT reset selection.
    fireEvent.change(screen.getByPlaceholderText(/search/i), { target: { value: 'Alpha' } });
    await waitFor(() => expect(screen.getByText(rowText(alpha))).toBeInTheDocument());
    expect(screen.getByText(/visits selected/i)).toBeInTheDocument();
  });

  it('4. changing the filter does not trigger an additional backend requests fetch for the memo', async () => {
    await renderWithRequests([bookingReq('alpha', { client_name: 'Alpha Client' })]);
    const callsAfterLoad = getAdminRequests.mock.calls.length;

    // Switching the status filter is a client-side memo recompute; the reactive
    // data-fetch effect is keyed on (view, statusFilter, timeframe) and will
    // refetch, but the memo/selection changes themselves must not add extra
    // calls beyond that single filter-driven refresh.
    fireEvent.click(screen.getByRole('button', { name: /Booking Queue/i }));
    await waitFor(() => {
      // At most one additional fetch for the filter change (debounced reactive
      // effect) — not multiple cascading fetches from the memo recompute.
      expect(getAdminRequests.mock.calls.length).toBeLessThanOrEqual(callsAfterLoad + 1);
    });
  });
});
