import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import IntakeForm from '../src/components/IntakeForm';
import { getSession, getEffectiveRole } from '../src/api/auth';
import { getStaffOptions } from '../src/api/client';

vi.mock('../src/api/auth', () => ({
  getSession: vi.fn(),
  getEffectiveRole: vi.fn(),
}));

vi.mock('../src/api/client', () => ({
  getStaffOptions: vi.fn(),
  submitRequest: vi.fn(),
  submitClientRequest: vi.fn(),
}));

window.HTMLElement.prototype.scrollIntoView = vi.fn();

const renderIntake = () =>
  render(
    <MemoryRouter>
      <IntakeForm />
    </MemoryRouter>
  );

describe('IntakeForm — staff options loading (Gate C3b.2e-R2)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Anonymous visitor: no session (effect handles the rejection/empty path).
    getSession.mockResolvedValue(null);
    getEffectiveRole.mockReturnValue(null);
  });

  it('1. requests staff options on mount and still renders step 1', async () => {
    getStaffOptions.mockResolvedValue({ staff_options: [{ id: 's1', name: 'Pat Sitter' }] });
    renderIntake();

    // The intake form's first step renders regardless of the async staff load.
    expect(await screen.findByRole('button', { name: 'Next: Schedule →' })).toBeInTheDocument();
    await waitFor(() => expect(getStaffOptions).toHaveBeenCalledTimes(1));
  });

  it('2. staff options failure does not break the form (preferred sitter is optional)', async () => {
    getStaffOptions.mockRejectedValue(new Error('staff options unavailable'));
    renderIntake();

    // Form remains usable; the graceful catch sets an empty list and does not throw.
    expect(await screen.findByRole('button', { name: 'Next: Schedule →' })).toBeInTheDocument();
    await waitFor(() => expect(getStaffOptions).toHaveBeenCalledTimes(1));
    // No preferred-sitter dropdown is shown when the list is empty.
    expect(screen.queryByText(/Preferred Sitter \(Optional\)/i)).not.toBeInTheDocument();
  });
});
