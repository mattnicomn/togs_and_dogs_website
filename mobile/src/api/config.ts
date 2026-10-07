/**
 * OPS-3A.4A: Explicit, fail-closed mobile environment selection.
 *
 * SECURITY GOAL — remove the implicit behavior where EVERY build silently
 * targeted production merely because production values were hardcoded. A
 * production-backed build must now DELIBERATELY and VISIBLY declare production
 * intent via EXPO_PUBLIC_APP_ENV=production. Missing or invalid configuration
 * FAILS CLOSED (throws) rather than defaulting to production.
 *
 * Expo SDK 54: EXPO_PUBLIC_* variables are inlined at build/bundle time and are
 * readable through process.env.EXPO_PUBLIC_*. These are NON-SECRET client
 * configuration identifiers only (public REST API URL, Cognito pool/app-client
 * IDs, AWS region). No access tokens, passwords, JWTs, client secrets, or AWS
 * credentials are read or stored here.
 *
 * Supported environments:
 *   - "production": fully configured. The explicit production API/Cognito target.
 *   - "development": RESERVED. No operational PetCare Hero dev backend exists for
 *     this app yet, so selecting it fails closed (throws) until a real dev
 *     environment is provisioned and its config supplied. We intentionally do NOT
 *     fabricate a dev URL, create AWS resources, or point at any migration/dev
 *     AWS account. This remains future AWS Organization/dev-migration scope.
 *
 * This slice changes ONLY environment/config safety. Quote workflow, navigation,
 * auth behavior, token handling, API request semantics, and UI logic are
 * unchanged. API_URL/REGION/USER_POOL_ID/CLIENT_ID keep the same names/shape so
 * existing consumers (api/client.ts, auth/cognito.ts) are untouched.
 */

export type AppEnv = 'production' | 'development';

export interface AppConfig {
  APP_ENV: AppEnv;
  API_URL: string;
  REGION: string;
  USER_POOL_ID: string;
  CLIENT_ID: string;
}

/**
 * Canonical NON-SECRET production configuration. These are public client
 * identifiers (not credentials). They are only used when production is
 * EXPLICITLY selected via EXPO_PUBLIC_APP_ENV=production.
 */
const PRODUCTION_CONFIG: Omit<AppConfig, 'APP_ENV'> = {
  API_URL: 'https://a022yxuiue.execute-api.us-east-1.amazonaws.com/prod',
  REGION: 'us-east-1',
  USER_POOL_ID: 'us-east-1_counlsXGU',
  CLIENT_ID: '1u4t7rfo339nkcgaf6q8s8sc6u',
};

export class EnvironmentConfigError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'EnvironmentConfigError';
  }
}

/** A minimal env source — the subset of process.env we read. */
export type EnvSource = Record<string, string | undefined>;

const KNOWN_ENVS: readonly AppEnv[] = ['production', 'development'];

/**
 * Pure, testable resolver. Given an environment variable map, returns the
 * resolved AppConfig or THROWS. There is deliberately NO production fallback:
 * an unset/unknown APP_ENV, or an under-configured production selection, fails
 * closed so a build can never target production by accident.
 */
export function resolveConfig(env: EnvSource): AppConfig {
  const rawEnv = (env.EXPO_PUBLIC_APP_ENV || '').trim();

  if (!rawEnv) {
    throw new EnvironmentConfigError(
      'EXPO_PUBLIC_APP_ENV is not set. Refusing to start: a build must explicitly ' +
        "declare its environment (e.g. EXPO_PUBLIC_APP_ENV=production). There is no " +
        'implicit production default.',
    );
  }

  if (!(KNOWN_ENVS as readonly string[]).includes(rawEnv)) {
    throw new EnvironmentConfigError(
      `EXPO_PUBLIC_APP_ENV="${rawEnv}" is not a recognized environment. ` +
        `Expected one of: ${KNOWN_ENVS.join(', ')}.`,
    );
  }

  const appEnv = rawEnv as AppEnv;

  if (appEnv === 'development') {
    // No operational dev backend exists for this app. Fail closed rather than
    // fabricate one or silently borrow production.
    throw new EnvironmentConfigError(
      'EXPO_PUBLIC_APP_ENV=development is selected but no PetCare Hero development ' +
        'backend is configured for this app. Development is unsupported and fails ' +
        'closed until a real dev environment is provisioned. It will NEVER fall back ' +
        'to production.',
    );
  }

  // appEnv === 'production'
  // Production target may come from explicit env overrides (preferred) or the
  // canonical non-secret production identifiers. Either way, production is only
  // reached because it was EXPLICITLY selected above.
  const resolved: AppConfig = {
    APP_ENV: 'production',
    API_URL: (env.EXPO_PUBLIC_API_URL || PRODUCTION_CONFIG.API_URL).trim(),
    REGION: (env.EXPO_PUBLIC_COGNITO_REGION || PRODUCTION_CONFIG.REGION).trim(),
    USER_POOL_ID: (env.EXPO_PUBLIC_COGNITO_USER_POOL_ID || PRODUCTION_CONFIG.USER_POOL_ID).trim(),
    CLIENT_ID: (env.EXPO_PUBLIC_COGNITO_CLIENT_ID || PRODUCTION_CONFIG.CLIENT_ID).trim(),
  };

  // Defense-in-depth: a production selection with an empty/invalid resolved
  // value fails closed instead of shipping a half-configured production build.
  for (const [key, value] of Object.entries(resolved)) {
    if (typeof value !== 'string' || value.length === 0) {
      throw new EnvironmentConfigError(
        `Production configuration value "${key}" is missing or empty. Refusing to ` +
          'start a half-configured production build.',
      );
    }
  }
  if (!/^https:\/\//.test(resolved.API_URL)) {
    throw new EnvironmentConfigError(
      'Production API_URL must be an https:// URL. Refusing to start with an ' +
        'insecure or malformed API endpoint.',
    );
  }

  return resolved;
}

/**
 * Build the runtime environment map using EXPLICIT, STATIC dot-notation
 * references to process.env.EXPO_PUBLIC_*.
 *
 * Expo SDK 54 / Metro only inlines environment variables that are referenced
 * literally as `process.env.EXPO_PUBLIC_<NAME>`. Dynamic forms —
 * `process.env[name]`, destructuring, or passing the whole `process.env`
 * object to a function — are NOT inlined and resolve to undefined in a compiled
 * bundle. We therefore read each variable statically HERE, then hand the plain
 * map to the pure (unit-tested) resolver. Do not refactor these into a loop or
 * bracket access, or the production bundle will lose its values and fail closed
 * for every build.
 */
const runtimeEnv: EnvSource = {
  EXPO_PUBLIC_APP_ENV: process.env.EXPO_PUBLIC_APP_ENV,
  EXPO_PUBLIC_API_URL: process.env.EXPO_PUBLIC_API_URL,
  EXPO_PUBLIC_COGNITO_REGION: process.env.EXPO_PUBLIC_COGNITO_REGION,
  EXPO_PUBLIC_COGNITO_USER_POOL_ID: process.env.EXPO_PUBLIC_COGNITO_USER_POOL_ID,
  EXPO_PUBLIC_COGNITO_CLIENT_ID: process.env.EXPO_PUBLIC_COGNITO_CLIENT_ID,
};

/**
 * The resolved application configuration for the current build.
 *
 * Evaluated once at module load from the statically-inlined runtimeEnv. If the
 * build was produced WITHOUT an explicit, valid environment selection, importing
 * this module throws at startup — the intended fail-closed behavior.
 */
export const CONFIG: AppConfig = resolveConfig(runtimeEnv);
