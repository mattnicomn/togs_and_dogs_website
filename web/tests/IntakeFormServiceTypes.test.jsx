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

const goToSchedule = async () => {
  renderIntake();
  fireEvent.change(screen.getByPlaceholderText('Alex Barker'), { target: { value: 'Synthetic Customer' } });
  fireEvent.change(screen.getByPlaceholderText('alex@example.com'), { target: { value: 'customer@example.test' } });
  fireEvent.change(screen.getByPlaceholderText('555-123-4567'), { target: { value: '555-0102' } });
  fireEvent.click(screen.getByRole('button', { name: 'Next: Schedule →' }));
  return screen.findByRole('heading', { name: 'When do you need care?' });
};

const getServiceSelect = () => screen.getByRole('combobox', { name: 'Service Type *' });

const chooseDate = () => {
  const dateInputs = document.querySelectorAll('input[type="date"]');
  fireEvent.change(dateInputs[0], { target: { value: '2030-01-05' } });
  fireEvent.change(dateInputs[1], { target: { value: '2030-01-05' } });
  fireEvent.click(screen.getByRole('button', { name: 'Select Dates from Range' }));
};

const chooseCheckInSchedule = (visitsPerDay, windowLabels = []) => {
  fireEvent.click(screen.getByRole('radio', { name: `${visitsPerDay} visit${visitsPerDay === 1 ? '' : 's'} per day` }));
  windowLabels.forEach((label) => fireEvent.click(screen.getByRole('checkbox', { name: new RegExp(`^${label},`) })));
};

const goToPetInfo = async ({ serviceType = 'WALK_20MIN', visitsPerDay, windows = [] } = {}) => {
  await goToSchedule();
  fireEvent.change(getServiceSelect(), { target: { value: serviceType } });
  if (serviceType === 'CHECK_IN' && visitsPerDay) chooseCheckInSchedule(visitsPerDay, windows);
  if (serviceType === 'WALK_20MIN') {
    fireEvent.click(screen.getByRole('radio', { name: new RegExp(`^${windows[0] || 'Morning'},`) }));
  }
  chooseDate();
  fireEvent.change(screen.getByPlaceholderText('e.g. After 9am preferred, key under mat...'), {
    target: { value: 'Synthetic timing note' }
  });
  fireEvent.click(screen.getByRole('button', { name: 'Next: Pet Info →' }));
  return screen.findByRole('heading', { name: 'Tell us about your pets' });
};

const completeValidForm = async (schedule = {}) => {
  await goToPetInfo(schedule);
  fireEvent.change(screen.getByPlaceholderText('e.g. Luna'), { target: { value: 'Synthetic Pet' } });
  fireEvent.change(screen.getByPlaceholderText('e.g. Golden Retriever'), { target: { value: 'Retriever' } });
  fireEvent.change(screen.getByPlaceholderText('Food type, schedule, portions...'), {
    target: { value: 'Synthetic feeding note' }
  });
  fireEvent.click(screen.getByText(/I agree to the/).closest('label'));
};

describe('IntakeForm canonical new-booking behavior', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getSession.mockResolvedValue(null);
    getEffectiveRole.mockReturnValue('unknown');
    getStaffOptions.mockResolvedValue({ staff_options: [] });
    submitRequest.mockResolvedValue({ request_id: 'synthetic-request' });
    submitClientRequest.mockResolvedValue({ request_id: 'synthetic-client-request' });
  });

  it('uses exactly the active eligible contract services, labels, order, and contract-derived default', async () => {
    await goToSchedule();
    const options = within(getServiceSelect()).getAllByRole('option');
    const expectedEntries = Object.entries(SERVICE_TYPES.services)
      .filter(([, service]) => service.lifecycle === 'active' && service.newBookingEligibility === 'eligible');

    expect(options.map((option) => option.value)).toEqual(expectedEntries.map(([identifier]) => identifier));
    expect(options.map((option) => option.textContent)).toEqual(expectedEntries.map(([, service]) => service.labelLong));
    expect(options.map((option) => option.value)).toEqual(['WALK_20MIN', 'CHECK_IN', 'OVERNIGHT']);
    expect(options.map((option) => option.textContent)).toEqual(['20-Minute Walk', '30-Minute Check-In', 'Overnight Care']);
    expect(getServiceSelect()).toHaveValue('WALK_20MIN');
  });

  it('renders contract-derived accessible Check-In visit counts, windows, labels, and times', async () => {
    await goToSchedule();
    fireEvent.change(getServiceSelect(), { target: { value: 'CHECK_IN' } });

    expect(screen.getAllByRole('radio').map((radio) => Number(radio.value)))
      .toEqual(SERVICE_TYPES.services.CHECK_IN.visitsPerDayOptions);
    expect(screen.getByRole('checkbox', { name: 'Morning, 6:30 AM to 9:30 AM' })).not.toBeChecked();
    expect(screen.getByRole('checkbox', { name: 'Mid-day, 10:30 AM to 3:30 PM' })).not.toBeChecked();
    expect(screen.getByRole('checkbox', { name: 'Evening, 6:00 PM to 9:30 PM' })).not.toBeChecked();
    expect(screen.getByRole('group', { name: 'Visits per Day *' })).toBeInTheDocument();
    expect(screen.getByRole('group', { name: 'Preferred Visit Windows *' })).toBeInTheDocument();
  });

  it('renders an accessible exactly-one Walk selector from the canonical contract', async () => {
    await goToSchedule();
    expect(SERVICE_TYPES.services.WALK_20MIN.windowSelectionMode).toBe('exactly_one');
    expect(SERVICE_TYPES.services.WALK_20MIN.allowedWindowIds).toEqual(['MORNING', 'MIDDAY', 'EVENING']);
    expect(screen.getByRole('radio', { name: 'Morning, 6:30 AM to 9:30 AM' })).not.toBeChecked();
    expect(screen.getByRole('radio', { name: 'Mid-day, 10:30 AM to 3:30 PM' })).not.toBeChecked();
    expect(screen.getByRole('radio', { name: 'Evening, 6:00 PM to 9:30 PM' })).not.toBeChecked();
    expect(screen.queryByRole('group', { name: 'Visits per Day *' })).not.toBeInTheDocument();
  });

  it('requires one Walk window and replaces the selection atomically', async () => {
    await goToSchedule();
    chooseDate();
    fireEvent.click(screen.getByRole('button', { name: 'Next: Pet Info →' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Choose exactly one visit window.');

    fireEvent.click(screen.getByRole('radio', { name: /^Morning,/ }));
    fireEvent.click(screen.getByRole('radio', { name: /^Mid-day,/ }));
    expect(screen.getByRole('radio', { name: /^Morning,/ })).not.toBeChecked();
    expect(screen.getByRole('radio', { name: /^Mid-day,/ })).toBeChecked();
  });

  it('preserves human-readable required-service validation', async () => {
    await goToSchedule();
    fireEvent.change(getServiceSelect(), { target: { value: '' } });
    chooseDate();
    fireEvent.click(screen.getByRole('button', { name: 'Next: Pet Info →' }));
    expect(await screen.findByText('Service Type is required.')).toBeInTheDocument();
    expect(getServiceSelect()).toHaveAttribute('aria-invalid', 'true');
  });

  it('requires a Check-In visit count', async () => {
    await goToSchedule();
    fireEvent.change(getServiceSelect(), { target: { value: 'CHECK_IN' } });
    chooseDate();
    fireEvent.click(screen.getByRole('button', { name: 'Next: Pet Info →' }));
    expect(await screen.findByText('Choose how many Check-In visits you need each day.')).toBeInTheDocument();
  });

  it('requires the exact matching number of Check-In windows', async () => {
    await goToSchedule();
    fireEvent.change(getServiceSelect(), { target: { value: 'CHECK_IN' } });
    chooseCheckInSchedule(2, ['Morning']);
    chooseDate();
    fireEvent.click(screen.getByRole('button', { name: 'Next: Pet Info →' }));
    await waitFor(() => expect(screen.getAllByRole('alert').map((alert) => alert.textContent)).toEqual([
      '⚠️ Choose exactly 2 visit windows.'
    ]));
  });

  it('submits one Check-In visit with exactly one canonical window', async () => {
    await completeValidForm({ serviceType: 'CHECK_IN', visitsPerDay: 1, windows: ['Evening'] });
    fireEvent.click(screen.getByRole('button', { name: 'Submit Request' }));

    await waitFor(() => expect(submitRequest).toHaveBeenCalledOnce());
    expect(submitRequest).toHaveBeenCalledWith(expect.objectContaining({
      service_type: 'CHECK_IN',
      visits_per_day: 1,
      visit_windows: ['EVENING'],
      selected_dates: ['2030-01-05'],
      pets: [expect.objectContaining({ name: 'Synthetic Pet' })]
    }));
    expect(submitRequest.mock.calls[0][0]).not.toHaveProperty('visit_window');
  });

  it('caps two Check-In visits at two distinct windows and submits contract order instead of click order', async () => {
    await goToSchedule();
    fireEvent.change(getServiceSelect(), { target: { value: 'CHECK_IN' } });
    chooseCheckInSchedule(2, ['Evening', 'Morning']);

    expect(screen.getByRole('checkbox', { name: /^Mid-day,/ })).toBeDisabled();
    expect(screen.getByRole('checkbox', { name: /^Morning,/ })).toBeChecked();
    expect(screen.getByRole('checkbox', { name: /^Evening,/ })).toBeChecked();
    chooseDate();
    fireEvent.click(screen.getByRole('button', { name: 'Next: Pet Info →' }));
    await screen.findByRole('heading', { name: 'Tell us about your pets' });
    fireEvent.change(screen.getByPlaceholderText('e.g. Luna'), { target: { value: 'Synthetic Pet' } });
    fireEvent.click(screen.getByText(/I agree to the/).closest('label'));
    fireEvent.click(screen.getByRole('button', { name: 'Submit Request' }));

    await waitFor(() => expect(submitRequest).toHaveBeenCalledOnce());
    expect(submitRequest.mock.calls[0][0].visit_windows).toEqual(['MORNING', 'EVENING']);
  });

  it('automatically selects and locks all three canonical windows for three visits per day', async () => {
    await goToSchedule();
    fireEvent.change(getServiceSelect(), { target: { value: 'CHECK_IN' } });
    chooseCheckInSchedule(3);

    const windows = screen.getAllByRole('checkbox');
    expect(windows).toHaveLength(3);
    windows.forEach((window) => {
      expect(window).toBeChecked();
      expect(window).toBeDisabled();
    });
    expect(screen.getByText('All daily windows are selected automatically.')).toBeInTheDocument();
  });

  it('normalizes 2→1, 1→3, and 3→2 transitions deterministically', async () => {
    await goToSchedule();
    fireEvent.change(getServiceSelect(), { target: { value: 'CHECK_IN' } });
    chooseCheckInSchedule(2, ['Morning', 'Evening']);

    fireEvent.click(screen.getByRole('radio', { name: '1 visit per day' }));
    expect(screen.getByRole('checkbox', { name: /^Morning,/ })).toBeChecked();
    expect(screen.getByRole('checkbox', { name: /^Evening,/ })).not.toBeChecked();

    fireEvent.click(screen.getByRole('radio', { name: '3 visits per day' }));
    screen.getAllByRole('checkbox').forEach((window) => expect(window).toBeChecked());

    fireEvent.click(screen.getByRole('radio', { name: '2 visits per day' }));
    expect(screen.getByRole('checkbox', { name: /^Morning,/ })).toBeChecked();
    expect(screen.getByRole('checkbox', { name: /^Mid-day,/ })).toBeChecked();
    expect(screen.getByRole('checkbox', { name: /^Evening,/ })).not.toBeChecked();
  });

  it.each(['OVERNIGHT'])(
    'clears Check-In state when switching to %s and starts clean when switching back',
    async (serviceType) => {
      await goToSchedule();
      fireEvent.change(getServiceSelect(), { target: { value: 'CHECK_IN' } });
      chooseCheckInSchedule(2, ['Morning', 'Evening']);
      fireEvent.change(getServiceSelect(), { target: { value: serviceType } });
      expect(screen.queryByRole('group', { name: 'Visits per Day *' })).not.toBeInTheDocument();
      fireEvent.change(getServiceSelect(), { target: { value: 'CHECK_IN' } });
      expect(screen.getAllByRole('radio').every((radio) => !radio.checked)).toBe(true);
      expect(screen.getAllByRole('checkbox').every((window) => !window.checked)).toBe(true);
    }
  );

  it('submits Walk with one canonical window and no visits-per-day field', async () => {
    await completeValidForm({ serviceType: 'WALK_20MIN', windows: ['Evening'] });
    fireEvent.click(screen.getByRole('button', { name: 'Submit Request' }));
    await waitFor(() => expect(submitRequest).toHaveBeenCalledOnce());
    const payload = submitRequest.mock.calls[0][0];
    expect(payload.visit_windows).toEqual(['EVENING']);
    expect(payload).not.toHaveProperty('visits_per_day');
    expect(payload).not.toHaveProperty('visit_window');
  });

  it.each(['OVERNIGHT'])(
    'submits %s without Check-In-only or invented scheduling fields',
    async (serviceType) => {
      await completeValidForm({ serviceType });
      fireEvent.click(screen.getByRole('button', { name: 'Submit Request' }));
      await waitFor(() => expect(submitRequest).toHaveBeenCalledOnce());
      const payload = submitRequest.mock.calls[0][0];
      expect(payload).toEqual(expect.objectContaining({
        service_type: serviceType,
        selected_dates: ['2030-01-05'],
        pets: [expect.objectContaining({ name: 'Synthetic Pet' })],
        timing_notes: 'Synthetic timing note'
      }));
      expect(payload).not.toHaveProperty('visits_per_day');
      expect(payload).not.toHaveProperty('visit_windows');
      expect(payload).not.toHaveProperty('visit_window');
      expect(payload).not.toHaveProperty('preferred_time');
      expect(payload).not.toHaveProperty('scheduled_time');
      expect(payload).not.toHaveProperty('start_time');
      expect(payload).not.toHaveProperty('end_time');
    }
  );

  it('reviews Check-In duration, count, friendly windows, and dates without pricing', async () => {
    await goToPetInfo({ serviceType: 'CHECK_IN', visitsPerDay: 2, windows: ['Morning', 'Evening'] });
    const summary = screen.getByRole('region', { name: 'Request Summary' });
    expect(within(summary).getByText('Check-In')).toBeInTheDocument();
    expect(within(summary).getByText('30 minutes')).toBeInTheDocument();
    expect(within(summary).getByText('2')).toBeInTheDocument();
    expect(within(summary).getByText(/Morning/)).toBeInTheDocument();
    expect(within(summary).getByText(/Evening/)).toBeInTheDocument();
    expect(within(summary).getByText('2030-01-05')).toBeInTheDocument();
    expect(within(summary).queryByText(/\$|price|pricing/i)).not.toBeInTheDocument();
  });

  it('reviews Walk duration, friendly selected window range, and dates without pricing', async () => {
    await goToPetInfo({ serviceType: 'WALK_20MIN', windows: ['Mid-day'] });
    const summary = screen.getByRole('region', { name: 'Request Summary' });
    expect(within(summary).getByText('20-Min Walk')).toBeInTheDocument();
    expect(within(summary).getByText('20 minutes')).toBeInTheDocument();
    expect(within(summary).getByText('Mid-day (10:30 AM–3:30 PM)')).toBeInTheDocument();
    expect(within(summary).getByText('2030-01-05')).toBeInTheDocument();
    expect(within(summary).queryByText(/visits per day|\$|price|pricing/i)).not.toBeInTheDocument();
  });

  it('renders and reviews the contract-derived fixed Overnight schedule without selectors or legacy duration', async () => {
    await goToSchedule();
    fireEvent.change(getServiceSelect(), { target: { value: 'OVERNIGHT' } });
    const fixedSchedule = screen.getByRole('region', { name: 'Fixed Overnight schedule' });
    expect(within(fixedSchedule).getByText('9:00 PM–7:00 AM')).toBeInTheDocument();
    expect(within(fixedSchedule).getByText(/ends the following morning/i)).toBeInTheDocument();
    expect(within(fixedSchedule).getByText('10 hours nominal service.')).toBeInTheDocument();
    expect(screen.queryByRole('group', { name: /visit window|visits per day/i })).not.toBeInTheDocument();

    chooseDate();
    fireEvent.click(screen.getByRole('button', { name: 'Next: Pet Info →' }));
    await screen.findByRole('heading', { name: 'Tell us about your pets' });
    const summary = screen.getByRole('region', { name: 'Request Summary' });
    expect(within(summary).getByText('Overnight Care')).toBeInTheDocument();
    expect(within(summary).getByText('10 hours')).toBeInTheDocument();
    expect(within(summary).getByText('9:00 PM–7:00 AM next morning')).toBeInTheDocument();
    expect(within(summary).getByText('Overnight start dates')).toBeInTheDocument();
    expect(within(summary).queryByText(/720|12 hours|pricing|\$/i)).not.toBeInTheDocument();
  });

  it('preserves authenticated Overnight routing with no client scheduling-selection fields', async () => {
    getSession.mockResolvedValue({ idToken: { payload: { email: 'portal@example.test', name: 'Portal Client' } } });
    getEffectiveRole.mockReturnValue('client');
    await completeValidForm({ serviceType: 'OVERNIGHT' });
    fireEvent.click(screen.getByRole('button', { name: 'Submit Request' }));

    await waitFor(() => expect(submitClientRequest).toHaveBeenCalledOnce());
    const payload = submitClientRequest.mock.calls[0][0];
    expect(payload).toEqual(expect.objectContaining({
      service_type: 'OVERNIGHT',
      selected_dates: ['2030-01-05']
    }));
    for (const field of ['visits_per_day', 'visit_windows', 'visit_window', 'preferred_time', 'scheduled_time', 'start_time', 'end_time']) {
      expect(payload).not.toHaveProperty(field);
    }
    expect(submitRequest).not.toHaveBeenCalled();
  });

  it('preserves public payload fields and policy acceptance around the new Walk service', async () => {
    await completeValidForm({ serviceType: 'WALK_20MIN' });
    fireEvent.click(screen.getByRole('button', { name: 'Submit Request' }));

    await waitFor(() => expect(submitRequest).toHaveBeenCalledOnce());
    expect(submitRequest).toHaveBeenCalledWith({
      client_name: 'Synthetic Customer',
      client_email: 'customer@example.test',
      client_phone: '555-0102',
      selected_dates: ['2030-01-05'],
      range_start: '',
      range_end: '',
      preferred_time: '',
      timing_notes: 'Synthetic timing note',
      preferred_sitter: '',
      preferred_sitter_name: '',
      pets: [{
        name: 'Synthetic Pet', species: 'DOG', breed: 'Retriever', age: '',
        feeding_notes: 'Synthetic feeding note', medication_notes: '', behavior_notes: ''
      }],
      pet_names: '',
      pet_info: '',
      vet_info: {},
      emergency_contact: {},
      service_type: 'WALK_20MIN',
      visit_windows: ['MORNING'],
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
  });

  it('preserves the authenticated-client endpoint with canonical Walk payload semantics', async () => {
    getSession.mockResolvedValue({ idToken: { payload: { email: 'portal@example.test', name: 'Portal Client' } } });
    getEffectiveRole.mockReturnValue('client');
    await completeValidForm({ serviceType: 'WALK_20MIN', windows: ['Mid-day'] });
    fireEvent.click(screen.getByRole('button', { name: 'Submit Request' }));

    await waitFor(() => expect(submitClientRequest).toHaveBeenCalledOnce());
    expect(submitClientRequest).toHaveBeenCalledWith(expect.objectContaining({
      service_type: 'WALK_20MIN',
      visit_windows: ['MIDDAY'],
      selected_dates: ['2030-01-05']
    }));
    expect(submitClientRequest.mock.calls[0][0]).not.toHaveProperty('visits_per_day');
    expect(submitClientRequest.mock.calls[0][0]).not.toHaveProperty('visit_window');
  });

  it('preserves the authenticated-client endpoint with canonical Check-In payload semantics', async () => {
    getSession.mockResolvedValue({ idToken: { payload: { email: 'portal@example.test', name: 'Portal Client' } } });
    getEffectiveRole.mockReturnValue('client');
    await completeValidForm({ serviceType: 'CHECK_IN', visitsPerDay: 3 });
    fireEvent.click(screen.getByRole('button', { name: 'Submit Request' }));

    await waitFor(() => expect(submitClientRequest).toHaveBeenCalledOnce());
    expect(submitClientRequest).toHaveBeenCalledWith(expect.objectContaining({
      service_type: 'CHECK_IN',
      visits_per_day: 3,
      visit_windows: ['MORNING', 'MIDDAY', 'EVENING'],
      selected_dates: ['2030-01-05'],
      pets: [expect.objectContaining({ name: 'Synthetic Pet' })]
    }));
    expect(submitClientRequest.mock.calls[0][0]).not.toHaveProperty('visit_window');
    expect(submitRequest).not.toHaveBeenCalled();
  });

  it('preserves loading, error, and retry behavior without a real API call', async () => {
    let rejectFirstRequest;
    submitRequest
      .mockImplementationOnce(() => new Promise((_, reject) => { rejectFirstRequest = reject; }))
      .mockResolvedValueOnce({ request_id: 'synthetic-retry-request' });

    await completeValidForm({ serviceType: 'WALK_20MIN' });
    fireEvent.click(screen.getByRole('button', { name: 'Submit Request' }));
    expect(screen.getByRole('button', { name: 'Sending...' })).toBeDisabled();
    await waitFor(() => expect(submitRequest).toHaveBeenCalledOnce());
    rejectFirstRequest(new Error('Synthetic submission failure'));
    expect(await screen.findByText(/Synthetic submission failure/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Submit Request' }));
    await waitFor(() => expect(submitRequest).toHaveBeenCalledTimes(2));
    expect(await screen.findByRole('heading', { name: 'Request Received!' })).toBeInTheDocument();
  });
});
