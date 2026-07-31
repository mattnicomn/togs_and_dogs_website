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

import { CONFIG } from '../src/api/config';
import {
  getAdminRequests,
  getClientRequests,
  getStaff,
  getClients,
  getStaffOptions,
  submitRequest,
  reviewRequest,
  assignWorker,
  completeJob,
  getClientPets,
} from '../src/api/client';

jest.mock('../src/auth/storage', () => ({
  getIdToken: jest.fn().mockResolvedValue('mock-mobile-token'),
  isTokenExpired: jest.fn().mockReturnValue(false),
}));

describe('Phase 24A-2A Mobile API Client Behavioral Execution', () => {
  let fetchSpy: jest.SpyInstance;

  beforeEach(() => {
    fetchSpy = jest.spyOn(global, 'fetch').mockImplementation(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ success: true }),
      } as Response)
    );
  });

  afterEach(() => {
    jest.clearAllMocks();
    fetchSpy.mockRestore();
  });

  it('getAdminRequests sends GET to /admin/requests with query parameters and Authorization token', async () => {
    await getAdminRequests('PENDING_REVIEW');
    expect(fetchSpy).toHaveBeenCalledWith(
      `${CONFIG.API_URL}/admin/requests?status=PENDING_REVIEW`,
      expect.objectContaining({
        method: 'GET',
        headers: expect.objectContaining({ Authorization: 'mock-mobile-token' }),
      })
    );
  });

  it('getClientRequests sends GET to /client/requests with Authorization token', async () => {
    await getClientRequests();
    expect(fetchSpy).toHaveBeenCalledWith(
      `${CONFIG.API_URL}/client/requests`,
      expect.objectContaining({
        method: 'GET',
        headers: expect.objectContaining({ Authorization: 'mock-mobile-token' }),
      })
    );
  });

  it('getStaff and getClients send GET to canonical admin endpoints', async () => {
    await getStaff();
    expect(fetchSpy).toHaveBeenCalledWith(
      `${CONFIG.API_URL}/admin/staff`,
      expect.objectContaining({ method: 'GET' })
    );

    await getClients();
    expect(fetchSpy).toHaveBeenCalledWith(
      `${CONFIG.API_URL}/admin/clients`,
      expect.objectContaining({ method: 'GET' })
    );
  });

  it('getStaffOptions and submitRequest send POST to /requests', async () => {
    await getStaffOptions();
    expect(fetchSpy).toHaveBeenCalledWith(
      `${CONFIG.API_URL}/requests`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ action: 'staff-options' }),
      })
    );

    await submitRequest({ service: 'WALK_30MIN' });
    expect(fetchSpy).toHaveBeenCalledWith(
      `${CONFIG.API_URL}/requests`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ service: 'WALK_30MIN' }),
      })
    );
  });

  it('reviewRequest, assignWorker, and completeJob send POST to canonical admin endpoints', async () => {
    await reviewRequest('req-1', 'client-1', 'APPROVED', 'looks good');
    expect(fetchSpy).toHaveBeenCalledWith(
      `${CONFIG.API_URL}/admin/review`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          request_id: 'req-1',
          client_id: 'client-1',
          status: 'APPROVED',
          reason: 'looks good',
        }),
      })
    );

    await assignWorker('job-1', 'req-1', 'client-1', 'w-1', 'Alice');
    expect(fetchSpy).toHaveBeenCalledWith(
      `${CONFIG.API_URL}/admin/assign`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          job_id: 'job-1',
          req_id: 'req-1',
          client_id: 'client-1',
          worker_id: 'w-1',
          worker_name: 'Alice',
        }),
      })
    );

    await completeJob('job-1', 'req-1', 'done');
    expect(fetchSpy).toHaveBeenCalledWith(
      `${CONFIG.API_URL}/admin/job/complete`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          job_id: 'job-1',
          request_id: 'req-1',
          visit_notes: 'done',
        }),
      })
    );
  });

  it('getClientPets sends GET to /client/pets with Authorization token', async () => {
    await getClientPets();
    expect(fetchSpy).toHaveBeenCalledWith(
      `${CONFIG.API_URL}/client/pets`,
      expect.objectContaining({
        method: 'GET',
        headers: expect.objectContaining({ Authorization: 'mock-mobile-token' }),
      })
    );
  });
});

