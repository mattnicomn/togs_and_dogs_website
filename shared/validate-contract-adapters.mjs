/**
 * Phase 24A-2A: Shared Contract Adapters Validation
 *
 * Validates generated web/src/generated/contracts.js and mobile/src/contracts/generatedContracts.ts
 * against canonical JSON files in shared/contracts/ and shared/constants/.
 * Uses Node.js built-in test runner — no dependencies required.
 *
 * Run: node shared/validate-contract-adapters.mjs
 */

import { readFile } from 'node:fs/promises';
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT_DIR = join(__dirname, '..');

const API_PATHS_FILE = join(__dirname, 'contracts', 'api-paths.json');
const PET_FIELDS_FILE = join(__dirname, 'constants', 'pet-fields.json');
const STATUSES_FILE = join(__dirname, 'constants', 'request-statuses.json');
const SERVICES_FILE = join(__dirname, 'constants', 'service-types.json');

const WEB_ADAPTER = join(ROOT_DIR, 'web', 'src', 'generated', 'contracts.js');
const MOBILE_ADAPTER = join(ROOT_DIR, 'mobile', 'src', 'contracts', 'generatedContracts.ts');

function parseGeneratedExport(source, exportName, nextExportName) {
  const pattern = new RegExp(
    `export const ${exportName} = ([\\s\\S]*?)(?: as const)?;\\r?\\nexport const ${nextExportName}`
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

  assert.ok(webCode.includes('export const API_PATHS'), 'Web adapter missing API_PATHS export');
  assert.ok(mobileCode.includes('export const API_PATHS'), 'Mobile adapter missing API_PATHS export');
  assert.ok(webCode.includes('export function buildPath'), 'Web adapter missing buildPath export');
  assert.ok(mobileCode.includes('export function buildPath'), 'Mobile adapter missing buildPath export');

  // Verify canonical paths are present in generated text
  assert.ok(webCode.includes('/client/requests'), 'Web adapter missing /client/requests');
  assert.ok(mobileCode.includes('/client/requests'), 'Mobile adapter missing /client/requests');
  assert.ok(webCode.includes('/client/pets/{petId}'), 'Web adapter missing /client/pets/{petId}');
  assert.ok(mobileCode.includes('/client/pets/{petId}'), 'Mobile adapter missing /client/pets/{petId}');
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

  // Import and run generator main
  const { default: child_process } = await import('node:child_process');
  child_process.execSync('node shared/generate-contract-adapters.mjs', { cwd: ROOT_DIR });

  const webAfter = await readFile(WEB_ADAPTER, 'utf-8');
  const mobileAfter = await readFile(MOBILE_ADAPTER, 'utf-8');

  assert.equal(webBefore, webAfter, 'Web adapter output changed on second run');
  assert.equal(mobileBefore, mobileAfter, 'Mobile adapter output changed on second run');
});
