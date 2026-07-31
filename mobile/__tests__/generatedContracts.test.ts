/**
 * Phase 24A-2A: Generated Contract Adapters & Path Safety Tests
 */

import {
  API_PATHS,
  PET_FIELDS,
  REQUEST_STATUSES,
  SERVICE_TYPES,
  buildPath,
} from '../src/contracts/generatedContracts';

describe('Phase 24A-2A Contract Adapters', () => {
  it('exposes canonical API path constants', () => {
    expect(API_PATHS.client.getRequests).toBe('/client/requests');
    expect(API_PATHS.client.getPets).toBe('/client/pets');
    expect(API_PATHS.client.updatePet).toBe('/client/pets/{petId}');
    expect(API_PATHS.client.requestCancellation).toBe('/client/cancel');

    expect(API_PATHS.admin.getRequests).toBe('/admin/requests');
    expect(API_PATHS.admin.review).toBe('/admin/review');
    expect(API_PATHS.admin.assign).toBe('/admin/assign');
    expect(API_PATHS.admin.jobComplete).toBe('/admin/job/complete');
    expect(API_PATHS.admin.getPets).toBe('/admin/pets');
    expect(API_PATHS.admin.getPetById).toBe('/admin/pets/{petId}');
    expect(API_PATHS.admin.getStaff).toBe('/admin/staff');
    expect(API_PATHS.admin.getClients).toBe('/admin/clients');

    expect(API_PATHS.public.submitRequest).toBe('/requests');
    expect(API_PATHS.public.staffOptions).toBe('/requests');
  });

  it('substitutes and URL-encodes parameters safely in buildPath', () => {
    const singleParam = buildPath(API_PATHS.client.updatePet, { petId: 'pet-123' });
    expect(singleParam).toBe('/client/pets/pet-123');

    const encodedParam = buildPath(API_PATHS.client.updatePet, { petId: 'pet 123&special' });
    expect(encodedParam).toBe('/client/pets/pet%20123%26special');
  });

  it('throws an error if a required parameter is missing in buildPath', () => {
    expect(() => buildPath('/client/pets/{petId}', {})).toThrow(
      'Missing required path parameter: petId'
    );
  });

  it('exports PET_FIELDS, REQUEST_STATUSES, and SERVICE_TYPES for future use', () => {
    expect(Array.isArray(PET_FIELDS.clientReadFields)).toBe(true);
    expect(PET_FIELDS.clientReadFields).toContain('name');
    expect(REQUEST_STATUSES.statuses.PENDING_REVIEW).toBeDefined();
    expect(SERVICE_TYPES.services.WALK_30MIN).toBeDefined();
  });
});
