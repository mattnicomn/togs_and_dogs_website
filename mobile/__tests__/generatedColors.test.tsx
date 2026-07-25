/**
 * Phase 24A-3: Generated Color Token Compatibility Test
 *
 * Verifies the generated mobile adapter imports correctly and
 * preserves the expected COLORS API matching the shared contract.
 */
import { COLORS } from '../src/theme/colors';

import * as fs from 'fs';
import * as path from 'path';

const contractPath = path.join(__dirname, '..', '..', 'shared', 'tokens', 'colors.json');
const contract = JSON.parse(fs.readFileSync(contractPath, 'utf-8'));

const MOBILE_TOKEN_MAP: Record<string, string> = {
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

describe('Generated Color Token Compatibility', () => {
  it('COLORS object is defined and non-empty', () => {
    expect(COLORS).toBeDefined();
    expect(Object.keys(COLORS).length).toBeGreaterThan(0);
  });

  it('all contract mobile tokens are present in COLORS', () => {
    for (const [tokenName, token] of Object.entries(contract.tokens) as [string, any][]) {
      const propName = MOBILE_TOKEN_MAP[tokenName];
      if (!propName) continue;
      expect((COLORS as any)[propName]).toBeDefined();
    }
  });

  it('COLORS values match the shared contract mobile values', () => {
    for (const [tokenName, token] of Object.entries(contract.tokens) as [string, any][]) {
      const propName = MOBILE_TOKEN_MAP[tokenName];
      if (!propName) continue;
      expect((COLORS as any)[propName]).toBe(token.mobile);
    }
  });

  it('preserves existing property names for backward compatibility', () => {
    expect(COLORS.primary).toBeDefined();
    expect(COLORS.primaryHover).toBeDefined();
    expect(COLORS.background).toBeDefined();
    expect(COLORS.cardBg).toBeDefined();
    expect(COLORS.text).toBeDefined();
    expect(COLORS.textMuted).toBeDefined();
    expect(COLORS.border).toBeDefined();
    expect(COLORS.borderSoft).toBeDefined();
    expect(COLORS.success).toBeDefined();
    expect(COLORS.danger).toBeDefined();
    expect(COLORS.info).toBeDefined();
    expect(COLORS.white).toBeDefined();
  });
});
