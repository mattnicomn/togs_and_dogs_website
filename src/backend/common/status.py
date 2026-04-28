from enum import Enum

class RequestStatus(Enum):
    PENDING_REVIEW = "PENDING_REVIEW"
    NEEDS_REVIEW = "PENDING_REVIEW" # Synonym
    MEET_GREET_REQUIRED = "MEET_GREET_REQUIRED"
    NEEDS_MG = "MEET_GREET_REQUIRED" # Synonym
    MG_SCHEDULED = "MG_SCHEDULED"
    MG_COMPLETED = "MG_COMPLETED"
    READY_FOR_APPROVAL = "READY_FOR_APPROVAL"
    NEW_REQUEST = "READY_FOR_APPROVAL" # Synonym
    QUOTE_NEEDED = "QUOTE_NEEDED"
    QUOTE_SENT = "QUOTE_SENT"
    APPROVED = "APPROVED"
    BOOKED = "APPROVED" # Synonym
    ASSIGNED = "ASSIGNED"
    DECLINED = "DECLINED"
    CANCELLATION_REQUESTED = "CANCELLATION_REQUESTED"
    CANCELLATION_DENIED = "CANCELLATION_DENIED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"
    PROFILE_CREATED = "PROFILE_CREATED"
    QUOTED = "QUOTED"
    ARCHIVED = "ARCHIVED"
    DELETED = "DELETED"

class JobStatus(Enum):
    JOB_CREATED = "JOB_CREATED"
    ASSIGNED = "ASSIGNED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    ARCHIVED = "ARCHIVED"
    DELETED = "DELETED"

# Define valid transitions for Request
REQUEST_TRANSITIONS = {
    RequestStatus.PENDING_REVIEW.value: [
        RequestStatus.MEET_GREET_REQUIRED.value,
        RequestStatus.READY_FOR_APPROVAL.value,
        RequestStatus.PROFILE_CREATED.value,
        RequestStatus.QUOTE_NEEDED.value,
        RequestStatus.QUOTE_SENT.value,
        RequestStatus.QUOTED.value,
        RequestStatus.APPROVED.value,
        RequestStatus.DECLINED.value,
        RequestStatus.CANCELLED.value,
        RequestStatus.ARCHIVED.value,
        RequestStatus.DELETED.value
    ],
    RequestStatus.PROFILE_CREATED.value: [
        RequestStatus.READY_FOR_APPROVAL.value,
        RequestStatus.MEET_GREET_REQUIRED.value,
        RequestStatus.QUOTE_NEEDED.value,
        RequestStatus.QUOTE_SENT.value,
        RequestStatus.APPROVED.value,
        RequestStatus.DECLINED.value,
        RequestStatus.CANCELLED.value,
        RequestStatus.ARCHIVED.value
    ],
    RequestStatus.MEET_GREET_REQUIRED.value: [
        RequestStatus.MG_SCHEDULED.value,
        RequestStatus.MG_COMPLETED.value,
        RequestStatus.READY_FOR_APPROVAL.value,
        RequestStatus.QUOTE_NEEDED.value,
        RequestStatus.DECLINED.value,
        RequestStatus.CANCELLED.value,
        RequestStatus.ARCHIVED.value
    ],
    RequestStatus.MG_SCHEDULED.value: [
        RequestStatus.MG_COMPLETED.value,
        RequestStatus.MEET_GREET_REQUIRED.value, # Reschedule/Revert
        RequestStatus.CANCELLED.value,
        RequestStatus.ARCHIVED.value
    ],
    RequestStatus.MG_COMPLETED.value: [
        RequestStatus.QUOTE_NEEDED.value,
        RequestStatus.QUOTE_SENT.value,
        RequestStatus.QUOTED.value,
        RequestStatus.READY_FOR_APPROVAL.value,
        RequestStatus.APPROVED.value,
        RequestStatus.CANCELLED.value,
        RequestStatus.ARCHIVED.value
    ],
    RequestStatus.QUOTE_NEEDED.value: [
        RequestStatus.QUOTE_SENT.value,
        RequestStatus.QUOTED.value,
        RequestStatus.APPROVED.value,
        RequestStatus.READY_FOR_APPROVAL.value,
        RequestStatus.DECLINED.value,
        RequestStatus.CANCELLED.value,
        RequestStatus.ARCHIVED.value
    ],
    RequestStatus.QUOTE_SENT.value: [
        RequestStatus.APPROVED.value,
        RequestStatus.QUOTE_NEEDED.value, # Revision
        RequestStatus.DECLINED.value,
        RequestStatus.CANCELLED.value,
        RequestStatus.ARCHIVED.value
    ],
    RequestStatus.READY_FOR_APPROVAL.value: [
        RequestStatus.APPROVED.value,
        RequestStatus.QUOTE_NEEDED.value,
        RequestStatus.QUOTE_SENT.value,
        RequestStatus.QUOTED.value,
        RequestStatus.DECLINED.value,
        RequestStatus.ARCHIVED.value
    ],
    RequestStatus.QUOTED.value: [
        RequestStatus.APPROVED.value,
        RequestStatus.READY_FOR_APPROVAL.value,
        RequestStatus.DECLINED.value,
        RequestStatus.CANCELLED.value,
        RequestStatus.ARCHIVED.value,
        RequestStatus.DELETED.value
    ],
    RequestStatus.APPROVED.value: [
        RequestStatus.ASSIGNED.value,
        RequestStatus.CANCELLATION_REQUESTED.value,
        RequestStatus.CANCELLATION_DENIED.value,
        RequestStatus.ARCHIVED.value,
        RequestStatus.CANCELLED.value
    ],
    RequestStatus.ASSIGNED.value: [
        RequestStatus.APPROVED.value, # Allow rollback
        RequestStatus.COMPLETED.value,
        RequestStatus.ARCHIVED.value,
        RequestStatus.CANCELLED.value,
        RequestStatus.CANCELLATION_REQUESTED.value,
        RequestStatus.CANCELLATION_DENIED.value
    ],
    RequestStatus.CANCELLATION_REQUESTED.value: [
        RequestStatus.CANCELLED.value,
        RequestStatus.CANCELLATION_DENIED.value,
        RequestStatus.ARCHIVED.value
    ],
    RequestStatus.CANCELLATION_DENIED.value: [
        RequestStatus.ARCHIVED.value,
        RequestStatus.CANCELLED.value
    ],
    RequestStatus.DECLINED.value: [
        RequestStatus.ARCHIVED.value,
        RequestStatus.QUOTED.value,
        RequestStatus.PENDING_REVIEW.value
    ],
    RequestStatus.CANCELLED.value: [
        RequestStatus.ARCHIVED.value,
        RequestStatus.PENDING_REVIEW.value,
        RequestStatus.QUOTED.value,
        RequestStatus.APPROVED.value
    ],
    RequestStatus.COMPLETED.value: [
        RequestStatus.ARCHIVED.value,
        RequestStatus.ASSIGNED.value,
        RequestStatus.APPROVED.value
    ],
    RequestStatus.ARCHIVED.value: [
        RequestStatus.PENDING_REVIEW.value,
        RequestStatus.DELETED.value
    ],
    RequestStatus.DELETED.value: [
        RequestStatus.PENDING_REVIEW.value
    ]
}

# Define valid transitions for Job
JOB_TRANSITIONS = {
    JobStatus.JOB_CREATED.value: [
        JobStatus.ASSIGNED.value,
        JobStatus.CANCELLED.value,
        JobStatus.ARCHIVED.value
    ],
    "APPROVED": [ # Synonym for JOB_CREATED to handle legacy or mismatched status codes
        JobStatus.ASSIGNED.value,
        JobStatus.CANCELLED.value,
        JobStatus.ARCHIVED.value
    ],
    JobStatus.ASSIGNED.value: [
        JobStatus.ASSIGNED.value, # Self-transition for re-assignment
        JobStatus.JOB_CREATED.value, # Rollback to Approved equivalent
        JobStatus.COMPLETED.value,
        JobStatus.CANCELLED.value,
        JobStatus.ARCHIVED.value
    ],
    JobStatus.COMPLETED.value: [
        JobStatus.ASSIGNED.value, # Reopen
        JobStatus.JOB_CREATED.value, # Reopen to Approved
        JobStatus.ARCHIVED.value
    ],
    JobStatus.CANCELLED.value: [
        JobStatus.JOB_CREATED.value, # Reopen
        JobStatus.ARCHIVED.value
    ],
    JobStatus.ARCHIVED.value: [
        JobStatus.DELETED.value
    ],
    JobStatus.DELETED.value: []
}

def is_valid_transition(entity_type, current_status, new_status):
    """
    Validates if a status transition is allowed.
    entity_type: 'REQUEST' or 'JOB'
    """
    # Allow archiving or soft-deleting from any state for safety
    if new_status in ['ARCHIVED', 'DELETED']:
        return True

    # Allow same-status transitions (idempotency) to handle UI lag or double-clicks
    if current_status == new_status:
        return True

    if entity_type == 'REQUEST':
        transitions = REQUEST_TRANSITIONS
    elif entity_type == 'JOB':
        transitions = JOB_TRANSITIONS
    else:
        return False

    allowed_next = transitions.get(current_status, [])
    return new_status in allowed_next
