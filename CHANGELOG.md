# Changelog

## [1.1.0] - 2026-04-20

### Fixed
- **Production Persistence Bug**: Resolved 'Failed to fetch' and 500 errors on pet record updates by fixing API Gateway CORS and adding `Decimal` serialization support in the backend.
- **Data Lifecycle**: Fixed a gap where `PET` entities were not being created during the intake approval process.
- **Security**: Implemented protected admin guardrails to prevent accidental deletion or disabling of platform support accounts.
- **Staff Management**: Enhanced UI to distinguish protected accounts and prevent self-disabling.
- **Assignments**: Admin/Owner roles now default to non-assignable state.

### Added
- **Interactive Care Card**: Implemented a stateful edit mode in the `CareCard` component, allowing administrators to modify pet names, breeds, ages, and care instructions directly.
- **Safety Guardrails**: Added logic to verify `pet_id` presence before allowing edits, preventing malformed requests for unpersisted records.

### Infrastructure
- Updated Terraform modules to support `PUT`, `PATCH`, and `DELETE` methods in API Gateway.
- Added automated `PET` record creation in the `job_handler` Lambda.
