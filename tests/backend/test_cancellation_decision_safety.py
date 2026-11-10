"""BE-CANCEL-1: cancellation decision safety (validation, atomic gate, D1 Option A).

Moto evaluates the real ConditionExpression / UpdateExpression / ConsistentRead
semantics, so the decision gate is tested against real conditional-write
behaviour instead of a MagicMock that accepts every write.

Concurrency is simulated deterministically: the losing invocation reads a
pre-decision snapshot, then the competing decision commits before the loser
attempts its conditional write (a genuine read-then-write race window).
"""
import copy
import json
import os
import sys
from contextlib import ExitStack, contextmanager
from types import SimpleNamespace
from unittest.mock import patch

import boto3
import pytest
from moto import mock_aws

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'backend'))

from handlers import cancellation_handler as ch  # noqa: E402

TENANT = 'tog_and_dogs'
OTHER_TENANT = 'test_tenant_alpha'
CLIENT = 'client-1'
CLIENT_EMAIL = 'client@example.test'
MISSING = object()


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def admin_event(company=TENANT, role='admin', email='admin@example.test'):
    return {'requestContext': {'authorizer': {'claims': {
        'sub': 'sub-admin', 'email': email, 'email_verified': 'true',
        'cognito:groups': role, 'custom:company_id': company,
    }}}}


def client_event(company=TENANT, email=CLIENT_EMAIL):
    return admin_event(company=company, role='client', email=email)


def decide(req, decision, note=MISSING, event=None, client=CLIENT):
    body = {'request_id': req, 'client_id': client, 'decision': decision}
    if note is not MISSING:
        body['note'] = note
    return ch.handle_admin_decision(body, event or admin_event())


def request_cancel(req, event=None, client=CLIENT):
    body = {'request_id': req, 'client_id': client, 'reason': 'Plans changed'}
    return ch.handle_customer_request(body, event or client_event())


def body_of(res):
    return json.loads(res['body'])


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv('TENANT_RESOLUTION_MODE', 'multi')
    monkeypatch.delenv('STAFF_COORDINATION_SNS_ARN', raising=False)
    with mock_aws():
        table = boto3.resource('dynamodb', region_name='us-east-1').create_table(
            TableName='be-cancel-1',
            KeySchema=[{'AttributeName': 'PK', 'KeyType': 'HASH'},
                       {'AttributeName': 'SK', 'KeyType': 'RANGE'}],
            AttributeDefinitions=[{'AttributeName': k, 'AttributeType': 'S'} for k in ('PK', 'SK')],
            BillingMode='PAY_PER_REQUEST',
        )
        original_put = table.put_item

        def seed_request(key, status=MISSING, prior=MISSING, jobs=(), worker_id=None,
                         google_event_id=None, company=TENANT, **extra):
            item = {
                'PK': f'REQ#{key}', 'SK': f'CLIENT#{CLIENT}', 'request_id': key,
                'client_id': CLIENT, 'client_email': CLIENT_EMAIL, 'company_id': company,
                'client_name': 'Test Client', 'start_date': '2030-01-01',
                'job_ids': [j for j, *_ in jobs],
            }
            if status is not MISSING:
                item['status'] = status
            if prior is not MISSING:
                item[ch.PRIOR_STATUS_ATTR] = prior
            if worker_id:
                item['worker_id'] = worker_id
            if google_event_id:
                item['google_event_id'] = google_event_id
            item.update(extra)
            original_put(Item=item)
            for job_id, job_status, job_worker in jobs:
                job = {'PK': f'JOB#{job_id}', 'SK': f'REQ#{key}', 'company_id': company,
                       'status': job_status}
                if job_worker:
                    job['worker_id'] = job_worker
                    job['worker_name'] = 'Sam Sitter'
                original_put(Item=job)

        def req(key):
            return table.get_item(Key={'PK': f'REQ#{key}', 'SK': f'CLIENT#{CLIENT}'},
                                  ConsistentRead=True).get('Item')

        def job(job_id, key):
            return table.get_item(Key={'PK': f'JOB#{job_id}', 'SK': f'REQ#{key}'},
                                  ConsistentRead=True).get('Item')

        with ExitStack() as stack:
            stack.enter_context(patch('common.db.table', table))
            stack.enter_context(patch.object(ch, 'table', table))
            stack.enter_context(patch('common.cascade.table', table))
            update_spy = stack.enter_context(
                patch.object(table, 'update_item', wraps=table.update_item))
            get_spy = stack.enter_context(
                patch.object(table, 'get_item', wraps=table.get_item))
            sns = stack.enter_context(patch.object(ch, 'notify_worker', return_value='sns-msg-1'))
            notify = stack.enter_context(patch.object(ch, 'notify_event'))
            audit = stack.enter_context(patch.object(ch, 'log_action'))
            gcal = stack.enter_context(patch('common.google_calendar.delete_event_detailed',
                                             return_value=(True, False, None)))
            yield SimpleNamespace(table=table, seed=seed_request, req=req, job=job,
                                  update_spy=update_spy, get_spy=get_spy, sns=sns,
                                  notify=notify, audit=audit, gcal=gcal)


@contextmanager
def race(competitor):
    """The caller's first REQ read returns a snapshot taken BEFORE `competitor()`
    commits; the caller then attempts its conditional write against changed state."""
    from common.db import get_item as real_get
    fired = {'done': False}

    def racing_get(pk, sk):
        snapshot = real_get(pk, sk)
        if pk.startswith('REQ#') and not fired['done']:
            fired['done'] = True
            competitor()
        return snapshot

    with patch.object(ch, 'get_item', side_effect=racing_get):
        yield


@contextmanager
def stale_read(snapshot):
    """The caller's first REQ read returns `snapshot` (an eventually-consistent stale view)."""
    from common.db import get_item as real_get
    served = {'done': False}

    def stale_get(pk, sk):
        if pk.startswith('REQ#') and not served['done']:
            served['done'] = True
            return copy.deepcopy(snapshot)
        return real_get(pk, sk)

    with patch.object(ch, 'get_item', side_effect=stale_get):
        yield


def assert_no_decision_write(env, key, before):
    assert env.req(key) == before
    env.audit.assert_not_called()
    env.sns.assert_not_called()
    env.notify.assert_not_called()


# ---------------------------------------------------------------------------
# 1-3. Strict validation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('decision', ['APPROVE', 'DENY'])
def test_01_exact_decisions_accepted(env, decision):
    env.seed('r1', status='CANCELLATION_REQUESTED', prior='APPROVED')
    res = decide('r1', decision)
    assert res['statusCode'] == 200, res['body']
    assert body_of(res)['decision'] == decision


@pytest.mark.parametrize('decision', [
    'approve', 'Approve', 'deny', ' APPROVE', 'APPROVE ', 'CANCEL', 'APPROVED', 'DENIED',
    True, 1, ['APPROVE'], {'d': 'APPROVE'},
])
def test_02_invalid_decision_rejected_without_writes(env, decision):
    env.seed('r2', status='CANCELLATION_REQUESTED', prior='ASSIGNED')
    before = env.req('r2')
    reads_before = env.get_spy.call_count
    res = decide('r2', decision)
    assert res['statusCode'] == 400
    env.update_spy.assert_not_called()
    assert env.get_spy.call_count == reads_before  # validated before any read
    assert_no_decision_write(env, 'r2', before)


def test_02_missing_decision_rejected(env):
    env.seed('r2m', status='CANCELLATION_REQUESTED', prior='ASSIGNED')
    res = ch.handle_admin_decision({'request_id': 'r2m', 'client_id': CLIENT}, admin_event())
    assert res['statusCode'] == 400
    env.update_spy.assert_not_called()


@pytest.mark.parametrize('note,status', [
    (123, 400), (['x'], 400), ({'n': 1}, 400), ('x' * 501, 400),
    ('x' * 500, 200), ('', 200), (None, 200),
])
def test_03_note_type_and_length(env, note, status):
    env.seed('r3', status='CANCELLATION_REQUESTED', prior='APPROVED')
    before = env.req('r3')
    res = decide('r3', 'DENY', note=note)
    assert res['statusCode'] == status, res['body']
    if status == 400:
        env.update_spy.assert_not_called()
        assert env.req('r3') == before
    else:
        assert env.req('r3')['cancellation_decision_note'] == (note or '')


# ---------------------------------------------------------------------------
# 4-5. State eligibility
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('status', ['APPROVED', 'ASSIGNED', 'CANCELLED', 'COMPLETED',
                                    'CANCELLATION_DENIED', 'PENDING_REVIEW'])
@pytest.mark.parametrize('decision', ['APPROVE', 'DENY'])
def test_04_non_pending_decision_rejected(env, status, decision):
    env.seed('r4', status=status, prior='ASSIGNED')
    before = env.req('r4')
    res = decide('r4', decision)
    assert res['statusCode'] == 409
    assert body_of(res)['code'] == ch.CODE_NOT_PENDING
    assert body_of(res)['current_status'] == status
    assert_no_decision_write(env, 'r4', before)


REFUSED_REQUEST_STATUSES = [
    # finished / closed
    'CANCELLED', 'COMPLETED', 'ARCHIVED', 'DELETED', 'DECLINED',
    # early workflow: not a canonical predecessor of CANCELLATION_REQUESTED
    'PENDING_REVIEW', 'PROFILE_CREATED', 'MEET_GREET_REQUIRED', 'MG_SCHEDULED',
    'MG_COMPLETED', 'READY_FOR_APPROVAL', 'QUOTE_NEEDED', 'QUOTE_SENT', 'QUOTED',
    # already decided / unknown
    'CANCELLATION_DENIED', 'BOGUS', 'approved',
]


def test_05_restorable_allowlist_is_canonical():
    """The restorable set is exactly the canonical predecessors of CANCELLATION_REQUESTED."""
    from common.status import REQUEST_TRANSITIONS
    predecessors = {s for s, nxt in REQUEST_TRANSITIONS.items() if 'CANCELLATION_REQUESTED' in nxt}
    assert ch.RESTORABLE_PRIOR_STATUSES == predecessors == {'APPROVED', 'ASSIGNED'}
    assert not (ch.LEGACY_CANCELLABLE_SYNONYMS & ch.RESTORABLE_PRIOR_STATUSES)


@pytest.mark.parametrize('status', REFUSED_REQUEST_STATUSES)
def test_05_cancellation_request_on_ineligible_booking_rejected(env, status):
    env.seed('r5', status=status)
    before = env.req('r5')
    res = request_cancel('r5')
    assert res['statusCode'] == 409
    assert body_of(res)['code'] == ch.CODE_BOOKING_NOT_CANCELLABLE
    env.update_spy.assert_not_called()
    assert env.req('r5') == before


def test_05_cancellation_request_with_unknown_status_rejected(env):
    env.seed('r5u')  # no status attribute
    res = request_cancel('r5u')
    assert res['statusCode'] == 409
    assert body_of(res)['code'] == ch.CODE_BOOKING_STATE_UNKNOWN
    env.update_spy.assert_not_called()


def test_05_cancellation_request_condition_failure_is_409(env):
    """Booking completed between the client's read and write: never overwritten."""
    env.seed('r5c', status='ASSIGNED')
    snapshot = env.req('r5c')
    env.table.update_item(Key={'PK': 'REQ#r5c', 'SK': f'CLIENT#{CLIENT}'},
                          UpdateExpression='SET #s = :c', ExpressionAttributeNames={'#s': 'status'},
                          ExpressionAttributeValues={':c': 'COMPLETED'})
    with stale_read(snapshot):
        res = request_cancel('r5c')
    assert res['statusCode'] == 409
    assert body_of(res)['code'] == ch.CODE_STATE_CHANGED
    assert env.req('r5c')['status'] == 'COMPLETED'
    assert ch.PRIOR_STATUS_ATTR not in env.req('r5c')


# ---------------------------------------------------------------------------
# 6-8. Competing decisions and replay
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('winner,loser', [('APPROVE', 'DENY'), ('DENY', 'APPROVE')])
def test_06_competing_decisions_exactly_one_wins(env, winner, loser):
    env.seed('r6', status='CANCELLATION_REQUESTED', prior='ASSIGNED', worker_id='w1',
             jobs=[('j1', 'ASSIGNED', 'w1')])
    results = {}

    def competitor():
        results['winner'] = decide('r6', winner)

    with race(competitor):
        results['loser'] = decide('r6', loser)

    assert results['winner']['statusCode'] == 200
    assert results['loser']['statusCode'] == 409
    assert body_of(results['loser'])['code'] == ch.CODE_NOT_PENDING
    assert body_of(results['loser'])['previous_decision'] == winner

    final = env.req('r6')
    assert final['cancellation_decision'] == winner
    assert final['status'] == ('CANCELLED' if winner == 'APPROVE' else 'ASSIGNED')
    decisions = [e.get('decision') for e in final['audit_log'] if e.get('decision')]
    assert decisions == [winner]
    assert env.job('j1', 'r6')['status'] == ('CANCELLED' if winner == 'APPROVE' else 'ASSIGNED')
    assert env.sns.call_count == (1 if winner == 'APPROVE' else 0)
    assert env.notify.call_count == (1 if winner == 'APPROVE' else 0)
    assert env.audit.call_count == 1
    # The loser reconciled with a consistent read.
    assert any(c.kwargs.get('ConsistentRead') is True for c in env.get_spy.call_args_list)


def test_06_two_racing_approves_send_one_notification(env):
    env.seed('r6a', status='CANCELLATION_REQUESTED', prior='ASSIGNED', worker_id='w1')
    results = {}
    with race(lambda: results.setdefault('first', decide('r6a', 'APPROVE'))):
        results['second'] = decide('r6a', 'APPROVE')
    assert results['first']['statusCode'] == 200
    assert results['second']['statusCode'] == 200
    assert body_of(results['first'])['idempotent_replay'] is False
    assert body_of(results['second'])['idempotent_replay'] is True
    assert env.sns.call_count == 1
    assert env.notify.call_count == 1


@pytest.mark.parametrize('decision,expected', [('APPROVE', 'CANCELLED'), ('DENY', 'APPROVED')])
def test_07_same_decision_replay_is_idempotent(env, decision, expected):
    env.seed('r7', status='CANCELLATION_REQUESTED', prior='APPROVED', worker_id='w1',
             google_event_id='evt-1')
    first = decide('r7', decision)
    after_first = env.req('r7')
    second = decide('r7', decision)
    assert first['statusCode'] == 200 and second['statusCode'] == 200
    b = body_of(second)
    assert b['idempotent_replay'] is True
    assert b['new_status'] == expected
    assert b['sns_message_id'] is None
    assert env.req('r7')['status'] == expected
    assert env.req('r7')['audit_log'] == after_first['audit_log']  # no second decision entry
    assert env.sns.call_count == (1 if decision == 'APPROVE' else 0)
    assert env.notify.call_count == (1 if decision == 'APPROVE' else 0)
    assert env.audit.call_count == 1
    # Calendar event was removed after the first delete; replay does not re-delete it.
    assert env.gcal.call_count == (1 if decision == 'APPROVE' else 0)


@pytest.mark.parametrize('first,second', [('APPROVE', 'DENY'), ('DENY', 'APPROVE')])
def test_08_different_decision_replay_rejected(env, first, second):
    env.seed('r8', status='CANCELLATION_REQUESTED', prior='ASSIGNED', worker_id='w1')
    assert decide('r8', first)['statusCode'] == 200
    after_first = env.req('r8')
    sns_count, notify_count = env.sns.call_count, env.notify.call_count
    res = decide('r8', second)
    assert res['statusCode'] == 409
    assert body_of(res)['code'] == ch.CODE_NOT_PENDING
    assert body_of(res)['previous_decision'] == first
    assert env.req('r8') == after_first
    assert (env.sns.call_count, env.notify.call_count) == (sns_count, notify_count)


# ---------------------------------------------------------------------------
# 9. RBAC and tenant isolation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('role', ['staff', 'client', 'platform_admin', ''])
def test_09_non_owner_admin_forbidden(env, role):
    env.seed('r9', status='CANCELLATION_REQUESTED', prior='ASSIGNED')
    before = env.req('r9')
    res = decide('r9', 'APPROVE', event=admin_event(role=role, email='someone@example.test'))
    assert res['statusCode'] == 403
    env.update_spy.assert_not_called()
    assert_no_decision_write(env, 'r9', before)


@pytest.mark.parametrize('role', ['owner', 'admin'])
def test_09_owner_and_admin_allowed(env, role):
    env.seed('r9ok', status='CANCELLATION_REQUESTED', prior='ASSIGNED')
    assert decide('r9ok', 'DENY', event=admin_event(role=role))['statusCode'] == 200


@pytest.mark.parametrize('decision', ['APPROVE', 'DENY'])
def test_09_cross_tenant_decision_forbidden(env, decision):
    env.seed('r9x', status='CANCELLATION_REQUESTED', prior='ASSIGNED', company=OTHER_TENANT)
    before = env.req('r9x')
    res = decide('r9x', decision, event=admin_event(company=TENANT))
    assert res['statusCode'] == 403
    env.update_spy.assert_not_called()
    assert_no_decision_write(env, 'r9x', before)


def test_09_cross_tenant_on_reconciliation_read_forbidden(env):
    """Tenant ownership is re-validated on the consistent reconciliation read."""
    env.seed('r9r', status='CANCELLED', company=OTHER_TENANT, cancellation_decision='APPROVE',
             cancellation_decision_result_status='CANCELLED')
    stale = env.req('r9r')
    stale['company_id'] = TENANT          # a misleading first read
    stale['status'] = 'APPROVED'          # non-pending -> reconciliation path
    with stale_read(stale):
        res = decide('r9r', 'APPROVE')
    assert res['statusCode'] == 403
    assert 'idempotent_replay' not in res['body']
    env.update_spy.assert_not_called()


def test_09_cross_tenant_customer_request_forbidden(env):
    env.seed('r9c', status='ASSIGNED', company=OTHER_TENANT)
    res = request_cancel('r9c', event=client_event(company=TENANT))
    assert res['statusCode'] == 403
    env.update_spy.assert_not_called()


# ---------------------------------------------------------------------------
# 10-14. D1 Option A: prior status capture and DENY restoration
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('status', sorted(ch.RESTORABLE_PRIOR_STATUSES))
def test_10_prior_status_captured_on_request(env, status):
    env.seed('r10', status=status)
    res = request_cancel('r10')
    assert res['statusCode'] == 200, res['body']
    item = env.req('r10')
    assert item['status'] == 'CANCELLATION_REQUESTED'
    assert item[ch.PRIOR_STATUS_ATTR] == status
    assert item['cancellation_prior_status_captured_at']


def test_10_repeat_request_never_replaces_recorded_prior(env):
    env.seed('r10r', status='ASSIGNED')
    assert request_cancel('r10r')['statusCode'] == 200
    assert request_cancel('r10r')['statusCode'] == 200
    assert env.req('r10r')[ch.PRIOR_STATUS_ATTR] == 'ASSIGNED'


@pytest.mark.parametrize('status', sorted(ch.LEGACY_CANCELLABLE_SYNONYMS))
def test_10_legacy_synonym_is_accepted_but_never_captured(env, status):
    """Web still offers cancel for legacy synonyms; their prior is never trusted, so a
    DENY fails closed (stale prior/decision fields from an earlier cycle are cleared)."""
    env.seed('r10u', status=status, prior='ASSIGNED', jobs=[('j1', 'ASSIGNED', 'w1')],
             cancellation_decision='DENY', cancellation_decision_result_status='ASSIGNED')
    assert request_cancel('r10u')['statusCode'] == 200
    item = env.req('r10u')
    assert item['status'] == 'CANCELLATION_REQUESTED'
    assert ch.PRIOR_STATUS_ATTR not in item           # stale prior cleared, never reused
    assert 'cancellation_decision' not in item
    before, job_before = env.req('r10u'), env.job('j1', 'r10u')
    res = decide('r10u', 'DENY')
    assert res['statusCode'] == 409
    assert body_of(res)['code'] == ch.CODE_LEGACY_PRIOR_STATUS_UNKNOWN
    assert env.req('r10u') == before
    assert env.job('j1', 'r10u') == job_before


def test_10_new_cycle_after_deny_recaptures_prior(env):
    env.seed('r10n', status='APPROVED')
    assert request_cancel('r10n')['statusCode'] == 200
    assert decide('r10n', 'DENY')['statusCode'] == 200
    assert env.req('r10n')['status'] == 'APPROVED'
    assert request_cancel('r10n')['statusCode'] == 200
    item = env.req('r10n')
    assert item[ch.PRIOR_STATUS_ATTR] == 'APPROVED'
    assert 'cancellation_decision' not in item
    assert decide('r10n', 'DENY')['statusCode'] == 200   # not mistaken for a replay
    assert env.req('r10n')['status'] == 'APPROVED'


@pytest.mark.parametrize('prior', ['APPROVED', 'ASSIGNED'])
def test_11_deny_restores_prior_status(env, prior):
    env.seed('r11', status=prior)
    assert request_cancel('r11')['statusCode'] == 200
    res = decide('r11', 'DENY')
    assert res['statusCode'] == 200
    b = body_of(res)
    assert b['new_status'] == prior
    assert prior in b['message']
    item = env.req('r11')
    assert item['status'] == prior
    assert item['cancellation_decision'] == 'DENY'
    assert item['cancellation_decision_result_status'] == prior
    assert item['cancellation_decision_actor'] == 'admin@example.test'
    env.sns.assert_not_called()
    env.notify.assert_not_called()


def test_12_13_deny_leaves_jobs_untouched(env):
    """DENY never runs the forced-ASSIGNED cascade: unassigned stays unassigned,
    assigned keeps its worker, completed stays completed, no job is created."""
    env.seed('r12', status='CANCELLATION_REQUESTED', prior='APPROVED', jobs=[
        ('j-un', 'JOB_CREATED', None), ('j-as', 'ASSIGNED', 'w1'), ('j-done', 'COMPLETED', 'w1'),
    ])
    jobs_before = {j: env.job(j, 'r12') for j in ('j-un', 'j-as', 'j-done')}
    with patch('common.cascade.cascade_status_to_job') as cascade:
        res = decide('r12', 'DENY')
    assert res['statusCode'] == 200
    cascade.assert_not_called()
    for j, before in jobs_before.items():
        assert env.job(j, 'r12') == before
    assert 'worker_id' not in env.job('j-un', 'r12')
    assert env.job('j-ghost', 'r12') is None


def test_13_approve_preserves_completed_visits(env):
    env.seed('r13', status='CANCELLATION_REQUESTED', prior='ASSIGNED', jobs=[
        ('j-open', 'ASSIGNED', 'w1'), ('j-done', 'COMPLETED', 'w1'),
    ])
    assert decide('r13', 'APPROVE')['statusCode'] == 200
    assert env.job('j-open', 'r13')['status'] == 'CANCELLED'
    assert env.job('j-done', 'r13')['status'] == 'COMPLETED'


@pytest.mark.parametrize('prior', [MISSING, 'CANCELLATION_DENIED', 'COMPLETED', 'CANCELLED',
                                   'BOGUS', '', 'approved'])
def test_14_legacy_unknown_prior_status_deny_is_409(env, prior):
    env.seed('r14', status='CANCELLATION_REQUESTED', prior=prior,
             jobs=[('j1', 'ASSIGNED', 'w1')])     # jobs must NOT be used to infer a prior
    before = env.req('r14')
    job_before = env.job('j1', 'r14')
    res = decide('r14', 'DENY')
    assert res['statusCode'] == 409
    assert body_of(res)['code'] == ch.CODE_LEGACY_PRIOR_STATUS_UNKNOWN
    env.update_spy.assert_not_called()
    assert_no_decision_write(env, 'r14', before)
    assert env.job('j1', 'r14') == job_before


def test_14_legacy_request_can_still_be_approved(env):
    env.seed('r14a', status='CANCELLATION_REQUESTED')
    assert decide('r14a', 'APPROVE')['statusCode'] == 200
    assert env.req('r14a')['status'] == 'CANCELLED'


# ---------------------------------------------------------------------------
# 15. Conditional-write failure and consistent-read reconciliation
# ---------------------------------------------------------------------------

def test_15_deny_with_changed_prior_status_is_rejected(env):
    """Still pending, but the recorded prior changed after our read: never applied."""
    env.seed('r15', status='CANCELLATION_REQUESTED', prior='ASSIGNED')
    snapshot = env.req('r15')
    env.table.update_item(Key={'PK': 'REQ#r15', 'SK': f'CLIENT#{CLIENT}'},
                          UpdateExpression='SET #p = :p', ExpressionAttributeNames={'#p': ch.PRIOR_STATUS_ATTR},
                          ExpressionAttributeValues={':p': 'APPROVED'})
    env.update_spy.reset_mock()
    env.get_spy.reset_mock()
    with stale_read(snapshot):
        res = decide('r15', 'DENY')
    assert res['statusCode'] == 409
    assert body_of(res)['code'] == ch.CODE_STATE_CHANGED
    item = env.req('r15')
    assert item['status'] == 'CANCELLATION_REQUESTED'
    assert item[ch.PRIOR_STATUS_ATTR] == 'APPROVED'
    assert 'cancellation_decision' not in item
    assert env.update_spy.call_count == 1                   # only the failed conditional write
    assert any(c.kwargs.get('ConsistentRead') is True for c in env.get_spy.call_args_list)


def test_15_stale_non_pending_read_is_verified_consistently(env):
    """An eventually-consistent read that looks non-pending is re-checked; a still
    pending request is reported as changed, not as already decided."""
    env.seed('r15s', status='CANCELLATION_REQUESTED', prior='ASSIGNED')
    stale = env.req('r15s')
    stale['status'] = 'ASSIGNED'
    with stale_read(stale):
        res = decide('r15s', 'APPROVE')
    assert res['statusCode'] == 409
    assert body_of(res)['code'] == ch.CODE_STATE_CHANGED
    assert env.req('r15s')['status'] == 'CANCELLATION_REQUESTED'


def test_15_non_conditional_write_error_is_500_without_side_effects(env):
    from botocore.exceptions import ClientError
    env.seed('r15e', status='CANCELLATION_REQUESTED', prior='ASSIGNED', worker_id='w1')
    err = ClientError({'Error': {'Code': 'ProvisionedThroughputExceededException', 'Message': 'x'}},
                      'UpdateItem')
    with patch.object(env.table, 'update_item', side_effect=err):
        res = decide('r15e', 'APPROVE')
    assert res['statusCode'] == 500
    env.sns.assert_not_called()
    env.notify.assert_not_called()


# ---------------------------------------------------------------------------
# 16-18. Separately fallible side effects
# ---------------------------------------------------------------------------

class _FailingJobTable:
    """Delegates to the moto table but fails updates for one job."""

    def __init__(self, table, failing_pk):
        self._table, self._failing_pk = table, failing_pk

    def get_item(self, **kw):
        return self._table.get_item(**kw)

    def update_item(self, **kw):
        if kw['Key']['PK'] == self._failing_pk:
            raise RuntimeError('simulated job write failure')
        return self._table.update_item(**kw)


def test_16_partial_job_cascade_failure_recorded_and_replay_repairs(env):
    env.seed('r16', status='CANCELLATION_REQUESTED', prior='ASSIGNED', worker_id='w1', jobs=[
        ('j1', 'ASSIGNED', 'w1'), ('j2', 'ASSIGNED', 'w1'), ('j3', 'COMPLETED', 'w1'),
    ])
    with patch('common.cascade.table', _FailingJobTable(env.table, 'JOB#j2')):
        res = decide('r16', 'APPROVE')
    assert res['statusCode'] == 200
    b = body_of(res)
    assert [w['type'] for w in b['warnings']] == ['JOB_CASCADE']
    item = env.req('r16')
    assert item['status'] == 'CANCELLED'                      # decision committed
    assert [f['type'] for f in item['sync_failures']] == ['JOB_CASCADE']
    assert env.job('j1', 'r16')['status'] == 'CANCELLED'
    assert env.job('j2', 'r16')['status'] == 'ASSIGNED'       # truthfully left behind
    assert env.job('j3', 'r16')['status'] == 'COMPLETED'

    # Same-decision replay re-runs only the idempotent cascade, never SNS.
    replay = decide('r16', 'APPROVE')
    assert replay['statusCode'] == 200
    assert body_of(replay)['idempotent_replay'] is True
    assert env.job('j2', 'r16')['status'] == 'CANCELLED'
    assert env.job('j3', 'r16')['status'] == 'COMPLETED'
    assert env.sns.call_count == 1
    assert env.notify.call_count == 1


def test_17_calendar_sns_notification_and_audit_failures_recorded(env):
    env.seed('r17', status='CANCELLATION_REQUESTED', prior='ASSIGNED', worker_id='w1',
             google_event_id='evt-1')
    env.gcal.return_value = (False, False, 'API connection timeout')
    env.sns.side_effect = RuntimeError('SNS down')
    env.notify.side_effect = RuntimeError('email down')
    env.audit.side_effect = RuntimeError('audit down')
    res = decide('r17', 'APPROVE')
    assert res['statusCode'] == 200
    kinds = sorted(w['type'] for w in body_of(res)['warnings'])
    assert kinds == ['AUDIT_LOG', 'GOOGLE_CALENDAR', 'NOTIFICATION', 'SNS_NOTIFICATION']
    item = env.req('r17')
    assert item['status'] == 'CANCELLED'
    assert sorted(f['type'] for f in item['sync_failures']) == kinds
    assert item['google_event_id'] == 'evt-1'   # not removed after a failed delete


def test_18_no_duplicate_notifications_on_replay_after_failure(env):
    """Documented limitation: a failed SNS is recorded, NOT retried by replay
    (no duplicates is favoured over guaranteed delivery)."""
    env.seed('r18', status='CANCELLATION_REQUESTED', prior='ASSIGNED', worker_id='w1')
    env.sns.side_effect = RuntimeError('SNS down')
    assert decide('r18', 'APPROVE')['statusCode'] == 200
    env.sns.side_effect = None
    for _ in range(3):
        res = decide('r18', 'APPROVE')
        assert res['statusCode'] == 200
        assert body_of(res)['idempotent_replay'] is True
    assert env.sns.call_count == 1
    assert env.notify.call_count == 1


# ---------------------------------------------------------------------------
# BE-CANCEL-1A: cancellation-cycle identity
# ---------------------------------------------------------------------------
import re as _re
import uuid as _uuid

_UUID4 = _re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$')


def decide_cycle(req, decision, cycle, event=None):
    body = {'request_id': req, 'client_id': CLIENT, 'decision': decision,
            ch.CYCLE_ATTR: cycle}
    return ch.handle_admin_decision(body, event or admin_event())


def test_19_cycle_identity_lifecycle(env):
    env.seed('c19', status='APPROVED')
    assert request_cancel('c19')['statusCode'] == 200
    cycle_a = env.req('c19')[ch.CYCLE_ATTR]
    assert _UUID4.match(cycle_a)
    assert request_cancel('c19')['statusCode'] == 200          # repeat while pending
    assert env.req('c19')[ch.CYCLE_ATTR] == cycle_a            # identity never replaced
    assert decide_cycle('c19', 'DENY', cycle_a)['statusCode'] == 200
    assert env.req('c19')[ch.DECISION_CYCLE_ATTR] == cycle_a
    assert request_cancel('c19')['statusCode'] == 200          # new cycle B
    item = env.req('c19')
    assert _UUID4.match(item[ch.CYCLE_ATTR]) and item[ch.CYCLE_ATTR] != cycle_a
    assert ch.DECISION_CYCLE_ATTR not in item                  # A's decision identity cleared


@pytest.mark.parametrize('delayed', ['APPROVE', 'DENY'])
def test_20_delayed_decision_from_cycle_a_never_applies_to_cycle_b(env, delayed):
    env.seed('c20', status='ASSIGNED', worker_id='w1', jobs=[('j1', 'ASSIGNED', 'w1')])
    assert request_cancel('c20')['statusCode'] == 200
    cycle_a = env.req('c20')[ch.CYCLE_ATTR]
    assert decide_cycle('c20', 'DENY', cycle_a)['statusCode'] == 200   # A denied
    assert request_cancel('c20')['statusCode'] == 200                  # B pending
    before, job_before = env.req('c20'), env.job('j1', 'c20')
    counts = (env.sns.call_count, env.notify.call_count, env.audit.call_count)
    res = decide_cycle('c20', delayed, cycle_a)                         # delayed A decision
    assert res['statusCode'] == 409
    assert body_of(res)['code'] == ch.CODE_CYCLE_MISMATCH
    assert env.req('c20') == before                                    # B untouched
    assert env.job('j1', 'c20') == job_before
    assert (env.sns.call_count, env.notify.call_count, env.audit.call_count) == counts


@pytest.mark.parametrize('decision', ['APPROVE', 'DENY'])
def test_20_delayed_decision_not_replayed_against_decided_cycle_b(env, decision):
    """B decided with the same decision: A's delayed copy is a mismatch, not a replay."""
    env.seed('c20b', status='APPROVED', worker_id='w1')
    assert request_cancel('c20b')['statusCode'] == 200
    cycle_a = env.req('c20b')[ch.CYCLE_ATTR]
    assert decide_cycle('c20b', 'DENY', cycle_a)['statusCode'] == 200
    assert request_cancel('c20b')['statusCode'] == 200
    cycle_b = env.req('c20b')[ch.CYCLE_ATTR]
    assert decide_cycle('c20b', decision, cycle_b)['statusCode'] == 200
    before = env.req('c20b')
    counts = (env.sns.call_count, env.notify.call_count)
    res = decide_cycle('c20b', decision, cycle_a)
    assert res['statusCode'] == 409
    assert body_of(res)['code'] == ch.CODE_CYCLE_MISMATCH
    assert 'idempotent_replay' not in res['body']
    assert env.req('c20b') == before
    assert (env.sns.call_count, env.notify.call_count) == counts


@pytest.mark.parametrize('decision,expected', [('APPROVE', 'CANCELLED'), ('DENY', 'APPROVED')])
def test_21_same_cycle_replay_is_idempotent(env, decision, expected):
    env.seed('c21', status='APPROVED', worker_id='w1')
    assert request_cancel('c21')['statusCode'] == 200
    cycle = env.req('c21')[ch.CYCLE_ATTR]
    assert decide_cycle('c21', decision, cycle)['statusCode'] == 200
    res = decide_cycle('c21', decision, cycle)
    assert res['statusCode'] == 200
    assert body_of(res)['idempotent_replay'] is True
    assert body_of(res)['new_status'] == expected
    assert env.sns.call_count == (1 if decision == 'APPROVE' else 0)
    assert env.notify.call_count == (1 if decision == 'APPROVE' else 0)


@pytest.mark.parametrize('first,second', [('APPROVE', 'DENY'), ('DENY', 'APPROVE')])
def test_22_different_decision_same_cycle_conflicts(env, first, second):
    env.seed('c22', status='ASSIGNED')
    assert request_cancel('c22')['statusCode'] == 200
    cycle = env.req('c22')[ch.CYCLE_ATTR]
    assert decide_cycle('c22', first, cycle)['statusCode'] == 200
    after = env.req('c22')
    res = decide_cycle('c22', second, cycle)
    assert res['statusCode'] == 409
    assert body_of(res)['code'] == ch.CODE_NOT_PENDING
    assert env.req('c22') == after


@pytest.mark.parametrize('cycle', [
    '', 'abc', 123, True, ['x'], {'c': 1},
    str(_uuid.uuid4()).upper(), str(_uuid.uuid1()), str(_uuid.uuid4()) + ' ',
])
def test_23_malformed_cycle_identity_rejected_before_any_read(env, cycle):
    env.seed('c23', status='CANCELLATION_REQUESTED', prior='ASSIGNED')
    before = env.req('c23')
    reads = env.get_spy.call_count
    res = decide_cycle('c23', 'DENY', cycle)
    assert res['statusCode'] == 400
    assert env.get_spy.call_count == reads
    env.update_spy.assert_not_called()
    assert env.req('c23') == before


def test_23_unknown_cycle_on_pending_request_is_mismatch(env):
    env.seed('c23u', status='APPROVED')
    assert request_cancel('c23u')['statusCode'] == 200
    before = env.req('c23u')
    env.update_spy.reset_mock()
    res = decide_cycle('c23u', 'APPROVE', str(_uuid.uuid4()))
    assert res['statusCode'] == 409
    assert body_of(res)['code'] == ch.CODE_CYCLE_MISMATCH
    env.update_spy.assert_not_called()
    assert env.req('c23u') == before


def test_23_legacy_pending_without_cycle_rejects_supplied_cycle(env):
    env.seed('c23l', status='CANCELLATION_REQUESTED', prior='ASSIGNED')   # pre-1A record
    before = env.req('c23l')
    res = decide_cycle('c23l', 'DENY', str(_uuid.uuid4()))
    assert res['statusCode'] == 409
    assert body_of(res)['code'] == ch.CODE_CYCLE_MISMATCH
    assert env.req('c23l') == before


@pytest.mark.parametrize('decision', ['APPROVE', 'DENY'])
def test_24_mobile_s2_contract_without_cycle_id_still_works(env, decision):
    """Existing mobile S2 sends {request_id, client_id, decision, note} only."""
    env.seed('c24', status='ASSIGNED')
    assert request_cancel('c24')['statusCode'] == 200
    cycle = env.req('c24')[ch.CYCLE_ATTR]
    res = decide('c24', decision, note='ok')
    assert res['statusCode'] == 200
    b = body_of(res)
    assert set(b) >= {'message', 'new_status', 'decision', 'sns_message_id',
                      'idempotent_replay', 'warnings'}
    assert env.req('c24')[ch.DECISION_CYCLE_ATTR] == cycle     # bound to the observed cycle
    assert decide('c24', decision)['statusCode'] == 200        # replay still idempotent


def test_25_new_cycle_between_read_and_write_is_not_decided(env):
    """Legacy client (no cycle id): its read saw cycle A, but A was denied and cycle B
    requested before its write. The write is pinned to A, so B is never decided."""
    env.seed('c25', status='APPROVED')
    assert request_cancel('c25')['statusCode'] == 200
    snapshot_a = env.req('c25')
    assert decide('c25', 'DENY')['statusCode'] == 200
    assert request_cancel('c25')['statusCode'] == 200
    before_b = env.req('c25')
    with stale_read(snapshot_a):
        res = decide('c25', 'APPROVE')
    assert res['statusCode'] == 409
    assert body_of(res)['code'] == ch.CODE_STATE_CHANGED
    assert env.req('c25') == before_b
    assert env.sns.call_count == 0


# ---------------------------------------------------------------------------
# BE-CANCEL-1A: missing-job safety in the APPROVE cascade
# ---------------------------------------------------------------------------

def test_26_missing_referenced_job_is_never_created(env):
    env.seed('c26', status='CANCELLATION_REQUESTED', prior='ASSIGNED', worker_id='w1',
             jobs=[('j1', 'ASSIGNED', 'w1'), ('j3', 'COMPLETED', 'w1')],
             job_ids=['j1', 'j-ghost', 'j3'])
    res = decide('c26', 'APPROVE')
    assert res['statusCode'] == 200
    assert env.job('j-ghost', 'c26') is None                    # no stub JOB
    assert env.job('j1', 'c26')['status'] == 'CANCELLED'        # existing job cancelled
    assert env.job('j3', 'c26')['status'] == 'COMPLETED'        # completed preserved
    kinds = [w['type'] for w in body_of(res)['warnings']]
    assert kinds == ['JOB_MISSING']
    assert 'j-ghost' in body_of(res)['warnings'][0]['error']
    assert [f['type'] for f in env.req('c26')['sync_failures']] == ['JOB_MISSING']
    # Replay keeps it missing and still sends nothing twice.
    replay = decide('c26', 'APPROVE')
    assert body_of(replay)['idempotent_replay'] is True
    assert env.job('j-ghost', 'c26') is None
    assert env.sns.call_count == 1 and env.notify.call_count == 1


class _StaleJobReadTable:
    """Cascade sees `stale_job` on read, while the real table holds something else."""

    def __init__(self, table, job_pk, stale_job):
        self._table, self._job_pk, self._stale = table, job_pk, stale_job

    def get_item(self, **kw):
        if kw['Key']['PK'] == self._job_pk:
            return {'Item': dict(self._stale)}
        return self._table.get_item(**kw)

    def update_item(self, **kw):
        return self._table.update_item(**kw)


def test_27_job_deleted_after_read_is_not_recreated(env):
    env.seed('c27', status='CANCELLATION_REQUESTED', prior='ASSIGNED', job_ids=['j-gone'])
    stale = {'PK': 'JOB#j-gone', 'SK': 'REQ#c27', 'company_id': TENANT, 'status': 'ASSIGNED'}
    with patch('common.cascade.table', _StaleJobReadTable(env.table, 'JOB#j-gone', stale)):
        res = decide('c27', 'APPROVE')
    assert res['statusCode'] == 200
    assert env.job('j-gone', 'c27') is None
    assert [w['type'] for w in body_of(res)['warnings']] == ['JOB_CASCADE']


def test_28_job_completed_after_read_stays_completed(env):
    env.seed('c28', status='CANCELLATION_REQUESTED', prior='ASSIGNED',
             jobs=[('j1', 'COMPLETED', 'w1')])
    stale = {'PK': 'JOB#j1', 'SK': 'REQ#c28', 'company_id': TENANT, 'status': 'ASSIGNED'}
    with patch('common.cascade.table', _StaleJobReadTable(env.table, 'JOB#j1', stale)):
        res = decide('c28', 'APPROVE')
    assert res['statusCode'] == 200
    assert env.job('j1', 'c28')['status'] == 'COMPLETED'
    assert [w['type'] for w in body_of(res)['warnings']] == ['JOB_CASCADE']
    # The idempotent replay re-reads and preserves COMPLETED without a failure.
    replay = decide('c28', 'APPROVE')
    assert body_of(replay)['warnings'] == []
    assert env.job('j1', 'c28')['status'] == 'COMPLETED'


def test_29_deny_never_touches_missing_or_existing_jobs(env):
    env.seed('c29', status='CANCELLATION_REQUESTED', prior='ASSIGNED',
             jobs=[('j1', 'ASSIGNED', 'w1')], job_ids=['j1', 'j-ghost'])
    before = env.job('j1', 'c29')
    assert decide('c29', 'DENY')['statusCode'] == 200
    assert env.job('j1', 'c29') == before
    assert env.job('j-ghost', 'c29') is None
