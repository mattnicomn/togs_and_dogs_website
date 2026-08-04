import { SERVICE_TYPES } from '../contracts/generatedContracts';

type ServiceTypeKey = keyof typeof SERVICE_TYPES.services;

function isCanonicalServiceType(value: string): value is ServiceTypeKey {
  return Object.prototype.hasOwnProperty.call(SERVICE_TYPES.services, value);
}

function formatLegacyServiceType(value: string): string {
  return value
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

export function getServiceTypeLabel(value: string | null | undefined): string {
  if (!value) return '';

  if (isCanonicalServiceType(value)) {
    return SERVICE_TYPES.services[value].label;
  }

  return formatLegacyServiceType(value);
}
