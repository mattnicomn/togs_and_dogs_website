import { describe, expect, it } from 'vitest';
import { SERVICE_TYPES } from '../src/generated/contracts.js';
import * as serviceLabels from '../src/utils/serviceLabels.js';

const { getKnownServiceTypeLabel } = serviceLabels;

const canonicalCases = Object.entries(SERVICE_TYPES.services).map(([identifier, service]) => [
  identifier,
  service.labelLong
]);

const legacyCases = [
  ['DOG_WALKING', 'Daily Dog Walking'],
  ['WALKING', 'Dog Walking'],
  ['OTHER', 'Other']
];

describe('getKnownServiceTypeLabel', () => {
  it.each(canonicalCases)('returns generated labelLong for exact canonical key %s', (input, expected) => {
    expect(getKnownServiceTypeLabel(input)).toBe(expected);
  });

  it.each(legacyCases)('returns the approved display alias for exact legacy key %s', (input, expected) => {
    expect(getKnownServiceTypeLabel(input)).toBe(expected);
  });

  it.each([
    'HOUSE_SITTING',
    'walk_30min',
    'Walk_30Min',
    'dog_walking',
    'Dog_Walking',
    null,
    undefined,
    '',
    '   ',
    'toString',
    'constructor',
    '__proto__',
    'label',
    'labelLong',
    'durationMinutes',
    'availableInIntake',
    'supportedOnMobile'
  ])('returns undefined for unresolved value %p', (input) => {
    expect(getKnownServiceTypeLabel(input)).toBeUndefined();
  });

  it('does not mutate the generated contract or supplied containing values', () => {
    const contractBefore = JSON.stringify(SERVICE_TYPES);
    const supplied = Object.freeze({ service_type: 'DOG_WALKING' });

    expect(getKnownServiceTypeLabel(supplied.service_type)).toBe('Daily Dog Walking');
    expect(supplied).toEqual({ service_type: 'DOG_WALKING' });
    expect(JSON.stringify(SERVICE_TYPES)).toBe(contractBefore);
  });

  it('keeps the frozen internal alias behavior stable without exporting the alias table', () => {
    expect(Object.keys(serviceLabels)).toEqual(['getKnownServiceTypeLabel']);
    expect(legacyCases.map(([input]) => getKnownServiceTypeLabel(input))).toEqual(
      legacyCases.map(([, expected]) => expected)
    );
  });
});
