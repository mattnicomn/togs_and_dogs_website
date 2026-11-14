/**
 * B6-C2 — VITE_W1_EXISTING_PET_SELECTION release-compatibility flag.
 *
 * Proves that, unless the build-time flag is exactly "true":
 *  - the existing-pet picker is not rendered and getClientPets() is not called,
 *  - the pre-W1 typed-pet workflow is required and still submits,
 *  - neither the authenticated (submitClientRequest) nor the public
 *    (submitRequest) intake payload carries pet_ids or selected_pet_ids,
 *  - stale selection state from an earlier render cannot leak those fields,
 * and that with the flag exactly "true" the W1 picker/pet_ids path is intact.
 *
 * The flag is a release-compatibility switch, not a security boundary.
 */
import React from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import IntakeForm from '../src/components/IntakeForm';
import { isExistingPetSelectionEnabled } from '../src/config/featureFlags';
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

const FLAG = 'VITE_W1_EXISTING_PET_SELECTION';

const clientSession = {
  idToken: { payload: { email: 'client@example.test', name: 'Client Person' } },
};

const renderIntake = () => render(
  <MemoryRouter>
    <IntakeForm />
  </MemoryRouter>
);

const goToPets = async ({ publicVisitor = false } = {}) => {
  renderIntake();
  await screen.findByRole('heading', { name: 'How can we reach you?' });
  if (publicVisitor) {
    fireEvent.change(screen.getByPlaceholderText('Alex Barker'), { target: { value: 'Synthetic Visitor' } });
    fireEvent.change(screen.getByPlaceholderText('alex@example.com'), { target: { value: 'visitor@example.test' } });
  } else {
    // Wait for the session prefill so the step-1 validation passes.
    await waitFor(() => expect(screen.getByPlaceholderText('alex@example.com')).toHaveValue('client@example.test'));
  }
  fireEvent.click(screen.getByRole('button', { name: 'Next: Schedule →' }));
  await screen.findByRole('heading', { name: 'When do you need care?' });
  fireEvent.click(screen.getByRole('radio', { name: /^Morning,/ }));
  const dateInputs = document.querySelectorAll('input[type="date"]');
  fireEvent.change(dateInputs[0], { target: { value: '2030-01-05' } });
  fireEvent.change(dateInputs[1], { target: { value: '2030-01-05' } });
  fireEvent.click(screen.getByRole('button', { name: 'Select Dates from Range' }));
  fireEvent.click(screen.getByRole('button', { name: 'Next: Pet Info →' }));
  return screen.findByRole('heading', { name: 'Tell us about your pets' });
};

const typePet = (name = 'Milo') => {
  fireEvent.change(screen.getByPlaceholderText('e.g. Luna'), { target: { value: name } });
};

const acceptAndSubmit = () => {
  fireEvent.click(screen.getByText(/I agree to the/).closest('label'));
  fireEvent.click(screen.getByRole('button', { name: /Submit/i }));
};

const submittedClientPayload = async () => {
  await waitFor(() => expect(submitClientRequest).toHaveBeenCalledTimes(1));
  return submitClientRequest.mock.calls[0][0];
};

const submittedPublicPayload = async () => {
  await waitFor(() => expect(submitRequest).toHaveBeenCalledTimes(1));
  return submitRequest.mock.calls[0][0];
};

const expectNoExistingPetFields = (payload) => {
  expect(payload).not.toHaveProperty('pet_ids');
  expect(payload).not.toHaveProperty('selected_pet_ids');
};

describe('isExistingPetSelectionEnabled', () => {
  afterEach(() => vi.unstubAllEnvs());

  it('is OFF when unset', () => {
    vi.stubEnv(FLAG, undefined);
    expect(isExistingPetSelectionEnabled()).toBe(false);
  });

  it.each(['false', '', 'TRUE', 'True', '1', 'yes', ' true'])('is OFF for %j', (value) => {
    vi.stubEnv(FLAG, value);
    expect(isExistingPetSelectionEnabled()).toBe(false);
  });

  it('is ON only for the exact string "true"', () => {
    vi.stubEnv(FLAG, 'true');
    expect(isExistingPetSelectionEnabled()).toBe(true);
  });
});

describe('IntakeForm — existing-pet selection flag OFF', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getSession.mockResolvedValue(clientSession);
    getEffectiveRole.mockReturnValue('client');
    getStaffOptions.mockResolvedValue({ staff_options: [] });
    submitRequest.mockResolvedValue({ request_id: 'public-req' });
    submitClientRequest.mockResolvedValue({ request_id: 'client-req' });
    getClientPets.mockResolvedValue({
      pets: [{ pet_id: 'PET-1', name: 'Buster', species: 'DOG' }],
    });
  });

  afterEach(() => vi.unstubAllEnvs());

  it.each([
    ['unset', undefined],
    ['explicit "false"', 'false'],
  ])('%s: hides the picker and never calls getClientPets()', async (_label, value) => {
    vi.stubEnv(FLAG, value);
    await goToPets();
    expect(screen.queryByTestId('existing-pet-picker')).not.toBeInTheDocument();
    expect(getClientPets).not.toHaveBeenCalled();
  });

  it('requires a typed pet (pre-W1 workflow)', async () => {
    vi.stubEnv(FLAG, 'false');
    await goToPets();
    acceptAndSubmit();
    expect(await screen.findByText(/At least one pet name is required\./)).toBeInTheDocument();
    expect(submitClientRequest).not.toHaveBeenCalled();
  });

  it('authenticated client: typed-pet submission works and omits pet_ids/selected_pet_ids', async () => {
    vi.stubEnv(FLAG, 'false');
    await goToPets();
    typePet('Milo');
    acceptAndSubmit();
    const payload = await submittedClientPayload();
    expectNoExistingPetFields(payload);
    expect(payload.pets.some((p) => p.name === 'Milo')).toBe(true);
    expect(submitRequest).not.toHaveBeenCalled();
  });

  it('public visitor: typed-pet submission works and omits pet_ids/selected_pet_ids', async () => {
    vi.stubEnv(FLAG, 'false');
    getSession.mockResolvedValue(null);
    getEffectiveRole.mockReturnValue('unknown');
    await goToPets({ publicVisitor: true });
    typePet('Milo');
    acceptAndSubmit();
    const payload = await submittedPublicPayload();
    expectNoExistingPetFields(payload);
    expect(payload.source).toBe('public_intake');
    expect(payload.pets.some((p) => p.name === 'Milo')).toBe(true);
    expect(getClientPets).not.toHaveBeenCalled();
  });

  it('stale selection state cannot leak pet_ids into the authenticated payload', async () => {
    // Build up W1 selection state while the flag is ON, then turn it OFF.
    vi.stubEnv(FLAG, 'true');
    await goToPets();
    const picker = await screen.findByTestId('existing-pet-picker');
    fireEvent.click(within(picker).getByRole('checkbox', { name: 'Select pet Buster' }));
    vi.stubEnv(FLAG, 'false');
    typePet('Milo'); // re-render with the flag OFF; selected_pet_ids is still in state
    expect(screen.queryByTestId('existing-pet-picker')).not.toBeInTheDocument();
    acceptAndSubmit();
    const payload = await submittedClientPayload();
    expectNoExistingPetFields(payload);
    expect(payload.pet_names || '').not.toContain('Buster');
  });

  it('stale selection state cannot leak pet_ids into the public payload', async () => {
    vi.stubEnv(FLAG, 'true');
    await goToPets();
    const picker = await screen.findByTestId('existing-pet-picker');
    fireEvent.click(within(picker).getByRole('checkbox', { name: 'Select pet Buster' }));
    vi.stubEnv(FLAG, 'false');
    // The session is re-read at submit time; route this submission down the public path.
    getSession.mockResolvedValue(null);
    getEffectiveRole.mockReturnValue('unknown');
    typePet('Milo');
    acceptAndSubmit();
    const payload = await submittedPublicPayload();
    expectNoExistingPetFields(payload);
    expect(submitClientRequest).not.toHaveBeenCalled();
  });
});

describe('IntakeForm — existing-pet selection flag ON ("true")', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubEnv(FLAG, 'true');
    getSession.mockResolvedValue(clientSession);
    getEffectiveRole.mockReturnValue('client');
    getStaffOptions.mockResolvedValue({ staff_options: [] });
    submitRequest.mockResolvedValue({ request_id: 'public-req' });
    submitClientRequest.mockResolvedValue({ request_id: 'client-req' });
    getClientPets.mockResolvedValue({
      pets: [{ pet_id: 'PET-1', name: 'Buster', species: 'DOG' }],
    });
  });

  afterEach(() => vi.unstubAllEnvs());

  it('renders the picker and submits canonical pet_ids as before', async () => {
    await goToPets();
    const picker = await screen.findByTestId('existing-pet-picker');
    expect(getClientPets).toHaveBeenCalledTimes(1);
    fireEvent.click(within(picker).getByRole('checkbox', { name: 'Select pet Buster' }));
    acceptAndSubmit();
    const payload = await submittedClientPayload();
    expect(payload.pet_ids).toEqual(['PET-1']);
    expect(payload).not.toHaveProperty('selected_pet_ids');
    expect(payload.pet_names).toContain('Buster');
  });

  it('keeps the W1 validation message when nothing is selected or typed', async () => {
    await goToPets();
    await screen.findByTestId('existing-pet-picker');
    acceptAndSubmit();
    expect(await screen.findByText(/Select an existing pet or add at least one new pet\./)).toBeInTheDocument();
    expect(submitClientRequest).not.toHaveBeenCalled();
  });
});
