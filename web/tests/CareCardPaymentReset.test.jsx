import React from 'react';
import { fireEvent, render, screen, act } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import CareCard from '../src/components/CareCard';

// Mock the payment API so no real AWS/Stripe/Cognito/Google calls occur.
vi.mock('../src/api/client', () => ({
  createPaymentSession: vi.fn(),
  sendPaymentEmail: vi.fn(),
}));

import { createPaymentSession, sendPaymentEmail } from '../src/api/client';

const NOW = new Date('2026-10-12T08:00:00.000Z').getTime();

// A request in the "unpaid / not set" state surfaces the Amount-to-Charge input
// and the Generate Payment Link flow.
const makeUnpaidPet = (originOverrides = {}, petOverrides = {}) => ({
  pet_id: 'pet-buddy',
  client_id: 'client-123',
  name: 'Buddy',
  species: 'DOG',
  status: 'APPROVED',
  _originItem: {
    PK: 'REQ#request-123',
    request_id: 'request-123',
    client_id: 'client-123',
    linked_client_profile_id: 'client-123',
    client_email: 'owner@example.test',
    status: 'APPROVED',
    ...originOverrides,
  },
  ...petOverrides,
});

// A request in the "payment_link_sent" state surfaces the Send Payment Email
// button and the cooldown indicators.
const makeSentPet = (originOverrides = {}, petOverrides = {}) => ({
  pet_id: 'pet-buddy',
  client_id: 'client-123',
  name: 'Buddy',
  species: 'DOG',
  status: 'APPROVED',
  _originItem: {
    PK: 'REQ#request-123',
    request_id: 'request-123',
    client_id: 'client-123',
    linked_client_profile_id: 'client-123',
    client_email: 'owner@example.test',
    status: 'APPROVED',
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
  ...overrides,
});

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

const amountInput = () => screen.getByRole('spinbutton');
const sendButton = () => screen.getByRole('button', { name: /Send Payment Email/i });

// -- Payment / email transient-state reset -----------------------------------

describe('CareCard payment amount initialization & reset (Gate C3b.2k Batch 4B-2)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('1. seeds the amount from payment_amount_cents when present', () => {
    renderCard(makeProps(makeUnpaidPet({ payment_amount_cents: 4500 })));
    expect(amountInput()).toHaveValue(45);
  });

  it('2. falls back to quote_amount when no payment_amount_cents', () => {
    renderCard(makeProps(makeUnpaidPet({}, { quote_amount: '32.5' })));
    expect(amountInput()).toHaveValue(32.5);
  });

  it('3. payment_amount_cents takes precedence over quote_amount', () => {
    renderCard(makeProps(makeUnpaidPet({ payment_amount_cents: 7000 }, { quote_amount: '12.00' })));
    expect(amountInput()).toHaveValue(70);
  });

  it('4. empty when neither source is present', () => {
    renderCard(makeProps(makeUnpaidPet()));
    expect(amountInput()).toHaveValue(null);
  });

  it('5. an unrelated local rerender preserves a user-typed amount (same pet reference)', () => {
    const pet = makeUnpaidPet({ payment_amount_cents: 1000 });
    const props = makeProps(pet);
    const { rerender } = renderCard(props);
    expect(amountInput()).toHaveValue(10);

    // User overrides the amount.
    act(() => { fireEvent.change(amountInput(), { target: { value: '87.65' } }); });
    expect(amountInput()).toHaveValue(87.65);

    // Rerender with the SAME pet reference (unrelated prop/parent rerender).
    act(() => { rerender(<CareCard {...props} />); });
    expect(amountInput()).toHaveValue(87.65);
  });

  it('6. a same-request refresh (new pet reference) resets the typed amount and transient state', () => {
    const pet = makeUnpaidPet({ payment_amount_cents: 1000 });
    const { rerender } = renderCard(makeProps(pet));
    act(() => { fireEvent.change(amountInput(), { target: { value: '87.65' } }); });
    expect(amountInput()).toHaveValue(87.65);

    // Same request (same PK) but a NEW object reference, as the parent produces
    // on refresh. Approved behavior: transient state resets on every new ref.
    const refreshed = makeUnpaidPet({ payment_amount_cents: 1000 });
    act(() => { rerender(<CareCard {...makeProps(refreshed)} />); });
    expect(amountInput()).toHaveValue(10);
  });

  it('7. switching requests reseeds the amount from the new request', () => {
    const reqA = makeUnpaidPet({ PK: 'REQ#A', request_id: 'A', payment_amount_cents: 2500 });
    const { rerender } = renderCard(makeProps(reqA));
    expect(amountInput()).toHaveValue(25);

    const reqB = makeUnpaidPet({ PK: 'REQ#B', request_id: 'B', payment_amount_cents: 9900 });
    act(() => { rerender(<CareCard {...makeProps(reqB)} />); });
    expect(amountInput()).toHaveValue(99);
  });

  it('8. the generate-confirmation dialog clears when the pet prop refreshes', () => {
    const pet = makeUnpaidPet({ payment_amount_cents: 5000 });
    const { rerender } = renderCard(makeProps(pet));

    // Open the inline generate confirmation.
    act(() => { fireEvent.click(screen.getByRole('button', { name: /Generate Payment Link/i })); });
    expect(screen.getByText(/Are you sure you want to generate/i)).toBeInTheDocument();

    // A new pet reference (refresh) must clear the confirmation.
    const refreshed = makeUnpaidPet({ payment_amount_cents: 5000 });
    act(() => { rerender(<CareCard {...makeProps(refreshed)} />); });
    expect(screen.queryByText(/Are you sure you want to generate/i)).not.toBeInTheDocument();
  });

  it('9. generate payment link still issues exactly one API call with the correct amount', async () => {
    createPaymentSession.mockResolvedValue({
      payment_status: 'payment_link_sent',
      stripe_payment_url: 'https://pay.example.test/x',
      stripe_checkout_session_id: 'cs_1',
    });
    const pet = makeUnpaidPet({ payment_amount_cents: 4200 });
    const props = makeProps(pet);
    renderCard(props);

    act(() => { fireEvent.click(screen.getByRole('button', { name: /Generate Payment Link/i })); });
    const confirmBtn = screen.getByRole('button', { name: /Yes, Generate Link/i });

    await act(async () => {
      fireEvent.click(confirmBtn);
      await Promise.resolve();
    });

    expect(createPaymentSession).toHaveBeenCalledTimes(1);
    expect(createPaymentSession).toHaveBeenCalledWith('request-123', 'client-123', 4200);
  });
});

// -- Cooldown cross-request isolation ----------------------------------------

describe('CareCard cooldown cross-request isolation (Gate C3b.2k Batch 4B-2)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
    vi.setSystemTime(NOW);
  });

  afterEach(() => {
    vi.runOnlyPendingTimers();
    vi.useRealTimers();
  });

  it('10. two requests sharing the same payment_email_sent_at stay isolated after a send', async () => {
    sendPaymentEmail.mockResolvedValue({ ok: true });
    const sharedSentAt = new Date(NOW - 60000).toISOString(); // 60s elapsed -> 60s left

    // Request A: cooldown already active (60s remaining).
    const reqA = makeSentPet({ PK: 'REQ#A', request_id: 'A', payment_email_sent_at: sharedSentAt });
    const { rerender } = renderCard(makeProps(reqA));
    expect(sendButton()).toHaveTextContent('Wait 60s');

    // Switch to Request B which, by coincidence, carries the IDENTICAL
    // payment_email_sent_at. Its cooldown must be derived for B in its own
    // right (same timestamp -> same 60s), not leaked from A's state object.
    const reqB = makeSentPet({ PK: 'REQ#B', request_id: 'B', payment_email_sent_at: sharedSentAt });
    act(() => { rerender(<CareCard {...makeProps(reqB)} />); });
    expect(sendButton()).toHaveTextContent('Wait 60s');
  });

  it('11. an optimistic cooldown on request A does not leak into request B with the same timestamp', async () => {
    sendPaymentEmail.mockResolvedValue({ ok: true });
    // Request A has NO prior send -> no cooldown; sending engages optimistic 120s.
    const reqA = makeSentPet({ PK: 'REQ#A', request_id: 'A', payment_email_sent_at: undefined });
    const props = makeProps(reqA);
    const { rerender } = renderCard(props);
    expect(sendButton()).toHaveTextContent('Send Payment Email');

    act(() => { fireEvent.click(sendButton()); });
    const confirmBtn = screen.getByRole('button', { name: /^Send Email$/i });
    await act(async () => {
      fireEvent.click(confirmBtn);
      await Promise.resolve();
      await Promise.resolve();
    });
    // Optimistic cooldown engaged for A.
    expect(sendButton()).toHaveTextContent('Wait 120s');

    // Switch to request B (different identity) that has no prior send. B must
    // NOT inherit A's optimistic 120s cooldown.
    const reqB = makeSentPet({ PK: 'REQ#B', request_id: 'B', payment_email_sent_at: undefined });
    act(() => { rerender(<CareCard {...makeProps(reqB)} />); });
    const btn = sendButton();
    expect(btn).toHaveTextContent('Send Payment Email');
    expect(btn).not.toHaveTextContent(/Wait/);
  });

  it('12. send-email still issues exactly one API call and engages the local cooldown', async () => {
    sendPaymentEmail.mockResolvedValue({ ok: true });
    const pet = makeSentPet({ payment_email_sent_at: undefined });
    const props = makeProps(pet);
    renderCard(props);

    act(() => { fireEvent.click(sendButton()); });
    const confirmBtn = screen.getByRole('button', { name: /^Send Email$/i });
    await act(async () => {
      fireEvent.click(confirmBtn);
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(sendPaymentEmail).toHaveBeenCalledTimes(1);
    expect(sendPaymentEmail).toHaveBeenCalledWith('request-123', 'client-123');
    expect(sendButton()).toHaveTextContent('Wait 120s');
    expect(props.onPaymentSessionCreated).toHaveBeenCalledTimes(1);
  });

  it('13. the countdown still ticks and clears at the boundary (unchanged behavior)', () => {
    const pet = makeSentPet({ payment_email_sent_at: new Date(NOW - 118000).toISOString() }); // 2s left
    renderCard(makeProps(pet));
    expect(sendButton()).toHaveTextContent('Wait 2s');

    act(() => { vi.advanceTimersByTime(2000); });
    const btn = sendButton();
    expect(btn).toHaveTextContent('Send Payment Email');
    expect(btn).not.toHaveTextContent(/Wait/);
  });
});
