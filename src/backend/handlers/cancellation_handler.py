import json
import os
import re
import uuid
import boto3
from botocore.exceptions import ClientError
from datetime import datetime, timezone
from common.db import get_item, update_status, update_item, table
from common.response import success, error, bad_request, internal_error, format_response
from common.status import RequestStatus, is_valid_transition
from common.google_calendar import delete_event
from common.audit import log_action
from common.notifications.service import notify_event

# SNS client
sns = boto3.client('sns')

# ---------------------------------------------------------------------------
# BE-CANCEL-1: cancellation decision safety contract
# ---------------------------------------------------------------------------
# The only decision literals accepted (exact, case-sensitive).
CANCELLATION_DECISIONS = ('APPROVE', 'DENY')
CANCELLATION_REQUESTED = 'CANCELLATION_REQUESTED'
MAX_DECISION_NOTE_LEN = 500

# D1 Option A: the only statuses that are captured when a client requests
# cancellation and that a DENY may restore. These are exactly the canonical
# predecessors of CANCELLATION_REQUESTED in common.status.REQUEST_TRANSITIONS.
# Anything else (absent, legacy synonyms, CANCELLATION_DENIED, unknown values) is
# never captured and never guessed.
RESTORABLE_PRIOR_STATUSES = frozenset({'APPROVED', 'ASSIGNED'})

# Legacy display synonyms (shared/constants/request-statuses.json) that the web
# client portal still offers "request cancellation" for. Accepted for compatibility,
# but never captured as a prior status: a DENY on such a request fails closed with
# LEGACY_PRIOR_STATUS_UNKNOWN instead of restoring a non-canonical status.
LEGACY_CANCELLABLE_SYNONYMS = frozenset({'BOOKED', 'SCHEDULED', 'JOB_CREATED'})

# A client may request cancellation only from these statuses (plus a repeat request
# while already CANCELLATION_REQUESTED). This mirrors the canonical transition map
# and the web portal's canCancel list; every other status is refused.
CANCELLATION_REQUESTABLE_STATUSES = (
    RESTORABLE_PRIOR_STATUSES | LEGACY_CANCELLABLE_SYNONYMS | {'CANCELLATION_REQUESTED'}
)

PRIOR_STATUS_ATTR = 'cancellation_prior_status'

# BE-CANCEL-1A: server-generated cancellation-cycle identity. A new UUID4 is written
# when a client starts a new cancellation cycle and is never replaced while that cycle
# is pending (cancellation_requested_at is NOT used: a repeat request rewrites it).
# Every decision write is pinned to the cycle it was made against, and the decision
# records which cycle it decided.
CYCLE_ATTR = 'cancellation_request_id'
DECISION_CYCLE_ATTR = 'cancellation_decision_request_id'
_CYCLE_ID_RE = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$')

# Stable machine-readable classifications returned with 409 responses.
CODE_BOOKING_NOT_CANCELLABLE = 'BOOKING_NOT_CANCELLABLE'
CODE_BOOKING_STATE_UNKNOWN = 'BOOKING_STATE_UNKNOWN'
CODE_STATE_CHANGED = 'CANCELLATION_STATE_CHANGED'
CODE_NOT_PENDING = 'CANCELLATION_NOT_PENDING'
CODE_LEGACY_PRIOR_STATUS_UNKNOWN = 'LEGACY_PRIOR_STATUS_UNKNOWN'
CODE_CYCLE_MISMATCH = 'CANCELLATION_CYCLE_MISMATCH'


def _conflict(code, message, event, **extra):
    body = {"error": message, "code": code}
    body.update({k: v for k, v in extra.items() if v is not None})
    return format_response(409, body, event)


def _is_conditional_failure(exc):
    return (isinstance(exc, ClientError)
            and exc.response.get('Error', {}).get('Code') == 'ConditionalCheckFailedException')


def _consistent_read(request_id, client_id):
    resp = table.get_item(
        Key={'PK': f"REQ#{request_id}", 'SK': f"CLIENT#{client_id}"},
        ConsistentRead=True,
    )
    return resp.get('Item')


def handler(event, context):
    try:
        from common.entitlement import require_active_tenant
        block_resp = require_active_tenant(event)
        if block_resp:
            return block_resp

        http_method = event.get('httpMethod')
        path = event.get('path', '')
        body = json.loads(event.get('body', '{}'))

        # 1. Customer Request Path
        if http_method == 'POST' and 'cancel' in path:
            return handle_customer_request(body, event)
        
        # 2. Admin Decision Path
        if http_method == 'PUT' and 'decision' in path:
            return handle_admin_decision(body, event)

        return bad_request("Invalid endpoint for cancellation management", event)

    except Exception as e:
        print(f"Cancellation Handler Error: {str(e)}")
        return internal_error(str(e), event)

def handle_customer_request(body, event):
    request_id = body.get('request_id')
    client_id = body.get('client_id')
    reason = body.get('reason', 'No reason provided.')

    if not request_id or not client_id:
        return bad_request("Missing request_id or client_id", event)

    item = get_item(f"REQ#{request_id}", f"CLIENT#{client_id}")
    if not item:
        return error(403, "Forbidden", event)

    # Release 11E: Post-read tenant ownership validation
    from common.auth import validate_tenant_ownership, get_claims as _get_claims
    try:
        validate_tenant_ownership(item, event)
    except PermissionError:
        _claims = _get_claims(event)
        print(f"SECURITY: Cross-tenant cancel attempt by {_claims.get('email')} for REQ#{request_id}")
        return error(403, "Forbidden", event)

    from common.auth import require_client_booking_access
    try:
        require_client_booking_access(event, item)
    except PermissionError:
        return error(403, "Forbidden", event)

    # BE-CANCEL-1: only an approved/assigned (or legacy-synonym) booking may enter the
    # cancellation flow; finished, closed, early-workflow and denied bookings may not.
    observed_status = item.get('status')
    if not isinstance(observed_status, str) or not observed_status:
        return _conflict(CODE_BOOKING_STATE_UNKNOWN,
                         "This booking's status could not be verified, so cancellation cannot be requested.",
                         event)
    if observed_status not in CANCELLATION_REQUESTABLE_STATUSES:
        return _conflict(CODE_BOOKING_NOT_CANCELLABLE,
                         f"Cancellation cannot be requested for a booking in status {observed_status}.",
                         event, current_status=observed_status)

    # 24-hour warning logic check
    service_start_str = item.get('start_date')
    is_urgent = False
    if service_start_str:
        try:
            # Handle start_date which is often just YYYY-MM-DD for MVP
            if len(service_start_str) == 10:
                # Assume start of day if no time
                start_dt = datetime.fromisoformat(service_start_str).replace(tzinfo=timezone.utc)
            else:
                start_dt = datetime.fromisoformat(service_start_str.replace('Z', '+00:00'))
            
            now = datetime.now(timezone.utc)
            hours_diff = (start_dt - now).total_seconds() / 3600
            if hours_diff < 24:
                is_urgent = True
        except ValueError:
            pass

    # Update record with requested status
    audit_entry = {
        "status": "CANCELLATION_REQUESTED",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "by": f"CLIENT#{client_id}",
        "reason": reason
    }

    values = {
        ":s": CANCELLATION_REQUESTED,
        ":r": reason,
        ":t": audit_entry["timestamp"],
        ":b": audit_entry["by"],
        ":a": [audit_entry],
        ":empty_list": [],
        ":observed": observed_status,
        ":cyc": str(uuid.uuid4()),
    }
    names = {"#stat": "status", "#cyc": CYCLE_ATTR}
    set_parts = [
        "#stat = :s", "cancellation_reason = :r", "cancellation_requested_at = :t",
        "cancellation_requested_by = :b",
        "audit_log = list_append(if_not_exists(audit_log, :empty_list), :a)",
    ]
    remove_parts = []
    if observed_status != CANCELLATION_REQUESTED:
        # BE-CANCEL-1A: a new cycle always gets a fresh server-generated identity.
        set_parts.append("#cyc = :cyc")
        remove_parts.append(DECISION_CYCLE_ATTR)
    else:
        # Same pending cycle: never replace its identity (a legacy pending request
        # without one is assigned one once).
        set_parts.append("#cyc = if_not_exists(#cyc, :cyc)")
    if observed_status != CANCELLATION_REQUESTED:
        # A new cancellation cycle. D1 Option A: capture the verified prior
        # status atomically (the write is conditioned on the status we observed).
        # Legacy synonyms are never captured, and any stale prior status or decision
        # from an earlier cycle is cleared so it cannot be reused.
        if observed_status in RESTORABLE_PRIOR_STATUSES:
            set_parts.append(f"{PRIOR_STATUS_ATTR} = :observed")
            set_parts.append("cancellation_prior_status_captured_at = :t")
        else:
            remove_parts.append(PRIOR_STATUS_ATTR)
        remove_parts += ["cancellation_decision", "cancellation_decision_result_status"]
    # else: a repeat request while still pending never replaces the recorded prior status.

    update_expr = "SET " + ", ".join(set_parts)
    if remove_parts:
        update_expr += " REMOVE " + ", ".join(remove_parts)

    try:
        table.update_item(
            Key={'PK': f"REQ#{request_id}", 'SK': f"CLIENT#{client_id}"},
            UpdateExpression=update_expr,
            ConditionExpression="#stat = :observed",
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=values,
        )
    except Exception as e:
        if _is_conditional_failure(e):
            return _conflict(CODE_STATE_CHANGED,
                             "This booking changed while the cancellation request was being recorded. Reload and try again.",
                             event)
        print(f"Error recording cancellation request: {e}")
        return internal_error("Failed to record cancellation request", event)

    return success({
        "message": "Cancellation request submitted for review.",
        "urgent_warning": is_urgent
    }, event)

def handle_admin_decision(body, event):
    if not isinstance(body, dict):
        return bad_request("Invalid request body", event)
    request_id = body.get('request_id')
    client_id = body.get('client_id')
    decision = body.get('decision')  # exactly 'APPROVE' or 'DENY'
    note = body.get('note', '')

    from common.auth import get_effective_role
    role = get_effective_role(event)
    if role not in ['owner', 'admin']:
        return error(403, "Forbidden: Only owners and admins can process cancellation decisions", event)

    if not request_id or not client_id or not decision:
        return bad_request("Missing required decision fields", event)
    if not isinstance(request_id, str) or not isinstance(client_id, str):
        return bad_request("request_id and client_id must be strings", event)

    # BE-CANCEL-1 A: strict validation BEFORE any read or write.
    if not isinstance(decision, str) or decision not in CANCELLATION_DECISIONS:
        return bad_request("decision must be exactly 'APPROVE' or 'DENY'", event)
    if note is None:
        note = ''
    if not isinstance(note, str):
        return bad_request("note must be a string", event)
    if len(note) > MAX_DECISION_NOTE_LEN:
        return bad_request(f"note must be at most {MAX_DECISION_NOTE_LEN} characters", event)

    # BE-CANCEL-1A: optional expected cancellation-cycle identity. Optional so existing
    # clients (mobile S2) keep working; when supplied it is strictly validated and
    # enforced by the conditional write.
    expected_cycle = body.get(CYCLE_ATTR)
    if expected_cycle is not None and (
            not isinstance(expected_cycle, str) or not _CYCLE_ID_RE.match(expected_cycle)):
        return bad_request(f"{CYCLE_ATTR} must be a cancellation request identifier", event)

    item = get_item(f"REQ#{request_id}", f"CLIENT#{client_id}")
    if not item:
        return error(404, "Booking request not found", event)

    # Release 11E: Post-read tenant ownership validation
    from common.auth import validate_tenant_ownership, get_claims as _get_claims
    try:
        validate_tenant_ownership(item, event)
    except PermissionError:
        _claims = _get_claims(event)
        print(f"SECURITY: Cross-tenant cancel decision attempt by {_claims.get('email')} for REQ#{request_id}")
        return error(403, "Forbidden", event)

    # The initial read is eventually consistent. A non-pending observation is
    # verified with a consistent read before anything is reported.
    if item.get('status') != CANCELLATION_REQUESTED:
        return _reconcile_decision(request_id, client_id, decision, event, expected_cycle)

    # The cycle this decision is bound to: the caller's expected cycle if supplied,
    # otherwise the cycle observed on this read (legacy-client compatibility).
    observed_cycle = item.get(CYCLE_ATTR)
    if expected_cycle is not None and observed_cycle != expected_cycle:
        return _reconcile_decision(request_id, client_id, decision, event, expected_cycle)
    bound_cycle = observed_cycle if isinstance(observed_cycle, str) and observed_cycle else None

    if decision == 'APPROVE':
        new_status = "CANCELLED"
        prior_status = None
    else:
        # BE-CANCEL-1 C / D1 Option A: restore only a trustworthy, allowlisted prior
        # operational status. Never infer it from job records.
        prior_status = item.get(PRIOR_STATUS_ATTR)
        if not isinstance(prior_status, str) or prior_status not in RESTORABLE_PRIOR_STATUSES:
            return _conflict(
                CODE_LEGACY_PRIOR_STATUS_UNKNOWN,
                "This cancellation request has no verified prior booking status, so it cannot be denied "
                "automatically. The owner must resolve this booking manually.",
                event, current_status=CANCELLATION_REQUESTED)
        new_status = prior_status

    ts = datetime.now(timezone.utc).isoformat()
    actor = (_get_claims(event).get('email') or _get_claims(event).get('username') or 'ADMIN')
    
    audit_entry = {
        "status": new_status,
        "timestamp": ts,
        "by": "ADMIN",
        "actor": actor,
        "decision": decision,
        "prior_status": prior_status,
        "note": note,
        "sync_failures": []
    }

    # BE-CANCEL-1 B: the atomic decision gate. Exactly one decision can win, and a
    # DENY additionally requires the prior status it restores to be the recorded one.
    condition = "#stat = :requested"
    values = {
        ":s": new_status,
        ":d": decision,
        ":t": ts,
        ":b": "ADMIN",
        ":actor": actor,
        ":n": note,
        ":a": [audit_entry],
        ":empty_list": [],
        ":requested": CANCELLATION_REQUESTED,
    }
    names = {"#stat": "status", "#cyc": CYCLE_ATTR, "#dcyc": DECISION_CYCLE_ATTR}
    if prior_status is not None:
        condition += " AND #prior = :prior"
        values[":prior"] = prior_status
        names["#prior"] = PRIOR_STATUS_ATTR

    # BE-CANCEL-1A: pin the write to the bound cancellation cycle, so a decision can
    # never land on a different cycle than the one it was made against (including a
    # new cycle created between this read and this write).
    update_expr = (
        "SET #stat = :s, cancellation_decision = :d, cancellation_decision_result_status = :s, "
        "cancellation_decision_at = :t, cancellation_decision_by = :b, "
        "cancellation_decision_actor = :actor, cancellation_decision_note = :n, "
        "audit_log = list_append(if_not_exists(audit_log, :empty_list), :a)"
    )
    if bound_cycle is not None:
        condition += " AND #cyc = :cyc"
        values[":cyc"] = bound_cycle
        update_expr += ", #dcyc = :cyc"
    else:
        condition += " AND attribute_not_exists(#cyc)"
        update_expr += " REMOVE #dcyc"
    audit_entry["cancellation_request_id"] = bound_cycle

    try:
        table.update_item(
            Key={'PK': f"REQ#{request_id}", 'SK': f"CLIENT#{client_id}"},
            UpdateExpression=update_expr,
            ConditionExpression=condition,
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=values,
        )
    except Exception as e:
        if _is_conditional_failure(e):
            return _reconcile_decision(request_id, client_id, decision, event, expected_cycle)
        print(f"Error updating cancellation decision: {e}")
        return internal_error("Failed to update cancellation decision", event)

    # ---- The decision is committed. Everything below is separately fallible and is
    # ---- NOT atomic with the decision; failures are recorded, never hidden.
    warnings = []

    def note_failure(kind, message):
        record_sync_failure(request_id, client_id, kind, message)
        warnings.append({"type": kind, "error": message})

    try:
        log_action(
            event,
            f"CANCEL_DECISION_{decision}",
            f"REQ#{request_id}",
            f"CLIENT#{client_id}",
            previous_status=item.get('status'),
            new_status=new_status,
            metadata={"client_name": item.get('client_name'), "pet_names": item.get('pet_names'),
                      "decision": decision, "note": note, "prior_status": prior_status}
        )
    except Exception as ex:
        note_failure("AUDIT_LOG", f"Audit log write failed: {ex}")

    message_id = None
    calendar_msg = ""
    if decision == 'APPROVE':
        # Idempotent steps (also re-run on a same-decision replay).
        calendar_msg = _run_idempotent_approve_effects(item, request_id, client_id, note_failure)

        # Non-idempotent steps: only the invocation that won the decision write runs
        # them, so a replay can never send a duplicate SNS or notification.
        worker_id = item.get('worker_id')
        if worker_id:
            try:
                message_id = notify_worker(worker_id, item)
            except Exception as ex:
                fail_msg = f"SNS notification failed: {str(ex)}"
                print(fail_msg)
                note_failure("SNS_NOTIFICATION", fail_msg)

        try:
            notify_event('VISIT_CANCELLED', item)
        except Exception as ex:
            note_failure("NOTIFICATION", f"Cancellation notification failed: {ex}")
    # DENY: D1 Option A restores the parent status only. No job cascade runs, so
    # assigned, unassigned and completed visits all keep their existing state.

    if decision == 'APPROVE':
        final_msg = "Cancellation request approved."
        if calendar_msg:
            final_msg += f" {calendar_msg}"
    else:
        final_msg = f"Cancellation request denied. Booking status restored to {new_status}."

    return success({
        "message": final_msg,
        "new_status": new_status,
        "decision": decision,
        "sns_message_id": message_id,
        "idempotent_replay": False,
        "warnings": warnings,
    }, event)


def _run_idempotent_approve_effects(item, request_id, client_id, note_failure):
    """Job cascade + calendar cleanup for an APPROVED cancellation.

    Both steps are idempotent: the cascade sets non-COMPLETED child jobs to CANCELLED
    (COMPLETED jobs are preserved by common.cascade), and calendar cleanup deletes only
    event IDs still recorded on the records (removed after a successful delete; an
    already-deleted event is treated as success). Returns a user-facing calendar message.
    """
    # 1. Job cascade (separately fallible).
    try:
        from common.cascade import cascade_status_to_job
        # BE-CANCEL-1A: require_existing=True never creates a stub JOB for a dangling
        # job_ids reference and never overwrites a JOB that became COMPLETED.
        result = cascade_status_to_job(item, "CANCELLED", updated_by="ADMIN", require_existing=True)
        if isinstance(result, dict):
            missing = result.get('missing_job_ids')
            failed = result.get('failed_count')
            if isinstance(missing, list) and missing:
                note_failure("JOB_MISSING",
                             "Referenced JOB record(s) not found and not created: "
                             + ", ".join(str(m) for m in missing))
            if (isinstance(failed, int) and failed > 0) or (
                    result.get('success') is False and not isinstance(failed, int)):
                note_failure("JOB_CASCADE", str(result.get('message') or 'Job cascade failed'))
    except Exception as ex:
        note_failure("JOB_CASCADE", f"Job cascade failed: {ex}")

    # 2. Google Calendar Removal
    from common.google_calendar import delete_event_detailed
    calendar_msg = ""

    # Collect event IDs from parent Request and all child Jobs
    event_to_records = {} # unique_event_id -> list of record keys to update
    job_ids = item.get('job_ids') or []
    company_id = item.get('company_id')

    parent_event_id = item.get('google_event_id')
    if parent_event_id:
        event_to_records.setdefault(parent_event_id, []).append({
            "PK": f"REQ#{request_id}",
            "SK": f"CLIENT#{client_id}"
        })

    for jid in job_ids:
        job_item = get_item(f"JOB#{jid}", f"REQ#{request_id}")
        if job_item and job_item.get('google_event_id'):
            if not company_id or job_item.get('company_id') != company_id:
                note_failure('GOOGLE_CALENDAR', 'INVALID_CALENDAR_TENANT_CONTEXT')
                continue
            jid_event_id = job_item['google_event_id']
            event_to_records.setdefault(jid_event_id, []).append({
                "PK": f"JOB#{jid}",
                "SK": f"REQ#{request_id}"
            })

    # Deduplicate and count unique event IDs
    unique_event_ids = list(event_to_records.keys())
    event_id_count = len(unique_event_ids)

    if event_id_count > 0:
        # Structured log for collection
        print(json.dumps({
            "event": "CALENDAR_CLEANUP_COLLECTED",
            "company_id": company_id,
            "request_id": request_id,
            "job_count": len(job_ids),
            "event_id_count": event_id_count
        }))

        deleted_count = 0
        for event_id in unique_event_ids:
            try:
                if not company_id:
                    raise ValueError('MISSING_CALENDAR_TENANT_CONTEXT')
                gcal_success, already_gone, err_msg = delete_event_detailed(
                    event_id, request_id, company_id=company_id)
                if gcal_success:
                    if already_gone:
                        print(json.dumps({
                            "event": "CALENDAR_CLEANUP_ALREADY_GONE",
                            "company_id": company_id,
                            "request_id": request_id,
                            "event_id": event_id,
                            "deletion_status": "already_gone"
                        }))
                    else:
                        print(json.dumps({
                            "event": "CALENDAR_CLEANUP_DELETED",
                            "company_id": company_id,
                            "request_id": request_id,
                            "event_id": event_id,
                            "deletion_status": "deleted"
                        }))
                        deleted_count += 1

                    # Remove google_event_id from all associated records in DynamoDB
                    for rec in event_to_records[event_id]:
                        try:
                            table.update_item(
                                Key={'PK': rec['PK'], 'SK': rec['SK']},
                                UpdateExpression="REMOVE google_event_id"
                            )
                        except Exception as db_err:
                            print(f"WARNING: Failed to remove google_event_id from {rec['PK']}: {db_err}")
                else:
                    raise Exception(err_msg or "Unknown error")
            except Exception as ex:
                fail_msg = str(ex)
                print(json.dumps({
                    "event": "CALENDAR_CLEANUP_WARNING",
                    "company_id": company_id,
                    "request_id": request_id,
                    "event_id": event_id,
                    "deletion_status": "failed",
                    "error_type": fail_msg
                }))
                note_failure("GOOGLE_CALENDAR", f"Event ID {event_id} cleanup failed: {fail_msg}")

        if deleted_count > 0:
            calendar_msg = f"Deleted {deleted_count} calendar event(s)."
    else:
        # Structured log for no events
        print(json.dumps({
            "event": "CALENDAR_CLEANUP_NONE",
            "company_id": company_id,
            "request_id": request_id,
            "job_count": len(job_ids),
            "event_id_count": 0
        }))
    return calendar_msg


def _reconcile_decision(request_id, client_id, decision, event, expected_cycle=None):
    """Classify a decision that did not win the conditional write (or observed a
    non-pending status) using a CONSISTENT read, with tenant validation."""
    try:
        current = _consistent_read(request_id, client_id)
    except Exception as e:
        print(f"Error reading cancellation state for reconciliation: {e}")
        return internal_error("Could not verify the cancellation state", event)
    if not isinstance(current, dict) or not current:
        # Fail closed: an absent or malformed record is never trusted for reconciliation.
        return error(404, "Booking request not found", event)

    from common.auth import validate_tenant_ownership, get_claims as _get_claims
    try:
        validate_tenant_ownership(current, event)
    except PermissionError:
        _claims = _get_claims(event)
        print(f"SECURITY: Cross-tenant cancel reconciliation by {_claims.get('email')} for REQ#{request_id}")
        return error(403, "Forbidden", event)

    current_status = current.get('status')
    previous_decision = current.get('cancellation_decision')
    result_status = current.get('cancellation_decision_result_status')
    current_cycle = current.get(CYCLE_ATTR) or None
    decided_cycle = current.get(DECISION_CYCLE_ATTR) or None

    if expected_cycle is not None and current_cycle != expected_cycle:
        # BE-CANCEL-1A: the caller decided a different cancellation cycle than the one
        # on the booking now. Never apply or replay it against this cycle.
        return _conflict(CODE_CYCLE_MISMATCH,
                         "This decision was made for an earlier cancellation request. Reload and review "
                         "the current cancellation request.",
                         event, current_status=current_status)

    if current_status == CANCELLATION_REQUESTED:
        # Still pending, but the conditional write failed (e.g. the request or its
        # recorded prior status changed). Never apply a decision to changed state.
        return _conflict(CODE_STATE_CHANGED,
                         "This cancellation request changed before the decision could be applied. Reload and review it.",
                         event, current_status=current_status)

    if (previous_decision == decision and result_status and current_status == result_status
            and decided_cycle == current_cycle):
        # Same-decision replay of an already-applied decision. Only idempotent steps
        # are repeated; SNS / notifications are never re-sent.
        warnings = []

        def note_failure(kind, message):
            record_sync_failure(request_id, client_id, kind, message)
            warnings.append({"type": kind, "error": message})

        if decision == 'APPROVE':
            _run_idempotent_approve_effects(current, request_id, client_id, note_failure)
        return success({
            "message": "This cancellation decision was already applied.",
            "new_status": current_status,
            "decision": decision,
            "sns_message_id": None,
            "idempotent_replay": True,
            "warnings": warnings,
        }, event)

    return _conflict(CODE_NOT_PENDING,
                     f"This booking is not awaiting a cancellation decision (current status: {current_status}).",
                     event, current_status=current_status, previous_decision=previous_decision)

def notify_worker(worker_id, item):
    """Sends SMS notification via AWS SNS."""
    topic_arn = os.environ.get('STAFF_COORDINATION_SNS_ARN')
    if not topic_arn:
        raise Exception("STAFF_COORDINATION_SNS_ARN environment variable not set")

    message = (
        f"Tog and Dogs ALERT: Visit for {item.get('client_name')} on {item.get('start_date')} "
        f"has been CANCELLED. Please update your schedule accordingly."
    )
    
    response = sns.publish(
        TopicArn=topic_arn,
        Message=message,
        Subject="Visit Cancellation Alert"
    )
    
    msg_id = response.get('MessageId')
    print(f"SUCCESS: SNS Alert sent to {worker_id}, MessageId: {msg_id}")
    return msg_id

def record_sync_failure(request_id, client_id, sync_type, error_msg):
    """Records a synchronization failure in the audit log of the record."""
    try:
        failure_log = {
            "type": sync_type,
            "error": error_msg,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # We append to the last audit_log entry or just generally to a failure field
        table.update_item(
            Key={'PK': f"REQ#{request_id}", 'SK': f"CLIENT#{client_id}"},
            UpdateExpression="SET sync_failures = list_append(if_not_exists(sync_failures, :empty_list), :f)",
            ExpressionAttributeValues={
                ":f": [failure_log],
                ":empty_list": []
            }
        )
    except Exception as e:
        print(f"CRITICAL: Failed to record sync failure for {request_id}: {e}")
