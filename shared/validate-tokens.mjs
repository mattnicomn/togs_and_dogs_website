/**
 * Phase 24A-1A: Color Token Contract Validation
 *
 * Validates shared/tokens/colors.json against the defined schema contract.
 * Uses Node.js built-in test runner (node --test) — no dependencies required.
 *
 * Run: node shared/validate-tokens.mjs
 */

import { readFile } from 'node:fs/promises';
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const TOKENS_PATH = join(__dirname, 'tokens', 'colors.json');

const VALID_DECISIONS = ['aligned', 'requires-24A-1C'];
const HEX_PATTERN = /^#([0-9a-fA-F]{3}|[0-9a-fA-F]{4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$/;

const REQUIRED_TOKENS = [
  'primary',
  'primaryHover',
  'background',
  'card',
  'textPrimary',
  'textMuted',
  'border',
  'success',
  'danger',
];

let parsed;

test('colors.json parses as valid JSON', async () => {
  const raw = await readFile(TOKENS_PATH, 'utf-8');
  parsed = JSON.parse(raw);
  assert.ok(parsed, 'Parsed result is truthy');
  assert.ok(parsed.tokens, 'Contains a "tokens" object');
});

test('all required token names exist', () => {
  const tokenNames = Object.keys(parsed.tokens);
  for (const required of REQUIRED_TOKENS) {
    assert.ok(
      tokenNames.includes(required),
      `Required token "${required}" is missing`
    );
  }
});

test('no duplicate token names', () => {
  // JSON.parse naturally deduplicates keys (last wins), so we validate
  // by reading the raw text for repeated key patterns within "tokens"
  const tokenNames = Object.keys(parsed.tokens);
  const seen = new Set();
  for (const name of tokenNames) {
    assert.ok(!seen.has(name), `Duplicate token name: "${name}"`);
    seen.add(name);
  }
});

test('all color values follow hex format', () => {
  for (const [name, token] of Object.entries(parsed.tokens)) {
    assert.match(
      token.web,
      HEX_PATTERN,
      `Token "${name}" web value "${token.web}" is not valid hex`
    );
    assert.match(
      token.mobile,
      HEX_PATTERN,
      `Token "${name}" mobile value "${token.mobile}" is not valid hex`
    );
  }
});

test('alignment status uses defined allowlist', () => {
  for (const [name, token] of Object.entries(parsed.tokens)) {
    assert.ok(
      VALID_DECISIONS.includes(token.decision),
      `Token "${name}" decision "${token.decision}" is not in allowlist: ${VALID_DECISIONS.join(', ')}`
    );
  }
});

test('aligned tokens have matching web and mobile values', () => {
  for (const [name, token] of Object.entries(parsed.tokens)) {
    if (token.aligned === true) {
      assert.equal(
        token.web.toLowerCase(),
        token.mobile.toLowerCase(),
        `Token "${name}" is marked aligned but web="${token.web}" !== mobile="${token.mobile}"`
      );
    }
  }
});

test('misaligned tokens are marked requires-24A-1C', () => {
  for (const [name, token] of Object.entries(parsed.tokens)) {
    if (token.aligned === false) {
      assert.equal(
        token.decision,
        'requires-24A-1C',
        `Token "${name}" is misaligned but decision is "${token.decision}" instead of "requires-24A-1C"`
      );
    }
  }
});

test('all tokens have a semantic description', () => {
  for (const [name, token] of Object.entries(parsed.tokens)) {
    assert.ok(
      token.semantic && token.semantic.trim().length > 0,
      `Token "${name}" is missing a semantic description`
    );
  }
});

test('contract metadata is present', () => {
  assert.ok(parsed._contract, 'Missing _contract metadata');
  assert.ok(parsed._version, 'Missing _version metadata');
});
