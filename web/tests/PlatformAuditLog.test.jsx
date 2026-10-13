import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import PlatformAuditLog from '../src/components/PlatformAuditLog';
import { getPlatformAudit } from '../src/api/platform';

vi.mock('../src/api/platform', () => ({
  getPlatformAudit: vi.fn(),
}));

const renderComponent = () =>
  render(
    <MemoryRouter>
      <PlatformAuditLog />
    </MemoryRouter>
  );

const sampleAudit = {
  SK: 'AUDIT#2026-10-11T00:00:00Z',
  timestamp: '2026-10-11T00:00:00Z',
  action: 'TENANT_UPDATE',
  target_company_id: 'tog_and_dogs',
  changed_fields: ['subscription_tier'],
  old_values: { subscription_tier: 'starter' },
  new_values: { subscription_tier: 'premium' },
  actor: 'owner@example.com',
};

describe('PlatformAuditLog — loading, success, failure, refresh (Gate C3b.2e-R2)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('1. shows the loading spinner on mount, then renders fetched audit rows', async () => {
    getPlatformAudit.mockResolvedValue({ audits: [sampleAudit] });
    renderComponent();

    // Initial loading state (loading initializes true; spinner shown before resolve)
    expect(screen.getByText(/Fetching platform audit trails/i)).toBeInTheDocument();

    // After the fetch resolves, the row renders and the spinner is gone
    await waitFor(() => {
      expect(screen.getByText('TENANT_UPDATE'.replace(/_/g, ' '), { exact: false })).toBeInTheDocument();
    });
    expect(screen.queryByText(/Fetching platform audit trails/i)).not.toBeInTheDocument();
    expect(getPlatformAudit).toHaveBeenCalledTimes(1);
  });

  it('2. renders empty state when no audits are returned', async () => {
    getPlatformAudit.mockResolvedValue({ audits: [] });
    renderComponent();

    await waitFor(() => {
      expect(screen.getByText(/No Audit Entries Found/i)).toBeInTheDocument();
    });
  });

  it('3. shows an error and clears the loading state on fetch failure', async () => {
    getPlatformAudit.mockRejectedValue(new Error('network down'));
    renderComponent();

    await waitFor(() => {
      expect(screen.getByText(/Log Retrieval Error/i)).toBeInTheDocument();
    });
    expect(screen.getByText('network down')).toBeInTheDocument();
    // Loading spinner must not remain after failure
    expect(screen.queryByText(/Fetching platform audit trails/i)).not.toBeInTheDocument();
  });

  it('4. retry after an error re-fetches and shows data (loading restored then cleared)', async () => {
    getPlatformAudit.mockRejectedValueOnce(new Error('temporary'));
    getPlatformAudit.mockResolvedValueOnce({ audits: [sampleAudit] });
    renderComponent();

    await waitFor(() => {
      expect(screen.getByText(/Log Retrieval Error/i)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText(/Retry Fetching Logs/i));

    await waitFor(() => {
      expect(screen.getByText('TENANT UPDATE', { exact: false })).toBeInTheDocument();
    });
    expect(getPlatformAudit).toHaveBeenCalledTimes(2);
    expect(screen.queryByText(/Log Retrieval Error/i)).not.toBeInTheDocument();
  });
});
