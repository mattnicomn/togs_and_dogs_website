import React from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import CareCard from '../src/components/CareCard';
import { SERVICE_TYPES } from '../src/generated/contracts.js';

const canonicalCases = Object.entries(SERVICE_TYPES.services).map(([identifier, service]) => [
  identifier,
  service.labelLong
]);

const legacyCases = [
  ['DOG_WALKING', 'Daily Dog Walking'],
  ['WALKING', 'Dog Walking'],
  ['OTHER', 'Other']
];

const makePet = (overrides = {}) => ({
  pet_id: 'pet-buddy',
  client_id: 'client-123',
  name: 'Buddy',
  species: 'DOG',
  breed: 'Golden Retriever',
  age: '3',
  care_instructions: 'Keep the water bowl full.',
  feeding_notes: 'Breakfast at 7.',
  medication_notes: 'None.',
  behavior_notes: 'Friendly.',
  health: { vet_name: 'Dr. Rivera', vet_phone: '555-0100' },
  document_links: { vaccination: 'https://example.test/vaccination' },
  scheduled_duration: 45,
  service_type: 'PET_SITTING',
  status: 'APPROVED',
  _originItem: {
    request_id: 'request-123',
    client_id: 'client-123',
    service_type: 'WALK_30MIN',
    status: 'APPROVED'
  },
  ...overrides
});

const makeProps = (pet, overrides = {}) => ({
  pet,
  onClose: vi.fn(),
  onUpdate: vi.fn().mockResolvedValue(undefined),
  onStatusUpdate: vi.fn().mockResolvedValue(undefined),
  userRole: 'owner',
  ...overrides
});

const openVisitDetails = () => {
  fireEvent.click(screen.getByText('Visit Details'));
};

const getServiceField = () => screen.getByText('Service Type').closest('.field');

const expectServiceValue = (expected) => {
  const field = getServiceField();
  expect(field).not.toBeNull();
  expect(field.querySelector('p')).toHaveTextContent(expected);
};

describe('CareCard service-type compatibility', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it.each(canonicalCases)('renders generated labelLong for exact canonical request value %s', (serviceType, expected) => {
    render(<CareCard {...makeProps(makePet({
      _originItem: { request_id: 'request-123', client_id: 'client-123', service_type: serviceType, status: 'APPROVED' }
    }))} />);

    openVisitDetails();
    expectServiceValue(expected);
  });

  it.each(legacyCases)('renders the approved display alias for exact legacy request value %s', (serviceType, expected) => {
    render(<CareCard {...makeProps(makePet({
      _originItem: { request_id: 'request-123', client_id: 'client-123', service_type: serviceType, status: 'APPROVED' }
    }))} />);

    openVisitDetails();
    expectServiceValue(expected);
  });

  it('uses the request value before the historical PET value', () => {
    render(<CareCard {...makeProps(makePet({
      service_type: 'OTHER',
      _originItem: { request_id: 'request-123', client_id: 'client-123', service_type: 'OVERNIGHT', status: 'APPROVED' }
    }))} />);

    openVisitDetails();
    expectServiceValue(SERVICE_TYPES.services.OVERNIGHT.labelLong);
  });

  it('falls back to the historical PET value when the request value is absent', () => {
    render(<CareCard {...makeProps(makePet({
      service_type: 'WALKING',
      _originItem: { request_id: 'request-123', client_id: 'client-123', status: 'APPROVED' }
    }))} />);

    openVisitDetails();
    expectServiceValue('Dog Walking');
  });

  it.each([
    ['HOUSE_SITTING', 'HOUSE_SITTING'],
    ['walk_30min', 'walk_30min'],
    ['Walk_30Min', 'Walk_30Min']
  ])('preserves unresolved nonblank value %s exactly', (serviceType, expected) => {
    render(<CareCard {...makeProps(makePet({
      _originItem: { request_id: 'request-123', client_id: 'client-123', service_type: serviceType, status: 'APPROVED' }
    }))} />);

    openVisitDetails();
    expectServiceValue(expected);
  });

  it.each([undefined, null, '', '   '])('renders Not Specified for missing or blank value %p', (serviceType) => {
    render(<CareCard {...makeProps(makePet({
      service_type: serviceType,
      _originItem: { request_id: 'request-123', client_id: 'client-123', status: 'APPROVED' }
    }))} />);

    openVisitDetails();
    expectServiceValue('Not Specified');
  });

  it('keeps Service Type read-only in edit mode and removes only the top-level field from the exact save payload', async () => {
    const pet = makePet();
    const originalPet = structuredClone(pet);
    const props = makeProps(pet);

    render(<CareCard {...props} />);
    fireEvent.click(screen.getByRole('button', { name: 'Edit Record' }));
    openVisitDetails();

    expect(within(getServiceField()).queryByRole('combobox')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Save Changes' }));

    await waitFor(() => expect(props.onUpdate).toHaveBeenCalledOnce());
    const { service_type: omittedServiceType, ...expectedPetFields } = originalPet;
    expect(omittedServiceType).toBe('PET_SITTING');
    expect(props.onUpdate).toHaveBeenCalledWith(expectedPetFields);
    expect(props.onUpdate.mock.calls[0][0]).not.toHaveProperty('service_type');
    expect(props.onStatusUpdate).not.toHaveBeenCalled();
    expect(pet).toEqual(originalPet);
  });

  it('preserves active-pet selection and identifiers while omitting service_type on save', async () => {
    const buddy = makePet();
    const max = {
      ...makePet({ pet_id: 'pet-max', name: 'Max', service_type: 'DOG_WALKING' }),
      _originItem: undefined
    };
    const pet = { ...buddy, _allPets: [buddy, max] };
    const props = makeProps(pet);

    render(<CareCard {...props} />);
    fireEvent.click(screen.getByRole('button', { name: 'Max' }));
    await waitFor(() => expect(screen.getAllByRole('heading', { name: 'Max' })).toHaveLength(2));
    fireEvent.click(screen.getByRole('button', { name: 'Edit Record' }));
    fireEvent.click(screen.getByRole('button', { name: 'Save Changes' }));

    await waitFor(() => expect(props.onUpdate).toHaveBeenCalledOnce());
    expect(props.onUpdate.mock.calls[0][0]).toMatchObject({ pet_id: 'pet-max', client_id: 'client-123', name: 'Max' });
    expect(props.onUpdate.mock.calls[0][0]).not.toHaveProperty('service_type');
  });

  it('preserves the fallback create-profile save shape except for service_type', async () => {
    const pet = makePet({ pet_id: undefined, service_type: 'OTHER' });
    const props = makeProps(pet);

    render(<CareCard {...props} />);
    fireEvent.click(screen.getByRole('button', { name: 'Create Profile' }));
    fireEvent.click(screen.getByRole('button', { name: 'Save Changes' }));

    await waitFor(() => expect(props.onUpdate).toHaveBeenCalledOnce());
    const { service_type: omittedServiceType, ...expectedPetFields } = pet;
    expect(omittedServiceType).toBe('OTHER');
    expect(props.onUpdate).toHaveBeenCalledWith(expectedPetFields);
    expect(props.onUpdate.mock.calls[0][0]).not.toHaveProperty('service_type');
  });
});
