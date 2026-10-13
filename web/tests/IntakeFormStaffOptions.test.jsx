import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
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

// Navigate through the real step-1 contact fields to the Schedule step, where
// the preferred-sitter dropdown renders. Uses the form's actual navigation and
// validation (the Next button only advances when step 1 is valid).
const goToScheduleStep = async () => {
  fireEvent.change(screen.getByPlaceholderText('Alex Barker'), { target: { value: 'Synthetic Customer' } });
  fireEvent.change(screen.getByPlaceholderText('alex@example.com'), { target: { value: 'customer@example.test' } });
  fireEvent.change(screen.getByPlaceholderText('555-123-4567'), { target: { value: '555-0102' } });
  fireEvent.click(screen.getByRole('button', { name: 'Next: Schedule →' }));
  return screen.findByRole('heading', { name: 'When do you need care?' });
};

describe('IntakeForm — staff options loading (Gate C3b.2e-R2 / R3)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Anonymous visitor: no session (effect handles the empty/rejection path).
    getSession.mockResolvedValue(null);
    getEffectiveRole.mockReturnValue(null);
  });

  it('1. requests staff options on mount and still renders step 1', async () => {
    getStaffOptions.mockResolvedValue({ staff_options: [{ id: 's1', name: 'Pat Sitter' }] });
    renderIntake();

    expect(await screen.findByRole('button', { name: 'Next: Schedule →' })).toBeInTheDocument();
    await waitFor(() => expect(getStaffOptions).toHaveBeenCalledTimes(1));
  });

  it('2. loaded staff options appear in the preferred-sitter dropdown on the schedule step', async () => {
    getStaffOptions.mockResolvedValue({
      staff_options: [
        { id: 's1', name: 'Pat Sitter' },
        { id: 's2', name: 'Jordan Walker' },
      ],
    });
    renderIntake();

    // Wait for the staff options to load before navigating.
    await waitFor(() => expect(getStaffOptions).toHaveBeenCalledTimes(1));
    await goToScheduleStep();

    // The optional preferred-sitter control appears with the loaded names.
    expect(await screen.findByText(/Preferred Sitter \(Optional\)/i)).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Pat Sitter' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Jordan Walker' })).toBeInTheDocument();
    // "No preference" default option is present.
    expect(screen.getByRole('option', { name: /No preference/i })).toBeInTheDocument();
  });

  it('3. staff-options failure leaves the form usable and shows no sitter dropdown', async () => {
    getStaffOptions.mockRejectedValue(new Error('staff options unavailable'));
    renderIntake();

    await waitFor(() => expect(getStaffOptions).toHaveBeenCalledTimes(1));
    await goToScheduleStep();

    // Form advanced normally; the optional sitter dropdown is absent (empty list).
    expect(screen.getByRole('heading', { name: 'When do you need care?' })).toBeInTheDocument();
    expect(screen.queryByText(/Preferred Sitter \(Optional\)/i)).not.toBeInTheDocument();
  });
});
