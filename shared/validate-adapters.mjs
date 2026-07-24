/**
 * Phase 24A-1B: Generated Adapter Validation
 *
 * Validates that generated platform adapters match the shared contract.
 * Uses Node.js built-in test runner — no dependencies required.
 *
 * Run: node shared/validate-adapters.mjs
 */

import { readFile } from 'node:fs/promises';
import { readFileSync, writeFileSync } from 'node:fs';
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { execSync } from 'node:child_process';

const __dirname = dirname(fileURLToPath(import.meta.url));
const CONTRACT_PATH = join(__dirname, 'tokens', 'colors.json');
const WEB_OUTPUT = join(__dirname, '..', 'web', 'src', 'generated', 'color-tokens.css');
const MOBILE_OUTPUT = join(__dirname, '..', 'mobile', 'src', 'theme', 'generatedColors.ts');

// Token-to-platform-name mappings (must match generator)
const WEB_TOKEN_MAP = {
  primary: '--primary',
  primaryHover: '--primary-hover',
  background: '--page-bg',
  card: '--card-bg',
  textPrimary: '--text-primary',
  textMuted: '--text-muted',
  border: '--border-color',
  borderSoft: '--border-soft',
  success: '--success-color',
  danger: '--warning-color',
  info: '--info-color',
  warning: '--caution-color',
  white: '--white',
};

const MOBILE_TOKEN_MAP = {
  primary: 'primary',
  primaryHover: 'primaryHover',
  background: 'background',
  card: 'cardBg',
  textPrimary: 'text',
  textMuted: 'textMuted',
  border: 'border',
  borderSoft: 'borderSoft',
  success: 'success',
  danger: 'danger',
  info: 'info',
  warning: 'warning',
  white: 'white',
};

let contract;
let webContent;
let mobileContent;

test('load contract and generated files', async () => {
  contract = JSON.parse(await readFile(CONTRACT_PATH, 'utf-8'));
  webContent = await readFile(WEB_OUTPUT, 'utf-8');
  mobileContent = await readFile(MOBILE_OUTPUT, 'utf-8');
  assert.ok(contract.tokens);
  assert.ok(webContent.length > 0);
  assert.ok(mobileContent.length > 0);
});

test('web adapter contains all contract tokens with web values', () => {
  for (const [tokenName, token] of Object.entries(contract.tokens)) {
    const cssVar = WEB_TOKEN_MAP[tokenName];
    if (!cssVar) continue;
    const expected = `${cssVar}: ${token.web};`;
    assert.ok(
      webContent.includes(expected),
      `Web adapter missing "${expected}" for token "${tokenName}"`
    );
  }
});

test('mobile adapter contains all contract tokens with mobile values', () => {
  for (const [tokenName, token] of Object.entries(contract.tokens)) {
    const prop = MOBILE_TOKEN_MAP[tokenName];
    if (!prop) continue;
    const expected = `${prop}: '${token.mobile}'`;
    assert.ok(
      mobileContent.includes(expected),
      `Mobile adapter missing "${expected}" for token "${tokenName}"`
    );
  }
});

test('mismatched tokens remain different between platforms', () => {
  for (const [tokenName, token] of Object.entries(contract.tokens)) {
    if (token.aligned === false) {
      const webVar = WEB_TOKEN_MAP[tokenName];
      const mobileProp = MOBILE_TOKEN_MAP[tokenName];
      if (!webVar || !mobileProp) continue;
      // Verify web uses web value (not mobile value)
      const webExpected = `${webVar}: ${token.web};`;
      assert.ok(webContent.includes(webExpected),
        `Token "${tokenName}": web adapter should use web value "${token.web}"`);
      // Verify mobile uses mobile value (not web value)
      const mobileExpected = `${mobileProp}: '${token.mobile}'`;
      assert.ok(mobileContent.includes(mobileExpected),
        `Token "${tokenName}": mobile adapter should use mobile value "${token.mobile}"`);
    }
  }
});

test('generated files carry the required warning header', () => {
  assert.ok(
    webContent.includes('GENERATED FILE — DO NOT EDIT MANUALLY'),
    'Web adapter missing generated-file warning'
  );
  assert.ok(
    mobileContent.includes('GENERATED FILE — DO NOT EDIT MANUALLY'),
    'Mobile adapter missing generated-file warning'
  );
});

test('generator is deterministic (running twice produces identical output)', () => {
  // Run generator
  execSync('node shared/generate-adapters.mjs', { cwd: join(__dirname, '..') });
  // Read outputs again
  const webAfter = readFileSync(WEB_OUTPUT, 'utf-8');
  const mobileAfter = readFileSync(MOBILE_OUTPUT, 'utf-8');
  assert.equal(webAfter, webContent, 'Web adapter changed after re-running generator');
  assert.equal(mobileAfter, mobileContent, 'Mobile adapter changed after re-running generator');
});

test('generator fails on invalid contract', () => {
  const originalContent = readFileSync(CONTRACT_PATH, 'utf-8');
  try {
    writeFileSync(CONTRACT_PATH, '{ invalid json !!!', 'utf-8');
    let exitCode = 0;
    try {
      execSync('node shared/generate-adapters.mjs', {
        cwd: join(__dirname, '..'),
        stdio: 'pipe'
      });
    } catch (e) {
      exitCode = e.status;
    }
    assert.notEqual(exitCode, 0, 'Generator should exit nonzero for invalid JSON');
  } finally {
    // Restore original contract
    writeFileSync(CONTRACT_PATH, originalContent, 'utf-8');
  }
});
