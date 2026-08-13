#!/usr/bin/env python3
"""
scripts/provision_tenant.py
Release 17W: Tenant Provisioning Script

Safe tenant metadata seed tool for the usmissionhero SaaS platform.

MODES:
  --dry-run  (DEFAULT) — Print the proposed tenant metadata, audit record,
             Cognito command templates, and rollback plan. No AWS writes.
  --apply    — Write tenant metadata and audit record to DynamoDB.
             Requires --confirm-apply flag. NOT approved for production use
             until explicitly gate-approved by Matthew.

USAGE:
  # Dry-run (safe, default):
  python scripts/provision_tenant.py --company-id <COMPANY_ID> --display-name "<NAME>"

  # Apply mode (requires explicit confirmation — NOT YET APPROVED):
  python scripts/provision_tenant.py --company-id <COMPANY_ID> --display-name "<NAME>" \
      --apply --confirm-apply --aws-profile <PROFILE>

GUARDRAILS:
  - DEFAULT is dry-run. Script will not write unless --apply AND --confirm-apply are both set.
  - Script never creates Cognito users or groups. It only prints CLI command templates.
  - Script never modifies existing tenant metadata unless --force-overwrite is set.
  - Script never touches payment, Stripe, OAuth, or secret fields.
  - No private user data, credentials, or tokens are included in output or records.
"""

import argparse
import json
from pathlib import Path
import sys
import uuid
from datetime import datetime, timezone

# Make the shared backend domain importable when this file is executed directly.
BACKEND_SRC = Path(__file__).resolve().parents[1] / 'src' / 'backend'
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from common.tenant_catalog import (  # noqa: E402
    VALID_STATUSES,
    VALID_TIERS,
    get_all_tier_limits,
)
from common.tenant_provisioning import (  # noqa: E402
    ProvisioningValidationError,
    build_proposed_audit,
    build_proposed_metadata,
    validate_company_id,
    validate_display_name,
    validate_notes,
    validate_status,
    validate_tier,
)

# Backwards-compatible public symbol for existing tests/importers. This is a
# detached copy, so mutations cannot change the canonical catalog.
TIER_LIMITS = get_all_tier_limits()


# ---------------------------------------------------------------------------
# Metadata Builder
# ---------------------------------------------------------------------------

def build_tenant_metadata(company_id, display_name, tier='starter',
                           status='active', notes='', actor='platform_admin:system'):
    """
    Build the DynamoDB tenant metadata record dict.

    Keys match the TENANT#<company_id>/METADATA schema used in production.
    Payment keys, OAuth tokens, and Stripe secrets are intentionally excluded.
    """
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    return build_proposed_metadata(
        company_id=company_id,
        display_name=display_name,
        tier=tier,
        status=status,
        notes=notes,
        actor=actor,
        now_iso=now,
        default_notes=f'Provisioned via provision_tenant.py on {now}',
    )


def build_audit_record(company_id, metadata, actor):
    """
    Build the PLATFORM_AUDIT record for the provisioning action.

    Uses the same schema as platform_handler.py _handle_patch_tenant audit writes.
    Idempotency: the audit SK includes a UUID, so a second run produces a new audit
    record rather than overwriting. The provisioning idempotency check (tenant already
    exists) prevents duplicate metadata writes; duplicate audit records are benign.
    """
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    return build_proposed_audit(
        company_id=company_id,
        proposed_metadata=metadata,
        actor=actor,
        audit_id=str(uuid.uuid4()),
        now_iso=now,
    )


# ---------------------------------------------------------------------------
# Cognito Command Templates
# ---------------------------------------------------------------------------

def print_cognito_templates(company_id):
    """
    Print placeholder Cognito CLI command templates only.

    DOES NOT execute any commands or create any users or groups.
    Matthew must execute these manually after explicit approval gate.

    IMPORTANT ROLE RULES:
    - The tenant owner must be added to the 'owner' Cognito group for their company.
    - The tenant owner must NEVER receive 'platform_admin' group membership.
    - 'platform_admin' is reserved for usmissionhero operators only.
    - All <PLACEHOLDER> values must be replaced with real values by Matthew before running.
    """
    print("\n" + "=" * 60)
    print("COGNITO CLI COMMAND TEMPLATES (placeholder only — do not execute as-is)")
    print("Replace ALL <PLACEHOLDER> values before running.")
    print("Execute ONLY after Matthew's explicit approval gate.")
    print("=" * 60)

    print("""
STEP 1 — Create the tenant owner Cognito user:
  aws cognito-idp admin-create-user \\
      --user-pool-id <USER_POOL_ID> \\
      --username <USERNAME_OR_EMAIL> \\
      --user-attributes Name=email,Value=<EMAIL> \\
                        Name=custom:company_id,Value={company_id} \\
      --temporary-password <TEMP_PASSWORD> \\
      --message-action SUPPRESS \\
      --profile <AWS_PROFILE>

  NOTE: custom:company_id MUST be set to '{company_id}' (the new tenant ID).
  NOTE: Do NOT set custom:company_id to 'tog_and_dogs' (the existing production tenant).

STEP 2 — Add the tenant owner to the 'owner' group (tenant-level access):
  aws cognito-idp admin-add-user-to-group \\
      --user-pool-id <USER_POOL_ID> \\
      --username <USERNAME_OR_EMAIL> \\
      --group-name owner \\
      --profile <AWS_PROFILE>

  NOTE: 'owner' group grants full tenant-level access for company_id={company_id}.
  NOTE: Do NOT add this user to 'platform_admin' — that is reserved for usmissionhero operators.

STEP 3 — Force the tenant owner to change their password (first login):
  # The user will be prompted to change their temporary password on first login.
  # No additional command required — Cognito handles FORCE_CHANGE_PASSWORD flow.

STEP 4 — Verify the user and group membership:
  aws cognito-idp admin-get-user \\
      --user-pool-id <USER_POOL_ID> \\
      --username <USERNAME_OR_EMAIL> \\
      --profile <AWS_PROFILE>

  aws cognito-idp admin-list-groups-for-user \\
      --user-pool-id <USER_POOL_ID> \\
      --username <USERNAME_OR_EMAIL> \\
      --profile <AWS_PROFILE>
""".format(company_id=company_id))

    print("=" * 60)
    print("ROLE CLARIFICATION:")
    print("  owner group      -> tenant-level admin for company_id=" + company_id)
    print("  platform_admin   -> usmissionhero operator ONLY - do NOT assign to tenant owners")
    print("=" * 60)


# ---------------------------------------------------------------------------
# Rollback / Disable Guidance
# ---------------------------------------------------------------------------

def print_rollback_guidance(company_id):
    """
    Print rollback and disable guidance.

    Default policy: do not delete records. Disable via subscription_status only.
    """
    print("\n" + "=" * 60)
    print("ROLLBACK / DISABLE GUIDANCE")
    print("=" * 60)
    print(f"""
If the tenant provisioning needs to be reversed or the tenant disabled:

OPTION A — Disable via Platform Admin UI (preferred):
  1. Log in to https://toganddogs.usmissionhero.com/platform-admin
  2. Navigate to /platform-admin/tenants/{company_id}
  3. Click 'Edit Subscription'
  4. Set Subscription Status to 'Disabled' or 'Canceled'
  5. Confirm & Save — this prevents all tenant users from logging in.

OPTION B — Disable via Platform Admin PATCH API:
  PATCH /platform/tenants/{company_id}
  Body: {{"subscription_status": "disabled"}}
  (Requires platform_admin JWT)

OPTION C — Disable Cognito test users manually (if created):
  aws cognito-idp admin-disable-user \\
      --user-pool-id <USER_POOL_ID> \\
      --username <USERNAME_OR_EMAIL> \\
      --profile <AWS_PROFILE>

  OR remove from owner group:
  aws cognito-idp admin-remove-user-from-group \\
      --user-pool-id <USER_POOL_ID> \\
      --username <USERNAME_OR_EMAIL> \\
      --group-name owner \\
      --profile <AWS_PROFILE>

DO NOT delete DynamoDB records — set subscription_status to 'disabled' instead.
DO NOT delete Cognito users — disable them instead to preserve audit trail.
""")
    print("=" * 60)


# ---------------------------------------------------------------------------
# Dry-Run Output
# ---------------------------------------------------------------------------

def run_dry_run(company_id, display_name, tier, status, notes, actor):
    """
    Print the proposed provisioning summary without writing anything.
    """
    metadata = build_tenant_metadata(company_id, display_name, tier, status, notes, actor)
    audit = build_audit_record(company_id, metadata, actor)

    print("\n" + "=" * 60)
    print("DRY-RUN MODE — NO WRITES WILL OCCUR")
    print("=" * 60)

    print("\n[1] TENANT METADATA RECORD (proposed):")
    # Print metadata omitting any sensitive fields (belt-and-suspenders)
    safe_meta = {k: v for k, v in metadata.items()
                 if k not in ('stripe_customer_id', 'stripe_subscription_id',
                              'owner_email', 'owner_cognito_sub')}
    print(json.dumps(safe_meta, indent=2, default=str))

    print("\n[2] PLATFORM AUDIT RECORD (proposed):")
    safe_audit = {k: v for k, v in audit.items()}
    print(json.dumps(safe_audit, indent=2, default=str))

    print_cognito_templates(company_id)
    print_rollback_guidance(company_id)

    print("\n" + "=" * 60)
    print("IDEMPOTENCY NOTES:")
    print("  - If TENANT#" + company_id + "/METADATA already exists, apply mode will SKIP the write.")
    print("  - Use --force-overwrite (future flag) only if explicitly gate-approved.")
    print("  - A new audit record with a unique UUID SK is written on each apply call.")
    print("=" * 60)

    print("\n[OK] Dry-run complete. No writes occurred.")
    print("   To apply (requires Matthew approval gate): add --apply --confirm-apply")


# ---------------------------------------------------------------------------
# Apply Mode (guarded — NOT APPROVED FOR PRODUCTION USE IN THIS RELEASE)
# ---------------------------------------------------------------------------

def run_apply(company_id, display_name, tier, status, notes, actor,
              aws_profile, table_name, force_overwrite=False):
    """
    Write tenant metadata and audit record to DynamoDB.

    IDEMPOTENCY:
    - Checks for existing TENANT#<company_id>/METADATA before writing.
    - If it exists and force_overwrite is False, skips the metadata write.
    - Always writes a new audit record (unique SK via UUID).

    NOT APPROVED FOR PRODUCTION USE IN RELEASE 17W.
    Gate approval from Matthew required before running against production.
    """
    try:
        import boto3
    except ImportError:
        print("ERROR: boto3 is required for apply mode. Install it with: pip install boto3")
        sys.exit(1)

    print(f"\n[WARNING] APPLY MODE - Writing to DynamoDB table: {table_name}")
    print(f"   AWS Profile: {aws_profile}")
    print(f"   Target company_id: {company_id}\n")

    session = boto3.Session(profile_name=aws_profile)
    dynamodb = session.resource('dynamodb')
    table = dynamodb.Table(table_name)

    # --- Idempotency check ---
    existing = table.get_item(Key={'PK': f'TENANT#{company_id}', 'SK': 'METADATA'}).get('Item')
    if existing and not force_overwrite:
        print(f"[WARNING] SKIPPED: Tenant '{company_id}' metadata already exists (idempotency guard).")
        print("   Set --force-overwrite to update existing record (requires future gate approval).")
        metadata_written = False
    else:
        if existing:
            print(f"[WARNING] force-overwrite is set - overwriting existing metadata for '{company_id}'.")
        metadata = build_tenant_metadata(company_id, display_name, tier, status, notes, actor)
        table.put_item(Item=metadata)
        print(f"[OK] Tenant metadata written: TENANT#{company_id}/METADATA")
        metadata_written = True

    # --- Audit record (always written, UUID ensures uniqueness) ---
    metadata_for_audit = build_tenant_metadata(company_id, display_name, tier, status, notes, actor)
    audit = build_audit_record(company_id, metadata_for_audit, actor)
    table.put_item(Item=audit)
    print(f"[OK] Platform audit record written: {audit['SK']}")

    print("\nProvisioning apply complete.")
    print_cognito_templates(company_id)
    print_rollback_guidance(company_id)
    return metadata_written


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Tenant provisioning script for the usmissionhero SaaS platform.\n"
            "Default mode is DRY-RUN — safe to run without any AWS credentials.\n"
            "Apply mode requires --apply AND --confirm-apply flags."
        )
    )
    parser.add_argument('--company-id', required=True,
                        help='Unique company_id slug for the new tenant (e.g. acme_pets)')
    parser.add_argument('--display-name', required=True,
                        help='Human-readable business display name')
    parser.add_argument('--tier', default='starter', choices=sorted(VALID_TIERS),
                        help='Subscription tier (default: starter)')
    parser.add_argument('--status', default='active', choices=sorted(VALID_STATUSES),
                        help='Initial subscription status (default: active)')
    parser.add_argument('--notes', default='',
                        help='Optional platform admin notes (no private user data)')
    parser.add_argument('--actor', default='platform_admin:system',
                        help='Actor identifier for audit record (default: platform_admin:system)')

    # Apply mode flags
    parser.add_argument('--apply', action='store_true',
                        help='Run in apply mode — writes to DynamoDB. Requires --confirm-apply.')
    parser.add_argument('--confirm-apply', action='store_true',
                        help='Required confirmation flag for apply mode.')
    parser.add_argument('--aws-profile', default='usmissionhero-website-prod',
                        help='AWS profile name for apply mode')
    parser.add_argument('--table-name', default='togs-and-dogs-prod-data',
                        help='DynamoDB table name for apply mode')
    parser.add_argument('--force-overwrite', action='store_true',
                        help='Allow overwriting existing tenant metadata (future gate approval required)')

    args = parser.parse_args()

    try:
        args.company_id = validate_company_id(args.company_id)
        args.display_name = validate_display_name(args.display_name)
        args.tier = validate_tier(args.tier)
        args.status = validate_status(args.status)
        args.notes = validate_notes(args.notes)
    except ProvisioningValidationError as exc:
        print(f"ERROR: {exc.message}")
        sys.exit(1)

    if args.apply:
        if not args.confirm_apply:
            print("ERROR: --apply requires --confirm-apply flag. This is a safety guard.")
            print("       Add --confirm-apply only after explicit Matthew approval gate.")
            sys.exit(1)
        print("[WARNING] APPLY MODE ACTIVATED - this will write to the production DynamoDB table.")
        print("   Gate approval status: APPROVED (Release 19D)")
        print("   If you have explicit approval, proceeding...")
        run_apply(
            company_id=args.company_id,
            display_name=args.display_name,
            tier=args.tier,
            status=args.status,
            notes=args.notes,
            actor=args.actor,
            aws_profile=args.aws_profile,
            table_name=args.table_name,
            force_overwrite=args.force_overwrite,
        )
    else:
        run_dry_run(
            company_id=args.company_id,
            display_name=args.display_name,
            tier=args.tier,
            status=args.status,
            notes=args.notes,
            actor=args.actor,
        )


if __name__ == '__main__':
    main()
