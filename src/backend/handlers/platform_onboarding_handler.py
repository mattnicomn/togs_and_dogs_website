"""
src/backend/handlers/platform_onboarding_handler.py
Preview-Only V1: Platform Admin Tenant-Onboarding Orchestrator Handler

Routes:
  POST /platform/onboarding/validate  — field validation + conflict detection
  POST /platform/onboarding/preview   — full proposed metadata/audit preview + hash

AUTHORIZATION: platform_admin Cognito group required for all routes.

NO WRITES:
  - No DynamoDB PutItem, UpdateItem, DeleteItem
  - No Cognito user/group actions
  - No Apply or create endpoint exists
  - Every successful validation/preview response contains "no_writes": true

VALIDATION FLOW (/validate):
  1. Auth check (platform_admin)
  2. Body parse (bounded, max 4KB)
  3. Field allowlist check (reject unknown fields)
  4. Domain validation via tenant_provisioning (company_id, display_name, tier, status, notes)
  5. Conflict checks via tenant_read_adapter (existence, display_name collision)
  6. Return structured validation result

PREVIEW FLOW (/preview):
  1. Auth check (platform_admin)
  2. Body parse
  3. Field allowlist check
  4. Independent domain re-validation (preview never trusts stale client state)
  5. Conflict checks
  6. Build proposed metadata + audit record (never written)
  7. Build approval checklist (informational)
  8. Compute preview hash
  9. Return full preview payload with no_writes: true
"""

import json
import uuid
from datetime import datetime, timedelta, timezone

from common.auth import get_claims, is_platform_admin
from common.response import success, bad_request, error, internal_error
from common.tenant_catalog import (
    CATALOG_VERSION,
    get_tier_limits,
)
from common.tenant_provisioning import (
    ProvisioningValidationError,
    build_approval_checklist,
    build_proposed_audit,
    build_proposed_metadata,
    compute_preview_hash,
    validate_company_id,
    validate_display_name,
    validate_notes,
    validate_status,
    validate_tier,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Allowed request body fields — reject any others to prevent injection
_ALLOWED_FIELDS = frozenset({
    'company_id',
    'display_name',
    'subscription_tier',
    'subscription_status',
    'notes',
})

# Maximum request body size (bytes)
_MAX_BODY_BYTES = 4096

# Preview validity window (seconds) — informational only, frontend should respect it
_PREVIEW_VALIDITY_SECONDS = 15 * 60  # 15 minutes


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_body(event: dict) -> tuple[dict | None, str | None]:
    """Parse and bounded-check the request body. Returns (body_dict, error_msg)."""
    raw = event.get('body') or ''
    if isinstance(raw, bytes):
        raw = raw.decode('utf-8', errors='replace')

    if len(raw) > _MAX_BODY_BYTES:
        return None, f"Request body exceeds maximum size ({_MAX_BODY_BYTES} bytes)"

    if not raw.strip():
        return {}, None

    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        return None, f"Invalid JSON body: {exc}"

    if not isinstance(parsed, dict):
        return None, "Request body must be a JSON object"

    return parsed, None


def _check_unknown_fields(body: dict) -> str | None:
    """Return an error message if any unknown fields are present."""
    unknown = [f for f in body.keys() if f not in _ALLOWED_FIELDS]
    if unknown:
        return f"Unknown fields not permitted: {', '.join(sorted(unknown))}"
    return None


def _derive_actor(event: dict) -> str:
    """Derive a safe actor identifier from Cognito claims only."""
    claims = get_claims(event)
    actor = (
        claims.get('email') or
        claims.get('username') or
        claims.get('cognito:username') or
        'platform_admin:unknown'
    )
    # Sanitize — strip whitespace, truncate
    actor = str(actor).strip()[:200]
    return f"platform_admin:{actor}"


def _run_validation(body: dict) -> tuple[dict | None, list]:
    """
    Run field validation. Returns (validated_fields, errors_list).
    errors_list is empty on success.
    """
    validated = {}
    errors = []

    for field_name, validator in [
        ('company_id', validate_company_id),
        ('display_name', validate_display_name),
    ]:
        val = body.get(field_name)
        try:
            validated[field_name] = validator(val)
        except ProvisioningValidationError as exc:
            errors.append(exc.to_dict())

    # Optional fields with defaults
    try:
        validated['subscription_tier'] = validate_tier(body.get('subscription_tier'))
    except ProvisioningValidationError as exc:
        errors.append(exc.to_dict())

    try:
        validated['subscription_status'] = validate_status(body.get('subscription_status'))
    except ProvisioningValidationError as exc:
        errors.append(exc.to_dict())

    try:
        validated['notes'] = validate_notes(body.get('notes'))
    except ProvisioningValidationError as exc:
        errors.append(exc.to_dict())

    if errors:
        return None, errors

    return validated, []


def _run_conflict_checks(validated: dict) -> tuple[list, list]:
    """
    Run read-only conflict checks. Returns (errors, warnings).
    Errors prevent preview; warnings are informational.
    """
    from common.tenant_read_adapter import (
        check_display_name_conflict,
        get_tenant_by_company_id,
    )

    errors = []
    warnings = []

    # Existence check — cannot provision if company_id already exists
    try:
        existing = get_tenant_by_company_id(validated['company_id'])
        if existing:
            errors.append({
                'error': (
                    f"Tenant '{validated['company_id']}' already exists "
                    f"(status: {existing.get('subscription_status', 'unknown')})."
                ),
                'field': 'company_id',
            })
    except Exception as exc:
        print(f"ONBOARDING: conflict check (existence) failed: {exc}")
        errors.append({
            'error': 'Unable to verify company_id uniqueness due to a system error.',
            'field': 'company_id',
        })

    # Display-name collision warning (not a hard error)
    if not errors:
        try:
            conflicts = check_display_name_conflict(validated['display_name'])
            if conflicts:
                warnings.append({
                    'warning': (
                        f"Display name '{validated['display_name']}' is already used "
                        f"by: {', '.join(conflicts)}. "
                        "This is a warning only — display names are not required to be unique."
                    ),
                    'field': 'display_name',
                    'conflicting_tenants': conflicts,
                })
        except Exception as exc:
            print(f"ONBOARDING: conflict check (display_name) failed: {exc}")
            warnings.append({
                'warning': 'Unable to check display name uniqueness. Proceeding.',
                'field': 'display_name',
            })

    return errors, warnings


def _now_iso() -> str:
    """Current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


# ---------------------------------------------------------------------------
# Route Handlers
# ---------------------------------------------------------------------------


def _handle_validate(event: dict) -> dict:
    """
    POST /platform/onboarding/validate

    Returns validation results for the supplied onboarding fields.
    Never writes to DynamoDB.
    """
    body, parse_error = _parse_body(event)
    if parse_error:
        return bad_request(parse_error, event)

    unknown_err = _check_unknown_fields(body)
    if unknown_err:
        return bad_request(unknown_err, event)

    validated, field_errors = _run_validation(body)

    if field_errors:
        return success({
            'valid': False,
            'errors': field_errors,
            'warnings': [],
            'no_writes': True,
        }, event)

    conflict_errors, warnings = _run_conflict_checks(validated)

    if conflict_errors:
        return success({
            'valid': False,
            'errors': conflict_errors,
            'warnings': warnings,
            'no_writes': True,
        }, event)

    return success({
        'valid': True,
        'errors': [],
        'warnings': warnings,
        'validated_fields': {
            'company_id': validated['company_id'],
            'display_name': validated['display_name'],
            'subscription_tier': validated['subscription_tier'],
            'subscription_status': validated['subscription_status'],
        },
        'no_writes': True,
    }, event)


def _handle_preview(event: dict) -> dict:
    """
    POST /platform/onboarding/preview

    Returns the full proposed metadata, audit record, approval checklist,
    and preview hash. Never writes to DynamoDB.
    """
    body, parse_error = _parse_body(event)
    if parse_error:
        return bad_request(parse_error, event)

    unknown_err = _check_unknown_fields(body)
    if unknown_err:
        return bad_request(unknown_err, event)

    # Independent re-validation — preview never trusts stale client state
    validated, field_errors = _run_validation(body)
    if field_errors:
        return success({
            'preview_state': 'VALIDATION_FAILED',
            'errors': field_errors,
            'warnings': [],
            'no_writes': True,
        }, event)

    conflict_errors, warnings = _run_conflict_checks(validated)
    if conflict_errors:
        return success({
            'preview_state': 'CONFLICT_DETECTED',
            'errors': conflict_errors,
            'warnings': warnings,
            'no_writes': True,
        }, event)

    actor = _derive_actor(event)
    now_iso = _now_iso()
    audit_id = str(uuid.uuid4())

    # Build proposed records (never written)
    proposed_metadata = build_proposed_metadata(
        company_id=validated['company_id'],
        display_name=validated['display_name'],
        tier=validated['subscription_tier'],
        status=validated['subscription_status'],
        notes=validated['notes'],
        actor=actor,
        now_iso=now_iso,
    )

    proposed_audit = build_proposed_audit(
        company_id=validated['company_id'],
        proposed_metadata=proposed_metadata,
        actor=actor,
        audit_id=audit_id,
        now_iso=now_iso,
    )

    limits = get_tier_limits(validated['subscription_tier'])
    checklist = build_approval_checklist(
        validated['company_id'],
        validated['subscription_tier'],
        validated['subscription_status'],
    )

    preview_payload = {
        'proposed_metadata': proposed_metadata,
        'proposed_audit': proposed_audit,
        'tier_limits': limits,
        'approval_checklist': checklist,
        'catalog_version': CATALOG_VERSION,
        'generated_at': now_iso,
        'no_writes': True,
    }

    preview_hash = compute_preview_hash(preview_payload)

    return success({
        'preview_state': 'PREVIEW_READY',
        'message': (
            'Preview generated successfully. '
            'No data has been written. '
            'Tenant creation requires explicit Matthew approval and is not available in V1.'
        ),
        'preview_hash': preview_hash,
        'preview_valid_until': _compute_valid_until(now_iso),
        'warnings': warnings,
        'no_writes': True,
        **preview_payload,
    }, event)


def _compute_valid_until(now_iso: str) -> str:
    """Return an ISO timestamp 15 minutes after now_iso."""
    try:
        dt = datetime.fromisoformat(now_iso.replace('Z', '+00:00'))
        valid_until = dt + timedelta(seconds=_PREVIEW_VALIDITY_SECONDS)
        return valid_until.strftime('%Y-%m-%dT%H:%M:%SZ')
    except Exception:
        return now_iso


# ---------------------------------------------------------------------------
# Lambda Handler Entry Point
# ---------------------------------------------------------------------------


def handler(event: dict, context=None) -> dict:
    """
    Lambda entry point for /platform/onboarding/* routes.

    All routes require platform_admin authorization.
    """
    try:
        if not is_platform_admin(event):
            return error(403, "Forbidden: Platform Admin access required", event)

        http_method = event.get('httpMethod', '')
        path = event.get('path', '')

        if http_method == 'POST' and path == '/platform/onboarding/validate':
            return _handle_validate(event)
        elif http_method == 'POST' and path == '/platform/onboarding/preview':
            return _handle_preview(event)
        else:
            return error(404, "Not Found", event)

    except Exception as exc:
        print(f"ONBOARDING HANDLER ERROR: {exc}")
        return internal_error("An unexpected error occurred in the onboarding handler.", event)
