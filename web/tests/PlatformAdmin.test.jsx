import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import PlatformAdmin from '../src/components/PlatformAdmin';
import { getPlatformTenants } from '../src/api/platform';

vi.mock('../src/api/platform', () => ({
  getPlatformTenants: vi.fn(),
}));

const renderComponent = () =>
  render(
    <MemoryRouter>
      <PlatformAdmin />
    </MemoryRouter>
  );

const sampleTenant = {
  company_id: 'tog_and_dogs',
  display_name: 'Togs & Dogs',
  subscription_tier: 'premium',
  subscription_status: 'active',
  created_at: '2026-01-01T00:00:00Z',
};

describe('PlatformAdmin — loading, success, failure, retry (Gate C3b.2e-R2)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('1. shows the loading spinner on mount, then renders the tenant registry', async () => {
    getPlatformTenants.mockResolvedValue({ tenants: [sampleTenant] });
    renderComponent();

    expect(screen.getByText(/Retrieving platform tenant registry/i)).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('Togs & Dogs')).toBeInTheDocument();
    });
    expect(screen.queryByText(/Retrieving platform tenant registry/i)).not.toBeInTheDocument();
    expect(getPlatformTenants).toHaveBeenCalledTimes(1);
  });

  it('2. shows an error and clears loading on fetch failure', async () => {
    getPlatformTenants.mockRejectedValue(new Error('registry unavailable'));
    renderComponent();

    await waitFor(() => {
      expect(screen.getByText(/System Error/i)).toBeInTheDocument();
    });
    expect(screen.getByText('registry unavailable')).toBeInTheDocument();
    expect(screen.queryByText(/Retrieving platform tenant registry/i)).not.toBeInTheDocument();
  });

  it('3. retry after an error re-fetches and shows tenants', async () => {
    getPlatformTenants.mockRejectedValueOnce(new Error('temporary'));
    getPlatformTenants.mockResolvedValueOnce({ tenants: [sampleTenant] });
    renderComponent();

    await waitFor(() => {
      expect(screen.getByText(/System Error/i)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText(/Retry Fetching Data/i));

    await waitFor(() => {
      expect(screen.getByText('Togs & Dogs')).toBeInTheDocument();
    });
    expect(getPlatformTenants).toHaveBeenCalledTimes(2);
    expect(screen.queryByText(/System Error/i)).not.toBeInTheDocument();
  });
});
