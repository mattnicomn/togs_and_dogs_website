import { SERVICE_TYPES } from '../generated/contracts.js';

const LEGACY_SERVICE_LABELS = Object.freeze({
  DOG_WALKING: 'Daily Dog Walking',
  WALKING: 'Dog Walking',
  OTHER: 'Other'
});

const hasOwn = (object, key) => Object.prototype.hasOwnProperty.call(object, key);

export function getKnownServiceTypeLabel(value) {
  if (typeof value !== 'string' || !value || /^\s+$/.test(value)) return undefined;

  if (hasOwn(SERVICE_TYPES.services, value)) {
    return SERVICE_TYPES.services[value].labelLong;
  }

  if (hasOwn(LEGACY_SERVICE_LABELS, value)) {
    return LEGACY_SERVICE_LABELS[value];
  }

  return undefined;
}
