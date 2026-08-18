import React from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import * as XLSX from 'xlsx';
import AdminDashboard from '../src/components/AdminDashboard';
import { SERVICE_TYPES } from '../src/generated/contracts';
import { getEffectiveRole, getSession } from '../src/api/auth';
import {
  createAdminBooking,
  getAdminRequests,
  getClients,
  getExportData,
  getGoogleStatus,
  getStaff,
  getTenantInfo,
  listAdminClientPets
} from '../src/api/client';

const xlsxState = vi.hoisted(() => ({ sheets: [] }));

vi.mock('xlsx', () => ({
  utils: {
    book_new: vi.fn(() => ({})),
    json_to_sheet: vi.fn(rows => ({ kind: 'json', rows })),
    aoa_to_sheet: vi.fn(rows => ({ kind: 'aoa', rows })),
    book_append_sheet: vi.fn((_workbook, sheet, name) => {
      xlsxState.sheets.push({ name, sheet });
    })
  },
  write: vi.fn(() => new ArrayBuffer(0))
}));

vi.mock('../src/api/auth', () => ({
  signIn: vi.fn(),
  getSession: vi.fn(),
  getEffectiveRole: vi.fn()
}));

vi.mock('../src/api/client', () => ({
  getAdminRequests: vi.fn(),
  reviewRequest: vi.fn(),
  assignWorker: vi.fn(),
  getGoogleStatus: vi.fn(),
  initiateGoogleAuth: vi.fn(),
  getPet: vi.fn(),
  updatePet: vi.fn(),
  createPet: vi.fn(),
  processCancellationDecision: vi.fn(),
  performAdminAction: vi.fn(),
  purgeRecord: vi.fn(),
  purgeRecordsBulk: vi.fn(),
  getStaff: vi.fn(),
  createStaff: vi.fn(),
  updateStaff: vi.fn(),
  disableStaff: vi.fn(),
  onboardStaff: vi.fn(),
  linkCognitoUser: vi.fn(),
  resendInvite: vi.fn(),
  resetStaffPassword: vi.fn(),
  setStaffTempPassword: vi.fn(),
  getClients: vi.fn(),
  createClient: vi.fn(),
  updateClient: vi.fn(),
  disableClient: vi.fn(),
  onboardClient: vi.fn(),
  resendClientInvite: vi.fn(),
  resetClientPassword: vi.fn(),
  setClientTempPassword: vi.fn(),
  linkClientCognitoUser: vi.fn(),
  getExportData: vi.fn(),
  createAdminBooking: vi.fn(),
  listAdminClientPets: vi.fn(),
  getTenantInfo: vi.fn()
}));

window.HTMLElement.prototype.scrollIntoView = vi.fn();

const canonicalLongLabels = [
  ['WALK_30MIN', '30-Minute Walk'],
  ['WALK_60MIN', '60-Minute Walk'],
  ['DROPIN_1HR', '1-Hour Drop-in'],
  ['DROPIN_3HR', '3-Hour Drop-in'],
  ['OVERNIGHT', 'Overnight Care'],
  ['PET_SITTING', 'Pet Sitting'],
  ['MEET_GREET', 'Meet & Greet']
];

const longFallbacks = [
  ['DOG_WALKING', 'DOG WALKING'],
  ['WALKING', 'WALKING'],
  ['OTHER', 'OTHER'],
  ['HOUSE_SITTING', 'HOUSE SITTING'],
  ['walk_30min', 'Walk 30min'],
  ['Walk_60Min', 'Walk 60Min'],
  [null, 'UNKNOWN SERVICE'],
  [undefined, 'UNKNOWN SERVICE'],
  ['', 'UNKNOWN SERVICE']
];

const makeRequest = (serviceType, index) => {
  const request = {
    PK: `REQ#service-${index}`,
    SK: `CLIENT#client-${index}`,
    request_id: `service-${index}`,
    status: 'PENDING_REVIEW',
    client_name: `Client ${index}`,
    client_email: `client-${index}@example.test`,
    pet_names: `Pet ${index}`,
    start_date: '2030-01-05'
  };
  if (serviceType !== undefined) request.service_type = serviceType;
  return request;
};

const renderDashboard = async () => {
  render(<AdminDashboard />);
  await screen.findByRole('button', { name: 'Request List' });
};

const openRequestList = async () => {
  fireEvent.click(screen.getByRole('button', { name: 'Request List' }));
  await screen.findByRole('heading', { name: /Request List/ });
};

const getSheetRows = name => xlsxState.sheets.find(sheet => sheet.name === name)?.sheet.rows;

const openNewVisit = async () => {
  await renderDashboard();
  fireEvent.click(screen.getByRole('button', { name: '+ New Visit' }));
  return screen.getByRole('heading', { name: 'Create Visit for Client' }).closest('.modal-content');
};

const getNewVisitServiceSelect = () => {
  const serviceField = screen.getByText('Service Type *').closest('.field');
  return within(serviceField).getByRole('combobox');
};

const selectClientPetAndDate = async (modal, date = '2030-01-05') => {
  const clientField = screen.getByText('Client *').closest('.field');
  fireEvent.change(within(clientField).getByRole('combobox'), { target: { value: 'client-1' } });
  fireEvent.click(await screen.findByRole('checkbox', { name: /Synthetic Pet/ }));
  const rangeInputs = modal.querySelectorAll('input[type="date"]');
  fireEvent.change(rangeInputs[0], { target: { value: date } });
  fireEvent.change(rangeInputs[1], { target: { value: date } });
  fireEvent.click(within(modal).getByRole('button', { name: 'Apply' }));
};

describe('AdminDashboard service-type behavior', () => {
  const mockSession = {
    getIdToken: () => ({
      payload: {
        email: 'owner@example.test',
        sub: 'owner-service-label-test',
        name: 'Owner Test'
      }
    })
  };

  beforeEach(() => {
    xlsxState.sheets = [];
    getSession.mockResolvedValue(mockSession);
    getEffectiveRole.mockReturnValue('owner');
    getGoogleStatus.mockResolvedValue({ status: 'CONNECTED' });
    getTenantInfo.mockResolvedValue({ company_name: 'Synthetic Test Company' });
    getStaff.mockResolvedValue({ staff: [] });
    getClients.mockResolvedValue({
      clients: [{
        client_id: 'client-1',
        display_name: 'Synthetic Client',
        email: 'client@example.test',
        phone: '555-0100',
        is_active: true
      }]
    });
    listAdminClientPets.mockResolvedValue({
      pets: [{ pet_id: 'pet-1', name: 'Synthetic Pet', species: 'DOG', is_active: true }]
    });
    createAdminBooking.mockResolvedValue({ message: 'Synthetic booking created.' });
    getAdminRequests.mockResolvedValue({ requests: [] });
    getExportData.mockResolvedValue({ requests: [], clients: [], pets: [], staff: [], jobs: [] });
    Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: vi.fn(() => 'blob:synthetic-export') });
    Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: vi.fn() });
    window.requestAnimationFrame = vi.fn();
  });

  it('preserves every canonical long label and every case-sensitive long fallback', async () => {
    const cases = [...canonicalLongLabels, ...longFallbacks];
    getAdminRequests.mockResolvedValue({
      requests: cases.map(([serviceType], index) => makeRequest(serviceType, index))
    });

    await renderDashboard();
    await openRequestList();

    for (const [index, [, expectedLabel]] of cases.entries()) {
      const row = (await screen.findByText(`Pet ${index} (Client ${index})`)).closest('tr');
      expect(within(row).getByText(expectedLabel)).toBeInTheDocument();
    }
  });

  it('keeps request search matched to the current long-label output', async () => {
    const requests = [
      makeRequest('WALK_30MIN', 0),
      makeRequest('walk_30min', 1),
      makeRequest('HOUSE_SITTING', 2)
    ];
    getAdminRequests.mockResolvedValue({ requests });

    await renderDashboard();
    await openRequestList();
    const search = screen.getByPlaceholderText('Search client, pet, email, ID...');

    fireEvent.change(search, { target: { value: '30-minute walk' } });
    expect(await screen.findByText('Pet 0 (Client 0)')).toBeInTheDocument();
    expect(screen.queryByText('Pet 1 (Client 1)')).not.toBeInTheDocument();

    fireEvent.change(search, { target: { value: 'walk 30min' } });
    expect(await screen.findByText('Pet 1 (Client 1)')).toBeInTheDocument();
    expect(screen.queryByText('Pet 0 (Client 0)')).not.toBeInTheDocument();
  });

  it('derives the complete admin catalog from the contract and preserves legacy raw payload behavior', async () => {
    const modal = await openNewVisit();
    const serviceSelect = getNewVisitServiceSelect();
    const options = within(serviceSelect).getAllByRole('option');
    expect(options.map(option => option.value)).toEqual(Object.keys(SERVICE_TYPES.services));
    expect(options.map(option => option.textContent)).toEqual(
      Object.values(SERVICE_TYPES.services).map(service => service.labelLong)
    );
    expect(serviceSelect).toHaveValue('PET_SITTING');
    expect(options.some(option => option.value === 'WALK_20MIN')).toBe(true);
    expect(options.some(option => option.value === 'CHECK_IN')).toBe(true);
    expect(options.some(option => option.value === 'OVERNIGHT')).toBe(true);
    expect(options.some(option => option.value === 'MEET_GREET')).toBe(true);
    expect(options.some(option => ['DOG_WALKING', 'WALKING', 'OTHER'].includes(option.value))).toBe(false);

    await selectClientPetAndDate(modal);
    fireEvent.change(serviceSelect, { target: { value: 'WALK_60MIN' } });
    fireEvent.click(within(modal).getByRole('button', { name: 'Create Visit' }));

    await waitFor(() => {
      expect(createAdminBooking).toHaveBeenCalledWith({
        client_id: 'client-1',
        client_name: 'Synthetic Client',
        client_email: 'client@example.test',
        client_phone: '555-0100',
        pet_names: 'Synthetic Pet',
        pet_ids: ['pet-1'],
        service_type: 'WALK_60MIN',
        visit_windows: ['ANYTIME'],
        details: undefined,
        preferred_sitter: undefined,
        selected_dates: ['2030-01-05'],
        start_date: '2030-01-05'
      });
    });
  });

  it('renders accessible contract-driven Check-In visits and canonical windows', async () => {
    await openNewVisit();
    fireEvent.change(getNewVisitServiceSelect(), { target: { value: 'CHECK_IN' } });

    const visitsGroup = screen.getByRole('group', { name: 'Visits per day *' });
    expect(within(visitsGroup).getAllByRole('radio').map(radio => radio.value)).toEqual(['1', '2', '3']);

    const windowsGroup = screen.getByRole('group', { name: 'Visit windows *' });
    expect(within(windowsGroup).getByRole('checkbox', { name: 'Morning, 6:30 AM to 9:30 AM' })).toBeDisabled();
    expect(within(windowsGroup).getByRole('checkbox', { name: 'Mid-day, 10:30 AM to 3:30 PM' })).toBeDisabled();
    expect(within(windowsGroup).getByRole('checkbox', { name: 'Evening, 6:00 PM to 9:30 PM' })).toBeDisabled();
    expect(screen.queryByText('Visit Window')).not.toBeInTheDocument();
  });

  it('submits one-window Check-In with the exact preserved admin payload and no status', async () => {
    getStaff.mockResolvedValue({
      staff: [{ staff_id: 'staff-1', display_name: 'Sitter One', email: 'sitter@example.test', is_active: true, is_assignable: true }]
    });
    const modal = await openNewVisit();
    await selectClientPetAndDate(modal);
    fireEvent.change(getNewVisitServiceSelect(), { target: { value: 'CHECK_IN' } });
    fireEvent.click(screen.getByRole('radio', { name: '1' }));
    fireEvent.click(screen.getByRole('checkbox', { name: 'Evening, 6:00 PM to 9:30 PM' }));

    const notesField = screen.getByText('Notes / Details').closest('.field');
    fireEvent.change(within(notesField).getByRole('textbox'), { target: { value: 'Use side gate.' } });
    const sitterField = screen.getByText('Preferred Sitter').closest('.field');
    fireEvent.change(within(sitterField).getByRole('combobox'), { target: { value: 'sitter@example.test' } });
    fireEvent.click(within(modal).getByRole('button', { name: 'Create Visit' }));

    await waitFor(() => expect(createAdminBooking).toHaveBeenCalledOnce());
    expect(createAdminBooking).toHaveBeenCalledWith({
      client_id: 'client-1',
      client_name: 'Synthetic Client',
      client_email: 'client@example.test',
      client_phone: '555-0100',
      pet_names: 'Synthetic Pet',
      pet_ids: ['pet-1'],
      service_type: 'CHECK_IN',
      details: 'Use side gate.',
      preferred_sitter: 'sitter@example.test',
      selected_dates: ['2030-01-05'],
      start_date: '2030-01-05',
      visits_per_day: 1,
      visit_windows: ['EVENING']
    });
    expect(createAdminBooking.mock.calls[0][0]).not.toHaveProperty('visit_window');
    expect(createAdminBooking.mock.calls[0][0]).not.toHaveProperty('status');
  });

  it('limits two-visit Check-In to two windows and submits canonical order', async () => {
    const modal = await openNewVisit();
    await selectClientPetAndDate(modal);
    fireEvent.change(getNewVisitServiceSelect(), { target: { value: 'CHECK_IN' } });
    fireEvent.click(screen.getByRole('radio', { name: '2' }));
    fireEvent.click(screen.getByRole('checkbox', { name: 'Evening, 6:00 PM to 9:30 PM' }));
    fireEvent.click(screen.getByRole('checkbox', { name: 'Morning, 6:30 AM to 9:30 AM' }));
    expect(screen.getByRole('checkbox', { name: 'Mid-day, 10:30 AM to 3:30 PM' })).toBeDisabled();
    fireEvent.click(within(modal).getByRole('button', { name: 'Create Visit' }));

    await waitFor(() => expect(createAdminBooking).toHaveBeenCalledOnce());
    expect(createAdminBooking.mock.calls[0][0]).toMatchObject({
      service_type: 'CHECK_IN',
      visits_per_day: 2,
      visit_windows: ['MORNING', 'EVENING']
    });
  });

  it('automatically selects all three canonical windows for three visits', async () => {
    const modal = await openNewVisit();
    await selectClientPetAndDate(modal);
    fireEvent.change(getNewVisitServiceSelect(), { target: { value: 'CHECK_IN' } });
    fireEvent.click(screen.getByRole('radio', { name: '3' }));

    const checkboxes = screen.getAllByRole('checkbox').filter(input => input.getAttribute('aria-label')?.includes(' to '));
    expect(checkboxes).toHaveLength(3);
    checkboxes.forEach(checkbox => {
      expect(checkbox).toBeChecked();
      expect(checkbox).toBeDisabled();
    });
    fireEvent.click(within(modal).getByRole('button', { name: 'Create Visit' }));
    await waitFor(() => expect(createAdminBooking).toHaveBeenCalledOnce());
    expect(createAdminBooking.mock.calls[0][0]).toMatchObject({
      visits_per_day: 3,
      visit_windows: ['MORNING', 'MIDDAY', 'EVENING']
    });
  });

  it('normalizes 2→1, 1→3, and 3→2 in canonical order', async () => {
    await openNewVisit();
    fireEvent.change(getNewVisitServiceSelect(), { target: { value: 'CHECK_IN' } });
    fireEvent.click(screen.getByRole('radio', { name: '2' }));
    fireEvent.click(screen.getByRole('checkbox', { name: 'Evening, 6:00 PM to 9:30 PM' }));
    fireEvent.click(screen.getByRole('checkbox', { name: 'Morning, 6:30 AM to 9:30 AM' }));

    fireEvent.click(screen.getByRole('radio', { name: '1' }));
    expect(screen.getByRole('checkbox', { name: 'Morning, 6:30 AM to 9:30 AM' })).toBeChecked();
    expect(screen.getByRole('checkbox', { name: 'Evening, 6:00 PM to 9:30 PM' })).not.toBeChecked();

    fireEvent.click(screen.getByRole('radio', { name: '3' }));
    screen.getAllByRole('checkbox').filter(input => input.getAttribute('aria-label')?.includes(' to ')).forEach(checkbox => {
      expect(checkbox).toBeChecked();
    });

    fireEvent.click(screen.getByRole('radio', { name: '2' }));
    expect(screen.getByRole('checkbox', { name: 'Morning, 6:30 AM to 9:30 AM' })).toBeChecked();
    expect(screen.getByRole('checkbox', { name: 'Mid-day, 10:30 AM to 3:30 PM' })).toBeChecked();
    expect(screen.getByRole('checkbox', { name: 'Evening, 6:00 PM to 9:30 PM' })).not.toBeChecked();
  });

  it('renders the fixed Overnight schedule, clears prior state, and preserves the exact admin payload boundary', async () => {
    getStaff.mockResolvedValue({
      staff: [{ staff_id: 'staff-1', display_name: 'Sitter One', email: 'sitter@example.test', is_active: true, is_assignable: true }]
    });
    const modal = await openNewVisit();
    await selectClientPetAndDate(modal);
    const serviceSelect = getNewVisitServiceSelect();
    fireEvent.change(serviceSelect, { target: { value: 'CHECK_IN' } });
    fireEvent.click(screen.getByRole('radio', { name: '2' }));
    fireEvent.click(screen.getByRole('checkbox', { name: 'Morning, 6:30 AM to 9:30 AM' }));
    fireEvent.click(screen.getByRole('checkbox', { name: 'Evening, 6:00 PM to 9:30 PM' }));

    fireEvent.change(serviceSelect, { target: { value: 'OVERNIGHT' } });
    expect(screen.queryByRole('group', { name: 'Visits per day *' })).not.toBeInTheDocument();
    expect(screen.queryByRole('group', { name: /visit window/i })).not.toBeInTheDocument();
    expect(screen.getByRole('note', { name: 'Fixed Overnight schedule' })).toHaveTextContent('9:00 PM–7:00 AM');
    expect(screen.getByRole('note', { name: 'Fixed Overnight schedule' })).toHaveTextContent('following morning');

    const notesField = screen.getByText('Notes / Details').closest('.field');
    fireEvent.change(within(notesField).getByRole('textbox'), { target: { value: 'Use side gate.' } });
    const sitterField = screen.getByText('Preferred Sitter').closest('.field');
    fireEvent.change(within(sitterField).getByRole('combobox'), { target: { value: 'sitter@example.test' } });
    fireEvent.click(within(modal).getByRole('button', { name: 'Create Visit' }));

    await waitFor(() => expect(createAdminBooking).toHaveBeenCalledOnce());
    const payload = createAdminBooking.mock.calls[0][0];
    expect(payload).toEqual({
      client_id: 'client-1',
      client_name: 'Synthetic Client',
      client_email: 'client@example.test',
      client_phone: '555-0100',
      pet_names: 'Synthetic Pet',
      pet_ids: ['pet-1'],
      service_type: 'OVERNIGHT',
      details: 'Use side gate.',
      preferred_sitter: 'sitter@example.test',
      selected_dates: ['2030-01-05'],
      start_date: '2030-01-05'
    });
    [
      'visits_per_day', 'visit_windows', 'visit_window', 'preferred_time', 'scheduled_time',
      'start_time', 'end_time', 'fixed_start_time', 'fixed_end_time', 'scheduled_duration'
    ].forEach(field => expect(payload).not.toHaveProperty(field));
  });

  it('renders and submits the exactly-one canonical Walk window with the preserved admin workflow payload', async () => {
    getStaff.mockResolvedValue({
      staff: [{ staff_id: 'staff-1', display_name: 'Sitter One', email: 'sitter@example.test', is_active: true, is_assignable: true }]
    });
    const modal = await openNewVisit();
    await selectClientPetAndDate(modal);
    fireEvent.change(getNewVisitServiceSelect(), { target: { value: 'WALK_20MIN' } });

    const group = screen.getByRole('group', { name: 'Visit window *' });
    expect(within(group).getByRole('radio', { name: 'Morning, 6:30 AM to 9:30 AM' })).not.toBeChecked();
    expect(within(group).getByRole('radio', { name: 'Mid-day, 10:30 AM to 3:30 PM' })).not.toBeChecked();
    expect(within(group).getByRole('radio', { name: 'Evening, 6:00 PM to 9:30 PM' })).not.toBeChecked();

    fireEvent.click(within(modal).getByRole('button', { name: 'Create Visit' }));
    expect(screen.getByRole('alert')).toHaveTextContent('Choose exactly one visit window.');
    expect(createAdminBooking).not.toHaveBeenCalled();

    fireEvent.click(within(group).getByRole('radio', { name: /^Morning,/ }));
    fireEvent.click(within(group).getByRole('radio', { name: /^Evening,/ }));
    expect(within(group).getByRole('radio', { name: /^Morning,/ })).not.toBeChecked();
    expect(within(group).getByRole('radio', { name: /^Evening,/ })).toBeChecked();

    const notesField = screen.getByText('Notes / Details').closest('.field');
    fireEvent.change(within(notesField).getByRole('textbox'), { target: { value: 'Use side gate.' } });
    const sitterField = screen.getByText('Preferred Sitter').closest('.field');
    fireEvent.change(within(sitterField).getByRole('combobox'), { target: { value: 'sitter@example.test' } });
    fireEvent.click(within(modal).getByRole('button', { name: 'Create Visit' }));

    await waitFor(() => expect(createAdminBooking).toHaveBeenCalledOnce());
    expect(createAdminBooking).toHaveBeenCalledWith({
      client_id: 'client-1',
      client_name: 'Synthetic Client',
      client_email: 'client@example.test',
      client_phone: '555-0100',
      pet_names: 'Synthetic Pet',
      pet_ids: ['pet-1'],
      service_type: 'WALK_20MIN',
      details: 'Use side gate.',
      preferred_sitter: 'sitter@example.test',
      selected_dates: ['2030-01-05'],
      start_date: '2030-01-05',
      visit_windows: ['EVENING']
    });
    expect(createAdminBooking.mock.calls[0][0]).not.toHaveProperty('visits_per_day');
    expect(createAdminBooking.mock.calls[0][0]).not.toHaveProperty('status');
  });

  it('returns from Walk or Overnight to a clean Check-In schedule', async () => {
    await openNewVisit();
    const serviceSelect = getNewVisitServiceSelect();
    fireEvent.change(serviceSelect, { target: { value: 'CHECK_IN' } });
    fireEvent.click(screen.getByRole('radio', { name: '3' }));
    fireEvent.change(serviceSelect, { target: { value: 'WALK_20MIN' } });
    fireEvent.change(serviceSelect, { target: { value: 'CHECK_IN' } });
    expect(screen.getAllByRole('radio').filter(radio => radio.name === 'admin-visits-per-day')).toHaveLength(3);
    expect(screen.getAllByRole('radio').filter(radio => radio.name === 'admin-visits-per-day').every(radio => !radio.checked)).toBe(true);
    fireEvent.change(serviceSelect, { target: { value: 'OVERNIGHT' } });
    fireEvent.change(serviceSelect, { target: { value: 'CHECK_IN' } });
    screen.getAllByRole('checkbox').filter(input => input.getAttribute('aria-label')?.includes(' to ')).forEach(checkbox => {
      expect(checkbox).not.toBeChecked();
      expect(checkbox).toBeDisabled();
    });
  });

  it('shows associated human-readable errors for missing count and exact window count', async () => {
    const modal = await openNewVisit();
    await selectClientPetAndDate(modal);
    fireEvent.change(getNewVisitServiceSelect(), { target: { value: 'CHECK_IN' } });
    fireEvent.click(within(modal).getByRole('button', { name: 'Create Visit' }));
    expect(screen.getByRole('alert')).toHaveTextContent('Choose how many Check-In visits are needed each day.');
    expect(createAdminBooking).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('radio', { name: '2' }));
    fireEvent.click(screen.getByRole('checkbox', { name: 'Morning, 6:30 AM to 9:30 AM' }));
    fireEvent.click(within(modal).getByRole('button', { name: 'Create Visit' }));
    expect(screen.getByRole('alert')).toHaveTextContent('Choose exactly 2 visit windows.');
    expect(screen.getByRole('group', { name: 'Visit windows *' })).toHaveAttribute('aria-describedby', 'admin-check-in-schedule-error');
    expect(createAdminBooking).not.toHaveBeenCalled();
  });

  it('keeps dispatch-friendly labels and raw request export values unchanged', async () => {
    const shortCases = [
      ['WALK_30MIN', '30-Min Walk'],
      ['WALK_60MIN', '60-Min Walk'],
      ['DROPIN_1HR', '1-Hour Drop-in'],
      ['DROPIN_3HR', '3-Hour Drop-in'],
      ['OVERNIGHT', 'Overnight Care'],
      ['PET_SITTING', 'Pet Sitting'],
      ['MEET_GREET', 'Meet & Greet'],
      ['walk_30min', '30-Min Walk'],
      ['wAlK_60mIn', '60-Min Walk'],
      ['DOG_WALKING', 'DOG_WALKING'],
      ['WALKING', 'WALKING'],
      ['OTHER', 'OTHER'],
      ['HOUSE_SITTING', 'HOUSE_SITTING'],
      ['Spa_Day', 'Spa_Day'],
      [null, ''],
      [undefined, ''],
      ['', '']
    ];
    const today = new Date();
    const occurrenceDate = [
      today.getFullYear(),
      String(today.getMonth() + 1).padStart(2, '0'),
      String(today.getDate()).padStart(2, '0')
    ].join('-');
    const jobs = shortCases.map(([serviceType], index) => {
      const job = {
        job_id: `job-${index}`,
        request_id: `export-${index}`,
        status: 'ASSIGNED',
        occurrence_date: occurrenceDate,
        worker_name: `Worker ${String(index).padStart(2, '0')}`,
        client_name: `Export Client ${index}`,
        pet_name: `Export Pet ${index}`
      };
      if (serviceType !== undefined) job.service_type = serviceType;
      return job;
    });
    const requests = shortCases.map(([serviceType], index) => {
      const request = {
        PK: `REQ#export-${index}`,
        request_id: `export-${index}`,
        status: 'ASSIGNED',
        client_name: `Export Client ${index}`,
        pet_names: `Export Pet ${index}`
      };
      if (serviceType !== undefined) request.service_type = serviceType;
      return request;
    });
    getExportData.mockResolvedValue({ requests, clients: [], pets: [], staff: [], jobs });

    await renderDashboard();
    fireEvent.click(screen.getByRole('button', { name: '📥 Download Offline Backup' }));
    const exportModal = screen.getByRole('heading', { name: 'Download Offline Backup' }).closest('.modal-content');
    fireEvent.click(within(exportModal).getByRole('button', { name: 'Confirm & Download' }));
    await waitFor(() => expect(XLSX.write).toHaveBeenCalledOnce());

    const dispatchRows = getSheetRows('Daily Dispatch');
    expect(dispatchRows.map(row => row['Service Type'])).toEqual(shortCases.map(([, expected]) => expected));

    const rawRows = getSheetRows('All Requests');
    expect(rawRows.map(row => row['Service Type'])).toEqual(shortCases.map(([input]) => input || ''));
  });
});
