import React from 'react';
import { fireEvent, render, screen, act } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import CareCard from '../src/components/CareCard';

// Mock the payment API so no real AWS/Stripe/Cognito/Google calls occur.
vi.mock('../src/api/client', () => ({
  createPaymentSession: vi.fn(),
  sendPaymentEmail: vi.fn(),
}));

import { sendPaymentEmail } from '../src/api/client';

// Fixed wall-clock anchor for deterministic countdown math.
const NOW = new Date('2026-10-12T08:00:00.000Z').getTime();

const makePet = (originOverrides = {}, petOverrides = {}) => ({
  pet_id: 'pet-buddy',
  client_id: 'client-123',
  name: 'Buddy',
  species: 'DOG',
  status: 'APPROVED',
  _originItem: {
    request_id: 'request-123',
    client_id: 'client-123',
    linked_client_profile_id: 'client-123',
    client_email: 'owner@example.test',
    status: 'APPROVED',
    // Payment-link-sent state is what surfaces the Send Payment Email UI
    payment_status: 'payment_link_sent',
    stripe_payment_url: 'https://pay.example.test/session/abc',
    ...originOverrides,
  },
  ...petOverrides,
});

const makeProps = (pet, overrides = {}) => ({
  pet,
  onClose: vi.fn(),
  onUpdate: vi.fn().mockResolvedValue(undefined),
  onStatusUpdate: vi.fn().mockResolvedValue(undefined),
  onPaymentSessionCreated: vi.fn().mockResolvedValue(undefined),
  userRole: 'owner',
  ...overrides
});

// The payment-email cooldown UI lives in the "Meet & Greet / Quote" (quoting)
// tab. Open it after rendering, then read the live Send button label.
const openQuotingTab = () => {
  act(() => {
    fireEvent.click(screen.getByText('Meet & Greet / Quote'));
  });
};

const renderCard = (props) => {
  let utils;
  act(() => {
    utils = render(<CareCard {...props} />);
  });
  openQuotingTab();
  return utils;
};

const sendButton = () =>
  screen.getByRole('button', { name: /Send Payment Email/i });

describe('CareCard payment-email cooldown/countdown (Gate C3b.2h Batch 4A)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
    vi.setSystemTime(NOW);
  });

  afterEach(() => {
    vi.runOnlyPendingTimers();
    vi.useRealTimers();
  });

  it('1. shows no cooldown when there is no prior send timestamp', () => {
    const pet = makePet({ payment_email_sent_at: undefined });
    renderCard(makeProps(pet));

    const btn = sendButton();
    expect(btn).toHaveTextContent('Send Payment Email');
    expect(btn).not.toHaveTextContent(/Wait/);
    // Enabled (client email present, no cooldown).
    expect(btn).not.toBeDisabled();
    expect(screen.queryByText(/Send Disabled \(Cooldown\)/)).not.toBeInTheDocument();
  });

  it('2. displays the correct remaining time for an active cooldown', () => {
    // Sent 30s ago -> 90s remaining of the 120s window.
    const sentAt = new Date(NOW - 30000).toISOString();
    const pet = makePet({ payment_email_sent_at: sentAt });
    renderCard(makeProps(pet));

    expect(sendButton()).toHaveTextContent('Wait 90s');
    expect(sendButton()).toBeDisabled();
    expect(screen.getByText(/wait 90 seconds/i)).toBeInTheDocument();
  });

  it('3. counts down as time advances', () => {
    const sentAt = new Date(NOW - 10000).toISOString(); // 110s remaining
    const pet = makePet({ payment_email_sent_at: sentAt });
    renderCard(makeProps(pet));

    expect(sendButton()).toHaveTextContent('Wait 110s');

    act(() => { vi.advanceTimersByTime(5000); }); // +5s elapsed
    expect(sendButton()).toHaveTextContent('Wait 105s');

    act(() => { vi.advanceTimersByTime(5000); });
    expect(sendButton()).toHaveTextContent('Wait 100s');
  });

  it('4. clears the cooldown at the 120s boundary', () => {
    const sentAt = new Date(NOW - 118000).toISOString(); // 2s remaining
    const pet = makePet({ payment_email_sent_at: sentAt });
    renderCard(makeProps(pet));

    expect(sendButton()).toHaveTextContent('Wait 2s');

    act(() => { vi.advanceTimersByTime(2000); }); // reach exactly 120s elapsed
    const btn = sendButton();
    expect(btn).toHaveTextContent('Send Payment Email');
    expect(btn).not.toHaveTextContent(/Wait/);
    expect(btn).not.toBeDisabled();
    expect(screen.queryByText(/Send Disabled \(Cooldown\)/)).not.toBeInTheDocument();
  });

  it('5. a newly supplied send timestamp restarts the countdown', () => {
    const pet = makePet({ payment_email_sent_at: new Date(NOW - 60000).toISOString() }); // 60s left
    const { rerender } = renderCard(makeProps(pet));
    expect(sendButton()).toHaveTextContent('Wait 60s');

    // Parent re-sends: a brand-new timestamp (now) should reset to the full window.
    const refreshed = makePet({ payment_email_sent_at: new Date(NOW).toISOString() });
    act(() => { rerender(<CareCard {...makeProps(refreshed)} />); });

    expect(sendButton()).toHaveTextContent('Wait 120s');
  });

  it('6. switching to another request does not show the previous request cooldown', () => {
    const petA = makePet({ payment_email_sent_at: new Date(NOW - 30000).toISOString() }); // cooling down
    const { rerender } = renderCard(makeProps(petA));
    expect(sendButton()).toHaveTextContent('Wait 90s');

    // Switch to a different request with no prior send -> no cooldown leaks in.
    const petB = makePet(
      { request_id: 'request-999', payment_email_sent_at: undefined },
      { pet_id: 'pet-other', name: 'Rex' }
    );
    act(() => { rerender(<CareCard {...makeProps(petB)} />); });

    const btn = sendButton();
    expect(btn).toHaveTextContent('Send Payment Email');
    expect(btn).not.toHaveTextContent(/Wait/);
  });

  it('7. clears the interval on unmount (no further ticks fire)', () => {
    const clearSpy = vi.spyOn(globalThis, 'clearInterval');
    const pet = makePet({ payment_email_sent_at: new Date(NOW - 30000).toISOString() });
    const { unmount } = renderCard(makeProps(pet));

    expect(sendButton()).toHaveTextContent('Wait 90s');
    const callsBefore = clearSpy.mock.calls.length;
    act(() => { unmount(); });
    expect(clearSpy.mock.calls.length).toBeGreaterThan(callsBefore);

    clearSpy.mockRestore();
  });

  it('8. sending starts the local cooldown and issues exactly one send request', async () => {
    sendPaymentEmail.mockResolvedValue({ ok: true });
    const pet = makePet({ payment_email_sent_at: undefined });
    const props = makeProps(pet);
    renderCard(props);

    // Open the confirm modal, then confirm the send.
    act(() => { fireEvent.click(sendButton()); });
    const confirmBtn = screen.getByRole('button', { name: /^Send Email$/i });

    await act(async () => {
      fireEvent.click(confirmBtn);
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(sendPaymentEmail).toHaveBeenCalledTimes(1);
    expect(sendPaymentEmail).toHaveBeenCalledWith('request-123', 'client-123');
    // Optimistic local cooldown engages immediately (full 120s window).
    expect(sendButton()).toHaveTextContent('Wait 120s');
    expect(props.onPaymentSessionCreated).toHaveBeenCalledTimes(1);
  });
});
