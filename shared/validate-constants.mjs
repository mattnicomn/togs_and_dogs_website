/**
 * Phase 24A-2: Shared Constants and API Contracts Validation
 *
 * Validates shared/constants/ and shared/contracts/ JSON files.
 * Uses Node.js built-in test runner — no dependencies required.
 *
 * Run: node shared/validate-constants.mjs
 */

import { readFile } from 'node:fs/promises';
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));

const STATUSES_PATH = join(__dirname, 'constants', 'request-statuses.json');
const SERVICES_PATH = join(__dirname, 'constants', 'service-types.json');
const PET_FIELDS_PATH = join(__dirname, 'constants', 'pet-fields.json');
const API_PATHS_PATH = join(__dirname, 'contracts', 'api-paths.json');

const VALID_CATEGORIES = ['neutral', 'informational', 'success', 'warning', 'danger'];
const STATUS_ID_PATTERN = /^[A-Z][A-Z0-9_]*$/;
const SERVICE_ID_PATTERN = /^[A-Z][A-Z0-9_]*$/;
const WINDOW_ID_PATTERN = /^[A-Z][A-Z0-9_]*$/;
const TIME_PATTERN = /^([01]\d|2[0-3]):[0-5]\d$/;
const API_PATH_PATTERN = /^\/[a-z][a-z0-9/_{}?=-]*$/;
const SERVICE_FIELDS = [
  'label',
  'labelLong',
  'durationMinutes',
  'durationStatus',
  'legacyDurationMinutes',
  'scheduleMode',
  'fixedStartTime',
  'fixedEndTime',
  'crossesMidnight',
  'availableInIntake',
  'supportedOnMobile',
  'lifecycle',
  'newBookingEligibility',
  'visitsPerDayOptions',
  'allowedWindowIds',
  'windowSelectionMode',
];
const WINDOW_FIELDS = [
  'label',
  'start',
  'end',
  'lifecycle',
  'newBookingEligibility',
];
const VALID_DURATION_STATUSES = new Set(['confirmed', 'historical', 'unresolved']);
const VALID_LIFECYCLES = new Set(['active', 'legacy']);
const VALID_NEW_BOOKING_ELIGIBILITY = new Set(['eligible', 'ineligible', 'pending']);
const VALID_WINDOW_SELECTION_MODES = new Set([
  'exactly_one',
  'match_visits_per_day',
  'none',
  'unresolved',
  'legacy_compatibility',
]);
const VALID_SCHEDULE_MODES = new Set(['selectable_windows', 'fixed', 'legacy_compatibility']);
const ACTIVE_CANONICAL_WINDOWS = ['MORNING', 'MIDDAY', 'EVENING'];
const EXPECTED_CLIENT_WRITE_HEALTH_FIELD_LIMITS = {
  vet_name: 100,
  vet_phone: 100,
};

let statuses, services, petFields, apiPaths;

// --- Request Statuses ---

test('request-statuses.json parses as valid JSON', async () => {
  statuses = JSON.parse(await readFile(STATUSES_PATH, 'utf-8'));
  assert.ok(statuses.statuses, 'Missing "statuses" object');
  assert.ok(statuses.categories, 'Missing "categories" array');
});

test('status identifiers use UPPER_SNAKE_CASE', () => {
  for (const id of Object.keys(statuses.statuses)) {
    assert.match(id, STATUS_ID_PATTERN, `Status "${id}" does not match UPPER_SNAKE_CASE`);
  }
});

test('status identifiers are unique', () => {
  const ids = Object.keys(statuses.statuses);
  const unique = new Set(ids);
  assert.equal(ids.length, unique.size, 'Duplicate status identifiers found');
});

test('status categories use the allowlist', () => {
  for (const [id, status] of Object.entries(statuses.statuses)) {
    assert.ok(
      VALID_CATEGORIES.includes(status.category),
      `Status "${id}" category "${status.category}" not in allowlist`
    );
  }
});

test('status synonyms reference existing statuses or are known legacy values', () => {
  const allIds = new Set(Object.keys(statuses.statuses));
  const knownLegacy = new Set(['NEEDS_REVIEW', 'NEEDS_MG', 'NEW_REQUEST', 'BOOKED', 'QUOTED', 'JOB_CREATED', 'SCHEDULED']);
  for (const [id, status] of Object.entries(statuses.statuses)) {
    for (const syn of status.synonyms || []) {
      const isKnown = allIds.has(syn) || knownLegacy.has(syn);
      assert.ok(isKnown, `Status "${id}" has unknown synonym "${syn}"`);
    }
  }
});

test('required status properties exist', () => {
  for (const [id, status] of Object.entries(statuses.statuses)) {
    assert.ok('label' in status, `Status "${id}" missing label`);
    assert.equal(typeof status.label, 'string', `Status "${id}" label must be a string`);
    assert.ok(status.label.trim().length > 0, `Status "${id}" label must be a non-empty string`);
    assert.ok('category' in status, `Status "${id}" missing category`);
    assert.ok('terminal' in status, `Status "${id}" missing terminal`);
    assert.ok('customerVisible' in status, `Status "${id}" missing customerVisible`);
    assert.ok('staffSettable' in status, `Status "${id}" missing staffSettable`);
    assert.ok('synonyms' in status, `Status "${id}" missing synonyms`);
  }
});

// --- Service Types ---

test('service-types.json parses as valid JSON', async () => {
  services = JSON.parse(await readFile(SERVICES_PATH, 'utf-8'));
  assert.ok(services.services, 'Missing "services" object');
  assert.ok(services.windows, 'Missing "windows" object');
});

test('service identifiers use UPPER_SNAKE_CASE', () => {
  for (const id of Object.keys(services.services)) {
    assert.match(id, SERVICE_ID_PATTERN, `Service "${id}" does not match UPPER_SNAKE_CASE`);
  }
});

test('service identifiers are unique', () => {
  const ids = Object.keys(services.services);
  assert.equal(ids.length, new Set(ids).size, 'Duplicate service identifiers');
});

test('services have required properties', () => {
  for (const [id, svc] of Object.entries(services.services)) {
    assert.ok(
      svc !== null
        && typeof svc === 'object'
        && !Array.isArray(svc)
        && Object.getPrototypeOf(svc) === Object.prototype,
      `Service "${id}" must be a plain object`
    );

    assert.deepEqual(
      Object.keys(svc),
      SERVICE_FIELDS,
      `Service "${id}" field membership or order differs`
    );

    for (const field of SERVICE_FIELDS) {
      assert.ok(field in svc, `Service "${id}" missing ${field}`);
      if (!['legacyDurationMinutes', 'fixedStartTime', 'fixedEndTime'].includes(field)) {
        assert.notEqual(svc[field], null, `Service "${id}" ${field} must not be null`);
      }
      assert.notEqual(svc[field], undefined, `Service "${id}" ${field} must not be undefined`);
    }

    assert.ok(
      typeof svc.label === 'string' && svc.label.trim().length > 0,
      `Service "${id}" label must be a non-empty string`
    );
    assert.ok(
      typeof svc.labelLong === 'string' && svc.labelLong.trim().length > 0,
      `Service "${id}" labelLong must be a non-empty string`
    );
    assert.ok(
      typeof svc.durationMinutes === 'number'
        && Number.isFinite(svc.durationMinutes)
        && Number.isInteger(svc.durationMinutes)
        && svc.durationMinutes > 0,
      `Service "${id}" durationMinutes must be a positive finite integer`
    );
    assert.equal(
      typeof svc.availableInIntake,
      'boolean',
      `Service "${id}" availableInIntake must be a boolean`
    );
    assert.equal(
      typeof svc.supportedOnMobile,
      'boolean',
      `Service "${id}" supportedOnMobile must be a boolean`
    );
    assert.ok(
      VALID_DURATION_STATUSES.has(svc.durationStatus),
      `Service "${id}" has invalid durationStatus "${svc.durationStatus}"`
    );
    assert.ok(
      VALID_LIFECYCLES.has(svc.lifecycle),
      `Service "${id}" has invalid lifecycle "${svc.lifecycle}"`
    );
    assert.ok(
      VALID_NEW_BOOKING_ELIGIBILITY.has(svc.newBookingEligibility),
      `Service "${id}" has invalid newBookingEligibility "${svc.newBookingEligibility}"`
    );
    assert.ok(
      VALID_WINDOW_SELECTION_MODES.has(svc.windowSelectionMode),
      `Service "${id}" has invalid windowSelectionMode "${svc.windowSelectionMode}"`
    );
    assert.ok(
      VALID_SCHEDULE_MODES.has(svc.scheduleMode),
      `Service "${id}" has invalid scheduleMode "${svc.scheduleMode}"`
    );
    assert.equal(typeof svc.crossesMidnight, 'boolean', `Service "${id}" crossesMidnight must be a boolean`);
    if (svc.scheduleMode === 'fixed') {
      assert.match(svc.fixedStartTime, TIME_PATTERN, `Service "${id}" fixedStartTime must be HH:mm`);
      assert.match(svc.fixedEndTime, TIME_PATTERN, `Service "${id}" fixedEndTime must be HH:mm`);
      assert.equal(svc.allowedWindowIds.length, 0, `Fixed service "${id}" must not expose selectable windows`);
      assert.equal(svc.windowSelectionMode, 'none', `Fixed service "${id}" windowSelectionMode must be none`);
    } else {
      assert.equal(svc.fixedStartTime, null, `Non-fixed service "${id}" fixedStartTime must be null`);
      assert.equal(svc.fixedEndTime, null, `Non-fixed service "${id}" fixedEndTime must be null`);
      assert.equal(svc.crossesMidnight, false, `Non-fixed service "${id}" must not cross midnight`);
    }
    if (svc.legacyDurationMinutes !== null) {
      assert.ok(
        Number.isInteger(svc.legacyDurationMinutes) && svc.legacyDurationMinutes > 0,
        `Service "${id}" legacyDurationMinutes must be null or a positive integer`
      );
    }
    assert.ok(Array.isArray(svc.visitsPerDayOptions), `Service "${id}" visitsPerDayOptions must be an array`);
    assert.equal(
      svc.visitsPerDayOptions.length,
      new Set(svc.visitsPerDayOptions).size,
      `Service "${id}" visitsPerDayOptions must be unique`
    );
    for (const option of svc.visitsPerDayOptions) {
      assert.ok(Number.isInteger(option) && option > 0, `Service "${id}" visit options must be positive integers`);
    }
    assert.ok(Array.isArray(svc.allowedWindowIds), `Service "${id}" allowedWindowIds must be an array`);
    assert.equal(
      svc.allowedWindowIds.length,
      new Set(svc.allowedWindowIds).size,
      `Service "${id}" allowedWindowIds must be distinct`
    );
    for (const windowId of svc.allowedWindowIds) {
      assert.ok(windowId in services.windows, `Service "${id}" references unknown window "${windowId}"`);
    }
    if (svc.lifecycle === 'legacy') {
      assert.notEqual(
        svc.newBookingEligibility,
        'eligible',
        `Legacy service "${id}" must not claim approved new-booking eligibility`
      );
    }
  }
});

test('Ryan target services and scheduling policies are exact', () => {
  const walk = services.services.WALK_20MIN;
  assert.equal(walk.label, '20-Min Walk');
  assert.equal(walk.labelLong, '20-Minute Walk');
  assert.equal(walk.durationMinutes, 20);
  assert.equal(walk.lifecycle, 'active');
  assert.equal(walk.newBookingEligibility, 'eligible');
  assert.deepEqual(walk.allowedWindowIds, ACTIVE_CANONICAL_WINDOWS);
  assert.equal(walk.windowSelectionMode, 'exactly_one');

  const checkIn = services.services.CHECK_IN;
  assert.equal(checkIn.label, 'Check-In');
  assert.equal(checkIn.labelLong, '30-Minute Check-In');
  assert.equal(checkIn.durationMinutes, 30);
  assert.deepEqual(checkIn.visitsPerDayOptions, [1, 2, 3]);
  assert.deepEqual(checkIn.allowedWindowIds, ACTIVE_CANONICAL_WINDOWS);
  assert.equal(checkIn.windowSelectionMode, 'match_visits_per_day');

  const overnight = services.services.OVERNIGHT;
  assert.equal(overnight.lifecycle, 'active');
  assert.equal(overnight.durationMinutes, 600);
  assert.equal(overnight.durationStatus, 'confirmed');
  assert.equal(overnight.legacyDurationMinutes, 720);
  assert.equal(overnight.scheduleMode, 'fixed');
  assert.equal(overnight.fixedStartTime, '21:00');
  assert.equal(overnight.fixedEndTime, '07:00');
  assert.equal(overnight.crossesMidnight, true);
  assert.deepEqual(overnight.allowedWindowIds, []);
  assert.equal(overnight.windowSelectionMode, 'none');

  assert.equal(services.services.MEET_GREET.availableInIntake, false);
  assert.equal(services.services.MEET_GREET.supportedOnMobile, true);
});

test('legacy services remain readable without reinterpreting PET_SITTING', () => {
  const expectedLegacy = [
    'WALK_30MIN',
    'WALK_60MIN',
    'DROPIN_1HR',
    'DROPIN_3HR',
    'PET_SITTING',
  ];

  for (const id of expectedLegacy) {
    assert.ok(services.services[id], `Missing historical service "${id}"`);
    assert.equal(services.services[id].lifecycle, 'legacy');
  }
  assert.equal(services.services.PET_SITTING.labelLong, 'Pet Sitting');
  assert.notEqual(services.services.PET_SITTING.labelLong, services.services.CHECK_IN.labelLong);
  assert.equal(services.services.WALK_60MIN.newBookingEligibility, 'pending');
  assert.equal(services.services.DROPIN_1HR.newBookingEligibility, 'pending');
  assert.equal(services.services.DROPIN_3HR.newBookingEligibility, 'pending');
});

test('visit windows use exact structured active values and preserve legacy IDs', () => {
  assert.deepEqual(Object.keys(services.windows), [
    'MORNING',
    'MIDDAY',
    'EVENING',
    'AFTERNOON',
    'ANYTIME',
  ]);

  for (const [id, window] of Object.entries(services.windows)) {
    assert.match(id, WINDOW_ID_PATTERN, `Window "${id}" does not match UPPER_SNAKE_CASE`);
    assert.deepEqual(Object.keys(window), WINDOW_FIELDS, `Window "${id}" field membership or order differs`);
    assert.ok(typeof window.label === 'string' && window.label.trim(), `Window "${id}" label must be non-empty`);
    assert.ok(VALID_LIFECYCLES.has(window.lifecycle), `Window "${id}" lifecycle is invalid`);
    assert.ok(
      VALID_NEW_BOOKING_ELIGIBILITY.has(window.newBookingEligibility),
      `Window "${id}" newBookingEligibility is invalid`
    );
  }

  assert.deepEqual(services.windows.MORNING, {
    label: 'Morning', start: '06:30', end: '09:30', lifecycle: 'active', newBookingEligibility: 'eligible',
  });
  assert.deepEqual(services.windows.MIDDAY, {
    label: 'Mid-day', start: '10:30', end: '15:30', lifecycle: 'active', newBookingEligibility: 'eligible',
  });
  assert.deepEqual(services.windows.EVENING, {
    label: 'Evening', start: '18:00', end: '21:30', lifecycle: 'active', newBookingEligibility: 'eligible',
  });

  for (const id of ACTIVE_CANONICAL_WINDOWS) {
    const window = services.windows[id];
    assert.match(window.start, TIME_PATTERN, `Window "${id}" start must be HH:mm`);
    assert.match(window.end, TIME_PATTERN, `Window "${id}" end must be HH:mm`);
    assert.ok(window.start < window.end, `Window "${id}" start must precede end`);
  }
  for (const id of ['AFTERNOON', 'ANYTIME']) {
    assert.equal(services.windows[id].lifecycle, 'legacy');
    assert.equal(services.windows[id].newBookingEligibility, 'ineligible');
    assert.equal(services.windows[id].start, null);
    assert.equal(services.windows[id].end, null);
  }
});

test('CHECK_IN metadata deterministically enforces count, distinctness, and active membership', () => {
  const checkIn = services.services.CHECK_IN;
  const isValidSelection = (visitsPerDay, selectedWindowIds) => (
    checkIn.visitsPerDayOptions.includes(visitsPerDay)
    && selectedWindowIds.length === visitsPerDay
    && new Set(selectedWindowIds).size === selectedWindowIds.length
    && selectedWindowIds.every((id) => checkIn.allowedWindowIds.includes(id))
  );

  assert.equal(isValidSelection(1, ['MORNING']), true);
  assert.equal(isValidSelection(2, ['MORNING', 'EVENING']), true);
  assert.equal(isValidSelection(2, ['MORNING', 'MORNING']), false);
  assert.equal(isValidSelection(3, ACTIVE_CANONICAL_WINDOWS), true);
  assert.equal(isValidSelection(3, ['MORNING', 'MIDDAY', 'AFTERNOON']), false);
  assert.equal(isValidSelection(4, ACTIVE_CANONICAL_WINDOWS), false);
});

test('WALK_20MIN metadata requires exactly one active canonical window', () => {
  const walk = services.services.WALK_20MIN;
  const isValidSelection = (selectedWindowIds) => (
    walk.windowSelectionMode === 'exactly_one'
    && selectedWindowIds.length === 1
    && walk.allowedWindowIds.includes(selectedWindowIds[0])
  );

  assert.equal(walk.durationMinutes, 20);
  assert.equal(walk.durationStatus, 'confirmed');
  assert.equal(isValidSelection(['MORNING']), true);
  assert.equal(isValidSelection(['MIDDAY']), true);
  assert.equal(isValidSelection(['EVENING']), true);
  assert.equal(isValidSelection([]), false);
  assert.equal(isValidSelection(['MORNING', 'EVENING']), false);
  assert.equal(isValidSelection(['AFTERNOON']), false);
});

// --- Pet Fields ---

test('pet-fields.json parses as valid JSON', async () => {
  petFields = JSON.parse(await readFile(PET_FIELDS_PATH, 'utf-8'));
  assert.ok(Array.isArray(petFields.clientReadFields), 'Missing clientReadFields array');
  assert.ok(Array.isArray(petFields.clientWriteFields), 'Missing clientWriteFields array');
});

test('pet field names are unique within each list', () => {
  const readSet = new Set(petFields.clientReadFields);
  assert.equal(readSet.size, petFields.clientReadFields.length, 'Duplicate in clientReadFields');
  const writeSet = new Set(petFields.clientWriteFields);
  assert.equal(writeSet.size, petFields.clientWriteFields.length, 'Duplicate in clientWriteFields');
});

test('pet field limits reference valid write fields', () => {
  const writeFields = new Set(petFields.clientWriteFields);
  for (const field of Object.keys(petFields.fieldLimits)) {
    assert.ok(writeFields.has(field), `Field limit "${field}" not in clientWriteFields`);
  }
});

test('customer health field limits match exact backend client PUT limits', () => {
  assert.deepEqual(
    petFields.clientWriteHealthFieldLimits,
    EXPECTED_CLIENT_WRITE_HEALTH_FIELD_LIMITS,
    'clientWriteHealthFieldLimits must contain exactly vet_name and vet_phone at backend limit 100'
  );
  assert.deepEqual(
    Object.keys(petFields.clientWriteHealthFieldLimits).sort(),
    [...petFields.clientWriteHealthSubfields].sort(),
    'clientWriteHealthFieldLimits keys must match clientWriteHealthSubfields'
  );
  for (const [field, limit] of Object.entries(petFields.clientWriteHealthFieldLimits)) {
    assert.ok(Number.isInteger(limit) && limit > 0, `Health field limit "${field}" must be a positive integer`);
  }
});

// --- API Paths ---

test('api-paths.json parses as valid JSON', async () => {
  apiPaths = JSON.parse(await readFile(API_PATHS_PATH, 'utf-8'));
  assert.ok(apiPaths.client, 'Missing "client" section');
  assert.ok(apiPaths.admin, 'Missing "admin" section');
  assert.ok(apiPaths.public, 'Missing "public" section');
});

test('API paths are relative and contain no hostname', () => {
  const allPaths = [
    ...Object.values(apiPaths.client),
    ...Object.values(apiPaths.admin),
    ...Object.values(apiPaths.public),
  ];
  for (const p of allPaths) {
    assert.ok(p.startsWith('/'), `Path "${p}" is not relative`);
    assert.ok(!p.includes('://'), `Path "${p}" contains a protocol`);
    assert.ok(!p.includes('.com'), `Path "${p}" contains a hostname`);
    assert.ok(!p.includes('amazonaws'), `Path "${p}" contains an AWS URL`);
  }
});

test('API paths contain no secrets or environment data', () => {
  const allPaths = [
    ...Object.values(apiPaths.client),
    ...Object.values(apiPaths.admin),
    ...Object.values(apiPaths.public),
  ];
  const pathsStr = JSON.stringify(allPaths);
  assert.ok(!pathsStr.includes('sk_'), 'Contains Stripe secret prefix');
  assert.ok(!pathsStr.includes('amazonaws.com'), 'Contains AWS hostname');
  assert.ok(!pathsStr.includes('://'), 'Contains protocol');
});

test('E3A admin child-job paths are canonical and explicit', () => {
  assert.equal(apiPaths.admin.getRequest, '/admin/requests/{requestId}');
  assert.equal(apiPaths.admin.jobStart, '/admin/job/start');
  assert.equal(apiPaths.admin.jobComplete, '/admin/job/complete');
  assert.equal(statuses.statuses.IN_PROGRESS, undefined, 'E3A must not canonicalize IN_PROGRESS');
});

test('contract metadata is present in all files', () => {
  assert.ok(statuses._contract, 'Statuses missing _contract');
  assert.ok(services._contract, 'Services missing _contract');
  assert.ok(petFields._contract, 'Pet fields missing _contract');
  assert.ok(apiPaths._contract, 'API paths missing _contract');
});
