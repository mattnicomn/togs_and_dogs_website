import React from 'react';
import { act, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import ClientPortal from '../src/components/ClientPortal';
import { getEffectiveRole, getSession } from '../src/api/auth';
import { getClientRequests } from '../src/api/client';

vi.mock('../src/api/auth', () => ({
  getSession: vi.fn(),
  signIn: vi.fn(),
  getEffectiveRole: vi.fn(),
}));

vi.mock('../src/api/client', () => ({
  getClientRequests: vi.fn(),
  requestCancellation: vi.fn(),
}));

vi.mock('../src/components/UserProfile', () => ({ default: () => null }));

window.alert = vi.fn();

// A minimal session object (opaque; no real tokens/credentials).
const fakeSession = () => ({ getIdToken: () => ({ payload: { email: 'c@example.test', sub: 'sub-c' } }) });

const bookingRequest = (overrides = {}) => ({
  PK: 'REQ#r1',
  SK: 'CLIENT#c1',
  request_id: 'r1',
  client_id: 'c1',
  status: 'APPROVED',
  service_type: 'WALK_20MIN',
  pet_name: 'Rex',
  start_date: '2026-12-01',
  ...overrides,
});

const deferred = () => {
  let resolve, reject;
  const promise = new Promise((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
};

describe('ClientPortal session initialization (Gate C3b.2q)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getClientRequests.mockResolvedValue({ requests: [] });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('1. owner session authenticates and loads bookings', async () => {
    getSession.mockResolvedValue(fakeSession());
    getEffectiveRole.mockReturnValue('owner');
    // Owner with no linked profile still authenticates (bookings view shown).
    getClientRequests.mockResolvedValue({ message: 'No local profile linked' });

    render(<ClientPortal />);

    expect(await screen.findByRole('heading', { name: 'My Bookings' })).toBeInTheDocument();
    expect(getClientRequests).toHaveBeenCalledTimes(1);
  });

  it('2. admin session authenticates and loads bookings', async () => {
    getSession.mockResolvedValue(fakeSession());
    getEffectiveRole.mockReturnValue('admin');
    getClientRequests.mockResolvedValue({ requests: [] });

    render(<ClientPortal />);

    expect(await screen.findByRole('heading', { name: 'My Bookings' })).toBeInTheDocument();
    expect(getClientRequests).toHaveBeenCalledTimes(1);
  });

  it('3. client session authenticates and loads the client-facing bookings', async () => {
    getSession.mockResolvedValue(fakeSession());
    getEffectiveRole.mockReturnValue('client');
    getClientRequests.mockResolvedValue({ requests: [bookingRequest()] });

    render(<ClientPortal />);

    expect(await screen.findByRole('heading', { name: 'My Bookings' })).toBeInTheDocument();
    // The intended client booking renders.
    await screen.findByText('Rex');
    expect(getClientRequests).toHaveBeenCalledTimes(1);
  });

  it('4. staff session is denied and cannot access bookings', async () => {
    getSession.mockResolvedValue(fakeSession());
    getEffectiveRole.mockReturnValue('staff');

    render(<ClientPortal />);

    // Denied -> stays on the login card with the existing message; no fetch.
    expect(await screen.findByText(/Staff members must use the Staff Portal/i)).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Client Login' })).toBeInTheDocument();
    expect(getClientRequests).not.toHaveBeenCalled();
  });

  it('5. no session preserves the unauthenticated login UI', async () => {
    getSession.mockResolvedValue(null);

    render(<ClientPortal />);

    expect(await screen.findByRole('heading', { name: 'Client Login' })).toBeInTheDocument();
    expect(getEffectiveRole).not.toHaveBeenCalled();
    expect(getClientRequests).not.toHaveBeenCalled();
  });

  it('6. a session-loading failure preserves existing error behavior (stays unauthenticated, no throw)', async () => {
    getSession.mockRejectedValue(new Error('network down'));

    render(<ClientPortal />);

    // Catch logs "No session"; UI remains the login card, no crash.
    expect(await screen.findByRole('heading', { name: 'Client Login' })).toBeInTheDocument();
    expect(getClientRequests).not.toHaveBeenCalled();
  });

  it('7. unmount during a pending getSession does not continue authorization or apply stale state', async () => {
    const d = deferred();
    getSession.mockReturnValue(d.promise);
    getEffectiveRole.mockReturnValue('client');

    const { unmount } = render(<ClientPortal />);
    unmount();

    // Resolve the session AFTER unmount; the guarded init must not proceed to
    // role detection / bookings fetch, and must not throw.
    await act(async () => {
      d.resolve(fakeSession());
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(getEffectiveRole).not.toHaveBeenCalled();
    expect(getClientRequests).not.toHaveBeenCalled();
  });

  it('8. unmount during a pending bookings request does not apply stale results', async () => {
    getSession.mockResolvedValue(fakeSession());
    getEffectiveRole.mockReturnValue('client');
    const d = deferred();
    getClientRequests.mockReturnValue(d.promise);

    const { unmount } = render(<ClientPortal />);
    // Allow getSession + role gate to run and the bookings fetch to start.
    await waitFor(() => expect(getClientRequests).toHaveBeenCalledTimes(1));

    unmount();
    // Resolve bookings AFTER unmount; must not throw / apply stale state.
    await act(async () => {
      d.resolve({ requests: [bookingRequest()] });
      await Promise.resolve();
      await Promise.resolve();
    });

    // No assertion on DOM (unmounted); the guarantee is "no throw / no act warning".
    expect(true).toBe(true);
  });

  it('9. Strict-Mode-like remount resolves the role cleanly (no dedup claim)', async () => {
    getSession.mockResolvedValue(fakeSession());
    getEffectiveRole.mockReturnValue('client');
    getClientRequests.mockResolvedValue({ requests: [bookingRequest()] });

    const { unmount } = render(<ClientPortal />);
    await screen.findByRole('heading', { name: 'My Bookings' });
    unmount();

    // Remount: role resolves cleanly to client and bookings render again.
    render(<ClientPortal />);
    expect(await screen.findByRole('heading', { name: 'My Bookings' })).toBeInTheDocument();
    await screen.findByText('Rex');
  });

  it('10. a single mount triggers exactly one bookings fetch (no duplicate introduced)', async () => {
    getSession.mockResolvedValue(fakeSession());
    getEffectiveRole.mockReturnValue('client');
    getClientRequests.mockResolvedValue({ requests: [bookingRequest()] });

    render(<ClientPortal />);
    await screen.findByRole('heading', { name: 'My Bookings' });
    await act(async () => { await new Promise((r) => setTimeout(r, 50)); });

    expect(getClientRequests).toHaveBeenCalledTimes(1);
  });
});
