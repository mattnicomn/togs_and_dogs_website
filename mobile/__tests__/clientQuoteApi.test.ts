/**
 * OPS-3A.3A: Client quote API/service foundation tests.
 *
 * Covers path building, request method/body shape, auth behavior, decline-reason
 * normalization at the API boundary, and HTTP-status preservation (incl. 409)
 * via the ApiError abstraction. No screen/UI behavior is tested here.
 */

import { CONFIG } from '../src/api/config';

jest.mock('../src/auth/storage', () => ({
  getIdToken: jest.fn().mockResolvedValue('mock-mobile-token'),
  isTokenExpired: jest.fn().mockReturnValue(false),
}));

import {
  ApiError,
  getClientQuote,
  acceptClientQuote,
  declineClientQuote,
} from '../src/api/client';

const okJson = (payload: any = { success: true }) =>
  Promise.resolve({ ok: true, json: () => Promise.resolve(payload) } as Response);

const errJson = (status: number, payload: any = {}) =>
  Promise.resolve({
    ok: false,
    status,
    json: () => Promise.resolve(payload),
  } as Response);

describe('OPS-3A.3A Client Quote API', () => {
  let fetchSpy: jest.SpyInstance;

  beforeEach(() => {
    fetchSpy = jest.spyOn(global, 'fetch').mockImplementation(() => okJson());
  });

  afterEach(() => {
    jest.clearAllMocks();
    fetchSpy.mockRestore();
  });

  it('getClientQuote GETs the generated path with requestId substituted and an auth token', async () => {
    await getClientQuote('req-123');
    expect(fetchSpy).toHaveBeenCalledWith(
      `${CONFIG.API_URL}/client/quotes/req-123`,
      expect.objectContaining({
        method: 'GET',
        headers: expect.objectContaining({ Authorization: 'mock-mobile-token' }),
      })
    );
  });

  it('getClientQuote URL-encodes the requestId path parameter', async () => {
    await getClientQuote('req 123&x');
    expect(fetchSpy).toHaveBeenCalledWith(
      `${CONFIG.API_URL}/client/quotes/req%20123%26x`,
      expect.objectContaining({ method: 'GET' })
    );
  });

  it('acceptClientQuote POSTs exactly { expected_revision } to the accept path', async () => {
    await acceptClientQuote('req-1', 3);
    expect(fetchSpy).toHaveBeenCalledWith(
      `${CONFIG.API_URL}/client/quotes/req-1/accept`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ expected_revision: 3 }),
        headers: expect.objectContaining({ Authorization: 'mock-mobile-token' }),
      })
    );
  });

  it('declineClientQuote with a reason POSTs { expected_revision, decline_reason }', async () => {
    await declineClientQuote('req-1', 2, 'too expensive');
    expect(fetchSpy).toHaveBeenCalledWith(
      `${CONFIG.API_URL}/client/quotes/req-1/decline`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ expected_revision: 2, decline_reason: 'too expensive' }),
      })
    );
  });

  it('declineClientQuote trims the decline reason', async () => {
    await declineClientQuote('req-1', 2, '   spaced reason   ');
    expect(fetchSpy).toHaveBeenCalledWith(
      `${CONFIG.API_URL}/client/quotes/req-1/decline`,
      expect.objectContaining({
        body: JSON.stringify({ expected_revision: 2, decline_reason: 'spaced reason' }),
      })
    );
  });

  it('declineClientQuote omits decline_reason when blank/whitespace-only', async () => {
    await declineClientQuote('req-1', 2, '    ');
    expect(fetchSpy).toHaveBeenCalledWith(
      `${CONFIG.API_URL}/client/quotes/req-1/decline`,
      expect.objectContaining({
        body: JSON.stringify({ expected_revision: 2 }),
      })
    );
  });

  it('declineClientQuote omits decline_reason when undefined', async () => {
    await declineClientQuote('req-1', 2);
    expect(fetchSpy).toHaveBeenCalledWith(
      `${CONFIG.API_URL}/client/quotes/req-1/decline`,
      expect.objectContaining({
        body: JSON.stringify({ expected_revision: 2 }),
      })
    );
  });

  it('preserves HTTP 409 as ApiError.status for conflict reconciliation', async () => {
    fetchSpy.mockImplementation(() =>
      errJson(409, { error: 'Conflict: the quote changed since it was loaded; reload and retry' })
    );
    expect.assertions(3);
    try {
      await acceptClientQuote('req-1', 1);
    } catch (e) {
      const err = e as ApiError;
      expect(err).toBeInstanceOf(ApiError);
      expect(err.status).toBe(409);
      expect(err.message).toContain('Conflict');
    }
  });

  it('preserves a non-409 error status (e.g. 400) on ApiError', async () => {
    fetchSpy.mockImplementation(() => errJson(400, { error: 'expected_revision is required' }));
    expect.assertions(2);
    try {
      await acceptClientQuote('req-1', 1);
    } catch (e) {
      const err = e as ApiError;
      expect(err.status).toBe(400);
      expect(err.message).toBe('expected_revision is required');
    }
  });

  it('maps 401 to the preserved session-expiry message with status 401 (no regression)', async () => {
    fetchSpy.mockImplementation(() => errJson(401, { error: 'unauthorized' }));
    expect.assertions(2);
    try {
      await getClientQuote('req-1');
    } catch (e) {
      const err = e as ApiError;
      expect(err.status).toBe(401);
      expect(err.message).toBe('Your session expired. Please sign in again.');
    }
  });

  it('maps 403 to a plain permission error with status 403 (no logout semantics)', async () => {
    fetchSpy.mockImplementation(() => errJson(403, { error: 'Forbidden' }));
    expect.assertions(2);
    try {
      await getClientQuote('req-1');
    } catch (e) {
      const err = e as ApiError;
      expect(err.status).toBe(403);
      expect(err.message).toBe('Forbidden');
    }
  });
});
