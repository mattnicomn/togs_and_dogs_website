"""BE-CANCEL-1C: /admin/review must never enter or leave cancellation state.

Moto evaluates the real ConditionExpression on the review write, so the read/write
race (a booking becoming CANCELLATION_REQUESTED after review read it) is tested
against real conditional-write semantics.
"""
import copy
import json
import os
import sys
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import patch

import boto3
import pytest
from moto import mock_aws

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'backend'))

from handlers import review_handler as rv  # noqa: E402

TENANT = 'tog_and_dogs'
OTHER_TENANT = 'test_tenant_alpha'
CLIENT = 'client-1'
ROLES = ['owner', 'admin', 'staff']
SENSITIVE_FOR_STAFF = {'APPROVED', 'BOOKED', 'DECLINED', 'CANCELLED', 'ARCHIVED', 'DELETED'}


def review_event(body, role='owner', company=TENANT, email='reviewer@example.test'):
    return {
        'httpMethod': 'POST', 'path': '/admin/review', 'body': json.dumps(body),
        'requestContext': {'authorizer': {'claims': {
            'sub': 'sub-reviewer', 'email': email, 'email_verified': 'true',
            'cognito:groups': role, 'custom:company_id': company,
        }}},
    }


def body_of(res):
    return json.loads(res['body'])


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv('TENANT_RESOLUTION_MODE', 'multi')
    monkeypatch.delenv('JOB_FUNCTION_NAME', raising=False)
    with mock_aws():
        table = boto3.resource('dynamodb', region_name='us-east-1').create_table(
            TableName='be-cancel-1c',
            KeySchema=[{'AttributeName': 'PK', 'KeyType': 'HASH'},
                       {'AttributeName': 'SK', 'KeyType': 'RANGE'}],
            AttributeDefinitions=[{'AttributeName': k, 'AttributeType': 'S'} for k in ('PK', 'SK')],
            BillingMode='PAY_PER_REQUEST',
        )

        def seed(key, status, company=TENANT, jobs=(), worker_id='staff@example.test', **extra):
            item = {'PK': f'REQ#{key}', 'SK': f'CLIENT#{CLIENT}', 'request_id': key,
                    'client_id': CLIENT, 'company_id': company, 'status': status,
                    'workflow_type': 'VISIT_BOOKING', 'client_name': 'Test Client',
                    'pet_names': 'Rex', 'start_date': '2030-01-01', 'end_date': '2030-01-01',
                    'worker_id': worker_id, 'job_ids': [j for j, _ in jobs]}
            item.setdefault('pet_id', 'pet-1')
            item.update(extra)
            table.put_item(Item=item)
            if not table.get_item(Key={'PK': 'PET#pet-1', 'SK': f'CLIENT#{CLIENT}'}).get('Item'):
                table.put_item(Item={'PK': 'PET#pet-1', 'SK': f'CLIENT#{CLIENT}', 'name': 'Rex'})
            for job_id, job_status in jobs:
                table.put_item(Item={'PK': f'JOB#{job_id}', 'SK': f'REQ#{key}',
                                     'company_id': company, 'status': job_status})

        def req(key):
            return table.get_item(Key={'PK': f'REQ#{key}', 'SK': f'CLIENT#{CLIENT}'},
                                  ConsistentRead=True).get('Item')

        def job(job_id, key):
            return table.get_item(Key={'PK': f'JOB#{job_id}', 'SK': f'REQ#{key}'},
                                  ConsistentRead=True).get('Item')

        def client_meta():
            return table.get_item(Key={'PK': f'CLIENT#{CLIENT}', 'SK': 'METADATA'},
                                  ConsistentRead=True).get('Item')

        def pet(pet_id):
            return table.get_item(Key={'PK': f'PET#{pet_id}', 'SK': f'CLIENT#{CLIENT}'},
                                  ConsistentRead=True).get('Item')

        def review(key, status, role='owner', company=TENANT, **extra_body):
            body = {'request_id': key, 'client_id': CLIENT, 'status': status}
            body.update(extra_body)
            return rv.handler(review_event(body, role=role, company=company), None)

        with ExitStack() as stack:
            stack.enter_context(patch('common.db.table', table))
            stack.enter_context(patch.object(rv, 'table', table))
            stack.enter_context(patch('common.cascade.table', table))
            stack.enter_context(patch('common.entitlement.require_active_tenant', return_value=None))
            audit = stack.enter_context(patch.object(rv, 'log_action'))
            notify = stack.enter_context(patch.object(rv, 'notify_event'))
            sync = stack.enter_context(patch.object(rv, 'sync_calendar_event',
                                                    return_value={'status': 'skipped'}))
            delete = stack.enter_context(patch.object(rv, 'delete_event', return_value=True))
            yield SimpleNamespace(table=table, seed=seed, req=req, job=job, review=review,
                                  client_meta=client_meta, pet=pet,
                                  audit=audit, notify=notify, sync=sync, delete=delete)


def assert_unchanged(env, key, before, jobs=()):
    assert env.req(key) == before
    for job_id, job_before in jobs:
        assert env.job(job_id, key) == job_before
    env.audit.assert_not_called()
    env.notify.assert_not_called()
    env.sync.assert_not_called()
    env.delete.assert_not_called()


def assert_conflict(res):
    assert res['statusCode'] == 409, res['body']
    assert body_of(res)['code'] == rv.CODE_CANCELLATION_TRANSITION_NOT_ALLOWED


# ---------------------------------------------------------------------------
# Entering CANCELLATION_REQUESTED / CANCELLATION_DENIED is refused for every role
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('role', ROLES)
@pytest.mark.parametrize('current', ['APPROVED', 'ASSIGNED'])
@pytest.mark.parametrize('target', ['CANCELLATION_REQUESTED', 'CANCELLATION_DENIED',
                                    'cancellation_requested', ' CANCELLATION_DENIED '])
def test_review_cannot_enter_cancellation_state(env, role, current, target):
    env.seed('e1', current, jobs=[('j1', 'ASSIGNED')])
    before, job_before = env.req('e1'), env.job('j1', 'e1')
    res = env.review('e1', target, role=role)
    assert_conflict(res)
    assert_unchanged(env, 'e1', before, jobs=[('j1', job_before)])


# ---------------------------------------------------------------------------
# Leaving CANCELLATION_REQUESTED is refused for every role
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('role', ROLES)
@pytest.mark.parametrize('target', ['CANCELLED', 'CANCELLATION_DENIED', 'APPROVED', 'ASSIGNED',
                                    'COMPLETED', 'ARCHIVED', 'DELETED', 'PENDING_REVIEW',
                                    'CANCELLATION_REQUESTED'])
def test_review_cannot_leave_cancellation_requested(env, role, target):
    env.seed('l1', 'CANCELLATION_REQUESTED', jobs=[('j1', 'ASSIGNED'), ('j2', 'COMPLETED')],
             cancellation_prior_status='ASSIGNED')
    before = env.req('l1')
    jobs_before = [(j, env.job(j, 'l1')) for j in ('j1', 'j2')]
    res = env.review('l1', target, role=role, worker_id='staff@example.test')
    if role == 'staff' and target in SENSITIVE_FOR_STAFF:
        assert res['statusCode'] == 403      # pre-existing RBAC still applies first
    else:
        assert_conflict(res)
    assert_unchanged(env, 'l1', before, jobs=jobs_before)


@pytest.mark.parametrize('role', ROLES)
def test_verify_meet_greet_cannot_leave_cancellation_requested(env, role):
    env.seed('v1', 'CANCELLATION_REQUESTED', pet_id='pet-1')
    before = env.req('v1')
    res = env.review('v1', 'VERIFY_MEET_GREET', role=role)
    assert_conflict(res)
    assert env.req('v1') == before
    assert env.table.get_item(Key={'PK': f'CLIENT#{CLIENT}', 'SK': 'METADATA'}).get('Item') is None


# ---------------------------------------------------------------------------
# Ordinary review transitions are preserved
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('role', ROLES)
def test_ordinary_review_transition_still_works(env, role):
    env.seed('o1', 'PENDING_REVIEW')
    res = env.review('o1', 'QUOTE_NEEDED', role=role)
    assert res['statusCode'] == 200, res['body']
    assert env.req('o1')['status'] == 'QUOTE_NEEDED'
    env.audit.assert_called_once()


def test_ordinary_completion_still_cascades(env):
    env.seed('o2', 'ASSIGNED', jobs=[('j1', 'ASSIGNED')])
    res = env.review('o2', 'COMPLETED', role='admin')
    assert res['statusCode'] == 200, res['body']
    assert env.req('o2')['status'] == 'COMPLETED'
    assert env.job('j1', 'o2')['status'] == 'COMPLETED'


def test_ordinary_cancel_from_approved_still_works(env):
    """Direct owner cancellation (not a cancellation *request*) is unchanged."""
    env.seed('o3', 'APPROVED')
    res = env.review('o3', 'CANCELLED', role='owner')
    assert res['statusCode'] == 200, res['body']
    assert env.req('o3')['status'] == 'CANCELLED'


def test_ordinary_staff_rbac_unchanged(env):
    env.seed('o4', 'PENDING_REVIEW')
    before = env.req('o4')
    res = env.review('o4', 'CANCELLED', role='staff')
    assert res['statusCode'] == 403
    assert env.req('o4') == before


# ---------------------------------------------------------------------------
# Tenant boundaries
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('current,target', [('CANCELLATION_REQUESTED', 'CANCELLED'),
                                            ('APPROVED', 'CANCELLATION_REQUESTED'),
                                            ('PENDING_REVIEW', 'QUOTE_NEEDED')])
def test_cross_tenant_review_is_forbidden(env, current, target):
    env.seed('t1', current, company=OTHER_TENANT)
    before = env.req('t1')
    res = env.review('t1', target, role='owner', company=TENANT)
    assert res['statusCode'] == 403
    assert env.req('t1') == before


# ---------------------------------------------------------------------------
# Read/write race: a booking that becomes CANCELLATION_REQUESTED after review
# read it is never overwritten (real conditional write).
# ---------------------------------------------------------------------------

def _stale_req_reads(env, stale):
    from common.db import get_item as real_get

    def fake_get(pk, sk):
        if pk.startswith('REQ#'):
            return copy.deepcopy(stale)
        return real_get(pk, sk)
    return patch.object(rv, 'get_item', side_effect=fake_get)


@pytest.mark.parametrize('stale_status,target,role', [
    ('PENDING_REVIEW', 'QUOTE_NEEDED', 'owner'),
    ('ASSIGNED', 'COMPLETED', 'admin'),
    ('APPROVED', 'CANCELLED', 'owner'),
    ('APPROVED', 'ASSIGNED', 'owner'),
])
def test_review_race_with_cancellation_request_is_rejected(env, stale_status, target, role):
    env.seed('r1', stale_status, jobs=[('j1', 'ASSIGNED')])
    stale = env.req('r1')
    # The client requests cancellation after review read the booking.
    env.table.update_item(Key={'PK': 'REQ#r1', 'SK': f'CLIENT#{CLIENT}'},
                          UpdateExpression='SET #s = :c', ExpressionAttributeNames={'#s': 'status'},
                          ExpressionAttributeValues={':c': 'CANCELLATION_REQUESTED'})
    before, job_before = env.req('r1'), env.job('j1', 'r1')
    with _stale_req_reads(env, stale):
        res = env.review('r1', target, role=role)
    assert_conflict(res)
    assert_unchanged(env, 'r1', before, jobs=[('j1', job_before)])


def test_verify_meet_greet_race_with_cancellation_request_is_rejected(env):
    env.seed('r2', 'MEET_GREET_REQUIRED')
    stale = env.req('r2')
    env.table.update_item(Key={'PK': 'REQ#r2', 'SK': f'CLIENT#{CLIENT}'},
                          UpdateExpression='SET #s = :c', ExpressionAttributeNames={'#s': 'status'},
                          ExpressionAttributeValues={':c': 'CANCELLATION_REQUESTED'})
    before = env.req('r2')
    with _stale_req_reads(env, stale):
        res = env.review('r2', 'VERIFY_MEET_GREET', role='owner')
    assert_conflict(res)
    assert env.req('r2') == before          # booking never moved out of the pending cancellation
    # BE-CANCEL-1C-R1 (B): the rejected booking write happens first, so no metadata changed.
    assert env.client_meta() is None
    assert env.pet('pet-1') == {'PK': 'PET#pet-1', 'SK': f'CLIENT#{CLIENT}', 'name': 'Rex'}


# ---------------------------------------------------------------------------
# BE-CANCEL-1C-R1: VERIFY_MEET_GREET tenant authorization and write ordering
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('role', ROLES)
def test_verify_meet_greet_normal_flow_succeeds(env, role):
    env.seed('m1', 'MEET_GREET_REQUIRED')
    res = env.review('m1', 'VERIFY_MEET_GREET', role=role)
    assert res['statusCode'] == 200, res['body']
    assert env.req('m1')['status'] == 'MG_COMPLETED'
    meta = env.client_meta()
    assert meta['meet_and_greet_completed'] is True and meta['company_id'] == TENANT
    assert env.pet('pet-1')['meet_and_greet_completed'] is True


def test_verify_meet_greet_client_level_normal_flow_succeeds(env):
    res = rv.handler(review_event({'client_id': CLIENT, 'status': 'VERIFY_MEET_GREET'}), None)
    assert res['statusCode'] == 200, res['body']
    assert env.client_meta()['meet_and_greet_completed'] is True


@pytest.mark.parametrize('role', ROLES)
def test_verify_meet_greet_cross_tenant_denied_before_any_write(env, role):
    env.seed('x1', 'MEET_GREET_REQUIRED', company=OTHER_TENANT)
    env.table.put_item(Item={'PK': f'CLIENT#{CLIENT}', 'SK': 'METADATA',
                             'company_id': OTHER_TENANT, 'meet_and_greet_completed': False})
    before, meta_before, pet_before = env.req('x1'), env.client_meta(), env.pet('pet-1')
    res = env.review('x1', 'VERIFY_MEET_GREET', role=role, company=TENANT)
    assert res['statusCode'] == 403
    assert 'MEET_GREET_REQUIRED' not in res['body']           # no cross-tenant status disclosed
    assert env.req('x1') == before
    assert env.client_meta() == meta_before
    assert env.pet('pet-1') == pet_before


def test_verify_meet_greet_cross_tenant_pending_cancellation_not_disclosed(env):
    env.seed('x2', 'CANCELLATION_REQUESTED', company=OTHER_TENANT)
    before = env.req('x2')
    res = env.review('x2', 'VERIFY_MEET_GREET', role='owner', company=TENANT)
    assert res['statusCode'] == 403                            # not a 409 that reveals status
    assert env.req('x2') == before
    assert env.client_meta() is None


def test_verify_meet_greet_missing_request_creates_nothing(env):
    res = env.review('ghost', 'VERIFY_MEET_GREET', role='owner')
    assert res['statusCode'] == 403
    assert env.req('ghost') is None                            # no stub REQ
    assert env.client_meta() is None


def test_verify_meet_greet_client_level_cross_tenant_denied(env):
    env.table.put_item(Item={'PK': f'CLIENT#{CLIENT}', 'SK': 'METADATA',
                             'company_id': OTHER_TENANT, 'meet_and_greet_completed': False})
    before = env.client_meta()
    res = rv.handler(review_event({'client_id': CLIENT, 'status': 'VERIFY_MEET_GREET'},
                                  company=TENANT), None)
    assert res['statusCode'] == 403
    assert env.client_meta() == before


def test_verify_meet_greet_booking_deleted_after_read_writes_no_metadata(env):
    env.seed('d1', 'MEET_GREET_REQUIRED')
    stale = env.req('d1')
    env.table.delete_item(Key={'PK': 'REQ#d1', 'SK': f'CLIENT#{CLIENT}'})
    with _stale_req_reads(env, stale):
        res = env.review('d1', 'VERIFY_MEET_GREET', role='owner')
    assert res['statusCode'] == 409
    assert env.req('d1') is None                               # not recreated as a stub
    assert env.client_meta() is None
    assert 'meet_and_greet_completed' not in env.pet('pet-1')


def test_cancellation_decision_gate_still_owns_the_pending_request(env):
    """After review is refused, the cancellation decision endpoint still decides it."""
    from handlers import cancellation_handler as ch
    env.seed('g1', 'CANCELLATION_REQUESTED', cancellation_prior_status='ASSIGNED')
    assert_conflict(env.review('g1', 'CANCELLED', role='owner'))
    event = review_event({}, role='owner')
    with patch.object(ch, 'table', env.table), patch.object(ch, 'log_action'), \
            patch.object(ch, 'notify_event'), patch.object(ch, 'notify_worker'):
        res = ch.handle_admin_decision(
            {'request_id': 'g1', 'client_id': CLIENT, 'decision': 'DENY'}, event)
    assert res['statusCode'] == 200, res['body']
    assert env.req('g1')['status'] == 'ASSIGNED'
