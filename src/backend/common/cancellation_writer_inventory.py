"""INACTIVE field-level writer inventory. Design requirements, never rollout approval."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Writer:
    name: str
    source: str
    function: str
    lines: tuple
    target: str
    reads: tuple
    writes: tuple
    behavior: str
    category: str
    coupled: tuple=()
    revision_domain: str="NONE"
    preserves_unknown: bool=True
    protected_lifetime: bool=False


# Exact call sites at corrected PR51 base. Dynamic/branch-specific field sets
# are explicitly bounded patterns, not a claim that generic writers are safe.
WRITERS=(
 Writer("intake_create","handlers/intake_handler.py","handler / _handle_admin_created_booking",(253,609),"REQ/request CLIENT/client",("tenant","client","booking fields"),("whole REQUEST",),"PUT","LIFETIME_IDENTITY_ADAPTATION",("client/PET linkage","notifications"),preserves_unknown=False),
 Writer("intake_calendar","handlers/intake_handler.py","_handle_admin_created_booking",(305,),"exact REQUEST",("REQUEST","Calendar result"),("google_event_id",),"UPDATE_UPSERT","ATOMIC_GUARDS_REQUIRED",("Calendar",)),
 Writer("submission","handlers/cancellation_handler.py","handle_customer_request",(97,),"exact REQUEST",("tenant","booking access","status","start_date"),("status","cancellation_reason","cancellation_requested_at","cancellation_requested_by","audit_log"),"UPDATE_UPSERT","ATOMIC_GUARDS_REQUIRED"),
 Writer("cancel_decision","handlers/cancellation_handler.py","handle_admin_decision",(164,278),"REQUEST and resolved event references",("REQUEST","children","event IDs"),("status","cancellation_decision_*","audit_log","google_event_id"),"UPDATE_UPSERT","COORDINATED_MULTI_RECORD_PROTOCOL",("JOB cascade","Calendar","notification","SNS")),
 Writer("cancel_sync_failure","handlers/cancellation_handler.py","record_sync_failure",(365,),"exact REQUEST",("sync error",),("sync_failures",),"UPDATE_UPSERT","ATOMIC_GUARDS_REQUIRED"),
 Writer("review","handlers/review_handler.py","handler",(112,250,316,355,440),"REQUEST",("REQUEST","client/PET","status","jobs"),("status","updated_at","updated_by","audit_log","worker_id","completed_at","completed_by","visit_notes","google_event_id","client_profile_link_status"),"UPDATE_UPSERT","COORDINATED_MULTI_RECORD_PROTOCOL",("CLIENT/PET M&G","JOB","Calendar","notifications","async creation")),
 Writer("assignment","handlers/assignment_handler.py","handler",(244,),"parent REQUEST",("STAFF","REQUEST","JOB"),("status","worker_id","worker_name","updated_at","updated_by"),"UPDATE_UPSERT","COORDINATED_MULTI_RECORD_PROTOCOL",("JOB","Calendar","notifications")),
 Writer("job_membership","handlers/job_handler.py","handler",(347,),"parent REQUEST",("REQUEST","PET","JOB"),("job_id","job_ids","is_multi_day","total_occurrences"),"UPDATE_UPSERT","COORDINATED_MULTI_RECORD_PROTOCOL",("PET creation","JOB creation","Calendar")),
 Writer("admin_quote_payment","handlers/admin_handler.py","handler",(771,2785,3097,3268,3377),"exact REQUEST",("quote/payment/status state",),("status (quote mirror)","quote_*","payment_*","stripe_*","currency","deposit_amount_cents","internal_pricing_notes","audit_log","updated_*"),"UPDATE_UPSERT","EXCLUDED_PENDING_APPROVAL",("payment/quote semantics","email"),"quote_revision (some branches)"),
 Writer("admin_rollup","handlers/admin_handler.py","handler",(3700,),"parent REQUEST",("JOB","siblings","REQUEST"),("completed_job_ids","completed_count","status","completed_at","completed_by","updated_at"),"UPDATE_UPSERT","COORDINATED_MULTI_RECORD_PROTOCOL",("JOB completion","audit/notification")),
 Writer("admin_lifecycle","handlers/admin_handler.py","handler",(3935,3958,3977,4002,4012),"resolved REQUEST/JOB keys",("resolved item","lifecycle"),("status","is_test_booking","archive_reason","archived_at","archived_by","deleted_at","audit_log","updated_*","google_event_id"),"GENERIC_UPDATE","COORDINATED_MULTI_RECORD_PROTOCOL",("cascade","Calendar","notifications")),
 Writer("admin_purge","handlers/admin_handler.py","handler",(3804,3816),"resolved parent and children",("trash/deleted item","children"),("DELETE",),"DELETE","UNSAFE_DELETE_RECREATION",("child deletion",),preserves_unknown=False),
 Writer("pet_link","handlers/pet_handler.py","handler",(458,),"REQUEST",("PET/client ownership",),("pet_id","pet_ids"),"UPDATE_UPSERT","COORDINATED_MULTI_RECORD_PROTOCOL",("PET write",)),
 Writer("client_link","common/client_profile.py","_update_request_link_status / _link_request_to_profile",(287,),"REQUEST",("profile/link provenance",),("client_profile_link_status","client_profile_linked_at","client_profile_link_method","linked_client_profile_id"),"UPDATE_UPSERT","LIFETIME_IDENTITY_ADAPTATION",("CLIENT linkage",)),
 Writer("client_link_audit","common/client_profile.py","_append_audit_to_request",(326,),"REQUEST",("audit entry",),("audit_log",),"UPDATE_UPSERT","ATOMIC_GUARDS_REQUIRED"),
 Writer("pet_provenance","common/pet_profile.py","create_or_link_pets_from_request / _link_mixed_existing_and_new / _create_legacy_single_pet",(263,383,437),"REQUEST",("PET provenance","linked client"),("pet_id","pet_ids"),"UPDATE_UPSERT","COORDINATED_MULTI_RECORD_PROTOCOL",("PET create/merge",)),
 Writer("pet_audit","common/pet_profile.py","_append_audit_to_request",(651,),"REQUEST",("audit entry",),("audit_log",),"UPDATE_UPSERT","ATOMIC_GUARDS_REQUIRED"),
 Writer("approval_metadata","common/notifications/service.py","notify_event",(499,),"REQUEST",("notification result",),("approval_notification_*",),"UPDATE_UPSERT","ATOMIC_GUARDS_REQUIRED",("provider effect already occurred",)),
 Writer("stripe_summary","handlers/stripe_webhook_handler.py","_handle_checkout_completed",(181,),"REQUEST",("tenant","session","REQUEST"),("payment_status","stripe_*","payment_completed_at","updated_at","updated_by"),"UPDATE_EXISTS_ONLY","EXCLUDED_PENDING_APPROVAL",("billing event",)),
 Writer("manual_external_summary","common/manual_external_adapter.py","record_external_payment / _build_summary_update_item / _execute_transaction",(225,443,454),"REQUEST plus PAYMENT_EVENT",("raw payment status","amount","payment revision"),("payment_status","amount_paid_cents","currency","payment_provider","payment_summary_revision","payment_completed_at","updated_at"),"DOMAIN_TRANSACTION","EXCLUDED_PENDING_APPROVAL",("PAYMENT_EVENT","audit"),"payment_summary_revision"),
 Writer("generic_db","common/db.py","put_item / update_status / update_item",(12,49,83),"arbitrary keys including REQUEST",("caller-supplied snapshot/fields",),("arbitrary fields/whole item",),"GENERIC_PUT_UPDATE","LIFETIME_IDENTITY_ADAPTATION",preserves_unknown=False),
 Writer("remediation","scripts/remediate_records.py","remediate",(83,),"scan-selected records including REQUEST",("scan status/test patterns",),("status","updated_at","remediation_flag"),"UPDATE_UPSERT","LIFETIME_IDENTITY_ADAPTATION"),
 Writer("zombie_cleanup","scripts/cleanup_zombie_data_issues.py","run_cleanup / is_zombie_candidate",(206,),"scan-selected records including REQUEST",("candidate/status/prefix",),("DELETE",),"DELETE","UNSAFE_DELETE_RECREATION",preserves_unknown=False),
 Writer("targeted_cleanup","scripts/cleanup_data_issues_targeted.py","run",(118,122,146),"current targets JOB/PET; REQUEST deletion protected",("fixed targets",),("DELETE","status","selected metadata"),"DELETE_UPDATE","EXCLUDED_PENDING_APPROVAL",("child/PET integrity",),preserves_unknown=False),
 Writer("audit_cleanup","scripts/cleanup_malformed_audit_records.py","run_cleanup / is_safety_excluded",(154,),"malformed audits; REQUEST prefix excluded",("audit prefix",),("DELETE",),"DELETE","EXCLUDED_PENDING_APPROVAL",("future journal-prefix exclusions",),preserves_unknown=False),
 Writer("child_cascade","common/cascade.py","cascade_status_to_job",(99,),"JOB only; indirect parent lifecycle",("parent membership","child state"),("status","worker_id","worker_name","is_test_booking","updated_*"),"UPDATE_UPSERT","COORDINATED_MULTI_RECORD_PROTOCOL",("REQUEST caller",)),
)

BASE_GUARDS=("exact_existing_target","tenant_identity","incarnation","expected_revision","reservation_absent",
             "live_lifetime","no_unconditional_fallback","truthful_failure")


@dataclass(frozen=True)
class WriterAssessment:
    category: str
    required_guards: tuple
    conflicts: tuple
    activation_ready: bool=False


def assess_writer(writer, supplied_guards=()):
    if type(writer) is not Writer or type(supplied_guards) is not tuple:raise ValueError("WRITER_SHAPE")
    required=set(BASE_GUARDS)
    if "UPSERT" in writer.behavior or "GENERIC" in writer.behavior:required.add("no_upsert")
    if not writer.preserves_unknown:required.add("field_preserving_adapter")
    if writer.behavior in ("DELETE","DELETE_UPDATE"):required.update(("atomic_retirement","never_reuse_lifetime"))
    if writer.coupled:required.add("complete_affected_set_and_effect_protocol")
    conflicts=[]
    fields=' '.join(writer.writes)
    if "status" in fields:conflicts.append("STATUS_CONFLICT")
    if "audit_log" in fields:conflicts.append("AUDIT_APPEND_PROTOCOL")
    if "linked_client" in fields:conflicts.append("BOOKING_IDENTITY_INVALIDATION")
    if writer.revision_domain!="legacy_write_revision":required.add("selected_workflow_revision_protocol")
    missing=required-set(supplied_guards)
    return WriterAssessment(writer.category,tuple(sorted(missing)),tuple(conflicts),False)


ROLLOUT_BLOCKERS=(
 "Older PR22 package b94455ac530e3ecca9a2fc2ddc69ed54902b84db on documented non-admin Lambdas",
 "Documented W3C2 admin source 263b3e744a2815f0d9da781b2589ce643d2750f6 lacks this workflow fencing",
 "Queued/in-flight invocations, aliases, triggers, old clients and operating credentials not inventoried live",
 "Untracked/manual/import writers cannot be certified from repository source",
 "Reservation/lifetime/receipt cleanup, restoration and mixed-version retirement protocols not deployed",
)
