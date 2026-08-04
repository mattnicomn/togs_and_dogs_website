import React from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import IntakeForm from '../src/components/IntakeForm';
import { getEffectiveRole, getSession } from '../src/api/auth';
import { getStaffOptions, submitClientRequest, submitRequest } from '../src/api/client';
import { SERVICE_TYPES } from '../src/generated/contracts';

vi.mock('../src/api/auth', () => ({
  getSession: vi.fn(),
  getEffectiveRole: vi.fn()
}));

vi.mock('../src/api/client', () => ({
  getStaffOptions: vi.fn(),
  submitRequest: vi.fn(),
  submitClientRequest: vi.fn()
}));

window.HTMLElement.prototype.scrollIntoView = vi.fn();

const renderIntake = () => render(
  <MemoryRouter>
    <IntakeForm />
  </MemoryRouter>
);

const goToSchedule = async ({
  name = 'Synthetic Customer',
  email = 'customer@example.test',
  phone = '555-0102'
} = {}) => {
  renderIntake();

  fireEvent.change(screen.getByPlaceholderText('Alex Barker'), { target: { value: name } });
  fireEvent.change(screen.getByPlaceholderText('alex@example.com'), { target: { value: email } });
  fireEvent.change(screen.getByPlaceholderText('555-123-4567'), { target: { value: phone } });
  fireEvent.click(screen.getByRole('button', { name: 'Next: Schedule →' }));

  return screen.findByRole('heading', { name: 'When do you need care?' });
};

const getServiceSelect = () => {
  const serviceField = screen.getByText('Service Type *').closest('.field');
  return within(serviceField).getByRole('combobox');
};

const completeValidForm = async ({ serviceType = 'PET_SITTING' } = {}) => {
  await goToSchedule();

  fireEvent.change(getServiceSelect(), { target: { value: serviceType } });

  const dateInputs = document.querySelectorAll('input[type="date"]');
  fireEvent.change(dateInputs[0], { target: { value: '2030-01-05' } });
  fireEvent.change(dateInputs[1], { target: { value: '2030-01-05' } });
  fireEvent.click(screen.getByRole('button', { name: 'Select Dates from Range' }));

  fireEvent.click(screen.getByText('Anytime (Flexible)').closest('label'));
  fireEvent.change(screen.getByPlaceholderText('e.g. After 9am preferred, key under mat...'), {
    target: { value: 'Synthetic timing note' }
  });
  fireEvent.click(screen.getByRole('button', { name: 'Next: Pet Info →' }));

  await screen.findByRole('heading', { name: 'Tell us about your pets' });
  fireEvent.change(screen.getByPlaceholderText('e.g. Luna'), { target: { value: 'Synthetic Pet' } });
  fireEvent.change(screen.getByPlaceholderText('e.g. Golden Retriever'), { target: { value: 'Retriever' } });
  fireEvent.change(screen.getByPlaceholderText('Food type, schedule, portions...'), {
    target: { value: 'Synthetic feeding note' }
  });
  fireEvent.click(screen.getByText(/I agree to the/).closest('label'));
};

describe('IntakeForm service-type behavior', () => {
  beforeEach(() => {
    getSession.mockResolvedValue(null);
    getEffectiveRole.mockReturnValue('unknown');
    getStaffOptions.mockResolvedValue({ staff_options: [] });
    submitRequest.mockResolvedValue({ request_id: 'synthetic-request' });
    submitClientRequest.mockResolvedValue({ request_id: 'synthetic-client-request' });
  });

  it('uses exactly the contract-defined available-in-intake membership, labels, order, and existing default', async () => {
    await goToSchedule();

    const serviceSelect = getServiceSelect();
    const options = within(serviceSelect).getAllByRole('option');
    const expectedEntries = Object.entries(SERVICE_TYPES.services)
      .filter(([, service]) => service.availableInIntake === true);

    expect(options.map(option => option.value)).toEqual(expectedEntries.map(([identifier]) => identifier));
    expect(options.map(option => option.textContent)).toEqual(expectedEntries.map(([, service]) => service.labelLong));
    expect(options.map(option => option.value)).toEqual([
      'WALK_30MIN',
      'WALK_60MIN',
      'DROPIN_1HR',
      'DROPIN_3HR',
      'OVERNIGHT',
      'PET_SITTING'
    ]);
    expect(options.map(option => option.textContent)).toEqual([
      '30-Minute Walk',
      '60-Minute Walk',
      '1-Hour Drop-in',
      '3-Hour Drop-in',
      'Overnight Care',
      'Pet Sitting'
    ]);
    expect(serviceSelect).toHaveValue('PET_SITTING');
    expect(options.some(option => ['DOG_WALKING', 'WALKING', 'OTHER', 'MEET_GREET'].includes(option.value))).toBe(false);
  });

  it('preserves the existing required-service validation when no service is selected', async () => {
    await goToSchedule();

    fireEvent.change(getServiceSelect(), { target: { value: '' } });
    const dateInputs = document.querySelectorAll('input[type="date"]');
    fireEvent.change(dateInputs[0], { target: { value: '2030-01-05' } });
    fireEvent.change(dateInputs[1], { target: { value: '2030-01-05' } });
    fireEvent.click(screen.getByRole('button', { name: 'Select Dates from Range' }));
    fireEvent.click(screen.getByText('Anytime (Flexible)').closest('label'));
    fireEvent.click(screen.getByRole('button', { name: 'Next: Pet Info →' }));

    expect(await screen.findByText('Service Type is required.')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'When do you need care?' })).toBeInTheDocument();
  });

  it('submits WALK_30MIN and every existing non-service field through the public API unchanged', async () => {
    await completeValidForm({ serviceType: 'WALK_30MIN' });
    fireEvent.click(screen.getByRole('button', { name: 'Submit Request' }));

    await waitFor(() => expect(submitRequest).toHaveBeenCalledOnce());
    expect(submitRequest).toHaveBeenCalledWith({
      client_name: 'Synthetic Customer',
      client_email: 'customer@example.test',
      client_phone: '555-0102',
      selected_dates: ['2030-01-05'],
      range_start: '',
      range_end: '',
      visit_windows: ['ANYTIME'],
      visit_window: 'ANYTIME',
      preferred_time: '',
      timing_notes: 'Synthetic timing note',
      preferred_sitter: '',
      preferred_sitter_name: '',
      pets: [{
        name: 'Synthetic Pet',
        species: 'DOG',
        breed: 'Retriever',
        age: '',
        feeding_notes: 'Synthetic feeding note',
        medication_notes: '',
        behavior_notes: ''
      }],
      pet_names: '',
      pet_info: '',
      vet_info: {},
      emergency_contact: {},
      service_type: 'WALK_30MIN',
      accepted_terms: true,
      start_date: '2030-01-05',
      end_date: '',
      accepted_privacy: true,
      terms_version: 'v1.0',
      privacy_version: 'v1.0',
      accepted_at: expect.any(String),
      accepted_by_email: 'customer@example.test',
      source: 'public_intake'
    });
    expect(submitClientRequest).not.toHaveBeenCalled();
    expect(await screen.findByRole('heading', { name: 'Request Received!' })).toBeInTheDocument();
  });

  it.each(['WALK_60MIN', 'DROPIN_3HR'])(
    'submits selected canonical service %s without normalization',
    async (serviceType) => {
      await completeValidForm({ serviceType });
      fireEvent.click(screen.getByRole('button', { name: 'Submit Request' }));

      await waitFor(() => expect(submitRequest).toHaveBeenCalledOnce());
      expect(submitRequest).toHaveBeenCalledWith(expect.objectContaining({
        service_type: serviceType,
        selected_dates: ['2030-01-05'],
        visit_windows: ['ANYTIME'],
        pets: [expect.objectContaining({ name: 'Synthetic Pet' })]
      }));
    }
  );

  it('preserves the authenticated-client submission endpoint and raw payload shape', async () => {
    const session = {
      idToken: {
        payload: {
          email: 'portal-client@example.test',
          name: 'Portal Client'
        }
      }
    };
    getSession.mockResolvedValue(session);
    getEffectiveRole.mockReturnValue('client');

    await completeValidForm({ serviceType: 'OVERNIGHT' });
    fireEvent.click(screen.getByRole('button', { name: 'Submit Request' }));

    await waitFor(() => expect(submitClientRequest).toHaveBeenCalledOnce());
    expect(submitClientRequest).toHaveBeenCalledWith(expect.objectContaining({
      client_name: 'Portal Client',
      client_email: 'portal-client@example.test',
      service_type: 'OVERNIGHT',
      selected_dates: ['2030-01-05'],
      start_date: '2030-01-05',
      end_date: '',
      visit_windows: ['ANYTIME'],
      visit_window: 'ANYTIME',
      pets: [expect.objectContaining({ name: 'Synthetic Pet' })],
      accepted_terms: true
    }));
    expect(submitRequest).not.toHaveBeenCalled();
  });

  it('preserves loading, error, and retry behavior without making a real API call', async () => {
    let rejectFirstRequest;
    submitRequest
      .mockImplementationOnce(() => new Promise((_, reject) => { rejectFirstRequest = reject; }))
      .mockResolvedValueOnce({ request_id: 'synthetic-retry-request' });

    await completeValidForm();
    fireEvent.click(screen.getByRole('button', { name: 'Submit Request' }));

    expect(screen.getByRole('button', { name: 'Sending...' })).toBeDisabled();
    await waitFor(() => expect(submitRequest).toHaveBeenCalledOnce());
    rejectFirstRequest(new Error('Synthetic submission failure'));
    expect(await screen.findByText(/Synthetic submission failure/)).toBeInTheDocument();

    const retryButton = screen.getByRole('button', { name: 'Submit Request' });
    expect(retryButton).toBeEnabled();
    fireEvent.click(retryButton);

    await waitFor(() => expect(submitRequest).toHaveBeenCalledTimes(2));
    expect(await screen.findByRole('heading', { name: 'Request Received!' })).toBeInTheDocument();
  });
});
