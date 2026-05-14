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

    # Idempotency guard: if pet_ids already set, skip
    existing_pet_ids = request_item.get('pet_ids')
    if existing_pet_ids and len(existing_pet_ids) > 0:
        print(f"INFO: [PetProfile] Skipped — pet_ids already exist on REQ#{request_id}: {existing_pet_ids}")
        return {"pet_ids": existing_pet_ids, "created": 0, "linked": 0, "warnings": []}

    # Also check legacy single pet_id
    legacy_pet_id = request_item.get('pet_id')
    if legacy_pet_id:
        print(f"INFO: [PetProfile] Skipped — legacy pet_id already exists on REQ#{request_id}: {legacy_pet_id}")
        return {"pet_ids": [legacy_pet_id], "created": 0, "linked": 0, "warnings": []}

    # Determine the owner client_id for PET# SK
    # Prefer linked_client_profile_id (from Release 3 auto-profile) for persistent ownership
    owner_client_id = request_item.get('linked_client_profile_id') or client_id

    # Get the pets array (Release 4 format) or fall back to legacy
    pets_array = request_item.get('pets')

    if not pets_array or not isinstance(pets_array, list) or len(pets_array) == 0:
        # Legacy fallback: use pet_names string (current behavior)
        return _create_legacy_single_pet(request_item, request_id, client_id, owner_client_id, company_id, now)

    # Load existing PET# records for this client (for name matching)
    existing_pets = _get_client_pets(owner_client_id)

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


def _get_client_pets(client_id):
    """Fetches all active PET# records for a client."""
    try:
        response = table.scan(
            FilterExpression=Attr('client_id').eq(client_id) & Attr('entity_type').eq('PET') & Attr('is_active').ne(False)
        )
        return response.get('Items', [])
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
        pets = _get_client_pets(owner_client_id)
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
