/**
 * Workstream 1 — Web client existing-pet selection parity.
 *
 * Proves the authenticated client intake flow:
 *  - loads the client's pets once through the client-safe endpoint,
 *  - selects existing pets by pet_id (duplicate names independently selectable),
 *  - submits a canonical pet_ids array,
 *  - supports removal/reselection,
 *  - preserves the add-new-pet path,
 *  - never calls an admin pet endpoint and makes no N+1 pet calls.
 */
import React from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import IntakeForm from '../src/components/IntakeForm';
import { getEffectiveRole, getSession } from '../src/api/auth';
import { getClientPets, getStaffOptions, submitClientRequest, submitRequest } from '../src/api/client';

vi.mock('../src/api/auth', () => ({
  getSession: vi.fn(),
  getEffectiveRole: vi.fn(),
}));

vi.mock('../src/api/client', () => ({
  getClientPets: vi.fn(),
  getStaffOptions: vi.fn(),
  submitRequest: vi.fn(),
  submitClientRequest: vi.fn(),
}));

window.HTMLElement.prototype.scrollIntoView = vi.fn();

const renderIntake = () => render(
  <MemoryRouter>
    <IntakeForm />
  </MemoryRouter>
);

const clientSession = {
  idToken: { payload: { email: 'client@example.test', name: 'Client Person' } },
};

const goToPets = async () => {
  renderIntake();
  // Step 1 (prefilled from session, but Next still required)
  await screen.findByRole('heading', { name: 'How can we reach you?' });
  fireEvent.click(screen.getByRole('button', { name: 'Next: Schedule →' }));
  await screen.findByRole('heading', { name: 'When do you need care?' });
  // Choose a Walk window + a date
  fireEvent.click(screen.getByRole('radio', { name: /^Morning,/ }));
  const dateInputs = document.querySelectorAll('input[type="date"]');
  fireEvent.change(dateInputs[0], { target: { value: '2030-01-05' } });
  fireEvent.change(dateInputs[1], { target: { value: '2030-01-05' } });
  fireEvent.click(screen.getByRole('button', { name: 'Select Dates from Range' }));
  fireEvent.click(screen.getByRole('button', { name: 'Next: Pet Info →' }));
  return screen.findByRole('heading', { name: 'Tell us about your pets' });
};

const acceptAndSubmit = async () => {
  fireEvent.click(screen.getByText(/I agree to the/).closest('label'));
  fireEvent.click(screen.getByRole('button', { name: /Submit/i }));
  await waitFor(() => expect(submitClientRequest).toHaveBeenCalledTimes(1));
  return submitClientRequest.mock.calls[0][0];
};

describe('IntakeForm — Workstream 1 client existing-pet selection', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getSession.mockResolvedValue(clientSession);
    getEffectiveRole.mockReturnValue('client');
    getStaffOptions.mockResolvedValue({ staff_options: [] });
    submitRequest.mockResolvedValue({ request_id: 'public-req' });
    submitClientRequest.mockResolvedValue({ request_id: 'client-req' });
    getClientPets.mockResolvedValue({
      pets: [
        { pet_id: 'PET-1', name: 'Buster', species: 'DOG', breed: 'Boxer' },
        { pet_id: 'PET-2', name: 'Luna', species: 'CAT' },
      ],
    });
  });

  it('loads client pets once via the client-safe endpoint (no admin endpoint, no N+1)', async () => {
    await goToPets();
    await screen.findByTestId('existing-pet-picker');
    expect(getClientPets).toHaveBeenCalledTimes(1);
  });

  it('selects an existing pet by id and submits canonical pet_ids', async () => {
    await goToPets();
    const picker = await screen.findByTestId('existing-pet-picker');
    fireEvent.click(within(picker).getByRole('checkbox', { name: 'Select pet Buster' }));
    const payload = await acceptAndSubmit();
    expect(payload.pet_ids).toEqual(['PET-1']);
    expect(payload.pet_names).toContain('Buster');
    // selected_pet_ids is an internal field and must not leak into the payload.
    expect(payload.selected_pet_ids).toBeUndefined();
  });

  it('supports multi-pet selection and removal/reselection by id', async () => {
    await goToPets();
    const picker = await screen.findByTestId('existing-pet-picker');
    const buster = within(picker).getByRole('checkbox', { name: 'Select pet Buster' });
    const luna = within(picker).getByRole('checkbox', { name: 'Select pet Luna' });
    fireEvent.click(buster);
    fireEvent.click(luna);
    fireEvent.click(buster); // remove Buster
    fireEvent.click(buster); // reselect Buster
    const payload = await acceptAndSubmit();
    expect(payload.pet_ids).toEqual(expect.arrayContaining(['PET-1', 'PET-2']));
    expect(payload.pet_ids.length).toBe(2);
  });

  it('keeps duplicate-name pets independently selectable', async () => {
    getClientPets.mockResolvedValue({
      pets: [
        { pet_id: 'PET-A', name: 'Max', species: 'DOG' },
        { pet_id: 'PET-B', name: 'Max', species: 'DOG' },
      ],
    });
    await goToPets();
    const picker = await screen.findByTestId('existing-pet-picker');
    const checkboxes = within(picker).getAllByRole('checkbox');
    expect(checkboxes.length).toBe(2);
    fireEvent.click(checkboxes[0]);
    fireEvent.click(checkboxes[1]);
    const payload = await acceptAndSubmit();
    expect(payload.pet_ids).toEqual(expect.arrayContaining(['PET-A', 'PET-B']));
    expect(payload.pet_ids.length).toBe(2);
  });

  it('preserves the add-new-pet path alongside existing selection', async () => {
    await goToPets();
    const picker = await screen.findByTestId('existing-pet-picker');
    fireEvent.click(within(picker).getByRole('checkbox', { name: 'Select pet Buster' }));
    // Add a brand new pet via the structured entry.
    fireEvent.change(screen.getByPlaceholderText('e.g. Luna'), { target: { value: 'Milo' } });
    const payload = await acceptAndSubmit();
    expect(payload.pet_ids).toEqual(['PET-1']);
    // New pet remains a structured entry; display string combines both.
    expect(payload.pets.some((p) => p.name === 'Milo')).toBe(true);
    expect(payload.pet_names).toContain('Milo');
    expect(payload.pet_names).toContain('Buster');
  });

  it('allows submitting with only an existing-pet selection (no typed pet)', async () => {
    await goToPets();
    const picker = await screen.findByTestId('existing-pet-picker');
    fireEvent.click(within(picker).getByRole('checkbox', { name: 'Select pet Luna' }));
    const payload = await acceptAndSubmit();
    expect(payload.pet_ids).toEqual(['PET-2']);
    // No non-empty structured new pet was typed.
    expect((payload.pets || []).length).toBe(0);
  });
});
