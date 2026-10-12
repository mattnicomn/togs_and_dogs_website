import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { MemoryRouter, Routes, Route, useNavigate } from 'react-router-dom';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import PlatformTenantDetail from '../src/components/PlatformTenantDetail';
import { getPlatformTenant } from '../src/api/platform';

// A deferred promise helper so tests control exact resolution ordering.
const deferred = () => {
  let resolve, reject;
  const promise = new Promise((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
};

vi.mock('../src/api/platform', () => ({
  getPlatformTenant: vi.fn(),
  updatePlatformTenant: vi.fn(),
}));

const tenant = (companyId, name) => ({
  company_id: companyId,
  profile: { display_name: name, notes: '' },
  subscription: { tier: 'premium', status: 'active' },
  entitlement_summary: { limits: {} },
});

const renderAt = (initialPath) =>
  render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/platform-admin/:companyId" element={<PlatformTenantDetail />} />
      </Routes>
    </MemoryRouter>
  );

describe('PlatformTenantDetail — load, failure, retry, companyId change, stale guard (Gate C3b.2e-R2)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('1. loads the tenant for the route companyId and renders its details', async () => {
    getPlatformTenant.mockResolvedValue(tenant('tog_and_dogs', 'Togs & Dogs'));
    renderAt('/platform-admin/tog_and_dogs');

    expect(screen.getByText(/Retrieving tenant metadata/i)).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Togs & Dogs' })).toBeInTheDocument();
    });
    expect(getPlatformTenant).toHaveBeenCalledWith('tog_and_dogs');
  });

  it('2. shows the load-failure state and clears loading on error', async () => {
    getPlatformTenant.mockRejectedValue(new Error('tenant fetch failed'));
    renderAt('/platform-admin/tog_and_dogs');

    await waitFor(() => {
      expect(screen.getByText(/Load Failure/i)).toBeInTheDocument();
    });
    expect(screen.getByText('tenant fetch failed')).toBeInTheDocument();
    expect(screen.queryByText(/Retrieving tenant metadata/i)).not.toBeInTheDocument();
  });

  it('3. retry re-fetches the same companyId and renders details', async () => {
    getPlatformTenant.mockRejectedValueOnce(new Error('temporary'));
    getPlatformTenant.mockResolvedValueOnce(tenant('tog_and_dogs', 'Togs & Dogs'));
    renderAt('/platform-admin/tog_and_dogs');

    await waitFor(() => {
      expect(screen.getByText(/Load Failure/i)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText(/Retry Fetching Details/i));

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Togs & Dogs' })).toBeInTheDocument();
    });
    expect(getPlatformTenant).toHaveBeenCalledTimes(2);
    expect(getPlatformTenant).toHaveBeenLastCalledWith('tog_and_dogs');
  });

  it('4. a stale (slower) response for a previous companyId does not overwrite the current one', async () => {
    // Company A (alpha) resolves slowly; an in-place navigation to company B
    // (beta) resolves first. The late alpha response must be discarded.
    const a = deferred();
    getPlatformTenant.mockImplementationOnce(() => a.promise); // alpha (stale, slow)
    getPlatformTenant.mockResolvedValueOnce(tenant('beta_co', 'Beta Co')); // beta (current, fast)

    // Harness button performs an in-place navigation (same router), changing the
    // :companyId param without remounting the router tree.
    const Nav = () => {
      const navigate = useNavigate();
      return <button onClick={() => navigate('/platform-admin/beta_co')}>go-beta</button>;
    };

    render(
      <MemoryRouter initialEntries={['/platform-admin/alpha_co']}>
        <Nav />
        <Routes>
          <Route path="/platform-admin/:companyId" element={<PlatformTenantDetail />} />
        </Routes>
      </MemoryRouter>
    );

    fireEvent.click(screen.getByText('go-beta')); // navigate to beta before alpha resolves

    expect(await screen.findByRole('heading', { name: 'Beta Co' })).toBeInTheDocument();

    // Resolve the late alpha response and let all React state updates settle.
    await act(async () => {
      a.resolve(tenant('alpha_co', 'Alpha Co'));
      await a.promise;
    });

    // Beta must remain; the stale alpha response must not have overwritten it,
    // its form fields, or re-triggered loading.
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Beta Co' })).toBeInTheDocument();
    });
    expect(screen.queryByRole('heading', { name: 'Alpha Co' })).not.toBeInTheDocument();
    expect(screen.getByText('beta_co', { exact: false })).toBeInTheDocument();
  });

  it('5. an in-flight manual Retry for a previous companyId does not overwrite the current one', async () => {
    // alpha first fails (shows Retry); the user clicks Retry (slow, deferred),
    // then navigates in place to beta (fast). The late alpha retry must be dropped.
    const alphaRetry = deferred();
    getPlatformTenant
      .mockRejectedValueOnce(new Error('alpha initial failure')) // alpha mount -> error
      .mockImplementationOnce(() => alphaRetry.promise)          // alpha manual retry (slow)
      .mockResolvedValueOnce(tenant('beta_co', 'Beta Co'));      // beta mount (fast)

    const Nav = () => {
      const navigate = useNavigate();
      return <button onClick={() => navigate('/platform-admin/beta_co')}>go-beta</button>;
    };

    render(
      <MemoryRouter initialEntries={['/platform-admin/alpha_co']}>
        <Nav />
        <Routes>
          <Route path="/platform-admin/:companyId" element={<PlatformTenantDetail />} />
        </Routes>
      </MemoryRouter>
    );

    // alpha fails -> Retry button appears; click it (retry is in-flight/deferred).
    expect(await screen.findByText(/Load Failure/i)).toBeInTheDocument();
    fireEvent.click(screen.getByText(/Retry Fetching Details/i));

    // Navigate to beta before the alpha retry resolves.
    fireEvent.click(screen.getByText('go-beta'));
    expect(await screen.findByRole('heading', { name: 'Beta Co' })).toBeInTheDocument();

    // Resolve the stale alpha retry late — it must NOT replace beta.
    await act(async () => {
      alphaRetry.resolve(tenant('alpha_co', 'Alpha Co'));
      await alphaRetry.promise;
    });

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Beta Co' })).toBeInTheDocument();
    });
    expect(screen.queryByRole('heading', { name: 'Alpha Co' })).not.toBeInTheDocument();
  });

  it('6. a response resolving after unmount is explicitly invalidated (handler does not consume it)', async () => {
    const d = deferred();
    getPlatformTenant.mockImplementationOnce(() => d.promise);

    // Instrument the resolved payload: applyTenant() reads `.profile` and
    // `.subscription`. If the post-unmount continuation were to run applyTenant,
    // these getters would fire. The unmount guard must short-circuit BEFORE that,
    // so the getters must never be read — this proves explicit request
    // invalidation rather than merely React ignoring a state update.
    let profileRead = 0;
    let subscriptionRead = 0;
    const instrumented = {
      company_id: 'tog_and_dogs',
      get profile() { profileRead++; return { display_name: 'Togs & Dogs', notes: '' }; },
      get subscription() { subscriptionRead++; return { tier: 'premium', status: 'active' }; },
      entitlement_summary: { limits: {} },
    };

    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    try {
      const { unmount } = renderAt('/platform-admin/tog_and_dogs');

      // Unmount while the request is still pending, then resolve it late.
      unmount();
      await act(async () => {
        d.resolve(instrumented);
        await d.promise;
      });

      // Explicit invalidation evidence: the success continuation short-circuited,
      // so applyTenant never consumed the payload.
      expect(profileRead).toBe(0);
      expect(subscriptionRead).toBe(0);
      // And no React "state update after unmount" / act warning was emitted.
      const warned = errorSpy.mock.calls.some(args =>
        String(args[0] || '').match(/unmounted|not wrapped in act|state update/i)
      );
      expect(warned).toBe(false);
      expect(getPlatformTenant).toHaveBeenCalledWith('tog_and_dogs');
    } finally {
      errorSpy.mockRestore();
    }
  });
});
