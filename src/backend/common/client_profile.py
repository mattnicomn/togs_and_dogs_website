"""
Release 3: Client Profile Auto-Creation and Linking Utility

When a CUSTOMER_INTAKE request is approved, this module automatically creates
or links a Client Management profile based on email matching.

Design decisions:
- Email is the ONLY automatic match key (exact, case-insensitive).
- Phone/name matches are logged but do NOT auto-link.
- If multiple profiles match the same email, do NOT auto-link (flag for review).
- If an inactive profile matches, reactivate unless manually disabled.
- Approval NEVER fails because of profile automation (fail-safe).
- No Cognito users are created.
- No portal access is granted.

Future enhancement: Add admin-facing "possible duplicate" alert for phone matches.
"""

from datetime import datetime, timezone
from common.db import table, get_item
from boto3.dynamodb.conditions import Key


def auto_create_or_link_client_profile(request_item, request_id, client_id, company_id, updated_by='system'):
    """
    Auto-creates or links a Client Management profile on CUSTOMER_INTAKE approval.

    Args:
        request_item: The REQ record dict.
        request_id: The request UUID.
        client_id: The client UUID from the REQ record (submission-time ID).
        company_id: The tenant company ID.
        updated_by: Who triggered the approval.

    Returns:
        dict: {
            "action": "created"|"linked"|"reactivated"|"skipped"|"needs_review"|"failed",
            "link_status": str,
            "client_profile_id": str or None,
            "message": str
        }
    """
    now = datetime.now(timezone.utc).isoformat()

    # 1. Normalize email
    email = (request_item.get('client_email') or '').lower().strip()

    if not email:
        # Cannot match without email — skip gracefully
        _update_request_link_status(request_id, client_id, 'SKIPPED_NO_EMAIL', None, 'skipped_no_email', now)
        print(f"INFO: [AutoProfile] Skipped for REQ#{request_id} — no email on request.")
        return {
            "action": "skipped",
            "link_status": "SKIPPED_NO_EMAIL",
            "client_profile_id": None,
            "message": "No email on request, profile automation skipped."
        }

    # 2. Query all client profiles for this company
    try:
        response = table.query(
            KeyConditionExpression=Key('PK').eq(f"COMPANY#{company_id}") & Key('SK').begins_with("CLIENT#")
        )
        all_profiles = response.get('Items', [])
    except Exception as e:
        print(f"ERROR: [AutoProfile] Failed to query client profiles: {e}")
        _update_request_link_status(request_id, client_id, 'FAILED', None, 'failed', now)
        return {
            "action": "failed",
            "link_status": "FAILED",
            "client_profile_id": None,
            "message": f"Failed to query profiles: {str(e)}"
        }

    # 3. Search for exact email match (case-insensitive)
    matches = [p for p in all_profiles if (p.get('email') or '').lower().strip() == email]

    # 4. Handle multiple matches — flag for admin review, do NOT auto-link
    if len(matches) > 1:
        match_ids = [m.get('client_id') for m in matches]
        print(f"WARNING: [AutoProfile] Multiple profiles match email '{email}': {match_ids}")
        _update_request_link_status(request_id, client_id, 'NEEDS_REVIEW_MULTIPLE_MATCHES', None, 'multiple_matches', now)
        _append_audit_to_request(request_id, client_id, {
            "action": "CLIENT_PROFILE_MULTIPLE_MATCHES",
            "timestamp": now,
            "email": email,
            "matching_profile_ids": match_ids,
            "updated_by": "system_auto_profile"
        })
        return {
            "action": "needs_review",
            "link_status": "NEEDS_REVIEW_MULTIPLE_MATCHES",
            "client_profile_id": None,
            "message": f"Multiple client profiles ({len(matches)}) match this email. Please review Client Management."
        }

    # 5. Exact match found — link or reactivate
    if len(matches) == 1:
        existing = matches[0]
        existing_profile_id = existing.get('client_id')

        # 5a. Active profile — link request to it
        if existing.get('is_active') == True:
            _link_request_to_profile(request_id, client_id, existing_profile_id, 'LINKED_EXISTING', 'auto_email_match', now)
            _update_profile_request_metadata(company_id, existing_profile_id, request_id, now)
            # Release 4C: Fill blank phone from intake if profile phone is empty.
            # Never overwrite an existing admin-entered phone.
            _fill_blank_phone(company_id, existing_profile_id, existing, request_item, now)
            _append_audit_to_request(request_id, client_id, {
                "action": "CLIENT_PROFILE_LINKED",
                "timestamp": now,
                "client_profile_id": existing_profile_id,
                "email": email,
                "method": "auto_email_match",
                "updated_by": "system_auto_profile"
            })
            print(f"INFO: [AutoProfile] Linked REQ#{request_id} to existing profile {existing_profile_id}")
            return {
                "action": "linked",
                "link_status": "LINKED_EXISTING",
                "client_profile_id": existing_profile_id,
                "message": "Linked to existing client profile."
            }

        # 5b. Inactive profile — check if manually disabled
        is_manually_disabled = (
            existing.get('cognito_status') == 'deleted' or
            existing.get('admin_disabled') == True
        )

        if is_manually_disabled:
            print(f"INFO: [AutoProfile] Skipped reactivation for {existing_profile_id} — manually disabled.")
            _update_request_link_status(request_id, client_id, 'SKIPPED_MANUALLY_DISABLED', existing_profile_id, 'skipped_disabled', now)
            return {
                "action": "skipped",
                "link_status": "SKIPPED_MANUALLY_DISABLED",
                "client_profile_id": existing_profile_id,
                "message": "Matching profile is manually disabled. Profile not reactivated."
            }

        # 5c. Inactive but not manually disabled — reactivate and link
        try:
            table.update_item(
                Key={'PK': f"COMPANY#{company_id}", 'SK': f"CLIENT#{existing_profile_id}"},
                UpdateExpression="SET is_active = :t, updated_at = :now",
                ExpressionAttributeValues={":t": True, ":now": now}
            )
        except Exception as e:
            print(f"WARNING: [AutoProfile] Failed to reactivate profile {existing_profile_id}: {e}")

        _link_request_to_profile(request_id, client_id, existing_profile_id, 'REACTIVATED_AND_LINKED', 'auto_reactivated', now)
        _update_profile_request_metadata(company_id, existing_profile_id, request_id, now)
        _append_audit_to_request(request_id, client_id, {
            "action": "CLIENT_PROFILE_REACTIVATED",
            "timestamp": now,
            "client_profile_id": existing_profile_id,
            "email": email,
            "updated_by": "system_auto_profile"
        })
        print(f"INFO: [AutoProfile] Reactivated and linked profile {existing_profile_id} for REQ#{request_id}")
        return {
            "action": "reactivated",
            "link_status": "REACTIVATED_AND_LINKED",
            "client_profile_id": existing_profile_id,
            "message": "Inactive client profile reactivated and linked."
        }

    # 6. No match — create new client profile
    import uuid
    new_profile_id = f"client_{str(uuid.uuid4())[:8]}"

    new_profile = {
        'PK': f"COMPANY#{company_id}",
        'SK': f"CLIENT#{new_profile_id}",
        'company_id': company_id,
        'client_id': new_profile_id,
        'display_name': request_item.get('client_name') or 'Unknown Client',
        'email': email,
        # Release 4C: Set phone from intake submission if provided.
        'phone': (request_item.get('client_phone') or '').strip() or None,
        'address': None,
        'emergency_contact': None,
        'notes': None,
        'is_active': True,
        'portal_enabled': False,  # No portal access until admin enables
        'cognito_sub': None,  # No Cognito user created
        'cognito_status': 'not_linked',
        # Release 3: Auto-creation metadata
        'auto_created': True,
        'auto_created_at': now,
        'auto_created_from': request_id,
        'source_request_id': request_id,
        'first_request_id': request_id,
        'latest_request_id': request_id,
        'intake_request_ids': [request_id],
        'request_count': 1,
        'last_request_date': now,
        'became_client_at': now,
        'created_at': now,
        'updated_at': now
    }

    try:
        table.put_item(Item=new_profile)
    except Exception as e:
        print(f"ERROR: [AutoProfile] Failed to create profile for REQ#{request_id}: {e}")
        _update_request_link_status(request_id, client_id, 'FAILED', None, 'failed', now)
        _append_audit_to_request(request_id, client_id, {
            "action": "CLIENT_PROFILE_FAILED",
            "timestamp": now,
            "email": email,
            "error": str(e),
            "updated_by": "system_auto_profile"
        })
        return {
            "action": "failed",
            "link_status": "FAILED",
            "client_profile_id": None,
            "message": f"Failed to create client profile: {str(e)}"
        }

    # Link request to the new profile
    _link_request_to_profile(request_id, client_id, new_profile_id, 'CREATED_NEW', 'auto_created', now)
    _append_audit_to_request(request_id, client_id, {
        "action": "CLIENT_PROFILE_AUTO_CREATED",
        "timestamp": now,
        "client_profile_id": new_profile_id,
        "email": email,
        "updated_by": "system_auto_profile"
    })
    print(f"INFO: [AutoProfile] Created new profile {new_profile_id} for REQ#{request_id} ({email})")
    return {
        "action": "created",
        "link_status": "CREATED_NEW",
        "client_profile_id": new_profile_id,
        "message": "New client profile auto-created."
    }


def _update_request_link_status(request_id, client_id, link_status, profile_id, method, timestamp):
    """Updates the REQ record with client profile linkage metadata."""
    try:
        update_expr = "SET client_profile_link_status = :ls, client_profile_linked_at = :t, client_profile_link_method = :m"
        expr_vals = {
            ":ls": link_status,
            ":t": timestamp,
            ":m": method,
        }
        if profile_id:
            update_expr += ", linked_client_profile_id = :pid"
            expr_vals[":pid"] = profile_id

        table.update_item(
            Key={'PK': f"REQ#{request_id}", 'SK': f"CLIENT#{client_id}"},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_vals
        )
    except Exception as e:
        print(f"WARNING: [AutoProfile] Failed to update link status on REQ#{request_id}: {e}")


def _link_request_to_profile(request_id, client_id, profile_id, link_status, method, timestamp):
    """Updates the REQ record with the linked client profile ID and status."""
    _update_request_link_status(request_id, client_id, link_status, profile_id, method, timestamp)


def _update_profile_request_metadata(company_id, profile_id, request_id, timestamp):
    """Updates the client profile with request linkage metadata (append to history)."""
    try:
        table.update_item(
            Key={'PK': f"COMPANY#{company_id}", 'SK': f"CLIENT#{profile_id}"},
            UpdateExpression=(
                "SET latest_request_id = :rid, last_request_date = :t, updated_at = :t"
                ", intake_request_ids = list_append(if_not_exists(intake_request_ids, :empty), :new_id)"
                " ADD request_count :one"
            ),
            ExpressionAttributeValues={
                ":rid": request_id,
                ":t": timestamp,
                ":empty": [],
                ":new_id": [request_id],
                ":one": 1
            }
        )
    except Exception as e:
        print(f"WARNING: [AutoProfile] Failed to update profile metadata for {profile_id}: {e}")


def _append_audit_to_request(request_id, client_id, audit_entry):
    """Appends an audit entry to the REQ record's audit_log."""
    try:
        table.update_item(
            Key={'PK': f"REQ#{request_id}", 'SK': f"CLIENT#{client_id}"},
            UpdateExpression="SET audit_log = list_append(if_not_exists(audit_log, :empty), :entry)",
            ExpressionAttributeValues={
                ":entry": [audit_entry],
                ":empty": []
            }
        )
    except Exception as e:
        print(f"WARNING: [AutoProfile] Failed to append audit to REQ#{request_id}: {e}")


def _fill_blank_phone(company_id, profile_id, existing_profile, request_item, now):
    """
    Release 4C: Fills blank phone on an existing client profile from intake client_phone.
    Only fills if profile phone is blank/None AND request has a client_phone.
    Never overwrites an existing admin-entered phone value.
    """
    client_phone = (request_item.get('client_phone') or '').strip()
    existing_phone = (existing_profile.get('phone') or '').strip()

    if client_phone and not existing_phone:
        try:
            table.update_item(
                Key={'PK': f"COMPANY#{company_id}", 'SK': f"CLIENT#{profile_id}"},
                UpdateExpression="SET phone = :p, updated_at = :now",
                ExpressionAttributeValues={":p": client_phone, ":now": now}
            )
            print(f"INFO: [AutoProfile] Filled blank phone on profile {profile_id}: {client_phone}")
        except Exception as e:
            print(f"WARNING: [AutoProfile] Failed to fill phone on profile {profile_id}: {e}")
