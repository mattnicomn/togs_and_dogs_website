/**
 * S2: cancellation decision API helper. Verifies the existing backend contract is used
 * exactly: PUT /admin/cancel/decision, body { request_id, client_id, decision, note },
 * auth header, exact literals, and HTTP status preservation via ApiError.
 */
import { CONFIG } from '../src/api/config';

jest.mock('../src/auth/storage', () => ({
  getIdToken: jest.fn().mockResolvedValue('mock-mobile-token'),
  isTokenExpired: jest.fn().mockReturnValue(false),
}));

import { ApiError, processCancellationDecision } from '../src/api/client';

const okJson = (payload: any = { message: 'ok' }) =>
  Promise.resolve({ ok: true, json: () => Promise.resolve(payload) } as Response);
const errJson = (status: number, payload: any = {}) =>
  Promise.resolve({ ok: false, status, json: () => Promise.resolve(payload) } as Response);

describe('S2 cancellation decision API', () => {
  let fetchSpy: jest.SpyInstance;
  beforeEach(() => {
    fetchSpy = jest.spyOn(global, 'fetch').mockImplementation(() => okJson());
  });
  afterEach(() => {
    jest.clearAllMocks();
    fetchSpy.mockRestore();
  });

  it.each(['APPROVE', 'DENY'] as const)('PUTs exactly { request_id, client_id, decision: %s, note } with auth', async decision => {
    await processCancellationDecision('req-1', 'client-1', decision, 'note text');
    const [url, options] = fetchSpy.mock.calls[0];
    expect(url).toBe(`${CONFIG.API_URL}/admin/cancel/decision`);
    expect(options.method).toBe('PUT');
    expect(options.headers.Authorization).toBe('mock-mobile-token');
    expect(JSON.parse(options.body)).toEqual({ request_id: 'req-1', client_id: 'client-1', decision, note: 'note text' });
  });

  it('sends an empty note by default (matching the web client)', async () => {
    await processCancellationDecision('req-1', 'client-1', 'DENY');
    expect(JSON.parse(fetchSpy.mock.calls[0][1].body)).toEqual({ request_id: 'req-1', client_id: 'client-1', decision: 'DENY', note: '' });
  });

  it('returns the server response body', async () => {
    fetchSpy.mockImplementation(() => okJson({ message: 'Cancellation request approved.', new_status: 'CANCELLED', sns_message_id: null }));
    await expect(processCancellationDecision('req-1', 'client-1', 'APPROVE')).resolves.toEqual({
      message: 'Cancellation request approved.', new_status: 'CANCELLED', sns_message_id: null,
    });
  });

  it.each([400, 403, 404, 409, 500])('preserves HTTP %p on ApiError and makes exactly one call', async status => {
    fetchSpy.mockImplementation(() => errJson(status, { error: `status ${status}` }));
    const err: any = await processCancellationDecision('req-1', 'client-1', 'APPROVE').catch(e => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(status);
    expect(fetchSpy).toHaveBeenCalledTimes(1);
  });

  it('maps 401 to the session-expired error', async () => {
    fetchSpy.mockImplementation(() => errJson(401, { error: 'Unauthorized' }));
    const err: any = await processCancellationDecision('req-1', 'client-1', 'DENY').catch(e => e);
    expect(err.status).toBe(401);
    expect(err.message).toBe('Your session expired. Please sign in again.');
  });
});
