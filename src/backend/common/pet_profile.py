"""
Release 4: Multi-Pet Profile Creation and Linking Utility

Creates individual PET# records from a request's pets array on approval.
Handles idempotency, name matching, and duplicate detection.

Design decisions:
- PET# records created ONLY on approval (not on public intake submission).
- pet_ids array on REQ record is the idempotency guard.
- PET# SK uses linked_client_profile_id when available (persistent ownership).
- Single exact name match → link/update existing PET# record.
- Multiple name matches → create new + audit warning (NEEDS_REVIEW).
- No match → create new PET# record.
- Never overwrite admin-entered data with empty values from intake.
- Rebuild pet_names_summary from active PET# records (idempotent).
"""

import uuid
from datetime import datetime, timezone
from common.db import table, put_item, get_item
from boto3.dynamodb.conditions import Attr


def resolve_owned_pet_ids(raw_pet_ids, client_id, company_id):
    """
    Workstream 1 (hardened): Validate caller-supplied existing-pet IDs against
    the authenticated client's own active pets. Existing-pet association is
    ALL-OR-NOTHING: if the caller supplied a `pet_ids` field at all, every entry
    must be a well-formed, owned, active pet under this tenant, or the whole
    request is invalid.

    This is the canonical ownership gate for the `pet_ids` request contract.
    The caller MUST pass a server-resolved `client_id` and `company_id` (from
    resolve_client_identity / get_current_company_id); this function never reads
    client/company identity from the request body.

    Validity model (the handler maps `ok == False` to a generic, non-disclosing
    HTTP 400 and does NOT persist the request):
    - `absent`: the field was not supplied at all (raw_pet_ids is None). Valid —
      new-pet-only intake. ok=True, empty pet_ids.
    - `invalid_shape`: the field was supplied but is not a list. ok=False.
    - `invalid_entry`: the list contains a non-string / empty / blank entry.
      ok=False.
    - `not_owned`: a well-formed id is not an active pet owned by this client
      under this tenant (covers foreign-client, foreign-tenant, inactive,
      unknown). ok=False.
    - otherwise ok=True with the validated, de-duplicated, order-preserving ids
      and their canonical display names (derived from the owned records only).

    The result NEVER tells the caller which id failed or why; `rejected` /
    `reason` are for server-side logging only and must not be surfaced.

    Returns:
        dict: {
            "ok": bool,
            "supplied": bool,                 # whether a pet_ids field was present
            "reason": str | None,             # internal: invalid_shape|invalid_entry|not_owned|no_identity
            "pet_ids": [validated owned IDs in deterministic order],
            "pet_names": [matching display names, same order],
            "rejected": [caller entries that were not accepted],  # internal only
        }
    """
    # Field absent entirely → valid new-pet-only intake.
    if raw_pet_ids is None:
        return {"ok": True, "supplied": False, "reason": None,
                "pet_ids": [], "pet_names": [], "rejected": []}

    # Field supplied → it MUST be a list.
    if not isinstance(raw_pet_ids, list):
        return {"ok": False, "supplied": True, "reason": "invalid_shape",
                "pet_ids": [], "pet_names": [], "rejected": [raw_pet_ids]}

    # An empty list is treated as "no existing-pet selection supplied" — valid,
    # because it carries no invalid identity (new-pet-only intake may send []).
    if len(raw_pet_ids) == 0:
        return {"ok": True, "supplied": True, "reason": None,
                "pet_ids": [], "pet_names": [], "rejected": []}

    if not client_id or not company_id:
        # No trusted identity → cannot prove ownership of a supplied selection.
        return {"ok": False, "supplied": True, "reason": "no_identity",
                "pet_ids": [], "pet_names": [], "rejected": [str(x) for x in raw_pet_ids]}

    # Normalize: every entry must be a non-empty string. Any malformed entry
    # invalidates the whole selection (no silent omission).
    seen = set()
    requested = []
    for entry in raw_pet_ids:
        if not isinstance(entry, str):
            return {"ok": False, "supplied": True, "reason": "invalid_entry",
                    "pet_ids": [], "pet_names": [], "rejected": [entry]}
        value = entry.strip()
        if not value:
            return {"ok": False, "supplied": True, "reason": "invalid_entry",
                    "pet_ids": [], "pet_names": [], "rejected": [entry]}
        if value in seen:
            continue  # duplicate valid id collapses to one
        seen.add(value)
        requested.append(value)

    # Ownership check against the authoritative owned-pet map (same filter as
    # GET /client/pets). EVERY requested id must be accepted.
    owned = _owned_pet_map(client_id, company_id)
    validated_ids = []
    validated_names = []
    for pet_id in requested:
        pet = owned.get(pet_id)
        if pet is None:
            # Not owned / foreign / foreign-tenant / inactive / unknown.
            # Reject the whole request; do NOT disclose which id or why.
            return {"ok": False, "supplied": True, "reason": "not_owned",
                    "pet_ids": [], "pet_names": [], "rejected": [pet_id]}
        validated_ids.append(pet_id)
        validated_names.append((pet.get('name') or '').strip())

    return {
        "ok": True,
        "supplied": True,
        "reason": None,
        "pet_ids": validated_ids,
        "pet_names": [n for n in validated_names if n],
        "rejected": [],
    }


def _owned_pet_map(client_id, company_id):
    """
    Returns {pet_id: pet_record} for the client's active pets under this tenant.

    Validates the client exists under the trusted company, then queries
    ClientPetIndex (paginated) and filters to active PET records whose
    company_id matches — identical to the GET /client/pets contract.
    """
    result = {}
    try:
        client_resp = table.get_item(
            Key={'PK': f"COMPANY#{company_id}", 'SK': f"CLIENT#{client_id}"}
        )
        if 'Item' not in client_resp:
            return result

        from boto3.dynamodb.conditions import Key
        query_kwargs = {
            'IndexName': 'ClientPetIndex',
            'KeyConditionExpression': Key('client_id').eq(client_id),
        }
        while True:
            resp = table.query(**query_kwargs)
            for p in resp.get('Items', []):
                if p.get('entity_type') != 'PET':
                    continue
                p_company = p.get('company_id')
                if not p_company or p_company != company_id:
                    continue
                if p.get('is_active') is False:
                    continue
                pid = p.get('pet_id')
                if pid:
                    result[pid] = p
            last_key = resp.get('LastEvaluatedKey')
            if not last_key:
                break
            query_kwargs['ExclusiveStartKey'] = last_key
    except Exception as e:
        print(f"WARNING: [PetProfile] Failed to build owned-pet map: {e}")
    return result


def create_or_link_pets_from_request(request_item, request_id, client_id, company_id, updated_by='system'):
    """
    Creates or links individual PET# records from a request's pets array.

    Idempotency: If pet_ids already exists on the request, skips entirely.

    Args:
        request_item: The REQ record dict (must have 'pets' array or 'pet_names' fallback).
        request_id: The request UUID.
        client_id: The submission-time client_id from the REQ record.
        company_id: Tenant company ID.
        updated_by: Who triggered the approval.

    Returns:
        dict: {"pet_ids": [...], "created": int, "linked": int, "warnings": [...]}
    """
    now = datetime.now(timezone.utc).isoformat()

    # Determine the owner client_id for PET# SK
    # Prefer linked_client_profile_id (from Release 3 auto-profile) for persistent ownership
    owner_client_id = request_item.get('linked_client_profile_id') or client_id

    # Workstream 1: canonical existing-pet association.
    # When the REQUEST already carries a canonical `pet_ids` array (the client
    # selected existing profile pets by ID), those associations are AUTHORITATIVE:
    # they are never re-created or name-matched. A request may ALSO carry a
    # structured `pets` array for genuinely-new pets; those still need PET#
    # records. We therefore process only the new-pet entries that are not already
    # represented by a canonical existing ID, and append their new IDs — keeping
    # the whole operation idempotent (re-running with pet_ids present and no
    # unrepresented new pets is a no-op).
    canonical_existing_ids = request_item.get('pet_ids')
    if canonical_existing_ids and isinstance(canonical_existing_ids, list) and len(canonical_existing_ids) > 0:
        return _link_mixed_existing_and_new(
            request_item, request_id, client_id, owner_client_id,
            company_id, now, canonical_existing_ids
        )

    # Also check legacy single pet_id
    legacy_pet_id = request_item.get('pet_id')
    if legacy_pet_id:
        print(f"INFO: [PetProfile] Skipped — legacy pet_id already exists on REQ#{request_id}: {legacy_pet_id}")
        return {"pet_ids": [legacy_pet_id], "created": 0, "linked": 0, "warnings": []}

    # Get the pets array (Release 4 format) or fall back to legacy
    pets_array = request_item.get('pets')

    if not pets_array or not isinstance(pets_array, list) or len(pets_array) == 0:
        # Legacy fallback: use pet_names string (current behavior)
        return _create_legacy_single_pet(request_item, request_id, client_id, owner_client_id, company_id, now)

    # Load existing PET# records for this client (for name matching)
    existing_pets = _get_client_pets(owner_client_id, company_id)

    pet_ids = []
    created_count = 0
    linked_count = 0
    warnings = []

    for pet_data in pets_array:
        pet_name = (pet_data.get('name') or '').strip()
        if not pet_name:
            continue  # Skip unnamed pets

        # Attempt name match against existing PET# records
        match_result = _find_existing_pet(existing_pets, pet_name)

        if match_result['status'] == 'single_match':
            # Link to existing, update with new non-empty data
            existing_pet_id = match_result['pet_id']
            _merge_pet_data(owner_client_id, existing_pet_id, pet_data, now)
            pet_ids.append(existing_pet_id)
            linked_count += 1
            print(f"INFO: [PetProfile] Linked to existing PET#{existing_pet_id} (name: {pet_name})")

        elif match_result['status'] == 'multiple_matches':
            # Ambiguous — create new + warning
            new_pet_id = _create_new_pet(pet_data, owner_client_id, company_id, request_id, now)
            pet_ids.append(new_pet_id)
            created_count += 1
            warning_msg = f"Multiple existing pets named '{pet_name}' for this client. Created new PET#{new_pet_id}."
            warnings.append(warning_msg)
            print(f"WARNING: [PetProfile] {warning_msg}")

        else:
            # No match — create new
            new_pet_id = _create_new_pet(pet_data, owner_client_id, company_id, request_id, now)
            pet_ids.append(new_pet_id)
            created_count += 1
            print(f"INFO: [PetProfile] Created new PET#{new_pet_id} (name: {pet_name})")

    # Link pet_ids back to REQ record
    if pet_ids:
        try:
            table.update_item(
                Key={'PK': f"REQ#{request_id}", 'SK': f"CLIENT#{client_id}"},
                UpdateExpression="SET pet_ids = :pids, pet_id = :first_pid",
                ExpressionAttributeValues={
                    ":pids": pet_ids,
                    ":first_pid": pet_ids[0]  # Legacy compat: pet_id = first pet
                }
            )
        except Exception as e:
            print(f"WARNING: [PetProfile] Failed to link pet_ids to REQ#{request_id}: {e}")

    # Copy vet/emergency info to client profile (household level)
    _copy_vet_to_client_profile(request_item, owner_client_id, company_id, now)

    # Rebuild pet_names_summary on client profile (idempotent)
    _rebuild_pet_summary(owner_client_id, company_id)

    # Append audit if warnings
    if warnings:
        _append_audit_to_request(request_id, client_id, {
            "action": "PET_PROFILE_WARNINGS",
            "timestamp": now,
            "warnings": warnings,
            "updated_by": "system_pet_profile"
        })

    return {"pet_ids": pet_ids, "created": created_count, "linked": linked_count, "warnings": warnings}


def _link_mixed_existing_and_new(request_item, request_id, client_id,
                                 owner_client_id, company_id, now,
                                 canonical_existing_ids):
    """
    Workstream 1 (hardened): honor canonical existing `pet_ids` and create the
    genuinely-new structured `pets` entries — using IDENTITY/PROVENANCE, never
    name equality, to decide what is new and to stay idempotent.

    Rules:
    - Canonical existing IDs are authoritative and preserved in order; never
      re-created or renamed here.
    - A structured `pets` entry is an ECHO of a selected existing pet iff it
      carries a `pet_id` that is one of `canonical_existing_ids`. Echoes are not
      created again. (Name is irrelevant to this decision.)
    - Every other structured entry (no canonical `pet_id`) is a NEW-pet intent
      and MUST be created — it is NEVER suppressed merely because some unrelated
      owned pet shares its display name. A new pet named the same as a selected
      existing pet is still created.
    - Idempotency is REQUEST-SCOPED: pets previously created by THIS request are
      recognized via `created_from_request_id == request_id` and reused in order,
      so a retry does not duplicate them. A same-name pet created by a DIFFERENT
      request (or a pre-existing owned pet) is NOT treated as this request's
      identity and does NOT suppress creation.
    """
    canonical_set = set(canonical_existing_ids)

    # All active owned PET records this request created on any earlier run,
    # in a stable order so retries reconcile deterministically. CRUCIAL: we keep
    # these request-created IDs available for reconciliation EVEN WHEN they are
    # already present in canonical_existing_ids. On a real retry the request's
    # persisted pet_ids already contains the previously-created new-pet IDs
    # (e.g. first run appended NEW-MILO), so those IDs ARE in canonical_set; we
    # must still recognize them as this request's own new-pet provenance to
    # reconcile the id-less structured new-pet entries, otherwise we would create
    # duplicates. True client-selected existing IDs are those canonical IDs that
    # are NOT request-created provenance.
    owned_pets = _get_client_pets(owner_client_id, company_id)
    request_created_ids = [
        p.get('pet_id')
        for p in sorted(owned_pets, key=lambda x: (x.get('created_at') or '', x.get('pet_id') or ''))
        if p.get('created_from_request_id') == request_id
        and p.get('pet_id')
    ]

    pets_array = request_item.get('pets')
    created_ids = []       # freshly created on THIS invocation
    reconciled_ids = []    # matched to this request's prior provenance (reused)
    created_count = 0

    if pets_array and isinstance(pets_array, list):
        reuse_index = 0
        for pet_data in pets_array:
            if not isinstance(pet_data, dict):
                continue
            pet_name = (pet_data.get('name') or '').strip()
            if not pet_name:
                continue
            entry_id = pet_data.get('pet_id')
            # Echo of a CLIENT-SELECTED existing pet — identified by a canonical
            # id that is NOT this request's own creation provenance. Not created.
            if (isinstance(entry_id, str)
                    and entry_id.strip() in canonical_set
                    and entry_id.strip() not in request_created_ids):
                continue
            # New-pet intent (id-less, or an id that is this request's own
            # provenance). Reuse this request's previously-created PET in order
            # (request-scoped idempotency) before creating a fresh one.
            if reuse_index < len(request_created_ids):
                reconciled_ids.append(request_created_ids[reuse_index])
                reuse_index += 1
                print(f"INFO: [PetProfile] Reconciled request-scoped PET#{request_created_ids[reuse_index - 1]} "
                      f"(name: {pet_name}) on retry of REQ#{request_id}")
                continue
            new_pet_id = _create_new_pet(pet_data, owner_client_id, company_id, request_id, now)
            created_ids.append(new_pet_id)
            created_count += 1
            print(f"INFO: [PetProfile] Created new PET#{new_pet_id} (name: {pet_name}) alongside canonical existing selection")

    # New-pet IDs contributed by this call = reconciled (prior provenance) + fresh.
    created_ids = reconciled_ids + created_ids
    warnings = []

    # Final authoritative association: canonical existing IDs (order preserved)
    # followed by any newly created IDs, de-duplicated.
    final_ids = []
    for pid in list(canonical_existing_ids) + created_ids:
        if pid and pid not in final_ids:
            final_ids.append(pid)

    if created_ids:
        try:
            table.update_item(
                Key={'PK': f"REQ#{request_id}", 'SK': f"CLIENT#{client_id}"},
                UpdateExpression="SET pet_ids = :pids, pet_id = :first_pid",
                ExpressionAttributeValues={
                    ":pids": final_ids,
                    ":first_pid": final_ids[0],
                },
            )
        except Exception as e:
            print(f"WARNING: [PetProfile] Failed to extend pet_ids on REQ#{request_id}: {e}")

    _copy_vet_to_client_profile(request_item, owner_client_id, company_id, now)
    _rebuild_pet_summary(owner_client_id, company_id)

    if warnings:
        _append_audit_to_request(request_id, client_id, {
            "action": "PET_PROFILE_WARNINGS",
            "timestamp": now,
            "warnings": warnings,
            "updated_by": "system_pet_profile",
        })

    return {
        "pet_ids": final_ids,
        "created": created_count,
        "linked": len(canonical_existing_ids),
        "warnings": warnings,
    }


def _create_legacy_single_pet(request_item, request_id, client_id, owner_client_id, company_id, now):
    """Falls back to current single-PET creation from pet_names string."""
    pet_names = request_item.get('pet_names') or 'Unnamed Pet'
    pet_id = str(uuid.uuid4())

    pet_item = {
        'PK': f"PET#{pet_id}",
        'SK': f"CLIENT#{owner_client_id}",
        'company_id': company_id,
        'entity_type': 'PET',
        'pet_id': pet_id,
        'client_id': owner_client_id,
        'name': pet_names,
        'care_instructions': request_item.get('pet_info'),
        'meet_and_greet_completed': True,
        'created_from_request_id': request_id,
        'is_active': True,
        'created_at': now,
        'updated_at': now
    }

    if put_item(pet_item):
        # Link back to REQ
        try:
            table.update_item(
                Key={'PK': f"REQ#{request_id}", 'SK': f"CLIENT#{client_id}"},
                UpdateExpression="SET pet_id = :pid, pet_ids = :pids",
                ExpressionAttributeValues={":pid": pet_id, ":pids": [pet_id]}
            )
        except Exception as e:
            print(f"WARNING: [PetProfile] Failed to link legacy pet_id: {e}")

        _rebuild_pet_summary(owner_client_id, company_id)
        return {"pet_ids": [pet_id], "created": 1, "linked": 0, "warnings": []}

    return {"pet_ids": [], "created": 0, "linked": 0, "warnings": ["Failed to create legacy PET record"]}


def _get_client_pets(client_id, company_id):
    """Fetches all active PET# records for a client."""
    try:
        # Security: Validate the client exists under the trusted company
        client_key = {'PK': f"COMPANY#{company_id}", 'SK': f"CLIENT#{client_id}"}
        client_resp = table.get_item(Key=client_key)
        if 'Item' not in client_resp:
            return []

        # Query ClientPetIndex with pagination
        from boto3.dynamodb.conditions import Key
        query_kwargs = {
            'IndexName': 'ClientPetIndex',
            'KeyConditionExpression': Key('client_id').eq(client_id)
        }
        items = []
        while True:
            resp = table.query(**query_kwargs)
            items.extend(resp.get('Items', []))
            last_key = resp.get('LastEvaluatedKey')
            if not last_key:
                break
            query_kwargs['ExclusiveStartKey'] = last_key

        # Result filtering
        filtered_items = []
        for p in items:
            if p.get('entity_type') != 'PET':
                continue
            p_company = p.get('company_id')
            if not p_company or p_company != company_id:
                continue
            if p.get('is_active') is False:
                continue
            filtered_items.append(p)

        return filtered_items
    except Exception as e:
        print(f"WARNING: [PetProfile] Failed to query client pets: {e}")
        return []


def _find_existing_pet(existing_pets, pet_name):
    """
    Finds existing PET# record by name match.
    Returns: {"status": "single_match"|"multiple_matches"|"no_match", "pet_id": str|None}
    """
    normalized = pet_name.lower().strip()
    matches = [p for p in existing_pets if (p.get('name') or '').lower().strip() == normalized]

    if len(matches) == 1:
        return {"status": "single_match", "pet_id": matches[0].get('pet_id')}
    elif len(matches) > 1:
        return {"status": "multiple_matches", "pet_id": None}
    return {"status": "no_match", "pet_id": None}


def _create_new_pet(pet_data, owner_client_id, company_id, request_id, now):
    """Creates a new PET# record from intake pet data."""
    pet_id = str(uuid.uuid4())

    item = {
        'PK': f"PET#{pet_id}",
        'SK': f"CLIENT#{owner_client_id}",
        'company_id': company_id,
        'entity_type': 'PET',
        'pet_id': pet_id,
        'client_id': owner_client_id,
        'name': (pet_data.get('name') or '').strip(),
        'species': pet_data.get('species') or None,
        'breed': pet_data.get('breed') or None,
        'age': pet_data.get('age') or None,
        'feeding_notes': pet_data.get('feeding_notes') or None,
        'medication_notes': pet_data.get('medication_notes') or None,
        'behavior_notes': pet_data.get('behavior_notes') or None,
        'care_instructions': pet_data.get('care_instructions') or None,
        'vet_notes': pet_data.get('vet_notes') or None,
        'emergency_notes': pet_data.get('emergency_notes') or None,
        'meet_and_greet_completed': True,
        'is_active': True,
        'created_from_request_id': request_id,
        'created_at': now,
        'updated_at': now
    }

    put_item(item)
    return pet_id


def _merge_pet_data(owner_client_id, pet_id, pet_data, now):
    """
    Merges new intake data into an existing PET# record.
    Only updates fields that are non-empty in the new data.
    Never overwrites admin-entered data with empty values.
    """
    updates = {}
    merge_fields = ['species', 'breed', 'age', 'feeding_notes', 'medication_notes', 'behavior_notes']

    for field in merge_fields:
        new_val = pet_data.get(field)
        if new_val:  # Only update if non-empty
            updates[field] = new_val

    if not updates:
        return  # Nothing to merge

    updates['updated_at'] = now

    try:
        update_parts = []
        expr_names = {}
        expr_vals = {}
        for i, (k, v) in enumerate(updates.items()):
            name_key = f"#f{i}"
            val_key = f":v{i}"
            update_parts.append(f"{name_key} = {val_key}")
            expr_names[name_key] = k
            expr_vals[val_key] = v

        table.update_item(
            Key={'PK': f"PET#{pet_id}", 'SK': f"CLIENT#{owner_client_id}"},
            UpdateExpression="SET " + ", ".join(update_parts),
            ExpressionAttributeNames=expr_names,
            ExpressionAttributeValues=expr_vals
        )
    except Exception as e:
        print(f"WARNING: [PetProfile] Failed to merge data into PET#{pet_id}: {e}")


def _copy_vet_to_client_profile(request_item, owner_client_id, company_id, now):
    """Copies household-level vet/emergency info from request to client profile."""
    vet_info = request_item.get('vet_info')
    # Field stored as 'emergency_contact_info' on REQ record (Release 4 intake_handler)
    emergency_contact = request_item.get('emergency_contact_info') or request_item.get('emergency_contact')

    if not vet_info and not emergency_contact:
        return

    updates = {'updated_at': now}
    if vet_info:
        if vet_info.get('vet_name'): updates['vet_name'] = vet_info['vet_name']
        if vet_info.get('clinic_name'): updates['vet_clinic_name'] = vet_info['clinic_name']
        if vet_info.get('clinic_phone'): updates['vet_phone'] = vet_info['clinic_phone']
        if vet_info.get('clinic_address'): updates['vet_address'] = vet_info['clinic_address']
    if emergency_contact:
        ec_parts = []
        if emergency_contact.get('name'): ec_parts.append(emergency_contact['name'])
        if emergency_contact.get('phone'): ec_parts.append(emergency_contact['phone'])
        if ec_parts:
            updates['emergency_contact'] = ' — '.join(ec_parts)

    if len(updates) <= 1:  # Only updated_at
        return

    try:
        update_parts = []
        expr_names = {}
        expr_vals = {}
        for i, (k, v) in enumerate(updates.items()):
            name_key = f"#f{i}"
            val_key = f":v{i}"
            update_parts.append(f"{name_key} = {val_key}")
            expr_names[name_key] = k
            expr_vals[val_key] = v

        table.update_item(
            Key={'PK': f"COMPANY#{company_id}", 'SK': f"CLIENT#{owner_client_id}"},
            UpdateExpression="SET " + ", ".join(update_parts),
            ExpressionAttributeNames=expr_names,
            ExpressionAttributeValues=expr_vals
        )
    except Exception as e:
        print(f"WARNING: [PetProfile] Failed to copy vet info to client profile: {e}")


def _rebuild_pet_summary(owner_client_id, company_id):
    """
    Rebuilds pet_names_summary and pet_breeds_summary from active PET# records.
    Fully idempotent — always reflects current state.
    """
    try:
        pets = _get_client_pets(owner_client_id, company_id)
        names = sorted(set(p.get('name', '') for p in pets if p.get('name')))
        breeds = sorted(set(p.get('breed', '') for p in pets if p.get('breed')))

        table.update_item(
            Key={'PK': f"COMPANY#{company_id}", 'SK': f"CLIENT#{owner_client_id}"},
            UpdateExpression="SET pet_names_summary = :pns, pet_breeds_summary = :pbs",
            ExpressionAttributeValues={
                ":pns": ', '.join(names) if names else None,
                ":pbs": ', '.join(breeds) if breeds else None
            }
        )
    except Exception as e:
        print(f"WARNING: [PetProfile] Failed to rebuild pet summary: {e}")


def _append_audit_to_request(request_id, client_id, audit_entry):
    """Appends an audit entry to the REQ record's audit_log."""
    try:
        table.update_item(
            Key={'PK': f"REQ#{request_id}", 'SK': f"CLIENT#{client_id}"},
            UpdateExpression="SET audit_log = list_append(if_not_exists(audit_log, :empty), :entry)",
            ExpressionAttributeValues={":entry": [audit_entry], ":empty": []}
        )
    except Exception as e:
        print(f"WARNING: [PetProfile] Failed to append audit: {e}")
