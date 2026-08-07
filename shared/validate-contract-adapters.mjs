/**
 * Phase 24A-2A: Shared Contract Adapters Validation
 *
 * Validates generated web, mobile, and backend adapters against canonical JSON
 * files in shared/contracts/ and shared/constants/.
 * Uses Node.js built-in test runner — no dependencies required.
 *
 * Run: node shared/validate-contract-adapters.mjs
 */

import { readFile } from 'node:fs/promises';
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { spawnSync } from 'node:child_process';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT_DIR = join(__dirname, '..');

const API_PATHS_FILE = join(__dirname, 'contracts', 'api-paths.json');
const PET_FIELDS_FILE = join(__dirname, 'constants', 'pet-fields.json');
const STATUSES_FILE = join(__dirname, 'constants', 'request-statuses.json');
const SERVICES_FILE = join(__dirname, 'constants', 'service-types.json');

const WEB_ADAPTER = join(ROOT_DIR, 'web', 'src', 'generated', 'contracts.js');
const MOBILE_ADAPTER = join(ROOT_DIR, 'mobile', 'src', 'contracts', 'generatedContracts.ts');
const BACKEND_ADAPTER = join(ROOT_DIR, 'src', 'backend', 'common', 'generated_service_types.py');

const SERVICE_FIELDS = [
  'label',
  'labelLong',
  'durationMinutes',
  'availableInIntake',
  'supportedOnMobile',
];

const PYTHON_AST_EXTRACTOR = `
import ast
import json
from pathlib import Path
import sys

path = Path(sys.argv[1])
source = path.read_text(encoding="utf-8")

try:
    module = ast.parse(source, filename=str(path))
except SyntaxError as error:
    raise SystemExit(f"INVALID_PYTHON_SYNTAX: {error}")

if len(module.body) != 1:
    raise SystemExit("INVALID_ASSIGNMENT_STRUCTURE: expected exactly one executable statement")

assignment = module.body[0]
if not isinstance(assignment, ast.Assign):
    raise SystemExit("INVALID_ASSIGNMENT_STRUCTURE: expected a direct assignment")
if len(assignment.targets) != 1:
    raise SystemExit("INVALID_ASSIGNMENT_STRUCTURE: expected exactly one assignment target")

target = assignment.targets[0]
if not isinstance(target, ast.Name) or target.id != "SERVICE_TYPES":
    raise SystemExit("INVALID_ASSIGNMENT_STRUCTURE: expected assignment to SERVICE_TYPES")

try:
    value = ast.literal_eval(assignment.value)
except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError) as error:
    raise SystemExit(f"INVALID_ASSIGNMENT_STRUCTURE: SERVICE_TYPES must be a literal: {error}")

try:
    print(json.dumps(value, ensure_ascii=False, allow_nan=False))
except (TypeError, ValueError) as error:
    raise SystemExit(f"INVALID_ASSIGNMENT_STRUCTURE: SERVICE_TYPES is not JSON-compatible: {error}")
`;

function pythonLaunchers() {
  if (process.platform === 'win32') {
    return [
      { command: 'python', prefixArgs: [] },
      { command: 'py', prefixArgs: ['-3'] },
      { command: 'python3', prefixArgs: [] },
    ];
  }
  return [
    { command: 'python3', prefixArgs: [] },
    { command: 'python', prefixArgs: [] },
  ];
}

function parseGeneratedPythonServiceTypes() {
  const unavailable = [];

  for (const launcher of pythonLaunchers()) {
    const displayName = [launcher.command, ...launcher.prefixArgs].join(' ');
    const result = spawnSync(
      launcher.command,
      [...launcher.prefixArgs, '-c', PYTHON_AST_EXTRACTOR, BACKEND_ADAPTER],
      { encoding: 'utf-8', windowsHide: true }
    );

    if (result.error?.code === 'ENOENT') {
      unavailable.push(`${displayName}: command not found`);
      continue;
    }
    if (result.error) {
      throw new Error(`Python adapter parser failed to launch with ${displayName}: ${result.error.message}`);
    }

    if (result.status === 0) {
      try {
        return JSON.parse(result.stdout);
      } catch (error) {
        throw new Error(`Python adapter parser returned invalid JSON with ${displayName}: ${error.message}`);
      }
    }

    const detail = [result.stderr, result.stdout].filter(Boolean).join('\n').trim();
    if (/No installed Python found|Python was not found|command not found|not recognized/i.test(detail)) {
      unavailable.push(`${displayName}: ${detail}`);
      continue;
    }

    throw new Error(`Python adapter parsing failed with ${displayName}: ${detail || `exit ${result.status}`}`);
  }

  throw new Error(`No usable Python interpreter found. Attempts: ${unavailable.join(' | ')}`);
}

function assertServiceTypesShape(adapter, canonical, adapterName) {
  assert.deepEqual(
    Object.keys(adapter),
    Object.keys(canonical),
    `${adapterName} SERVICE_TYPES root membership or order differs`
  );
  assert.ok(
    adapter.services !== null && typeof adapter.services === 'object' && !Array.isArray(adapter.services),
    `${adapterName} SERVICE_TYPES services must be an object`
  );
  assert.deepEqual(
    Object.keys(adapter.services),
    Object.keys(canonical.services),
    `${adapterName} SERVICE_TYPES identifier membership or order differs`
  );

  for (const serviceId of Object.keys(canonical.services)) {
    const metadata = adapter.services[serviceId];
    assert.deepEqual(
      Object.keys(metadata),
      SERVICE_FIELDS,
      `${adapterName} ${serviceId} metadata membership or order differs`
    );
    assert.equal(typeof metadata.label, 'string', `${adapterName} ${serviceId} label must be a string`);
    assert.equal(typeof metadata.labelLong, 'string', `${adapterName} ${serviceId} labelLong must be a string`);
    assert.ok(
      Number.isInteger(metadata.durationMinutes) && metadata.durationMinutes > 0,
      `${adapterName} ${serviceId} durationMinutes must be a positive integer`
    );
    assert.equal(
      typeof metadata.availableInIntake,
      'boolean',
      `${adapterName} ${serviceId} availableInIntake must be a boolean`
    );
    assert.equal(
      typeof metadata.supportedOnMobile,
      'boolean',
      `${adapterName} ${serviceId} supportedOnMobile must be a boolean`
    );
  }
}

function parseGeneratedExport(source, exportName, nextExportName = null) {
  const terminator = nextExportName
    ? `export const ${nextExportName}`
    : '(?:/\\*\\*|export function)';
  const pattern = new RegExp(
    `export const ${exportName} = ([\\s\\S]*?)(?: as const)?;\\r?\\n(?:\\r?\\n)?${terminator}`
  );
  const match = source.match(pattern);
  assert.ok(match, `Unable to parse generated ${exportName} export`);
  return JSON.parse(match[1]);
}

test('load canonical JSON contracts and generated adapters', async () => {
  const apiPaths = JSON.parse(await readFile(API_PATHS_FILE, 'utf-8'));
  const petFields = JSON.parse(await readFile(PET_FIELDS_FILE, 'utf-8'));
  const statuses = JSON.parse(await readFile(STATUSES_FILE, 'utf-8'));
  const services = JSON.parse(await readFile(SERVICES_FILE, 'utf-8'));

  const webCode = await readFile(WEB_ADAPTER, 'utf-8');
  const mobileCode = await readFile(MOBILE_ADAPTER, 'utf-8');
  const backendCode = await readFile(BACKEND_ADAPTER, 'utf-8');

  assert.ok(webCode.includes('export const API_PATHS'), 'Web adapter missing API_PATHS export');
  assert.ok(mobileCode.includes('export const API_PATHS'), 'Mobile adapter missing API_PATHS export');
  assert.ok(webCode.includes('export function buildPath'), 'Web adapter missing buildPath export');
  assert.ok(mobileCode.includes('export function buildPath'), 'Mobile adapter missing buildPath export');
  assert.ok(backendCode.includes('SERVICE_TYPES ='), 'Backend adapter missing SERVICE_TYPES assignment');

  // Verify canonical paths are present in generated text
  assert.ok(webCode.includes('/client/requests'), 'Web adapter missing /client/requests');
  assert.ok(mobileCode.includes('/client/requests'), 'Mobile adapter missing /client/requests');
  assert.ok(webCode.includes('/client/pets/{petId}'), 'Web adapter missing /client/pets/{petId}');
  assert.ok(mobileCode.includes('/client/pets/{petId}'), 'Mobile adapter missing /client/pets/{petId}');
});

test('generated backend adapter is valid Python with one safe SERVICE_TYPES assignment', () => {
  const backendServices = parseGeneratedPythonServiceTypes();
  assert.ok(backendServices.services, 'Backend adapter missing services object');
});

test('buildPath helper substitutes and encodes parameters correctly', async () => {
  const { buildPath } = await import(`file:///${WEB_ADAPTER.replace(/\\/g, '/')}`);

  const routeTemplate = '/client/pets/{petId}';
  const result = buildPath(routeTemplate, { petId: 'pet 123&special' });
  assert.equal(result, '/client/pets/pet%20123%26special');

  const multiTemplate = '/admin/{resource}/{id}';
  const multiResult = buildPath(multiTemplate, { resource: 'staff', id: 'usr#1' });
  assert.equal(multiResult, '/admin/staff/usr%231');
});

test('generated adapters contain the complete canonical PET_FIELDS contract', async () => {
  const canonical = JSON.parse(await readFile(PET_FIELDS_FILE, 'utf-8'));
  const cleanCanonical = Object.fromEntries(
    Object.entries(canonical).filter(([key]) => !key.startsWith('_'))
  );
  const webCode = await readFile(WEB_ADAPTER, 'utf-8');
  const mobileCode = await readFile(MOBILE_ADAPTER, 'utf-8');

  assert.deepEqual(
    parseGeneratedExport(webCode, 'PET_FIELDS', 'REQUEST_STATUSES'),
    cleanCanonical,
    'Web PET_FIELDS adapter differs from canonical contract'
  );
  assert.deepEqual(
    parseGeneratedExport(mobileCode, 'PET_FIELDS', 'REQUEST_STATUSES'),
    cleanCanonical,
    'Mobile PET_FIELDS adapter differs from canonical contract'
  );
});

test('generated adapters contain the complete canonical REQUEST_STATUSES contract', async () => {
  const canonical = JSON.parse(await readFile(STATUSES_FILE, 'utf-8'));
  const cleanCanonical = Object.fromEntries(
    Object.entries(canonical).filter(([key]) => !key.startsWith('_'))
  );
  const webCode = await readFile(WEB_ADAPTER, 'utf-8');
  const mobileCode = await readFile(MOBILE_ADAPTER, 'utf-8');

  const webStatuses = parseGeneratedExport(webCode, 'REQUEST_STATUSES', 'SERVICE_TYPES');
  const mobileStatuses = parseGeneratedExport(mobileCode, 'REQUEST_STATUSES', 'SERVICE_TYPES');

  assert.deepEqual(
    webStatuses,
    cleanCanonical,
    'Web REQUEST_STATUSES adapter differs from canonical contract'
  );
  assert.deepEqual(
    mobileStatuses,
    cleanCanonical,
    'Mobile REQUEST_STATUSES adapter differs from canonical contract'
  );
  assert.deepEqual(
    webStatuses,
    mobileStatuses,
    'Web and mobile REQUEST_STATUSES adapters differ from one another'
  );
});

test('generated adapters contain the complete canonical SERVICE_TYPES contract', async () => {
  const canonical = JSON.parse(await readFile(SERVICES_FILE, 'utf-8'));
  const cleanCanonical = Object.fromEntries(
    Object.entries(canonical).filter(([key]) => !key.startsWith('_'))
  );
  const webCode = await readFile(WEB_ADAPTER, 'utf-8');
  const mobileCode = await readFile(MOBILE_ADAPTER, 'utf-8');
  const webServices = parseGeneratedExport(webCode, 'SERVICE_TYPES');
  const mobileServices = parseGeneratedExport(mobileCode, 'SERVICE_TYPES');
  const backendServices = parseGeneratedPythonServiceTypes();

  assertServiceTypesShape(webServices, cleanCanonical, 'Web');
  assertServiceTypesShape(mobileServices, cleanCanonical, 'Mobile');
  assertServiceTypesShape(backendServices, cleanCanonical, 'Backend');

  assert.deepEqual(
    webServices,
    cleanCanonical,
    'Canonical-to-web SERVICE_TYPES equality failed'
  );
  assert.deepEqual(
    mobileServices,
    cleanCanonical,
    'Canonical-to-mobile SERVICE_TYPES equality failed'
  );
  assert.deepEqual(
    backendServices,
    cleanCanonical,
    'Canonical-to-backend SERVICE_TYPES equality failed'
  );
  assert.deepEqual(
    webServices,
    mobileServices,
    'Web-to-mobile SERVICE_TYPES equality failed'
  );
  assert.deepEqual(
    webServices,
    backendServices,
    'Web-to-backend SERVICE_TYPES equality failed'
  );
  assert.deepEqual(
    mobileServices,
    backendServices,
    'Mobile-to-backend SERVICE_TYPES equality failed'
  );

  assert.equal(
    JSON.stringify(webServices),
    JSON.stringify(cleanCanonical),
    'Canonical-to-web SERVICE_TYPES identifier or metadata order differs'
  );
  assert.equal(
    JSON.stringify(mobileServices),
    JSON.stringify(cleanCanonical),
    'Canonical-to-mobile SERVICE_TYPES identifier or metadata order differs'
  );
  assert.equal(
    JSON.stringify(backendServices),
    JSON.stringify(cleanCanonical),
    'Canonical-to-backend SERVICE_TYPES identifier or metadata order differs'
  );
});

test('buildPath throws on missing required parameter', async () => {
  const { buildPath } = await import(`file:///${WEB_ADAPTER.replace(/\\/g, '/')}`);

  assert.throws(
    () => buildPath('/client/pets/{petId}', {}),
    /Missing required path parameter: petId/
  );
});

test('API path values contain no hostnames, credentials, or protocols', async () => {
  const webCode = await readFile(WEB_ADAPTER, 'utf-8');
  assert.ok(!webCode.includes('://'), 'Contains protocol');
  assert.ok(!webCode.includes('.com'), 'Contains hostname');
  assert.ok(!webCode.includes('amazonaws'), 'Contains AWS domain');
});

test('generator is deterministic and produces zero second diff', async () => {
  const webBefore = await readFile(WEB_ADAPTER, 'utf-8');
  const mobileBefore = await readFile(MOBILE_ADAPTER, 'utf-8');
  const backendBefore = await readFile(BACKEND_ADAPTER, 'utf-8');

  // Import and run generator main
  const { default: child_process } = await import('node:child_process');
  child_process.execSync('node shared/generate-contract-adapters.mjs', { cwd: ROOT_DIR });

  const webAfter = await readFile(WEB_ADAPTER, 'utf-8');
  const mobileAfter = await readFile(MOBILE_ADAPTER, 'utf-8');
  const backendAfter = await readFile(BACKEND_ADAPTER, 'utf-8');

  assert.equal(webBefore, webAfter, 'Web adapter output changed on second run');
  assert.equal(mobileBefore, mobileAfter, 'Mobile adapter output changed on second run');
  assert.equal(backendBefore, backendAfter, 'Backend adapter output changed on second run');
});
