/**
 * W2A — Web admin canonical quote API-client foundation tests.
 *
 * Proves the two new api/client.js functions call the already-deployed canonical
 * endpoints with the correct path/method/auth/body, and that neither touches the
 * legacy Stripe/payment-link endpoint. These exercise the REAL request() wrapper
 * (fetch + getIdToken are mocked), so path substitution and method are verified
 * end-to-end against the generated contracts.
 */
import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';

// Mock the auth token source used by the protected request() wrapper.
vi.mock('../src/api/auth', () => ({
  getIdToken: vi.fn(async () => 'test-id-token'),
}));

import {
  updateAdminRequestQuote,
  sendAdminRequestQuote,
} from '../src/api/client';
import { API_PATHS } from '../src/generated/contracts.js';

// The request() wrapper prefixes a build-time CONFIG.API_URL base we don't control
// in the test environment, so assertions check the canonical PATH suffix (method,
// requestId substitution, auth, body) rather than a hardcoded base URL.

let fetchMock;

beforeEach(() => {
  fetchMock = vi.fn(async () => ({
    ok: true,
    status: 200,
    json: async () => ({ message: 'ok' }),
  }));
  globalThis.fetch = fetchMock;
});

afterEach(() => {
  vi.clearAllMocks();
});

const lastCall = () => fetchMock.mock.calls[fetchMock.mock.calls.length - 1];

describe('W2A — generated contract paths', () => {
  it('exposes the canonical admin quote paths', () => {
    expect(API_PATHS.admin.updateQuote).toBe('/admin/requests/{requestId}/quote');
    expect(API_PATHS.admin.sendQuote).toBe('/admin/requests/{requestId}/quote/send');
  });
});

describe('updateAdminRequestQuote', () => {
  it('PATCHes the canonical quote path with the requestId substituted and payload forwarded', async () => {
    const payload = {
      quote_amount_cents: 5000,
      currency: 'USD',
      payment_requirement: 'FULL',
      quote_notes_client: 'Standard walk',
    };
    await updateAdminRequestQuote('req-123', payload);

    const [url, options] = lastCall();
    expect(url.endsWith('/admin/requests/req-123/quote')).toBe(true);
    expect(options.method).toBe('PATCH');
    // Protected request -> Authorization header present.
    expect(options.headers.Authorization).toBe('test-id-token');
    expect(options.headers['Content-Type']).toBe('application/json');
    // Payload forwarded verbatim (no fabricated fields).
    expect(JSON.parse(options.body)).toEqual(payload);
    // No legacy payment endpoint touched.
    expect(url).not.toContain('send-payment-email');
    expect(url).not.toContain('payment');
  });

  it('does not invoke any Stripe/payment endpoint', async () => {
    await updateAdminRequestQuote('req-1', { quote_amount_cents: 100 });
    for (const [url] of fetchMock.mock.calls) {
      expect(url).not.toMatch(/payment|stripe/i);
    }
  });
});

describe('sendAdminRequestQuote', () => {
  it('POSTs the canonical quote/send path with no client-supplied body', async () => {
    await sendAdminRequestQuote('req-456');

    const [url, options] = lastCall();
    expect(url.endsWith('/admin/requests/req-456/quote/send')).toBe(true);
    expect(options.method).toBe('POST');
    expect(options.headers.Authorization).toBe('test-id-token');
    // No body is sent (no fabricated expected_revision / payment fields).
    expect(options.body).toBeUndefined();
  });

  it('does not invoke any Stripe/payment endpoint', async () => {
    await sendAdminRequestQuote('req-1');
    for (const [url] of fetchMock.mock.calls) {
      expect(url).not.toMatch(/payment|stripe/i);
      expect(url).not.toContain('send-payment-email');
    }
  });
});
