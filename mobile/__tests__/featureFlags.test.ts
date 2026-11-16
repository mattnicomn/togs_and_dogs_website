/**
 * M-1: EXPO_PUBLIC_W1_EXISTING_PET_SELECTION semantics (off unless exactly "true").
 */
import * as fs from 'fs';
import * as path from 'path';
import {
  isExistingPetSelectionEnabled,
  resolveExistingPetSelectionEnabled,
} from '../src/config/featureFlags';

const FLAG = 'EXPO_PUBLIC_W1_EXISTING_PET_SELECTION';

describe('resolveExistingPetSelectionEnabled', () => {
  test('absent or null is OFF', () => {
    expect(resolveExistingPetSelectionEnabled(undefined)).toBe(false);
    expect(resolveExistingPetSelectionEnabled(null)).toBe(false);
  });

  test('"false" and other non-exact values are OFF', () => {
    ['false', '', ' ', 'TRUE', 'True', '1', 'yes', 'on', ' true', 'true '].forEach((value) => {
      expect(resolveExistingPetSelectionEnabled(value)).toBe(false);
    });
  });

  test('exactly "true" is ON', () => {
    expect(resolveExistingPetSelectionEnabled('true')).toBe(true);
  });
});

describe('isExistingPetSelectionEnabled', () => {
  const original = process.env[FLAG];

  afterEach(() => {
    if (original === undefined) {
      delete process.env[FLAG];
    } else {
      process.env[FLAG] = original;
    }
  });

  test('defaults to OFF when the variable is not set', () => {
    delete process.env[FLAG];
    expect(isExistingPetSelectionEnabled()).toBe(false);
  });

  test('is OFF for "false" and ON only for "true"', () => {
    process.env[FLAG] = 'false';
    expect(isExistingPetSelectionEnabled()).toBe(false);
    process.env[FLAG] = 'true';
    expect(isExistingPetSelectionEnabled()).toBe(true);
  });

  test('reads the variable through a static literal reference (Expo inlining)', () => {
    const source = fs.readFileSync(path.join(__dirname, '..', 'src', 'config', 'featureFlags.ts'), 'utf8');
    expect(source).toContain('process.env.EXPO_PUBLIC_W1_EXISTING_PET_SELECTION');
  });

  test('no EAS build profile enables the flag', () => {
    const eas = fs.readFileSync(path.join(__dirname, '..', 'eas.json'), 'utf8');
    expect(eas).not.toContain(FLAG);
  });
});
