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
const API_PATH_PATTERN = /^\/[a-z][a-z0-9/_{}?=-]*$/;

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
    assert.ok('label' in svc, `Service "${id}" missing label`);
    assert.ok('durationMinutes' in svc, `Service "${id}" missing durationMinutes`);
    assert.ok(typeof svc.durationMinutes === 'number', `Service "${id}" durationMinutes not a number`);
  }
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

test('contract metadata is present in all files', () => {
  assert.ok(statuses._contract, 'Statuses missing _contract');
  assert.ok(services._contract, 'Services missing _contract');
  assert.ok(petFields._contract, 'Pet fields missing _contract');
  assert.ok(apiPaths._contract, 'API paths missing _contract');
});
