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
    expect(PET_FIELDS.clientWriteHealthFieldLimits).toEqual({
      vet_name: 100,
      vet_phone: 100,
    });
    expect(REQUEST_STATUSES.statuses.APPROVED).toBeDefined();
    expect(SERVICE_TYPES.services.WALK_60MIN).toBeDefined();
  });
});

import { vi, beforeEach, afterEach } from 'vitest';
import CONFIG from '../src/api/config';
import {
  submitRequest,
  getClientRequests,
  getClientPets,
  updateClientPet,
  getAdminRequests,
  listAdminClientPets,
  requestCancellation,
  processCancellationDecision,
  getExportData,
  getTenantInfo,
} from '../src/api/client';

vi.mock('../src/api/auth', () => ({
  getIdToken: vi.fn().mockResolvedValue('mock-web-token'),
}));

describe('Phase 24A-2A Web API Client Behavioral Execution', () => {
  let fetchMock;

  beforeEach(() => {
    fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ success: true }),
    });
    vi.stubGlobal('fetch', fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it('submitRequest sends POST to /requests without authorization header', async () => {
    await submitRequest({ name: 'Fido' });
    expect(fetchMock).toHaveBeenCalledWith(
      `${CONFIG.API_URL}/requests`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ name: 'Fido' }),
      })
    );
    expect(fetchMock.mock.calls[0][1].headers.Authorization).toBeUndefined();
  });

  it('getClientRequests sends GET to /client/requests with Authorization token', async () => {
    await getClientRequests();
    expect(fetchMock).toHaveBeenCalledWith(
      `${CONFIG.API_URL}/client/requests`,
      expect.objectContaining({
        method: 'GET',
        headers: expect.objectContaining({ Authorization: 'mock-web-token' }),
      })
    );
  });

  it('getClientPets sends GET to /client/pets with Authorization token', async () => {
    await getClientPets();
    expect(fetchMock).toHaveBeenCalledWith(
      `${CONFIG.API_URL}/client/pets`,
      expect.objectContaining({
        method: 'GET',
        headers: expect.objectContaining({ Authorization: 'mock-web-token' }),
      })
    );
  });

  it('updateClientPet sends PUT to /client/pets/{petId} with encoded petId', async () => {
    await updateClientPet('pet 123', { name: 'Rex' });
    expect(fetchMock).toHaveBeenCalledWith(
      `${CONFIG.API_URL}/client/pets/pet%20123`,
      expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify({ name: 'Rex' }),
        headers: expect.objectContaining({ Authorization: 'mock-web-token' }),
      })
    );
  });

  it('getAdminRequests sends GET to /admin/requests with query parameters', async () => {
    await getAdminRequests('PENDING_REVIEW', 'key1', 'today');
    expect(fetchMock).toHaveBeenCalledWith(
      `${CONFIG.API_URL}/admin/requests?status=PENDING_REVIEW&startKey=key1&timeframe=today`,
      expect.objectContaining({
        method: 'GET',
        headers: expect.objectContaining({ Authorization: 'mock-web-token' }),
      })
    );
  });

  it('listAdminClientPets sends GET to /admin/pets with encoded clientId and includeInactive query', async () => {
    await listAdminClientPets('client#1', true);
    expect(fetchMock).toHaveBeenCalledWith(
      `${CONFIG.API_URL}/admin/pets?clientId=client%231&includeInactive=true`,
      expect.objectContaining({
        method: 'GET',
        headers: expect.objectContaining({ Authorization: 'mock-web-token' }),
      })
    );
  });

  it('requestCancellation sends POST to /client/cancel with payload', async () => {
    await requestCancellation('req-1', 'client-1', 'moving');
    expect(fetchMock).toHaveBeenCalledWith(
      `${CONFIG.API_URL}/client/cancel`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ request_id: 'req-1', client_id: 'client-1', reason: 'moving' }),
      })
    );
  });

  it('processCancellationDecision sends PUT to /admin/cancel/decision with payload', async () => {
    await processCancellationDecision('req-1', 'client-1', 'APPROVE', 'ok');
    expect(fetchMock).toHaveBeenCalledWith(
      `${CONFIG.API_URL}/admin/cancel/decision`,
      expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify({ request_id: 'req-1', client_id: 'client-1', decision: 'APPROVE', note: 'ok' }),
      })
    );
  });

  it('getExportData and getTenantInfo send GET to canonical admin endpoints', async () => {
    await getExportData();
    expect(fetchMock).toHaveBeenCalledWith(
      `${CONFIG.API_URL}/admin/export-data`,
      expect.objectContaining({ method: 'GET' })
    );

    await getTenantInfo();
    expect(fetchMock).toHaveBeenCalledWith(
      `${CONFIG.API_URL}/admin/tenant-info`,
      expect.objectContaining({ method: 'GET' })
    );
  });
});
