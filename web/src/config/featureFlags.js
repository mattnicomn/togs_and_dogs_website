// Build-time web feature flags.
//
// VITE_W1_EXISTING_PET_SELECTION — Workstream 1 existing-pet selection in the
// client intake form (canonical `pet_ids` submission).
//
// Enabled ONLY when the build-time value is exactly the string "true". Every
// other value — "false", empty, unset, "TRUE", "1", etc. — is OFF.
//
// This is a RELEASE-COMPATIBILITY switch, NOT an authorization or security
// boundary. It exists so a web build can ship while the deployed intake backend
// predates W1 ownership validation. The pre-W1 intake backend must still never
// be treated as safely validating untrusted client `pet_ids`; server-side
// ownership validation only exists once the W1 intake release is authorized
// and deployed.
export const isExistingPetSelectionEnabled = () =>
  import.meta.env.VITE_W1_EXISTING_PET_SELECTION === 'true';
