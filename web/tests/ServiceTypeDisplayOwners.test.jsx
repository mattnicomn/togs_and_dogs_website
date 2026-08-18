import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import ClientPortal from '../src/components/ClientPortal';
import MasterScheduler from '../src/components/MasterScheduler';
import { getEffectiveRole, getSession } from '../src/api/auth';
import { getClientRequests, requestCancellation } from '../src/api/client';
import { SERVICE_TYPES } from '../src/generated/contracts.js';

vi.mock('../src/api/auth', () => ({
  getSession: vi.fn(),
  signIn: vi.fn(),
  getEffectiveRole: vi.fn()
}));

vi.mock('../src/api/client', () => ({
  getClientRequests: vi.fn(),
  requestCancellation: vi.fn()
}));

vi.mock('../src/components/UserProfile', () => ({
  default: () => null
}));

const canonicalCases = Object.entries(SERVICE_TYPES.services).map(([identifier, service]) => [
  identifier,
  service.labelLong
]);

const legacyCases = [
  ['DOG_WALKING', 'Daily Dog Walking'],
  ['WALKING', 'Dog Walking'],
  ['OTHER', 'Other']
];

const schedulerServiceFilterOptions = [
  ['ALL', 'All Services'],
  ...Object.entries(SERVICE_TYPES.services).map(([identifier, service]) => [
    identifier,
    service.labelLong
  ])
];

const schedulerCanonicalCases = schedulerServiceFilterOptions.slice(1).map(([identifier]) => [
  identifier,
  SERVICE_TYPES.services[identifier].labelLong
]);

const setViewportWidth = (width) => {
  Object.defineProperty(window, 'innerWidth', {
    configurable: true,
    writable: true,
    value: width
  });
};

const makePortalRequest = (serviceType, index, overrides = {}) => ({
  PK: `REQ#portal-${index}`,
  request_id: `portal-${index}`,
  client_id: `client-${index}`,
  status: 'PENDING_REVIEW',
  client_name: `Portal Client ${index}`,
  pet_names: `Portal Pet ${index}`,
  start_date: '2035-01-05',
  service_type: serviceType,
  ...overrides
});

const makeSchedulerItem = (serviceType, index, overrides = {}) => ({
  PK: `JOB#scheduler-${index}`,
  status: 'ASSIGNED',
  client_name: `Scheduler Client ${index}`,
  pet_name: `Scheduler Pet ${index}`,
  start_date: '2030-01-05',
  service_type: serviceType,
  ...overrides
});

const renderScheduler = (items, overrides = {}) => {
  const props = {
    items,
    onAssign: vi.fn(),
    onReview: vi.fn(),
    onSelectPet: vi.fn(),
    staffList: [],
    ...overrides
  };
  const result = render(<MasterScheduler {...props} />);
  return { ...result, props };
};

const getSchedulerFilter = (label) => screen
  .getByText(label, { selector: 'label' })
  .closest('.filter-group')
  .querySelector('select');

describe('ClientPortal service-type display compatibility', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getSession.mockResolvedValue({ idToken: { payload: { email: 'client@example.test' } } });
    getEffectiveRole.mockReturnValue('client');
    requestCancellation.mockResolvedValue({ message: 'Synthetic cancellation submitted.' });
  });

  it('renders canonical labels, approved aliases, and every existing owner fallback without mutation', async () => {
    const cases = [
      ...canonicalCases,
      ...legacyCases,
      ['HOUSE_SITTING', 'HOUSE SITTING'],
      ['walk_30min', 'walk 30min'],
      ['Walk_30Min', 'Walk 30Min'],
      [null, 'Pet Care Visit'],
      [undefined, 'Pet Care Visit'],
      ['', 'Pet Care Visit'],
      ['   ', '   ']
    ];
    const requests = cases.map(([serviceType], index) => makePortalRequest(serviceType, index));
    const before = requests.map(request => ({ ...request }));
    getClientRequests.mockResolvedValue({ requests });

    render(<ClientPortal />);
    await screen.findByText('Portal Pet 0');

    cases.forEach(([, expected], index) => {
      const card = screen.getByText(`Portal Pet ${index}`).closest('.booking-card');
      expect(card.querySelector('h4').textContent).toBe(expected);
    });
    expect(requests).toEqual(before);
    cases.forEach(([input], index) => {
      expect(requests[index].service_type).toBe(input);
    });
  });

  it('preserves cancellation identifiers and nearby behavior for a labeled legacy request', async () => {
    const request = makePortalRequest('DOG_WALKING', 0, { status: 'APPROVED' });
    const before = { ...request };
    getClientRequests.mockResolvedValue({ requests: [request] });
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    vi.spyOn(window, 'prompt').mockReturnValue('Synthetic cancellation reason');
    vi.spyOn(window, 'alert').mockImplementation(() => {});

    render(<ClientPortal />);
    expect(await screen.findByRole('heading', { name: 'Daily Dog Walking' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));

    await waitFor(() => {
      expect(requestCancellation).toHaveBeenCalledWith(
        'portal-0',
        'client-0',
        'Synthetic cancellation reason'
      );
    });
    expect(request).toEqual(before);
    expect(request.service_type).toBe('DOG_WALKING');
  });
});

describe('MasterScheduler service-type display compatibility', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2030-01-05T12:00:00'));
    setViewportWidth(1024);
  });

  afterEach(() => {
    vi.useRealTimers();
    setViewportWidth(1024);
    vi.restoreAllMocks();
  });

  it('exposes the complete contract-backed service-filter membership, labels, order, and ALL default', () => {
    renderScheduler([]);
    const serviceFilter = getSchedulerFilter('Service');

    expect(serviceFilter.value).toBe('ALL');
    expect(Array.from(serviceFilter.options, option => [option.value, option.textContent])).toEqual(
      schedulerServiceFilterOptions
    );
  });

  it('filters every canonical contract option by service_type equality without mutation', () => {
    const items = schedulerCanonicalCases.map(([serviceType], index) => makeSchedulerItem(serviceType, index));
    const before = items.map(item => ({ ...item }));
    const { container, props } = renderScheduler(items);
    const serviceFilter = getSchedulerFilter('Service');

    schedulerCanonicalCases.forEach(([serviceType], index) => {
      props.onSelectPet.mockClear();
      fireEvent.change(serviceFilter, { target: { value: serviceType } });

      expect(Array.from(container.querySelectorAll('.visit-pet'), node => node.textContent)).toEqual([
        `Scheduler Pet ${index}`
      ]);
      fireEvent.click(container.querySelector('.scheduled-visit'));
      expect(props.onSelectPet).toHaveBeenCalledTimes(1);
      expect(props.onSelectPet).toHaveBeenCalledWith(items[index]);
    });

    expect(items).toEqual(before);
  });

  it('filters target services while preserving Check-In occurrence scheduling data and selection actions', () => {
    const items = [
      makeSchedulerItem('WALK_20MIN', 0, { start_time: '08:15' }),
      makeSchedulerItem('CHECK_IN', 1, {
        start_date: '2030-01-05',
        start_time: '10:30',
        occurrence_window: 'MIDDAY',
        visit_window: 'MIDDAY'
      }),
      makeSchedulerItem('OVERNIGHT', 2, { window_start: '21:00' })
    ];
    const before = items.map(item => ({ ...item }));
    const { container, props } = renderScheduler(items);
    const serviceFilter = getSchedulerFilter('Service');

    expect(Array.from(container.querySelectorAll('.visit-pet'), node => node.textContent)).toEqual([
      'Scheduler Pet 0',
      'Scheduler Pet 1',
      'Scheduler Pet 2'
    ]);

    fireEvent.change(serviceFilter, { target: { value: 'CHECK_IN' } });
    expect(container.querySelector('.visit-pet')).toHaveTextContent('Scheduler Pet 1');
    expect(container.querySelector('.visit-type')).toHaveTextContent('30-Minute Check-In');
    expect(container.querySelector('.visit-time')).toHaveTextContent('2030-01-05');
    fireEvent.click(container.querySelector('.scheduled-visit'));
    expect(props.onSelectPet).toHaveBeenCalledWith(items[1]);

    fireEvent.change(serviceFilter, { target: { value: 'WALK_20MIN' } });
    expect(container.querySelector('.visit-pet')).toHaveTextContent('Scheduler Pet 0');
    fireEvent.change(serviceFilter, { target: { value: 'OVERNIGHT' } });
    expect(container.querySelector('.visit-pet')).toHaveTextContent('Scheduler Pet 2');

    expect(items).toEqual(before);
  });

  it('keeps legacy, unknown, case-variant, and blank-like values visible only under ALL', () => {
    const cases = [
      'WALK_30MIN',
      'walk_30min',
      'Walk_30Min',
      'DOG_WALKING',
      'WALKING',
      'OTHER',
      'HOUSE_SITTING',
      '',
      null,
      undefined
    ];
    const items = cases.map((serviceType, index) => makeSchedulerItem(serviceType, index));
    const before = items.map(item => ({ ...item }));
    const { container } = renderScheduler(items);
    const serviceFilter = getSchedulerFilter('Service');

    expect(Array.from(container.querySelectorAll('.visit-pet'), node => node.textContent)).toEqual(
      cases.map((_, index) => `Scheduler Pet ${index}`)
    );
    fireEvent.change(serviceFilter, { target: { value: 'WALK_30MIN' } });
    expect(Array.from(container.querySelectorAll('.visit-pet'), node => node.textContent)).toEqual([
      'Scheduler Pet 0'
    ]);
    expect(items).toEqual(before);
  });

  it('renders canonical and approved labels in desktop service-only visit cards', () => {
    const cases = [...canonicalCases, ...legacyCases];
    const items = cases.map(([serviceType], index) => makeSchedulerItem(serviceType, index));
    const before = items.map(item => ({ ...item }));

    const { container } = renderScheduler(items);
    expect(Array.from(container.querySelectorAll('.visit-type'), node => node.textContent.trim())).toEqual(
      cases.map(([, expected]) => expected)
    );
    expect(items).toEqual(before);
  });

  it('renders canonical and approved labels in pending-intake cards', () => {
    const cases = [...canonicalCases, ...legacyCases];
    const items = cases.map(([serviceType], index) => makeSchedulerItem(serviceType, index, {
      PK: `REQ#pending-${index}`,
      status: 'PENDING_REVIEW'
    }));

    const { container } = renderScheduler(items);
    const queueLabels = Array.from(
      container.querySelectorAll('.queue-item .queue-info > span:not(.status-pill)'),
      node => node.textContent
    );
    expect(queueLabels).toEqual(cases.map(([, expected]) => expected));
  });

  it('keeps pending intake independent from service filtering and preserves queue callbacks', () => {
    const scheduledMatch = makeSchedulerItem('WALK_60MIN', 0);
    const scheduledNonmatch = makeSchedulerItem('PET_SITTING', 1);
    const pending = makeSchedulerItem('PET_SITTING', 2, {
      PK: 'REQ#pending-filter-independence',
      status: 'PENDING_REVIEW'
    });
    const items = [scheduledMatch, scheduledNonmatch, pending];
    const before = items.map(item => ({ ...item }));
    const { container, props } = renderScheduler(items);

    fireEvent.change(getSchedulerFilter('Service'), { target: { value: 'WALK_60MIN' } });
    expect(Array.from(container.querySelectorAll('.visit-pet'), node => node.textContent)).toEqual([
      scheduledMatch.pet_name
    ]);

    const pendingQueueItem = screen.getByText(pending.client_name).closest('.queue-item');
    expect(pendingQueueItem).toHaveTextContent('Pet Sitting');
    fireEvent.click(pendingQueueItem);
    expect(props.onSelectPet).toHaveBeenCalledWith(pending);

    fireEvent.click(pendingQueueItem.querySelector('button'));
    expect(props.onReview).toHaveBeenCalledWith(pending);
    expect(items).toEqual(before);
  });

  it('filters only by service_type even when window_type overlaps a canonical filter value', () => {
    const windowOnlyMatch = makeSchedulerItem('OTHER', 0, { window_type: 'WALK_60MIN' });
    const serviceMatch = makeSchedulerItem('WALK_60MIN', 1, { window_type: 'OTHER' });
    const items = [windowOnlyMatch, serviceMatch];
    const before = items.map(item => ({ ...item }));
    const { container, props } = renderScheduler(items);

    fireEvent.change(getSchedulerFilter('Service'), { target: { value: 'WALK_60MIN' } });
    expect(Array.from(container.querySelectorAll('.visit-pet'), node => node.textContent)).toEqual([
      serviceMatch.pet_name
    ]);
    expect(container.querySelector('.visit-type')).toHaveTextContent('OTHER');
    fireEvent.click(container.querySelector('.scheduled-visit'));
    expect(props.onSelectPet).toHaveBeenCalledWith(serviceMatch);
    expect(items).toEqual(before);
  });

  it('uses the same service-filtered timeline collection on desktop and mobile', () => {
    const items = [
      makeSchedulerItem('WALK_30MIN', 0),
      makeSchedulerItem('PET_SITTING', 1)
    ];
    const before = items.map(item => ({ ...item }));
    const desktop = renderScheduler(items);

    fireEvent.change(getSchedulerFilter('Service'), { target: { value: 'PET_SITTING' } });
    expect(Array.from(desktop.container.querySelectorAll('.visit-pet'), node => node.textContent)).toEqual([
      items[1].pet_name
    ]);
    expect(desktop.container.querySelector('.badge-light')).toHaveTextContent('1 Visits');
    desktop.unmount();

    setViewportWidth(375);
    const mobile = renderScheduler(items);
    fireEvent.change(getSchedulerFilter('Service'), { target: { value: 'PET_SITTING' } });
    expect(Array.from(
      mobile.container.querySelectorAll('.scheduler-mobile-visit-pet'),
      node => node.textContent
    )).toEqual([items[1].pet_name]);
    expect(mobile.container.querySelector('.scheduler-mobile-list-header .badge-light')).toHaveTextContent('1');
    fireEvent.click(mobile.container.querySelector('.scheduler-mobile-visit-card'));
    expect(mobile.props.onSelectPet).toHaveBeenCalledWith(items[1]);
    expect(items).toEqual(before);
  });

  it('preserves date, staff, status, search, clear-filter, and visit-count behavior', () => {
    const items = [
      makeSchedulerItem('PET_SITTING', 0, { client_name: 'Target Client', worker_id: 'Ryan' }),
      makeSchedulerItem('PET_SITTING', 1, { start_date: '2030-01-06', worker_id: 'Ryan' }),
      makeSchedulerItem('WALK_30MIN', 2, { worker_id: 'Ryan' }),
      makeSchedulerItem('PET_SITTING', 3, { worker_id: 'Wife' }),
      makeSchedulerItem('PET_SITTING', 4, { status: 'IN_PROGRESS', worker_id: 'Ryan' }),
      makeSchedulerItem('PET_SITTING', 5, { status: 'COMPLETED', worker_id: 'Ryan' })
    ];
    const before = items.map(item => ({ ...item }));
    const { container } = renderScheduler(items, {
      staffList: [{ display_name: 'Ryan' }, { display_name: 'Wife' }]
    });
    const visiblePets = () => Array.from(container.querySelectorAll('.visit-pet'), node => node.textContent);

    expect(visiblePets()).toEqual(['Scheduler Pet 0', 'Scheduler Pet 2', 'Scheduler Pet 3', 'Scheduler Pet 4']);
    fireEvent.change(getSchedulerFilter('Service'), { target: { value: 'PET_SITTING' } });
    expect(visiblePets()).toEqual(['Scheduler Pet 0', 'Scheduler Pet 3', 'Scheduler Pet 4']);
    fireEvent.change(getSchedulerFilter('Staff'), { target: { value: 'Ryan' } });
    expect(visiblePets()).toEqual(['Scheduler Pet 0', 'Scheduler Pet 4']);
    fireEvent.change(getSchedulerFilter('Status'), { target: { value: 'ASSIGNED' } });
    expect(visiblePets()).toEqual(['Scheduler Pet 0']);
    fireEvent.change(screen.getByPlaceholderText('Customer or pet...'), { target: { value: 'target' } });
    expect(visiblePets()).toEqual(['Scheduler Pet 0']);
    expect(container.querySelector('.badge-light')).toHaveTextContent('1 Visits');
    fireEvent.change(screen.getByPlaceholderText('Customer or pet...'), { target: { value: 'no match' } });
    expect(visiblePets()).toEqual([]);

    fireEvent.click(screen.getByRole('button', { name: 'Clear Filters' }));
    expect(getSchedulerFilter('Service').value).toBe('ALL');
    expect(visiblePets()).toEqual(['Scheduler Pet 0', 'Scheduler Pet 2', 'Scheduler Pet 3', 'Scheduler Pet 4']);
    expect(items).toEqual(before);
  });

  it('keeps truthy window types raw and falls through only for falsey window types', () => {
    const items = [
      makeSchedulerItem('WALK_30MIN', 0, { window_type: 'EXACT_TIME' }),
      makeSchedulerItem('OTHER', 1, { window_type: 'WALK_30MIN' }),
      makeSchedulerItem('OTHER', 2, { window_type: 'DROPIN_1HR' }),
      makeSchedulerItem('OTHER', 3, { window_type: 'DROPIN_3HR' }),
      makeSchedulerItem('OTHER', 4, { window_type: 'OVERNIGHT' }),
      makeSchedulerItem('DOG_WALKING', 5, { window_type: '' }),
      makeSchedulerItem('WALKING', 6, { window_type: null }),
      makeSchedulerItem('PET_SITTING', 7, { window_type: undefined })
    ];

    const { container } = renderScheduler(items);
    expect(Array.from(container.querySelectorAll('.visit-type'), node => node.textContent.trim())).toEqual([
      'EXACT_TIME',
      'WALK_30MIN',
      'DROPIN_1HR',
      'DROPIN_3HR',
      'OVERNIGHT',
      'Daily Dog Walking',
      'Dog Walking',
      'Pet Sitting'
    ]);
  });

  it('preserves raw unknown, case-variant, nullish, empty, and whitespace service fallbacks', () => {
    const cases = [
      ['HOUSE_SITTING', 'HOUSE_SITTING'],
      ['walk_30min', 'walk_30min'],
      ['Walk_30Min', 'Walk_30Min'],
      [null, ''],
      [undefined, ''],
      ['', ''],
      ['   ', '   ']
    ];
    const items = cases.map(([serviceType], index) => makeSchedulerItem(serviceType, index));

    const { container } = renderScheduler(items);
    expect(Array.from(container.querySelectorAll('.visit-type'), node => node.textContent)).toEqual(
      cases.map(([, expected]) => expected)
    );
  });

  it('leaves mobile visit-card service output absent and preserves raw mobile time fallback', () => {
    setViewportWidth(375);
    const item = makeSchedulerItem('DOG_WALKING', 0, { window_type: 'EXACT_TIME' });
    const before = { ...item };

    const { container, props } = renderScheduler([item]);
    expect(container.querySelector('.visit-type')).toBeNull();
    expect(container.querySelector('.scheduler-mobile-visit-time')).toHaveTextContent('EXACT_TIME');
    expect(screen.queryByText('Daily Dog Walking')).not.toBeInTheDocument();

    fireEvent.click(container.querySelector('.scheduler-mobile-visit-card'));
    expect(props.onSelectPet).toHaveBeenCalledWith(item);
    expect(item).toEqual(before);
  });

  it('keeps service filtering exact and case-sensitive and passes the original selected object', () => {
    const items = [
      makeSchedulerItem('WALK_30MIN', 0),
      makeSchedulerItem('walk_30min', 1),
      makeSchedulerItem('DOG_WALKING', 2)
    ];
    const before = items.map(item => ({ ...item }));

    const { container, props } = renderScheduler(items);
    const serviceFilter = screen.getByText('Service', { selector: 'label' }).closest('.filter-group').querySelector('select');
    fireEvent.change(serviceFilter, { target: { value: 'WALK_30MIN' } });

    expect(Array.from(container.querySelectorAll('.visit-pet'), node => node.textContent)).toEqual([
      'Scheduler Pet 0'
    ]);
    fireEvent.click(container.querySelector('.scheduled-visit'));
    expect(props.onSelectPet).toHaveBeenCalledWith(items[0]);
    expect(items).toEqual(before);
    expect(items.map(item => item.service_type)).toEqual(['WALK_30MIN', 'walk_30min', 'DOG_WALKING']);
  });
});
