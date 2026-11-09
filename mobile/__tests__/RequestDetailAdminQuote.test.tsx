import React from 'react';
import { fireEvent, render, waitFor } from '@testing-library/react-native';

const mockRead = jest.fn();
const mockUpdate = jest.fn();
const mockSend = jest.fn();
const mockReview = jest.fn();
const mockStart = jest.fn();
const mockComplete = jest.fn();
let mockRole: string | null = 'owner';
const mockLogout = jest.fn();
jest.mock('../src/api/client', () => ({
  reviewRequest: (...a: any[]) => mockReview(...a),
  getAdminRequest: (...a: any[]) => mockRead(...a),
  startJob: (...a: any[]) => mockStart(...a),
  completeJob: (...a: any[]) => mockComplete(...a),
  updateAdminQuote: (...a: any[]) => mockUpdate(...a),
  sendAdminQuote: (...a: any[]) => mockSend(...a),
  assignWorker: jest.fn(),
}));
jest.mock('../src/auth/useAuth', () => ({ useAuth: () => ({ role: mockRole, logout: mockLogout }) }));
jest.mock('../src/hooks/useStaff', () => ({ useStaff: () => ({ staff: [], isLoading: false, error: null, refresh: jest.fn() }) }));
jest.mock('../src/components/StatusBadge', () => ({ StatusBadge: () => null }));
jest.mock('../src/components/StaffPickerSheet', () => ({ StaffPickerSheet: () => null }));
jest.mock('../src/components/ContentContainer', () => ({ ContentContainer: ({ children }: any) => children }));
jest.mock('../src/components/ConfirmationModal', () => {
  const { Text, TouchableOpacity } = require('react-native');
  return {
    ConfirmationModal: ({ visible, title, message, onConfirm, onCancel }: any) =>
      visible ? (
        <>
          <Text>{message}</Text>
          <TouchableOpacity onPress={onConfirm}><Text>{`Confirm ${title}`}</Text></TouchableOpacity>
          <TouchableOpacity onPress={onCancel}><Text>{`Cancel ${title}`}</Text></TouchableOpacity>
        </>
      ) : null,
  };
});

import { RequestDetailScreen } from '../src/screens/RequestDetailScreen';

const booking = (extra: any = {}) => ({
  request_id: 'req-test',
  client_id: 'client-test',
  status: 'QUOTE_NEEDED',
  service_type: 'DROPIN_1HR',
  selected_dates: ['2026-10-29'],
  pet_names: ['Test Pet'],
  ...extra,
});
const screen = (request: any) =>
  render(<RequestDetailScreen route={{ params: { request } }} navigation={{ goBack: jest.fn() }} />);

beforeEach(() => {
  jest.clearAllMocks();
  mockRole = 'owner';
  mockRead.mockReset();
  mockUpdate.mockReset().mockResolvedValue({});
  mockSend.mockReset().mockResolvedValue({});
  mockReview.mockReset().mockResolvedValue({});
});

describe('S1: quote editor mounted in RequestDetailScreen', () => {
  it.each(['owner', 'admin'])('%s sees the editor (after hydration) and the updated QUOTE_NEEDED guidance', async role => {
    mockRole = role;
    mockRead.mockResolvedValueOnce(booking());
    const v = await screen(booking());
    expect(await v.findByLabelText('Save quote draft')).toBeTruthy();
    expect(mockRead).toHaveBeenCalledTimes(1); // exactly one hydration read
    expect(mockRead).toHaveBeenCalledWith('req-test', 'client-test');
    expect(v.getByText(/Prepare the quote in the Quote section on this screen/)).toBeTruthy();
    expect(v.queryByText(/web quote editor/i)).toBeNull();
  });

  it.each(['staff', 'client', 'unknown', null])('role %p never sees the editor', async role => {
    mockRole = role as any;
    const v = await screen(booking({ status: 'ASSIGNED', job_ids: ['a'] }));
    expect(v.queryByLabelText('Save quote draft')).toBeNull();
    expect(v.queryByLabelText('Quote amount')).toBeNull();
    expect(v.queryByLabelText('Send quote to client')).toBeNull();
    expect(v.queryByText('Loading the latest quote…')).toBeNull();
    expect(mockRead).not.toHaveBeenCalled(); // no quote hydration for non-owner/admin roles
  });

  it('incomplete list payload from navigation: hydrates, then the first save succeeds (no false stale refusal)', async () => {
    const listShaped = { request_id: 'req-test', client_id: 'client-test', status: 'QUOTE_NEEDED', pet_names: ['Test Pet'] };
    const full = booking({ quote_status: 'DRAFT', quote_revision: 1, quote_amount_cents: 5000, currency: 'USD', deposit_amount_cents: 0, payment_requirement: 'NONE', quote_notes_internal: 'full-read only' });
    mockRead
      .mockResolvedValueOnce(full) // hydration
      .mockResolvedValueOnce(full) // pre-save guard
      .mockResolvedValueOnce({ ...full, quote_amount_cents: 8000 }); // post-save refresh
    const v = await screen(listShaped);
    const amount = await v.findByLabelText('Quote amount');
    expect(amount.props.value).toBe('50.00');
    await fireEvent.changeText(amount, '80');
    await fireEvent.press(v.getByLabelText('Save quote draft'));
    await waitFor(() => expect(v.getByText('Quote saved.')).toBeTruthy());
    expect(v.queryByText(/changed since it was loaded/)).toBeNull();
    expect(mockUpdate).toHaveBeenCalledTimes(1);
    expect(mockUpdate.mock.calls[0][1]).toMatchObject({ quote_amount_cents: 8000, quote_notes_internal: 'full-read only' });
  });

  it('saves a draft through the screen and merges only quote fields back (status mirror updates)', async () => {
    mockRead
      .mockResolvedValueOnce(booking()) // hydration
      .mockResolvedValueOnce(booking()) // guard
      .mockResolvedValueOnce(booking({ status: 'QUOTE_NEEDED', quote_status: 'DRAFT', quote_revision: 1, quote_amount_cents: 10000, currency: 'USD', deposit_amount_cents: 0, payment_requirement: 'NONE' }));
    const v = await screen(booking());
    await fireEvent.changeText(await v.findByLabelText('Quote amount'), '100');
    await fireEvent.press(v.getByLabelText('Save quote draft'));
    await waitFor(() => expect(v.getByText('Quote saved.')).toBeTruthy());
    expect(mockUpdate).toHaveBeenCalledWith('req-test', expect.objectContaining({ quote_amount_cents: 10000 }));
    expect(v.getByText('Status: Draft (not sent)')).toBeTruthy();
    expect(mockReview).not.toHaveBeenCalled();
    expect(mockStart).not.toHaveBeenCalled();
    expect(mockComplete).not.toHaveBeenCalled();
  });

  it('sending a quote never approves the booking or touches visit operations', async () => {
    const drafted = booking({ quote_status: 'DRAFT', quote_revision: 1, quote_amount_cents: 10000, currency: 'USD', deposit_amount_cents: 0, payment_requirement: 'NONE' });
    mockRead
      .mockResolvedValueOnce(drafted) // hydration
      .mockResolvedValueOnce(drafted) // guard
      .mockResolvedValueOnce({ ...drafted, status: 'QUOTE_SENT', quote_status: 'SENT' });
    const v = await screen(drafted);
    await fireEvent.press(await v.findByLabelText('Send quote to client'));
    await fireEvent.press(v.getByText('Confirm Send quote to client?'));
    await waitFor(() => expect(v.getByText('Quote sent to the client.')).toBeTruthy());
    expect(mockSend).toHaveBeenCalledTimes(1);
    expect(mockReview).not.toHaveBeenCalled();
    expect(mockStart).not.toHaveBeenCalled();
    expect(mockComplete).not.toHaveBeenCalled();
  });

  it('a 401 from the quote API logs the user out via the existing auth path', async () => {
    mockRead.mockResolvedValue(booking());
    mockUpdate.mockRejectedValueOnce(Object.assign(new Error('Your session expired. Please sign in again.'), { status: 401 }));
    const v = await screen(booking());
    await fireEvent.changeText(await v.findByLabelText('Quote amount'), '100');
    await fireEvent.press(v.getByLabelText('Save quote draft'));
    await waitFor(() => expect(mockLogout).toHaveBeenCalledTimes(1));
  });

  it('hydration failure on the screen shows a truthful error and a read-only Retry; other actions unaffected', async () => {
    mockRead.mockRejectedValueOnce(new Error('Network request failed')).mockResolvedValueOnce(booking());
    const v = await screen(booking());
    expect(await v.findByText(/We couldn't load the latest quote, so editing is unavailable/)).toBeTruthy();
    expect(v.queryByLabelText('Save quote draft')).toBeNull();
    await fireEvent.press(v.getByLabelText('Retry loading quote'));
    expect(await v.findByLabelText('Save quote draft')).toBeTruthy();
    expect(mockUpdate).not.toHaveBeenCalled();
    expect(mockReview).not.toHaveBeenCalled();
  });
});
