/**
 * Phase 24A-1B: Platform Color Token Adapter Generator
 *
 * Reads shared/tokens/colors.json and generates:
 * - web/src/generated/color-tokens.css (CSS custom properties using web values)
 * - mobile/src/theme/generatedColors.ts (TypeScript COLORS export using mobile values)
 *
 * This script uses only Node.js built-in modules. No dependencies required.
 *
 * Run: node shared/generate-adapters.mjs
 *
 * RULES:
 * - The generated files use PLATFORM-SPECIFIC values (web→web, mobile→mobile).
 * - Phase 24A-1C will later align mismatched values. Until then, each platform
 *   keeps its existing colors exactly.
 * - Generated files carry a header warning against manual edits.
 * - Output is deterministic: no timestamps, stable key ordering.
 */

import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const CONTRACT_PATH = join(__dirname, 'tokens', 'colors.json');
const WEB_OUTPUT = join(__dirname, '..', 'web', 'src', 'generated', 'color-tokens.css');
const MOBILE_OUTPUT = join(__dirname, '..', 'mobile', 'src', 'theme', 'generatedColors.ts');

const HEX_PATTERN = /^#([0-9a-fA-F]{3}|[0-9a-fA-F]{4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$/;

// --- Token-to-platform-name mappings ---
// Web CSS variable names (preserving existing conventions from index.css)
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

// Mobile COLORS property names (preserving existing conventions from colors.ts)
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

async function main() {
  // 1. Read and validate contract
  const raw = await readFile(CONTRACT_PATH, 'utf-8');
  let contract;
  try {
    contract = JSON.parse(raw);
  } catch (e) {
    console.error('ERROR: shared/tokens/colors.json is not valid JSON');
    process.exit(1);
  }

  if (!contract.tokens || typeof contract.tokens !== 'object') {
    console.error('ERROR: Contract missing "tokens" object');
    process.exit(1);
  }

  const tokens = contract.tokens;

  // Validate all token values
  for (const [name, token] of Object.entries(tokens)) {
    if (!HEX_PATTERN.test(token.web)) {
      console.error(`ERROR: Token "${name}" web value "${token.web}" is not valid hex`);
      process.exit(1);
    }
    if (!HEX_PATTERN.test(token.mobile)) {
      console.error(`ERROR: Token "${name}" mobile value "${token.mobile}" is not valid hex`);
      process.exit(1);
    }
  }

  // 2. Generate web CSS adapter
  const webHeader = [
    '/* ============================================================',
    ' * GENERATED FILE — DO NOT EDIT MANUALLY',
    ' *',
    ' * Source: shared/tokens/colors.json',
    ' * Generator: shared/generate-adapters.mjs',
    ' * Phase: 24A-1B (platform token adapters)',
    ' *',
    ' * To regenerate: node shared/generate-adapters.mjs',
    ' * To modify colors: edit shared/tokens/colors.json, then regenerate.',
    ' * ============================================================ */',
    '',
  ];

  const webVars = [];
  for (const [tokenName, token] of Object.entries(tokens)) {
    const cssVar = WEB_TOKEN_MAP[tokenName];
    if (cssVar) {
      webVars.push(`  ${cssVar}: ${token.web};`);
    }
  }

  const webContent = [
    ...webHeader,
    ':root {',
    ...webVars,
    '}',
    '',
  ].join('\n');

  // 3. Generate mobile TypeScript adapter
  const mobileHeader = [
    '/* ============================================================',
    ' * GENERATED FILE — DO NOT EDIT MANUALLY',
    ' *',
    ' * Source: shared/tokens/colors.json',
    ' * Generator: shared/generate-adapters.mjs',
    ' * Phase: 24A-1B (platform token adapters)',
    ' *',
    ' * To regenerate: node shared/generate-adapters.mjs',
    ' * To modify colors: edit shared/tokens/colors.json, then regenerate.',
    ' * ============================================================ */',
    '',
  ];

  const mobileProps = [];
  for (const [tokenName, token] of Object.entries(tokens)) {
    const propName = MOBILE_TOKEN_MAP[tokenName];
    if (propName) {
      mobileProps.push(`  ${propName}: '${token.mobile}',`);
    }
  }

  const mobileContent = [
    ...mobileHeader,
    'export const COLORS = {',
    ...mobileProps,
    '};',
    '',
  ].join('\n');

  // 4. Write output files
  await mkdir(join(__dirname, '..', 'web', 'src', 'generated'), { recursive: true });

  await writeFile(WEB_OUTPUT, webContent, 'utf-8');
  console.log(`✔ Generated: web/src/generated/color-tokens.css`);

  await writeFile(MOBILE_OUTPUT, mobileContent, 'utf-8');
  console.log(`✔ Generated: mobile/src/theme/generatedColors.ts`);

  console.log(`✔ All ${Object.keys(tokens).length} tokens processed`);
}

main().catch((err) => {
  console.error('Generator failed:', err.message);
  process.exit(1);
});
