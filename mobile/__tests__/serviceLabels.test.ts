import { SERVICE_TYPES } from '../src/contracts/generatedContracts';
import { getServiceTypeLabel } from '../src/utils/serviceLabels';

const canonicalCases = [
  ['WALK_30MIN', '30-Min Walk'],
  ['WALK_60MIN', '60-Min Walk'],
  ['DROPIN_1HR', '1-Hour Drop-in'],
  ['DROPIN_3HR', '3-Hour Drop-in'],
  ['OVERNIGHT', 'Overnight Care'],
  ['PET_SITTING', 'Pet Sitting'],
  ['MEET_GREET', 'Meet & Greet'],
] as const;

const fallbackCases = [
  ['DOG_WALKING', 'DOG WALKING'],
  ['WALKING', 'WALKING'],
  ['OTHER', 'OTHER'],
  ['HOUSE_SITTING', 'HOUSE SITTING'],
  ['UNKNOWN_SERVICE_TYPE', 'UNKNOWN SERVICE TYPE'],
  ['walk_30min', 'Walk 30min'],
  ['Walk_30Min', 'Walk 30Min'],
] as const;

describe('getServiceTypeLabel', () => {
  it.each(canonicalCases)('returns the contract label for exact canonical key %s', (input, expected) => {
    expect(getServiceTypeLabel(input)).toBe(expected);
  });

  it.each(fallbackCases)('preserves exact legacy fallback output for %s', (input, expected) => {
    expect(getServiceTypeLabel(input)).toBe(expected);
  });

  it.each([
    [null, ''],
    [undefined, ''],
    ['', ''],
  ] as const)('returns an empty string for blank-like input %p', (input, expected) => {
    expect(getServiceTypeLabel(input)).toBe(expected);
  });

  it('treats a prototype-like key as an unknown legacy value', () => {
    expect(getServiceTypeLabel('toString')).toBe('ToString');
  });

  it.each([
    ['labelLong', 'LabelLong'],
    ['availableInIntake', 'AvailableInIntake'],
    ['supportedOnMobile', 'SupportedOnMobile'],
    ['durationMinutes', 'DurationMinutes'],
  ] as const)('does not consume metadata-like input %s', (input, expected) => {
    expect(getServiceTypeLabel(input)).toBe(expected);
  });

  it('does not mutate the generated SERVICE_TYPES contract', () => {
    const before = JSON.stringify(SERVICE_TYPES);

    canonicalCases.forEach(([input]) => getServiceTypeLabel(input));
    fallbackCases.forEach(([input]) => getServiceTypeLabel(input));

    expect(JSON.stringify(SERVICE_TYPES)).toBe(before);
  });
});
