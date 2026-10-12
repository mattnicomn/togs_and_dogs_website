import React from 'react';
import { render, screen, waitFor, act, fireEvent } from '@testing-library/react';
import { MemoryRouter, useNavigate } from 'react-router-dom';
import { vi, describe, it, expect, beforeAll, afterAll, beforeEach } from 'vitest';
import { AppContent } from '../src/App';
import { getSession, getEffectiveRole } from '../src/api/auth';
import { getTenantInfo } from '../src/api/client';

// Node exposes a non-functional experimental `localStorage` global (requires
// --localstorage-file), which shadows jsdom's working window.localStorage and
// makes ThemeToggle's `localStorage.getItem` throw. The App shell renders
// ThemeToggle, so install a minimal in-memory Web Storage polyfill plus a
// matchMedia stub. This only supplies browser APIs jsdom isn't exposing in this
// Node runtime; it does not alter any behavior under test.
let originalLocalStorageDescriptor;

beforeAll(() => {
  // Capture whatever `localStorage` global exists so we can fully restore it
  // after this suite, preventing cross-suite leakage in the shared worker.
  originalLocalStorageDescriptor = Object.getOwnPropertyDescriptor(globalThis, 'localStorage');

  const store = new Map();
  const localStorageStub = {
    getItem: (k) => (store.has(k) ? store.get(k) : null),
    setItem: (k, v) => { store.set(k, String(v)); },
    removeItem: (k) => { store.delete(k); },
    clear: () => { store.clear(); },
    key: (i) => Array.from(store.keys())[i] ?? null,
    get length() { return store.size; },
  };
  Object.defineProperty(globalThis, 'localStorage', {
    configurable: true,
    value: localStorageStub,
  });
  if (typeof window !== 'undefined' && typeof window.matchMedia !== 'function') {
    window.matchMedia = () => ({
      matches: false,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
    });
  }
});

afterAll(() => {
  // Restore the original `localStorage` global so sibling suites in the same
  // worker see the environment they expect.
  if (originalLocalStorageDescriptor) {
    Object.defineProperty(globalThis, 'localStorage', originalLocalStorageDescriptor);
  } else {
    delete globalThis.localStorage;
  }
});

vi.mock('../src/api/auth', () => ({
  getSession: vi.fn(),
  getEffectiveRole: vi.fn(),
}));

vi.mock('../src/api/client', () => ({
  getTenantInfo: vi.fn(),
}));

const deferred = () => {
  let resolve, reject;
  const promise = new Promise((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
};

const session = { getIdToken: () => ({ payload: { 'cognito:groups': [], email: 'o@e.test', sub: 's' } }) };

const renderApp = (path) =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <AppContent />
    </MemoryRouter>
  );

describe('App tenant-shell presentation (Gate C3b.2g Batch 3B)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getSession.mockResolvedValue(session);
    getEffectiveRole.mockReturnValue('owner');
  });

  it('1. an admin route loads and displays the tenant display name in the shell', async () => {
    getTenantInfo.mockResolvedValue({ display_name: 'Togs & Dogs' });
    renderApp('/admin');

    // The branded label renders in both the header and footer, so assert at
    // least one occurrence is present.
    await waitFor(() => {
      expect(
        screen.getAllByText(/Togs & Dogs: A Pet Business Platform/).length
      ).toBeGreaterThan(0);
    });
    expect(getTenantInfo).toHaveBeenCalled();
  });

  it('2. a non-admin (public) route does not fetch or display tenant branding', async () => {
    renderApp('/');

    // Public shell shows the generic brand (header + footer), never a
    // tenant-admin logo.
    expect(screen.getAllByText('Tog&Dogs').length).toBeGreaterThan(0);
    expect(screen.queryByText(/A Pet Business Platform/)).not.toBeInTheDocument();
    await waitFor(() => expect(getTenantInfo).not.toHaveBeenCalled());
  });

  it('3. a tenant route (/t/:slug) does not fetch App-shell tenant info', async () => {
    renderApp('/t/alpha/admin');

    // Tenant routes manage their own presentation; the App shell must not fetch.
    await waitFor(() => expect(getTenantInfo).not.toHaveBeenCalled());
  });

  it('4. a failed tenant lookup leaves no stale/incorrect tenant identity visible', async () => {
    getTenantInfo.mockRejectedValue(new Error('tenant lookup failed'));
    renderApp('/admin');

    await waitFor(() => expect(getTenantInfo).toHaveBeenCalled());
    // Falls back to the neutral admin label, never a wrong tenant name.
    await waitFor(() => {
      expect(
        screen.getAllByText(/Pet Care Admin: A Pet Business Platform/).length
      ).toBeGreaterThan(0);
    });
  });

  it('5. a slow tenant fetch for a previous route cannot overwrite a newer route', async () => {
    const slow = deferred();
    getTenantInfo
      .mockImplementationOnce(() => slow.promise)                 // /admin (slow)
      .mockResolvedValueOnce({ display_name: 'Second Tenant' });  // (not used after nav away)

    const Nav = () => {
      const navigate = useNavigate();
      return <button onClick={() => navigate('/')}>go-home</button>;
    };

    render(
      <MemoryRouter initialEntries={['/admin']}>
        <Nav />
        <AppContent />
      </MemoryRouter>
    );

    // Navigate to the public route before the /admin tenant fetch resolves.
    fireEvent.click(screen.getByText('go-home'));

    await waitFor(() => expect(screen.getAllByText('Tog&Dogs').length).toBeGreaterThan(0));

    // Resolve the stale /admin fetch late — it must NOT inject tenant branding
    // into the now-public shell.
    await act(async () => {
      slow.resolve({ display_name: 'Stale Tenant' });
      await slow.promise;
    });

    expect(screen.getAllByText('Tog&Dogs').length).toBeGreaterThan(0);
    expect(screen.queryByText(/Stale Tenant/)).not.toBeInTheDocument();
  });

  it('6. a response resolving after unmount does not throw', async () => {
    const d = deferred();
    getTenantInfo.mockImplementationOnce(() => d.promise);
    const { unmount } = renderApp('/admin');

    unmount();
    await act(async () => {
      d.resolve({ display_name: 'Late Tenant' });
      await d.promise;
    });

    expect(getTenantInfo).toHaveBeenCalled();
  });

  it('7. once the tenant load settles, the fetch count stays stable (no runaway refetching)', async () => {
    getTenantInfo.mockResolvedValue({ display_name: 'Togs & Dogs' });
    renderApp('/admin');

    await waitFor(() =>
      expect(screen.getAllByText(/Togs & Dogs: A Pet Business Platform/).length).toBeGreaterThan(0)
    );
    const callsAfterLoad = getTenantInfo.mock.calls.length;

    // The resolved fetch calls setTenantInfo, causing a re-render. Because the
    // guarded effect's deps (pathname + shouldLoadTenantInfo) are unchanged,
    // that re-render must NOT issue further tenant fetches.
    await act(async () => {
      await new Promise((r) => setTimeout(r, 30));
    });

    expect(getTenantInfo.mock.calls.length).toBe(callsAfterLoad);
  });
});
