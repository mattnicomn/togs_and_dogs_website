import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../src/api/auth', () => ({ getIdToken: vi.fn(async () => 'id-token') }));
vi.mock('../src/api/config', () => ({ default: { API_URL: 'https://api.example.test' } }));

import { getAdminRequest, processCancellationDecision, reviewRequest } from '../src/api/client';

const CYCLE = '6f1c2a3b-4d5e-4f60-8a7b-9c0d1e2f3a4b';

const okResponse = (body) => ({ ok: true, status: 200, json: async () => body });
const errResponse = (status, body) => ({ ok: false, status, json: async () => body });

describe('WEB-CANCEL-1 cancellation decision API client', () => {
  beforeEach(() => { global.fetch = vi.fn(); });
  afterEach(() => { delete global.fetch; });

  it('sends exactly { request_id, client_id, decision, note, cancellation_request_id } via PUT', async () => {
    fetch.mockResolvedValue(okResponse({ message: 'ok' }));
    await processCancellationDecision('req-1', 'client-1', 'DENY', 'note', CYCLE);
    expect(fetch).toHaveBeenCalledTimes(1);
    const [url, opts] = fetch.mock.calls[0];
    expect(url).toBe('https://api.example.test/admin/cancel/decision');
    expect(opts.method).toBe('PUT');
    expect(opts.headers.Authorization).toBe('id-token');
    expect(JSON.parse(opts.body)).toEqual({
      request_id: 'req-1', client_id: 'client-1', decision: 'DENY', note: 'note', cancellation_request_id: CYCLE,
    });
  });

  it.each([undefined, null, '', '   ', 7])('refuses a missing cycle id %p without any request', async (cycle) => {
    await expect(processCancellationDecision('req-1', 'client-1', 'APPROVE', '', cycle))
      .rejects.toMatchObject({ code: 'MISSING_CANCELLATION_REQUEST_ID' });
    expect(fetch).not.toHaveBeenCalled();
  });

  it.each(['approve', 'deny', 'CANCEL', '', null])('refuses non-literal decision %p without any request', async (d) => {
    await expect(processCancellationDecision('req-1', 'client-1', d, '', CYCLE))
      .rejects.toMatchObject({ code: 'INVALID_DECISION' });
    expect(fetch).not.toHaveBeenCalled();
  });

  it('surfaces the HTTP status, server message and machine-readable code', async () => {
    fetch.mockResolvedValue(errResponse(409, { error: 'Earlier cycle.', code: 'CANCELLATION_CYCLE_MISMATCH' }));
    await expect(processCancellationDecision('req-1', 'client-1', 'APPROVE', '', CYCLE))
      .rejects.toMatchObject({ status: 409, code: 'CANCELLATION_CYCLE_MISMATCH', message: 'Earlier cycle.' });
    expect(fetch).toHaveBeenCalledTimes(1);   // never retried
  });

  it('getAdminRequest reads the exact request and client, and keeps the HTTP status on errors', async () => {
    fetch.mockResolvedValue(okResponse({ request_id: 'req 1' }));
    await getAdminRequest('req 1', 'client&1');
    expect(fetch.mock.calls[0][0]).toBe('https://api.example.test/admin/requests/req%201?clientId=client%261');
    fetch.mockResolvedValue(errResponse(403, { error: 'Forbidden' }));
    await expect(getAdminRequest('req-1', 'client-1')).rejects.toMatchObject({ status: 403, message: 'Forbidden' });
  });

  it('existing callers keep their error message unchanged', async () => {
    fetch.mockResolvedValue(errResponse(400, { error: 'Invalid transition' }));
    await expect(reviewRequest('req-1', 'client-1', 'APPROVED')).rejects.toThrow('Invalid transition');
  });
});
