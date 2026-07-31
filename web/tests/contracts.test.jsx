/**
 * Phase 24A-2A: Web Generated Contract Adapters & Path Safety Tests
 */
import { describe, it, expect } from 'vitest';
import {
  API_PATHS,
  PET_FIELDS,
  REQUEST_STATUSES,
  SERVICE_TYPES,
  buildPath,
} from '../src/generated/contracts';

describe('Phase 24A-2A Web Contract Adapters', () => {
  it('exposes canonical API path constants', () => {
    expect(API_PATHS.client.getRequests).toBe('/client/requests');
    expect(API_PATHS.client.getPets).toBe('/client/pets');
    expect(API_PATHS.client.updatePet).toBe('/client/pets/{petId}');
    expect(API_PATHS.client.requestCancellation).toBe('/client/cancel');

    expect(API_PATHS.admin.getRequests).toBe('/admin/requests');
    expect(API_PATHS.admin.review).toBe('/admin/review');
    expect(API_PATHS.admin.assign).toBe('/admin/assign');
    expect(API_PATHS.admin.getPets).toBe('/admin/pets');

    expect(API_PATHS.public.submitRequest).toBe('/requests');
  });

  it('substitutes and URL-encodes parameters safely in buildPath', () => {
    const route = buildPath(API_PATHS.admin.getPetById, { petId: 'pet 456' });
    expect(route).toBe('/admin/pets/pet%20456');
  });

  it('throws error when buildPath parameter is missing', () => {
    expect(() => buildPath(API_PATHS.admin.getPetById, {})).toThrow(
      'Missing required path parameter: petId'
    );
  });

  it('exports PET_FIELDS, REQUEST_STATUSES, and SERVICE_TYPES for future subphases', () => {
    expect(PET_FIELDS.clientReadFields).toContain('name');
    expect(REQUEST_STATUSES.statuses.APPROVED).toBeDefined();
    expect(SERVICE_TYPES.services.WALK_60MIN).toBeDefined();
  });
});
