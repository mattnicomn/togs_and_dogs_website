"""
Workstream 1 — Existing Pet Selection (canonical pet association by pet_id).

Covers:
- resolve_owned_pet_ids ownership/tenant/active gate + dedupe + order.
- Intake client-portal write path persists canonical pet_ids and derives names.
- Mixed existing + new pet linking is authoritative on pet_ids and idempotent.

These tests exercise real handler/helper code with mocked DynamoDB and auth
resolution. No production data or network is used.
"""
import json
import pytest
from unittest.mock import patch, MagicMock

import common.pet_profile as pet_profile
from common.pet_profile import resolve_owned_pet_ids
from handlers.intake_handler import handler as intake_handler


# ---------------------------------------------------------------------------
# resolve_owned_pet_ids — ownership / tenant / normalization
# ---------------------------------------------------------------------------

def _owned_map(pets):
    """Patch _owned_pet_map to return a deterministic {id: record} mapping."""
    return {p['pet_id']: p for p in pets}


def test_single_owned_pet_id_accepted():
    pets = [{'pet_id': 'PET-1', 'name': 'Buster'}]
    with patch.object(pet_profile, '_owned_pet_map', return_value=_owned_map(pets)):
        result = resolve_owned_pet_ids(['PET-1'], 'client-A', 'tenant-1')
    assert result['pet_ids'] == ['PET-1']
    assert result['pet_names'] == ['Buster']
    assert result['rejected'] == []


def test_multiple_owned_pet_ids_accepted_in_order():
    pets = [
        {'pet_id': 'PET-1', 'name': 'Buster'},
        {'pet_id': 'PET-2', 'name': 'Luna'},
    ]
    with patch.object(pet_profile, '_owned_pet_map', return_value=_owned_map(pets)):
        result = resolve_owned_pet_ids(['PET-2', 'PET-1'], 'client-A', 'tenant-1')
    # Order preserved as the caller requested.
    assert result['pet_ids'] == ['PET-2', 'PET-1']
    assert result['pet_names'] == ['Luna', 'Buster']


def test_duplicate_ids_are_deduped():
    pets = [{'pet_id': 'PET-1', 'name': 'Buster'}]
    with patch.object(pet_profile, '_owned_pet_map', return_value=_owned_map(pets)):
        result = resolve_owned_pet_ids(['PET-1', 'PET-1', 'PET-1'], 'client-A', 'tenant-1')
    assert result['pet_ids'] == ['PET-1']


def test_duplicate_names_distinct_ids_do_not_collide():
    # Two pets share the display name "Max" but have distinct IDs.
    pets = [
        {'pet_id': 'PET-1', 'name': 'Max'},
        {'pet_id': 'PET-2', 'name': 'Max'},
    ]
    with patch.object(pet_profile, '_owned_pet_map', return_value=_owned_map(pets)):
        result = resolve_owned_pet_ids(['PET-1', 'PET-2'], 'client-A', 'tenant-1')
    assert result['pet_ids'] == ['PET-1', 'PET-2']
    assert result['pet_names'] == ['Max', 'Max']


def test_foreign_client_pet_id_rejected_non_disclosing():
    # Owned map only contains this client's pets; a foreign pet simply isn't there.
    pets = [{'pet_id': 'PET-OWN', 'name': 'Buster'}]
    with patch.object(pet_profile, '_owned_pet_map', return_value=_owned_map(pets)):
        result = resolve_owned_pet_ids(['PET-FOREIGN'], 'client-A', 'tenant-1')
    assert result['ok'] is False and result['reason'] == 'not_owned'
    assert result['pet_ids'] == []
    assert result['pet_names'] == []
    # Rejected list is internal-only (never surfaced to the caller as existence).
    assert 'PET-FOREIGN' in result['rejected']


def test_foreign_tenant_pet_id_rejected():
    # _owned_pet_map filters by company; a pet under another tenant won't appear.
    pets = [{'pet_id': 'PET-OWN', 'name': 'Buster'}]
    with patch.object(pet_profile, '_owned_pet_map', return_value=_owned_map(pets)):
        result = resolve_owned_pet_ids(['PET-OTHER-TENANT'], 'client-A', 'tenant-1')
    assert result['ok'] is False and result['reason'] == 'not_owned'
    assert result['pet_ids'] == []
    assert 'PET-OTHER-TENANT' in result['rejected']


def test_malformed_pet_ids_rejected():
    # Hardened all-or-nothing: a malformed entry invalidates the whole selection
    # (no silent omission of bad entries while keeping the good ones).
    pets = [{'pet_id': 'PET-1', 'name': 'Buster'}]
    with patch.object(pet_profile, '_owned_pet_map', return_value=_owned_map(pets)):
        result = resolve_owned_pet_ids(['PET-1', 123], 'client-A', 'tenant-1')
    assert result['ok'] is False and result['reason'] == 'invalid_entry'
    assert result['pet_ids'] == []


def test_non_list_input_rejected_when_supplied():
    # Absent field is valid new-pet-only intake; a supplied non-list is invalid.
    assert resolve_owned_pet_ids(None, 'c', 't')['ok'] is True
    assert resolve_owned_pet_ids('PET-1', 'c', 't')['ok'] is False
    assert resolve_owned_pet_ids({}, 'c', 't')['ok'] is False


def test_missing_trusted_identity_fails_closed():
    result = resolve_owned_pet_ids(['PET-1'], None, 'tenant-1')
    assert result['ok'] is False
    assert result['pet_ids'] == []
    assert 'PET-1' in result['rejected']


def test_owned_map_filters_active_tenant_and_entity(monkeypatch):
    """_owned_pet_map must only surface active PET records under the tenant."""
    fake_table = MagicMock()
    fake_table.get_item.return_value = {'Item': {'PK': 'COMPANY#t1', 'SK': 'CLIENT#c1'}}
    fake_table.query.return_value = {
        'Items': [
            {'pet_id': 'P-ACTIVE', 'name': 'Active', 'entity_type': 'PET', 'company_id': 't1', 'is_active': True},
            {'pet_id': 'P-INACTIVE', 'name': 'Gone', 'entity_type': 'PET', 'company_id': 't1', 'is_active': False},
            {'pet_id': 'P-OTHERTENANT', 'name': 'Nope', 'entity_type': 'PET', 'company_id': 't2', 'is_active': True},
            {'pet_id': 'P-NOTPET', 'name': 'Job', 'entity_type': 'JOB', 'company_id': 't1', 'is_active': True},
        ],
    }
    monkeypatch.setattr(pet_profile, 'table', fake_table)
    owned = pet_profile._owned_pet_map('c1', 't1')
    assert set(owned.keys()) == {'P-ACTIVE'}


def test_owned_map_empty_when_client_not_in_tenant(monkeypatch):
    fake_table = MagicMock()
    fake_table.get_item.return_value = {}  # client not found under company
    monkeypatch.setattr(pet_profile, 'table', fake_table)
    owned = pet_profile._owned_pet_map('c1', 't1')
    assert owned == {}


# ---------------------------------------------------------------------------
# Intake client-portal write path — canonical pet_ids persisted
# ---------------------------------------------------------------------------

@pytest.fixture
def portal_client_env(monkeypatch):
    """Wire the intake handler's auth + entitlement for an approved client."""
    import handlers.intake_handler as ih

    monkeypatch.setattr(ih, 'require_active_tenant', lambda e: None, raising=False)
    # Auth resolution: role=client, resolved identity + company come from server.
    import common.auth as auth
    monkeypatch.setattr(auth, 'get_effective_role', lambda e: 'client')
    monkeypatch.setattr(auth, 'resolve_client_identity', lambda e: 'client-A')
    monkeypatch.setattr(auth, 'get_current_company_id', lambda e, claims=None: 'tenant-1')
    monkeypatch.setattr(auth, 'get_claims', lambda e: {'email': 'a@example.com', 'email_verified': True})

    # Approved client profile lookup used by the portal path.
    monkeypatch.setattr(ih, 'get_item', lambda pk, sk: {'is_active': True, 'portal_enabled': True})
    # Entitlement checks are no-ops here.
    import common.entitlement as ent
    monkeypatch.setattr(ent, 'check_limit', lambda *a, **k: None, raising=False)
    monkeypatch.setattr(ent, 'get_monthly_bookings_count', lambda c: 0, raising=False)
    monkeypatch.setattr(ent, 'increment_monthly_bookings', lambda c: None, raising=False)
    yield


def _portal_event(body):
    return {'path': '/client/requests', 'httpMethod': 'POST', 'body': json.dumps(body)}


def test_portal_submit_persists_canonical_pet_ids(portal_client_env, monkeypatch):
    import handlers.intake_handler as ih
    saved = {}
    monkeypatch.setattr(ih, 'put_item', lambda item: saved.update({'item': item}) or True)
    monkeypatch.setattr(ih, 'sfn', MagicMock())
    # Ownership gate returns two validated owned pets.
    monkeypatch.setattr(
        'common.pet_profile.resolve_owned_pet_ids',
        lambda raw, cid, comp: {'ok': True, 'supplied': True, 'reason': None,
                                'pet_ids': ['PET-1', 'PET-2'], 'pet_names': ['Buster', 'Luna'], 'rejected': []},
    )

    body = {
        'client_name': 'Client A', 'client_email': 'a@example.com',
        'start_date': '2026-07-01',
        'pet_ids': ['PET-1', 'PET-2'],
        'pets': [{'pet_id': 'PET-1', 'name': 'Buster'}, {'pet_id': 'PET-2', 'name': 'Luna'}],
    }
    resp = intake_handler(_portal_event(body), None)
    assert resp['statusCode'] == 200
    item = saved['item']
    assert item['pet_ids'] == ['PET-1', 'PET-2']
    # Display names derived from validated owned pets (echoes carry canonical ids).
    assert item['pet_names'] == 'Buster, Luna'


def test_portal_submit_spoofed_names_do_not_override_identity(portal_client_env, monkeypatch):
    import handlers.intake_handler as ih
    saved = {}
    monkeypatch.setattr(ih, 'put_item', lambda item: saved.update({'item': item}) or True)
    monkeypatch.setattr(ih, 'sfn', MagicMock())
    # The server validates ownership and returns the AUTHORITATIVE names, ignoring
    # whatever names the caller sent.
    monkeypatch.setattr(
        'common.pet_profile.resolve_owned_pet_ids',
        lambda raw, cid, comp: {'ok': True, 'supplied': True, 'reason': None,
                                'pet_ids': ['PET-1'], 'pet_names': ['RealName'], 'rejected': []},
    )
    body = {
        'client_name': 'Client A', 'client_email': 'a@example.com',
        'start_date': '2026-07-01',
        'pet_ids': ['PET-1'],
        'pet_names': 'AttackerControlledName',
        'pets': [{'name': 'AlsoSpoofed'}],  # new pet (no pet_id) → listed too
    }
    resp = intake_handler(_portal_event(body), None)
    assert resp['statusCode'] == 200
    item = saved['item']
    assert item['pet_ids'] == ['PET-1']
    # Canonical display name wins; spoofed caller names are not the authority.
    assert 'RealName' in item['pet_names']
    assert 'AttackerControlledName' not in item['pet_names']


def test_portal_submit_foreign_id_rejects_whole_request(portal_client_env, monkeypatch):
    """Hardened: a foreign/invalid supplied pet_id rejects the entire request
    generically, even when a new pet is also supplied — no silent fallback."""
    import handlers.intake_handler as ih
    put_calls = []
    monkeypatch.setattr(ih, 'put_item', lambda item: put_calls.append(item) or True)
    monkeypatch.setattr(ih, 'sfn', MagicMock())
    # The gate reports not-owned → ok=False.
    monkeypatch.setattr(
        'common.pet_profile.resolve_owned_pet_ids',
        lambda raw, cid, comp: {'ok': False, 'supplied': True, 'reason': 'not_owned',
                                'pet_ids': [], 'pet_names': [], 'rejected': ['PET-FOREIGN']},
    )
    body = {
        'client_name': 'Client A', 'client_email': 'a@example.com',
        'start_date': '2026-07-01',
        'pet_ids': ['PET-FOREIGN'],
        'pets': [{'name': 'NewPet'}],
    }
    resp = intake_handler(_portal_event(body), None)
    assert resp['statusCode'] == 400
    # Generic, non-disclosing wording; never reveals the id or the reason.
    assert 'PET-FOREIGN' not in resp['body']
    assert 'not_owned' not in resp['body']
    assert 'another' not in resp['body'].lower()
    assert 'tenant' not in resp['body'].lower()
    assert 'inactive' not in resp['body'].lower()
    # The request was NOT persisted.
    assert put_calls == []


def test_public_intake_unaffected_no_pet_ids(monkeypatch):
    """Public (unauthenticated) intake path never produces canonical pet_ids."""
    import handlers.intake_handler as ih
    import common.auth as auth
    monkeypatch.setattr(ih, 'require_active_tenant', lambda e: None, raising=False)
    monkeypatch.setattr(auth, 'get_effective_role', lambda e: 'unknown')
    monkeypatch.setattr(auth, 'resolve_public_intake_tenant', lambda e: 'tenant-1')
    import common.entitlement as ent
    monkeypatch.setattr(ent, 'check_limit', lambda *a, **k: None, raising=False)
    monkeypatch.setattr(ent, 'get_active_client_count', lambda c: 0, raising=False)
    monkeypatch.setattr(ent, 'get_monthly_bookings_count', lambda c: 0, raising=False)
    monkeypatch.setattr(ent, 'increment_monthly_bookings', lambda c: None, raising=False)
    monkeypatch.setattr(ih, 'table', MagicMock(query=MagicMock(return_value={'Items': []})))
    saved = {}
    monkeypatch.setattr(ih, 'put_item', lambda item: saved.update({'item': item}) or True)
    monkeypatch.setattr(ih, 'sfn', MagicMock())

    body = {
        'client_name': 'Public', 'client_email': 'p@example.com', 'start_date': '2026-07-01',
        'accepted_terms': True, 'accepted_privacy': True,
        'terms_version': '1.0', 'privacy_version': '1.0',
        'pet_ids': ['PET-SPOOF'],  # must be ignored on the public path
        'pets': [{'name': 'Rex'}],
    }
    resp = intake_handler({'path': '/requests', 'httpMethod': 'POST', 'body': json.dumps(body)}, None)
    assert resp['statusCode'] == 200
    assert saved['item']['pet_ids'] is None
    assert saved['item']['pet_names'] == 'Rex'


# ---------------------------------------------------------------------------
# resolve_owned_pet_ids — hardened all-or-nothing validity (real helper)
# ---------------------------------------------------------------------------

def test_resolve_absent_field_is_valid_new_pet_only():
    r = resolve_owned_pet_ids(None, 'c', 't')
    assert r['ok'] is True and r['supplied'] is False and r['pet_ids'] == []


def test_resolve_empty_list_is_valid():
    r = resolve_owned_pet_ids([], 'c', 't')
    assert r['ok'] is True and r['pet_ids'] == []


def test_resolve_non_list_shape_invalid():
    for bad in ['PET-1', {}, 123, {'a': 1}]:
        r = resolve_owned_pet_ids(bad, 'c', 't')
        assert r['ok'] is False and r['reason'] == 'invalid_shape'


def test_resolve_non_string_entry_invalid():
    with patch.object(pet_profile, '_owned_pet_map', return_value={'PET-1': {'pet_id': 'PET-1', 'name': 'B'}}):
        r = resolve_owned_pet_ids(['PET-1', 123], 'c', 't')
    assert r['ok'] is False and r['reason'] == 'invalid_entry'


def test_resolve_blank_entry_invalid():
    with patch.object(pet_profile, '_owned_pet_map', return_value={'PET-1': {'pet_id': 'PET-1', 'name': 'B'}}):
        r = resolve_owned_pet_ids(['PET-1', '   '], 'c', 't')
    assert r['ok'] is False and r['reason'] == 'invalid_entry'


def test_resolve_any_unowned_id_invalidates_whole_selection():
    owned = {'PET-1': {'pet_id': 'PET-1', 'name': 'Buster'}}
    with patch.object(pet_profile, '_owned_pet_map', return_value=owned):
        r = resolve_owned_pet_ids(['PET-1', 'PET-FOREIGN'], 'c', 't')
    assert r['ok'] is False and r['reason'] == 'not_owned'
    assert r['pet_ids'] == []  # all-or-nothing: no partial canonical set


def test_resolve_all_owned_ok_dedup_and_order():
    owned = {'PET-1': {'pet_id': 'PET-1', 'name': 'Buster'},
             'PET-2': {'pet_id': 'PET-2', 'name': 'Luna'}}
    with patch.object(pet_profile, '_owned_pet_map', return_value=owned):
        r = resolve_owned_pet_ids(['PET-2', 'PET-1', 'PET-2'], 'c', 't')
    assert r['ok'] is True
    assert r['pet_ids'] == ['PET-2', 'PET-1']       # order preserved, deduped
    assert r['pet_names'] == ['Luna', 'Buster']


def test_resolve_missing_identity_fails_closed():
    r = resolve_owned_pet_ids(['PET-1'], None, 't')
    assert r['ok'] is False and r['reason'] == 'no_identity'


# ---------------------------------------------------------------------------
# Handler-level input validation + rejection (real resolve_owned_pet_ids)
# ---------------------------------------------------------------------------

def _run_portal_with_owned(monkeypatch, owned_map, body):
    """Run the intake handler on the portal path with a real resolve_owned_pet_ids
    backed by a controlled _owned_pet_map; returns (resp, put_calls)."""
    import handlers.intake_handler as ih
    put_calls = []
    monkeypatch.setattr(ih, 'put_item', lambda item: put_calls.append(item) or True)
    monkeypatch.setattr(ih, 'sfn', MagicMock())
    monkeypatch.setattr(pet_profile, '_owned_pet_map', lambda cid, comp: owned_map)
    resp = intake_handler(_portal_event(body), None)
    return resp, put_calls


def test_handler_pet_ids_string_shape_rejected(portal_client_env, monkeypatch):
    resp, put_calls = _run_portal_with_owned(
        monkeypatch, {'PET-1': {'pet_id': 'PET-1', 'name': 'B'}},
        {'client_name': 'A', 'client_email': 'a@example.com', 'start_date': '2026-07-01',
         'pet_ids': 'PET-1', 'pets': [{'name': 'X'}]},
    )
    assert resp['statusCode'] == 400
    assert put_calls == []


def test_handler_non_string_entry_rejected(portal_client_env, monkeypatch):
    resp, put_calls = _run_portal_with_owned(
        monkeypatch, {'PET-1': {'pet_id': 'PET-1', 'name': 'B'}},
        {'client_name': 'A', 'client_email': 'a@example.com', 'start_date': '2026-07-01',
         'pet_ids': ['PET-1', 42], 'pets': []},
    )
    assert resp['statusCode'] == 400
    assert put_calls == []


def test_handler_valid_plus_foreign_rejected_no_persist(portal_client_env, monkeypatch):
    resp, put_calls = _run_portal_with_owned(
        monkeypatch, {'PET-1': {'pet_id': 'PET-1', 'name': 'Buster'}},  # PET-2 not owned
        {'client_name': 'A', 'client_email': 'a@example.com', 'start_date': '2026-07-01',
         'pet_ids': ['PET-1', 'PET-2'], 'pets': [{'name': 'New'}]},
    )
    assert resp['statusCode'] == 400
    assert 'PET-2' not in resp['body']   # non-disclosing
    assert put_calls == []


def test_handler_inactive_id_rejected(portal_client_env, monkeypatch):
    # _owned_pet_map excludes inactive pets, so an inactive id simply isn't owned.
    resp, put_calls = _run_portal_with_owned(
        monkeypatch, {},  # no active owned pets
        {'client_name': 'A', 'client_email': 'a@example.com', 'start_date': '2026-07-01',
         'pet_ids': ['PET-INACTIVE'], 'pets': []},
    )
    assert resp['statusCode'] == 400
    assert put_calls == []


def test_handler_all_valid_persists(portal_client_env, monkeypatch):
    resp, put_calls = _run_portal_with_owned(
        monkeypatch,
        {'PET-1': {'pet_id': 'PET-1', 'name': 'Buster'}, 'PET-2': {'pet_id': 'PET-2', 'name': 'Luna'}},
        {'client_name': 'A', 'client_email': 'a@example.com', 'start_date': '2026-07-01',
         'pet_ids': ['PET-1', 'PET-2'],
         'pets': [{'pet_id': 'PET-1', 'name': 'Buster'}, {'pet_id': 'PET-2', 'name': 'Luna'}]},
    )
    assert resp['statusCode'] == 200
    assert put_calls and put_calls[0]['pet_ids'] == ['PET-1', 'PET-2']


def test_handler_valid_existing_plus_new_pet_persists(portal_client_env, monkeypatch):
    resp, put_calls = _run_portal_with_owned(
        monkeypatch, {'PET-1': {'pet_id': 'PET-1', 'name': 'Buster'}},
        {'client_name': 'A', 'client_email': 'a@example.com', 'start_date': '2026-07-01',
         'pet_ids': ['PET-1'],
         'pets': [{'pet_id': 'PET-1', 'name': 'Buster'}, {'name': 'Milo'}]},
    )
    assert resp['statusCode'] == 200
    item = put_calls[0]
    assert item['pet_ids'] == ['PET-1']
    # Display combines existing + new (new entry has no canonical id).
    assert item['pet_names'] == 'Buster, Milo'


def test_handler_new_pet_same_name_as_selected_is_listed(portal_client_env, monkeypatch):
    # New pet shares the selected pet's display name but has no pet_id → still listed.
    resp, put_calls = _run_portal_with_owned(
        monkeypatch, {'PET-1': {'pet_id': 'PET-1', 'name': 'Max'}},
        {'client_name': 'A', 'client_email': 'a@example.com', 'start_date': '2026-07-01',
         'pet_ids': ['PET-1'],
         'pets': [{'pet_id': 'PET-1', 'name': 'Max'}, {'name': 'Max'}]},
    )
    assert resp['statusCode'] == 200
    # Both Max's represented in the display string (echo + genuinely-new).
    assert put_calls[0]['pet_names'] == 'Max, Max'


# ---------------------------------------------------------------------------
# Mixed existing + new linking — identity/provenance, not name (hardened)
# ---------------------------------------------------------------------------

def _mixed_env(monkeypatch, owned_pets):
    created = []
    monkeypatch.setattr(pet_profile, '_get_client_pets', lambda c, comp: owned_pets)
    monkeypatch.setattr(pet_profile, '_create_new_pet',
                        lambda pet_data, oc, comp, rid, now: created.append(pet_data['name'])
                        or f"NEW-{pet_data['name']}-{len(created)}")
    monkeypatch.setattr(pet_profile, '_copy_vet_to_client_profile', lambda *a, **k: None)
    monkeypatch.setattr(pet_profile, '_rebuild_pet_summary', lambda *a, **k: None)
    monkeypatch.setattr(pet_profile, '_append_audit_to_request', lambda *a, **k: None)
    monkeypatch.setattr(pet_profile, 'table', MagicMock())
    return created


def test_link_echo_skipped_by_id_new_created(monkeypatch):
    # Owned: PET-1 Buster (selected). Entries: echo of PET-1, plus genuinely-new Milo.
    created = _mixed_env(monkeypatch, [{'pet_id': 'PET-1', 'name': 'Buster'}])
    request_item = {
        'pet_ids': ['PET-1'],
        'pets': [{'pet_id': 'PET-1', 'name': 'Buster'},   # echo (by id) → skip
                 {'name': 'Milo'}],                         # new → create
    }
    result = pet_profile.create_or_link_pets_from_request(request_item, 'req-1', 'client-A', 'tenant-1')
    assert created == ['Milo']
    assert result['pet_ids'] == ['PET-1', 'NEW-Milo-1']


def test_link_new_pet_same_name_as_UNSELECTED_owned_is_still_created(monkeypatch):
    # Owned: PET-1 Buster (selected), PET-9 Rex (NOT selected). New entry "Rex"
    # (no pet_id) must be created despite the same-name unselected owned pet.
    created = _mixed_env(monkeypatch, [{'pet_id': 'PET-1', 'name': 'Buster'},
                                       {'pet_id': 'PET-9', 'name': 'Rex'}])
    request_item = {'pet_ids': ['PET-1'], 'pets': [{'name': 'Rex'}]}
    result = pet_profile.create_or_link_pets_from_request(request_item, 'req-1', 'client-A', 'tenant-1')
    assert created == ['Rex']                       # name is NOT identity
    assert result['pet_ids'] == ['PET-1', 'NEW-Rex-1']


def test_link_new_pet_same_name_as_SELECTED_is_still_created(monkeypatch):
    # Selected PET-1 "Max" AND a genuinely-new second "Max" (no id) → both kept.
    created = _mixed_env(monkeypatch, [{'pet_id': 'PET-1', 'name': 'Max'}])
    request_item = {'pet_ids': ['PET-1'],
                    'pets': [{'pet_id': 'PET-1', 'name': 'Max'}, {'name': 'Max'}]}
    result = pet_profile.create_or_link_pets_from_request(request_item, 'req-1', 'client-A', 'tenant-1')
    assert created == ['Max']
    assert result['pet_ids'] == ['PET-1', 'NEW-Max-1']


def test_link_request_scoped_idempotency_on_retry(monkeypatch):
    # First run created NEW-Milo attributable to req-1 (created_from_request_id).
    # On retry the owned set now includes it; it must be REUSED, not recreated.
    owned = [
        {'pet_id': 'PET-1', 'name': 'Buster'},
        {'pet_id': 'NEW-Milo', 'name': 'Milo', 'created_from_request_id': 'req-1',
         'created_at': '2026-07-01T00:00:00Z'},
    ]
    created = _mixed_env(monkeypatch, owned)
    request_item = {'pet_ids': ['PET-1'],
                    'pets': [{'pet_id': 'PET-1', 'name': 'Buster'}, {'name': 'Milo'}]}
    result = pet_profile.create_or_link_pets_from_request(request_item, 'req-1', 'client-A', 'tenant-1')
    assert created == []                              # idempotent — nothing recreated
    assert result['pet_ids'] == ['PET-1', 'NEW-Milo']


def test_link_same_name_from_DIFFERENT_request_does_not_suppress(monkeypatch):
    # An owned "Milo" was created by a DIFFERENT request (req-OTHER). It must NOT
    # be treated as this request's identity, so this request still creates Milo.
    owned = [
        {'pet_id': 'PET-1', 'name': 'Buster'},
        {'pet_id': 'OTHER-Milo', 'name': 'Milo', 'created_from_request_id': 'req-OTHER',
         'created_at': '2026-06-01T00:00:00Z'},
    ]
    created = _mixed_env(monkeypatch, owned)
    request_item = {'pet_ids': ['PET-1'], 'pets': [{'name': 'Milo'}]}
    result = pet_profile.create_or_link_pets_from_request(request_item, 'req-1', 'client-A', 'tenant-1')
    assert created == ['Milo']                        # not suppressed by same-name other-request pet
    assert 'OTHER-Milo' not in result['pet_ids']
    assert result['pet_ids'] == ['PET-1', 'NEW-Milo-1']


def test_link_existing_only_no_new_pets(monkeypatch):
    created = _mixed_env(monkeypatch, [{'pet_id': 'PET-1', 'name': 'Buster'},
                                       {'pet_id': 'PET-2', 'name': 'Luna'}])
    request_item = {'pet_ids': ['PET-1', 'PET-2'], 'pets': []}
    result = pet_profile.create_or_link_pets_from_request(request_item, 'req-1', 'client-A', 'tenant-1')
    assert created == []
    assert result['pet_ids'] == ['PET-1', 'PET-2']
    assert result['linked'] == 2


def test_link_two_selected_same_name_independent_by_id(monkeypatch):
    # Two owned pets both named "Max" selected → both associated by id, no collision.
    created = _mixed_env(monkeypatch, [{'pet_id': 'PET-A', 'name': 'Max'},
                                       {'pet_id': 'PET-B', 'name': 'Max'}])
    request_item = {'pet_ids': ['PET-A', 'PET-B'],
                    'pets': [{'pet_id': 'PET-A', 'name': 'Max'}, {'pet_id': 'PET-B', 'name': 'Max'}]}
    result = pet_profile.create_or_link_pets_from_request(request_item, 'req-1', 'client-A', 'tenant-1')
    assert created == []
    assert result['pet_ids'] == ['PET-A', 'PET-B']


def test_legacy_pets_array_name_path_still_works(monkeypatch):
    """No canonical pet_ids → legacy name-matching path is preserved."""
    monkeypatch.setattr(pet_profile, '_get_client_pets', lambda c, comp: [])
    created = []
    monkeypatch.setattr(pet_profile, '_create_new_pet',
                        lambda pet_data, oc, comp, rid, now: created.append(pet_data['name']) or f"NEW-{pet_data['name']}")
    monkeypatch.setattr(pet_profile, '_copy_vet_to_client_profile', lambda *a, **k: None)
    monkeypatch.setattr(pet_profile, '_rebuild_pet_summary', lambda *a, **k: None)
    monkeypatch.setattr(pet_profile, '_append_audit_to_request', lambda *a, **k: None)
    monkeypatch.setattr(pet_profile, 'table', MagicMock())

    request_item = {'pets': [{'name': 'Scout'}, {'name': 'Daisy'}]}  # no pet_ids
    result = pet_profile.create_or_link_pets_from_request(
        request_item, 'req-1', 'client-A', 'tenant-1'
    )
    assert created == ['Scout', 'Daisy']
    assert result['created'] == 2
