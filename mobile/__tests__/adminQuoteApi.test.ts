/**
 * S1: admin quote API helpers. Verifies the deployed contract is used exactly:
 * PATCH body shape (no expected_revision), body-less POST send, auth header, path
 * building, and HTTP status preservation (400/403/404/409) via ApiError.
 */
import { CONFIG } from '../src/api/config';

jest.mock('../src/auth/storage', () => ({
  getIdToken: jest.fn().mockResolvedValue('mock-mobile-token'),
  isTokenExpired: jest.fn().mockReturnValue(false),
}));

import { ApiError, sendAdminQuote, updateAdminQuote } from '../src/api/client';

const okJson = (payload: any = { success: true }) =>
  Promise.resolve({ ok: true, json: () => Promise.resolve(payload) } as Response);
const errJson = (status: number, payload: any = {}) =>
  Promise.resolve({ ok: false, status, json: () => Promise.resolve(payload) } as Response);

const payload = {
  quote_amount_cents: 12500,
  currency: 'USD',
  deposit_amount_cents: 0,
  payment_requirement: 'NONE' as const,
  quote_notes_client: 'Thanks!',
  quote_notes_internal: '',
  internal_pricing_notes: '',
};

describe('S1 admin quote API', () => {
  let fetchSpy: jest.SpyInstance;
  beforeEach(() => {
    fetchSpy = jest.spyOn(global, 'fetch').mockImplementation(() => okJson());
  });
  afterEach(() => {
    jest.clearAllMocks();
    fetchSpy.mockRestore();
  });

  it('updateAdminQuote PATCHes the generated path with auth and exactly the supplied body', async () => {
    await updateAdminQuote('req-1', payload);
    expect(fetchSpy).toHaveBeenCalledWith(
      `${CONFIG.API_URL}/admin/requests/req-1/quote`,
      expect.objectContaining({
        method: 'PATCH',
        headers: expect.objectContaining({ Authorization: 'mock-mobile-token' }),
        body: JSON.stringify(payload),
      })
    );
    const sent = JSON.parse(fetchSpy.mock.calls[0][1].body);
    expect(sent).not.toHaveProperty('expected_revision');
  });

  it('updateAdminQuote URL-encodes the requestId', async () => {
    await updateAdminQuote('req 1&x', payload);
    expect(fetchSpy.mock.calls[0][0]).toBe(`${CONFIG.API_URL}/admin/requests/req%201%26x/quote`);
  });

  it('sendAdminQuote POSTs the send path with auth and NO body', async () => {
    await sendAdminQuote('req-2');
    const [url, options] = fetchSpy.mock.calls[0];
    expect(url).toBe(`${CONFIG.API_URL}/admin/requests/req-2/quote/send`);
    expect(options.method).toBe('POST');
    expect(options.headers.Authorization).toBe('mock-mobile-token');
    expect(options.body).toBeUndefined();
  });

  it.each([400, 403, 404, 409])('preserves HTTP %p on ApiError', async status => {
    fetchSpy.mockImplementation(() => errJson(status, { error: `status ${status} message` }));
    const err: any = await updateAdminQuote('req-1', payload).catch(e => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(status);
    expect(err.message).toBe(`status ${status} message`);
  });

  it('send 409 is surfaced with its status and is not retried', async () => {
    fetchSpy.mockImplementation(() => errJson(409, { error: 'Conflict: the quote changed since it was loaded; reload and retry' }));
    const err: any = await sendAdminQuote('req-3').catch(e => e);
    expect(err.status).toBe(409);
    expect(fetchSpy).toHaveBeenCalledTimes(1);
  });
});
