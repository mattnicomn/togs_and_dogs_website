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
    assert result['pet_ids'] == []
    assert result['pet_names'] == []
    # Rejected list is internal-only (never surfaced to the caller as existence).
    assert 'PET-FOREIGN' in result['rejected']


def test_foreign_tenant_pet_id_rejected():
    # _owned_pet_map filters by company; a pet under another tenant won't appear.
    pets = [{'pet_id': 'PET-OWN', 'name': 'Buster'}]
    with patch.object(pet_profile, '_owned_pet_map', return_value=_owned_map(pets)):
        result = resolve_owned_pet_ids(['PET-OTHER-TENANT'], 'client-A', 'tenant-1')
    assert result['pet_ids'] == []
    assert 'PET-OTHER-TENANT' in result['rejected']


def test_malformed_pet_ids_rejected():
    pets = [{'pet_id': 'PET-1', 'name': 'Buster'}]
    with patch.object(pet_profile, '_owned_pet_map', return_value=_owned_map(pets)):
        result = resolve_owned_pet_ids(['PET-1', '', '   ', 123, None, {'x': 1}], 'client-A', 'tenant-1')
    assert result['pet_ids'] == ['PET-1']
    # Non-string / blank entries are rejected, not accepted.
    assert 123 in result['rejected']
    assert None in result['rejected']


def test_non_list_input_returns_empty():
    assert resolve_owned_pet_ids(None, 'c', 't')['pet_ids'] == []
    assert resolve_owned_pet_ids('PET-1', 'c', 't')['pet_ids'] == []
    assert resolve_owned_pet_ids({}, 'c', 't')['pet_ids'] == []


def test_missing_trusted_identity_fails_closed():
    result = resolve_owned_pet_ids(['PET-1'], None, 'tenant-1')
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
        lambda raw, cid, comp: {'pet_ids': ['PET-1', 'PET-2'], 'pet_names': ['Buster', 'Luna'], 'rejected': []},
    )

    body = {
        'client_name': 'Client A', 'client_email': 'a@example.com',
        'start_date': '2026-07-01',
        'pet_ids': ['PET-1', 'PET-2'],
        'pets': [{'name': 'Buster'}, {'name': 'Luna'}],
    }
    resp = intake_handler(_portal_event(body), None)
    assert resp['statusCode'] == 200
    item = saved['item']
    assert item['pet_ids'] == ['PET-1', 'PET-2']
    # Display names derived from validated owned pets.
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
        lambda raw, cid, comp: {'pet_ids': ['PET-1'], 'pet_names': ['RealName'], 'rejected': []},
    )
    body = {
        'client_name': 'Client A', 'client_email': 'a@example.com',
        'start_date': '2026-07-01',
        'pet_ids': ['PET-1'],
        'pet_names': 'AttackerControlledName',
        'pets': [{'name': 'AlsoSpoofed'}],
    }
    resp = intake_handler(_portal_event(body), None)
    assert resp['statusCode'] == 200
    item = saved['item']
    assert item['pet_ids'] == ['PET-1']
    # Canonical display name wins; spoofed caller names are not the authority.
    assert 'RealName' in item['pet_names']
    assert 'AttackerControlledName' not in item['pet_names']


def test_portal_submit_foreign_ids_dropped_fall_back_to_new_pet(portal_client_env, monkeypatch):
    import handlers.intake_handler as ih
    saved = {}
    monkeypatch.setattr(ih, 'put_item', lambda item: saved.update({'item': item}) or True)
    monkeypatch.setattr(ih, 'sfn', MagicMock())
    # All supplied IDs are foreign → validated set is empty.
    monkeypatch.setattr(
        'common.pet_profile.resolve_owned_pet_ids',
        lambda raw, cid, comp: {'pet_ids': [], 'pet_names': [], 'rejected': ['PET-FOREIGN']},
    )
    body = {
        'client_name': 'Client A', 'client_email': 'a@example.com',
        'start_date': '2026-07-01',
        'pet_ids': ['PET-FOREIGN'],
        'pets': [{'name': 'NewPet'}],
    }
    resp = intake_handler(_portal_event(body), None)
    assert resp['statusCode'] == 200
    item = saved['item']
    # No canonical association persisted; the new pet still flows via pets[].
    assert item['pet_ids'] is None
    assert item['pets'] == [{'name': 'NewPet'}]
    assert item['pet_names'] == 'NewPet'


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
# Mixed existing + new linking (create_or_link_pets_from_request)
# ---------------------------------------------------------------------------

def test_link_mixed_existing_authoritative_and_creates_only_new(monkeypatch):
    # Client already owns PET-1 "Buster" (selected) and PET-9 "Rex" (not selected,
    # but same name as a new-pet entry → must NOT be recreated).
    existing = [
        {'pet_id': 'PET-1', 'name': 'Buster'},
        {'pet_id': 'PET-9', 'name': 'Rex'},
    ]
    monkeypatch.setattr(pet_profile, '_get_client_pets', lambda c, comp: existing)
    created = []
    monkeypatch.setattr(pet_profile, '_create_new_pet',
                        lambda pet_data, oc, comp, rid, now: created.append(pet_data['name']) or f"NEW-{pet_data['name']}")
    monkeypatch.setattr(pet_profile, '_copy_vet_to_client_profile', lambda *a, **k: None)
    monkeypatch.setattr(pet_profile, '_rebuild_pet_summary', lambda *a, **k: None)
    monkeypatch.setattr(pet_profile, '_append_audit_to_request', lambda *a, **k: None)
    fake_table = MagicMock()
    monkeypatch.setattr(pet_profile, 'table', fake_table)

    request_item = {
        'pet_ids': ['PET-1'],                       # canonical existing selection
        'pets': [
            {'name': 'Buster'},                     # echoes selected existing → skip
            {'name': 'Rex'},                        # matches owned PET-9 by name → skip (no dup)
            {'name': 'Milo'},                       # genuinely new → create
        ],
    }
    result = pet_profile.create_or_link_pets_from_request(
        request_item, 'req-1', 'client-A', 'tenant-1'
    )
    # Only Milo was created; canonical existing preserved and listed first.
    assert created == ['Milo']
    assert result['pet_ids'] == ['PET-1', 'NEW-Milo']
    assert result['created'] == 1
    assert result['linked'] == 1


def test_link_mixed_idempotent_on_rerun(monkeypatch):
    # On re-run, the previously-new pet "Milo" is now owned → nothing new created.
    existing = [
        {'pet_id': 'PET-1', 'name': 'Buster'},
        {'pet_id': 'NEW-Milo', 'name': 'Milo'},
    ]
    monkeypatch.setattr(pet_profile, '_get_client_pets', lambda c, comp: existing)
    created = []
    monkeypatch.setattr(pet_profile, '_create_new_pet',
                        lambda pet_data, oc, comp, rid, now: created.append(pet_data['name']) or f"NEW-{pet_data['name']}")
    monkeypatch.setattr(pet_profile, '_copy_vet_to_client_profile', lambda *a, **k: None)
    monkeypatch.setattr(pet_profile, '_rebuild_pet_summary', lambda *a, **k: None)
    monkeypatch.setattr(pet_profile, '_append_audit_to_request', lambda *a, **k: None)
    monkeypatch.setattr(pet_profile, 'table', MagicMock())

    request_item = {'pet_ids': ['PET-1'], 'pets': [{'name': 'Buster'}, {'name': 'Milo'}]}
    result = pet_profile.create_or_link_pets_from_request(
        request_item, 'req-1', 'client-A', 'tenant-1'
    )
    assert created == []           # idempotent — no duplicate creation
    assert result['pet_ids'] == ['PET-1']
    assert result['created'] == 0


def test_link_existing_only_no_new_pets(monkeypatch):
    existing = [{'pet_id': 'PET-1', 'name': 'Buster'}, {'pet_id': 'PET-2', 'name': 'Luna'}]
    monkeypatch.setattr(pet_profile, '_get_client_pets', lambda c, comp: existing)
    monkeypatch.setattr(pet_profile, '_create_new_pet', lambda *a, **k: pytest.fail("should not create"))
    monkeypatch.setattr(pet_profile, '_copy_vet_to_client_profile', lambda *a, **k: None)
    monkeypatch.setattr(pet_profile, '_rebuild_pet_summary', lambda *a, **k: None)
    monkeypatch.setattr(pet_profile, '_append_audit_to_request', lambda *a, **k: None)
    monkeypatch.setattr(pet_profile, 'table', MagicMock())

    request_item = {'pet_ids': ['PET-1', 'PET-2'], 'pets': []}
    result = pet_profile.create_or_link_pets_from_request(
        request_item, 'req-1', 'client-A', 'tenant-1'
    )
    assert result['pet_ids'] == ['PET-1', 'PET-2']
    assert result['created'] == 0
    assert result['linked'] == 2


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
