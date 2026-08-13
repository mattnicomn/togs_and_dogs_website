import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import PlatformAdminOnboarding from '../src/components/PlatformAdminOnboarding';
import { validateOnboardingTenant, previewOnboardingTenant } from '../src/api/platform';

vi.mock('../src/api/platform', () => ({
  validateOnboardingTenant: vi.fn(),
  previewOnboardingTenant: vi.fn(),
}));

describe('PlatformAdminOnboarding Component Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const renderComponent = () =>
    render(
      <MemoryRouter>
        <PlatformAdminOnboarding />
      </MemoryRouter>
    );

  it('1. renders header, safety warning banner, and form fields', () => {
    renderComponent();

    expect(screen.getByText(/Tenant Onboarding Orchestrator/i)).toBeInTheDocument();
    expect(screen.getByText(/PREVIEW-ONLY MODE — NO WRITES WILL OCCUR/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Company ID/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Display Name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Subscription Tier/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Initial Subscription Status/i)).toBeInTheDocument();
  });

  it('2. validates input and displays errors when validation fails', async () => {
    validateOnboardingTenant.mockResolvedValue({
      valid: false,
      errors: [{ field: 'company_id', error: "company_id 'tog_and_dogs' is reserved." }],
      warnings: [],
      no_writes: true,
    });

    renderComponent();

    fireEvent.change(screen.getByLabelText(/Company ID/i), { target: { value: 'tog_and_dogs' } });
    fireEvent.change(screen.getByLabelText(/Display Name/i), { target: { value: 'Tog and Dogs' } });

    const validateBtn = screen.getByRole('button', { name: /1. Validate Fields/i });
    fireEvent.click(validateBtn);

    await waitFor(() => {
      expect(validateOnboardingTenant).toHaveBeenCalledWith({
        company_id: 'tog_and_dogs',
        display_name: 'Tog and Dogs',
        subscription_tier: 'starter',
        subscription_status: 'disabled',
        notes: '',
      });
      expect(screen.getByText(/Validation Failed/i)).toBeInTheDocument();
      expect(screen.getByText(/is reserved/i)).toBeInTheDocument();
    });
  });

  it('3. successful validation reveals preview button and handles preview generation', async () => {
    validateOnboardingTenant.mockResolvedValue({
      valid: true,
      errors: [],
      warnings: [],
      validated_fields: { company_id: 'acme_pets', display_name: 'Acme Pets' },
      no_writes: true,
    });

    previewOnboardingTenant.mockResolvedValue({
      preview_state: 'PREVIEW_READY',
      message: 'Preview generated successfully.',
      preview_hash: 'abc123hash',
      generated_at: '2026-08-12T12:00:00Z',
      catalog_version: 'v1',
      no_writes: true,
      proposed_metadata: {
        company_id: 'acme_pets',
        display_name: 'Acme Pets',
        subscription_tier: 'professional',
        subscription_status: 'disabled',
        created_by: 'platform_admin:ryan@example.com',
      },
      tier_limits: {
        max_active_clients: 100,
        max_staff: 5,
        google_calendar_enabled: true,
      },
      proposed_audit: {
        PK: 'PLATFORM_AUDIT',
        SK: 'ACTION#2026-08-12T12:00:00Z#uuid',
        action: 'PROVISION_TENANT',
        actor: 'platform_admin:ryan@example.com',
      },
      approval_checklist: [
        { item: 'Explicit Matthew approval', required: true, satisfied: false },
      ],
    });

    renderComponent();

    fireEvent.change(screen.getByLabelText(/Company ID/i), { target: { value: 'acme_pets' } });
    fireEvent.change(screen.getByLabelText(/Display Name/i), { target: { value: 'Acme Pets' } });

    fireEvent.click(screen.getByRole('button', { name: /1. Validate Fields/i }));

    await waitFor(() => {
      expect(screen.getByText(/Validation Passed/i)).toBeInTheDocument();
    });

    const previewBtn = screen.getByRole('button', { name: /2. Generate Full Preview/i });
    expect(previewBtn).toBeInTheDocument();

    fireEvent.click(previewBtn);

    await waitFor(() => {
      expect(previewOnboardingTenant).toHaveBeenCalled();
    });
    expect(previewOnboardingTenant).toHaveBeenCalledWith({
      company_id: 'acme_pets',
      display_name: 'Acme Pets',
      subscription_tier: 'starter',
      subscription_status: 'disabled',
      notes: '',
    });
    expect(screen.getAllByText(/Proposed End State Preview/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/abc123hash/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Explicit Matthew approval/i).length).toBeGreaterThan(0);
  });

  it('4. field changes after preview triggers stale preview warning', async () => {
    validateOnboardingTenant.mockResolvedValue({ valid: true, errors: [], warnings: [] });
    previewOnboardingTenant.mockResolvedValue({
      preview_state: 'PREVIEW_READY',
      preview_hash: 'hash1',
      proposed_metadata: { company_id: 'acme_pets' },
    });

    renderComponent();

    fireEvent.change(screen.getByLabelText(/Company ID/i), { target: { value: 'acme_pets' } });
    fireEvent.change(screen.getByLabelText(/Display Name/i), { target: { value: 'Acme Pets' } });
    fireEvent.click(screen.getByRole('button', { name: /1. Validate Fields/i }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /2. Generate Full Preview/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /2. Generate Full Preview/i }));

    await waitFor(() => {
      expect(screen.getAllByText(/Proposed End State Preview/i).length).toBeGreaterThan(0);
    });

    // Modify a field after generating preview
    fireEvent.change(screen.getByLabelText(/Display Name/i), { target: { value: 'Acme Pets Modified' } });

    expect(screen.getByText(/Inputs Modified/i)).toBeInTheDocument();
  });

  it('5. confirms NO Apply button exists in the interface', () => {
    renderComponent();
    expect(screen.queryByRole('button', { name: /Apply/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Create Tenant/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Submit/i })).not.toBeInTheDocument();
  });
});
