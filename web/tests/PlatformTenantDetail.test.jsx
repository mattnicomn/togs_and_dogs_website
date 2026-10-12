import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route, useNavigate } from 'react-router-dom';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import PlatformTenantDetail from '../src/components/PlatformTenantDetail';
import { getPlatformTenant } from '../src/api/platform';

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
    // Company A resolves slowly; an in-place navigation to company B resolves first.
    let resolveA;
    const slowA = new Promise((res) => { resolveA = res; });
    getPlatformTenant.mockImplementationOnce(() => slowA); // A (stale, slow)
    getPlatformTenant.mockResolvedValueOnce(tenant('beta_co', 'Beta Co')); // B (current, fast)

    // Harness: a button performs an in-place navigation (same router) from A to B,
    // changing the :companyId param without remounting the router tree.
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

    // Navigate to company B before A resolves (in place).
    fireEvent.click(screen.getByText('go-beta'));

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Beta Co' })).toBeInTheDocument();
    });

    // Now let the stale A response arrive late — it must NOT replace Beta Co.
    resolveA(tenant('alpha_co', 'Alpha Co'));
    await Promise.resolve();
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Beta Co' })).toBeInTheDocument();
    });
    expect(screen.queryByRole('heading', { name: 'Alpha Co' })).not.toBeInTheDocument();
  });
});
