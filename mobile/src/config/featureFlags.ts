/**
 * Build-time mobile feature flags.
 *
 * EXPO_PUBLIC_W1_EXISTING_PET_SELECTION — Workstream 1 existing-pet selection
 * in the client intake (canonical `pet_ids` / `pets[].pet_id` submission).
 *
 * Enabled ONLY when the build-time value is exactly the string "true". Every
 * other value — "false", empty, unset, "TRUE", "1", " true", etc. — is OFF.
 * No EAS profile sets it, so production builds default to OFF.
 *
 * This is a RELEASE-COMPATIBILITY switch, NOT an authorization or security
 * boundary. It mirrors the web flag VITE_W1_EXISTING_PET_SELECTION so an
 * Android build can ship while the deployed intake backend predates W1
 * ownership validation. Enable it only after the W1 intake release is
 * authorized and deployed.
 *
 * Expo SDK 54 inlines EXPO_PUBLIC_* only for literal
 * `process.env.EXPO_PUBLIC_<NAME>` references (see src/api/config.ts), so the
 * variable is read statically here and the pure resolver is unit-tested.
 */
export const resolveExistingPetSelectionEnabled = (value: string | undefined | null): boolean =>
  value === 'true';

export const isExistingPetSelectionEnabled = (): boolean =>
  resolveExistingPetSelectionEnabled(process.env.EXPO_PUBLIC_W1_EXISTING_PET_SELECTION);
