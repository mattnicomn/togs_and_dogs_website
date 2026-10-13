import React from 'react';
import { act, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// Mocked OAuth completion — never contacts Google / real services.
vi.mock('../src/api/client', () => ({
  completeGoogleAuth: vi.fn(),
}));

// Capture navigation without a real router transition.
const navigateSpy = vi.fn();
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual, useNavigate: () => navigateSpy };
});

import GoogleCallback from '../src/components/GoogleCallback';
import { completeGoogleAuth } from '../src/api/client';

// Opaque placeholder params — NOT real OAuth codes/tokens.
const CODE = 'test-code-xyz';
const STATE = 'test-state-abc';

const renderCallback = (search = `?code=${CODE}&state=${STATE}`) =>
  render(
    <MemoryRouter initialEntries={[`/google/callback${search}`]}>
      <GoogleCallback />
    </MemoryRouter>
  );

const deferred = () => {
  let resolve, reject;
  const promise = new Promise((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
};

describe('GoogleCallback OAuth completion (Gate C3b.2r)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.runOnlyPendingTimers();
    vi.useRealTimers();
  });

  it('1. valid code/state invokes completeGoogleAuth with the exact two arguments', async () => {
    completeGoogleAuth.mockResolvedValue({});
    await act(async () => { renderCallback(); await Promise.resolve(); });

    expect(completeGoogleAuth).toHaveBeenCalledTimes(1);
    expect(completeGoogleAuth).toHaveBeenCalledWith(CODE, STATE);
  });

  it('2. successful completion displays the success state', async () => {
    completeGoogleAuth.mockResolvedValue({});
    await act(async () => { renderCallback(); await Promise.resolve(); });

    expect(screen.getByRole('heading', { name: /Successfully Linked/i })).toBeInTheDocument();
  });

  it('3. successful completion navigates to /admin after the 3-second delay', async () => {
    completeGoogleAuth.mockResolvedValue({});
    await act(async () => { renderCallback(); await Promise.resolve(); });

    // No navigation yet.
    expect(navigateSpy).not.toHaveBeenCalled();
    await act(async () => { vi.advanceTimersByTime(3000); });
    expect(navigateSpy).toHaveBeenCalledWith('/admin');
    expect(navigateSpy).toHaveBeenCalledTimes(1);
  });

  it('4. no navigation occurs before the delay elapses', async () => {
    completeGoogleAuth.mockResolvedValue({});
    await act(async () => { renderCallback(); await Promise.resolve(); });

    await act(async () => { vi.advanceTimersByTime(2999); });
    expect(navigateSpy).not.toHaveBeenCalled();
  });

  it('5. a failed exchange displays the error state and does not redirect', async () => {
    completeGoogleAuth.mockRejectedValue(new Error('exchange failed'));
    await act(async () => { renderCallback(); await Promise.resolve(); await Promise.resolve(); });

    expect(screen.getByRole('heading', { name: /Connection Failed/i })).toBeInTheDocument();
    await act(async () => { vi.advanceTimersByTime(5000); });
    expect(navigateSpy).not.toHaveBeenCalled();
  });

  it('6. missing code and/or state shows the missing-parameters error without an exchange', async () => {
    await act(async () => { renderCallback('?code=only-code'); await Promise.resolve(); });

    expect(screen.getByRole('heading', { name: /Connection Failed/i })).toBeInTheDocument();
    expect(completeGoogleAuth).not.toHaveBeenCalled();

    // Also with neither param.
    vi.clearAllMocks();
    await act(async () => { renderCallback('?nothing=1'); await Promise.resolve(); });
    expect(completeGoogleAuth).not.toHaveBeenCalled();
  });

  it('7. unmount before exchange resolution prevents stale UI updates and navigation', async () => {
    const d = deferred();
    completeGoogleAuth.mockReturnValue(d.promise);
    let unmount;
    await act(async () => { ({ unmount } = renderCallback()); await Promise.resolve(); });

    // Still processing; now unmount, then resolve late.
    unmount();
    await act(async () => {
      d.resolve({});
      await Promise.resolve();
      await Promise.resolve();
    });
    // No navigation and no throw after unmount.
    await act(async () => { vi.advanceTimersByTime(3000); });
    expect(navigateSpy).not.toHaveBeenCalled();
  });

  it('8. unmount before redirect clears the timeout and prevents navigation', async () => {
    completeGoogleAuth.mockResolvedValue({});
    let unmount;
    await act(async () => { ({ unmount } = renderCallback()); await Promise.resolve(); });

    // Success shown; redirect timer scheduled but not yet fired.
    expect(screen.getByRole('heading', { name: /Successfully Linked/i })).toBeInTheDocument();
    unmount();
    await act(async () => { vi.advanceTimersByTime(3000); });
    expect(navigateSpy).not.toHaveBeenCalled();
  });

  it('9. a rerender with unchanged callback parameters does not trigger another exchange', async () => {
    completeGoogleAuth.mockResolvedValue({});
    let rerender;
    await act(async () => { ({ rerender } = renderCallback()); await Promise.resolve(); });
    expect(completeGoogleAuth).toHaveBeenCalledTimes(1);

    // Re-render the same tree (same location) — no new exchange.
    await act(async () => {
      rerender(
        <MemoryRouter initialEntries={[`/google/callback?code=${CODE}&state=${STATE}`]}>
          <GoogleCallback />
        </MemoryRouter>
      );
      await Promise.resolve();
    });
    // NOTE: a fresh MemoryRouter remounts, so this specifically asserts the
    // same mounted instance via rerender does not double-exchange. react-router
    // keeps location identity stable across ordinary rerenders.
    expect(completeGoogleAuth).toHaveBeenCalledTimes(1);
  });

  it('10. exchange count is measured explicitly (characterization, no dedup claim)', async () => {
    completeGoogleAuth.mockResolvedValue({});
    await act(async () => { renderCallback(); await Promise.resolve(); });

    // A single mount performs exactly one exchange of the code. (This test does
    // NOT assert cross-remount/Strict-Mode deduplication — the component holds
    // no persistent "already exchanged" state; a genuine double-mount would
    // exchange twice, which is out of scope here.)
    expect(completeGoogleAuth).toHaveBeenCalledTimes(1);
    expect(completeGoogleAuth).toHaveBeenCalledWith(CODE, STATE);
  });

  it('11. Back to Dashboard navigation works from the error state', async () => {
    completeGoogleAuth.mockRejectedValue(new Error('exchange failed'));
    await act(async () => { renderCallback(); await Promise.resolve(); await Promise.resolve(); });

    const btn = screen.getByRole('button', { name: /Back to Dashboard/i });
    await act(async () => { btn.click(); });
    expect(navigateSpy).toHaveBeenCalledWith('/admin');
  });
});
