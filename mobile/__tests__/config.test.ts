/**
 * OPS-3A.4A: Mobile environment-safety configuration tests.
 *
 * Validates the fail-closed, explicit-selection behavior of resolveConfig:
 *   - missing environment config does NOT fall back to production (throws)
 *   - invalid/unknown environment fails safely (throws)
 *   - development is unsupported and fails closed (throws), never prod fallback
 *   - explicit production resolves to the current production API + Cognito
 *   - explicit env overrides are honored for a production selection
 *   - a half-configured / insecure production selection fails closed
 *
 * These assert configuration SAFETY only. No backend contract, no secret value,
 * no network, and no app behavior is exercised here.
 */

import {
  resolveConfig,
  EnvironmentConfigError,
  type EnvSource,
} from '../src/api/config';

const PROD_API = 'https://a022yxuiue.execute-api.us-east-1.amazonaws.com/prod';
const PROD_POOL = 'us-east-1_counlsXGU';
const PROD_CLIENT = '1u4t7rfo339nkcgaf6q8s8sc6u';
const PROD_REGION = 'us-east-1';

describe('resolveConfig — fail-closed environment selection', () => {
  it('throws when EXPO_PUBLIC_APP_ENV is unset (no production fallback)', () => {
    const env: EnvSource = {};
    expect(() => resolveConfig(env)).toThrow(EnvironmentConfigError);
    expect(() => resolveConfig(env)).toThrow(/not set/i);
  });

  it('throws when EXPO_PUBLIC_APP_ENV is blank/whitespace (no production fallback)', () => {
    expect(() => resolveConfig({ EXPO_PUBLIC_APP_ENV: '   ' })).toThrow(
      EnvironmentConfigError,
    );
  });

  it('throws on an unknown environment value (fails safely)', () => {
    expect(() => resolveConfig({ EXPO_PUBLIC_APP_ENV: 'staging' })).toThrow(
      /not a recognized environment/i,
    );
  });

  it('does NOT leak production values when the env is invalid', () => {
    // Guard against any accidental partial return: a throw means nothing is
    // returned at all, so there is no object carrying the production API.
    let returned: unknown;
    try {
      returned = resolveConfig({ EXPO_PUBLIC_APP_ENV: 'nope' });
    } catch {
      returned = undefined;
    }
    expect(returned).toBeUndefined();
  });

  it('fails closed for development (unsupported, never prod fallback)', () => {
    expect(() => resolveConfig({ EXPO_PUBLIC_APP_ENV: 'development' })).toThrow(
      /development/i,
    );
    expect(() => resolveConfig({ EXPO_PUBLIC_APP_ENV: 'development' })).toThrow(
      /NEVER fall back to production/i,
    );
  });
});

describe('resolveConfig — explicit production selection', () => {
  it('resolves the canonical production API + Cognito when prod is declared', () => {
    const cfg = resolveConfig({ EXPO_PUBLIC_APP_ENV: 'production' });
    expect(cfg.APP_ENV).toBe('production');
    expect(cfg.API_URL).toBe(PROD_API);
    expect(cfg.USER_POOL_ID).toBe(PROD_POOL);
    expect(cfg.CLIENT_ID).toBe(PROD_CLIENT);
    expect(cfg.REGION).toBe(PROD_REGION);
  });

  it('honors explicit non-secret env overrides for production', () => {
    const cfg = resolveConfig({
      EXPO_PUBLIC_APP_ENV: 'production',
      EXPO_PUBLIC_API_URL: 'https://example.execute-api.us-east-1.amazonaws.com/prod',
      EXPO_PUBLIC_COGNITO_USER_POOL_ID: 'us-east-1_EXAMPLE',
      EXPO_PUBLIC_COGNITO_CLIENT_ID: 'exampleclientid',
      EXPO_PUBLIC_COGNITO_REGION: 'us-east-1',
    });
    expect(cfg.API_URL).toBe(
      'https://example.execute-api.us-east-1.amazonaws.com/prod',
    );
    expect(cfg.USER_POOL_ID).toBe('us-east-1_EXAMPLE');
    expect(cfg.CLIENT_ID).toBe('exampleclientid');
  });

  it('fails closed when a production override is explicitly emptied', () => {
    expect(() =>
      resolveConfig({
        EXPO_PUBLIC_APP_ENV: 'production',
        EXPO_PUBLIC_API_URL: '   ',
      }),
    ).toThrow(/missing or empty/i);
  });

  it('fails closed on an insecure (non-https) production API URL', () => {
    expect(() =>
      resolveConfig({
        EXPO_PUBLIC_APP_ENV: 'production',
        EXPO_PUBLIC_API_URL: 'http://a022yxuiue.execute-api.us-east-1.amazonaws.com/prod',
      }),
    ).toThrow(/https/i);
  });
});

describe('resolveConfig — no secrets in config surface', () => {
  it('production config contains only non-secret client identifiers', () => {
    const cfg = resolveConfig({ EXPO_PUBLIC_APP_ENV: 'production' });
    const serialized = JSON.stringify(cfg).toLowerCase();
    // None of these secret-ish markers should ever appear in resolved config.
    expect(serialized).not.toMatch(/password/);
    expect(serialized).not.toMatch(/secret/);
    expect(serialized).not.toMatch(/"authorization"/);
    expect(serialized).not.toMatch(/bearer /);
    // A JWT would contain two dots separating base64 segments; the config has none.
    expect(serialized).not.toMatch(/eyj[a-z0-9_-]+\.[a-z0-9_-]+\./);
    // Only the expected keys exist.
    expect(Object.keys(cfg).sort()).toEqual(
      ['API_URL', 'APP_ENV', 'CLIENT_ID', 'REGION', 'USER_POOL_ID'].sort(),
    );
  });
});
