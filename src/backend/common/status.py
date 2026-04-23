from enum import Enum

class RequestStatus(Enum):
    PENDING_REVIEW = "PENDING_REVIEW"
    MEET_GREET_REQUIRED = "MEET_GREET_REQUIRED"
    READY_FOR_APPROVAL = "READY_FOR_APPROVAL"
    APPROVED = "APPROVED"
    ASSIGNED = "ASSIGNED"
    DECLINED = "DECLINED"
    CANCELLATION_REQUESTED = "CANCELLATION_REQUESTED"
    CANCELLATION_DENIED = "CANCELLATION_DENIED"
    CANCELLED = "CANCELLED"
    ARCHIVED = "ARCHIVED"

class JobStatus(Enum):
    JOB_CREATED = "JOB_CREATED"
    ASSIGNED = "ASSIGNED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    ARCHIVED = "ARCHIVED"

# Define valid transitions for Request
REQUEST_TRANSITIONS = {
    RequestStatus.PENDING_REVIEW.value: [
        RequestStatus.MEET_GREET_REQUIRED.value,
        RequestStatus.READY_FOR_APPROVAL.value,
        RequestStatus.APPROVED.value,
        RequestStatus.DECLINED.value,
        RequestStatus.ARCHIVED.value
    ],
    RequestStatus.MEET_GREET_REQUIRED.value: [
        RequestStatus.READY_FOR_APPROVAL.value,
        RequestStatus.DECLINED.value,
        RequestStatus.ARCHIVED.value
    ],
    RequestStatus.READY_FOR_APPROVAL.value: [
        RequestStatus.APPROVED.value,
        RequestStatus.DECLINED.value,
        RequestStatus.ARCHIVED.value
    ],
    RequestStatus.APPROVED.value: [
        RequestStatus.ASSIGNED.value,
        RequestStatus.ARCHIVED.value,
        RequestStatus.CANCELLED.value
    ],
    RequestStatus.ASSIGNED.value: [
        RequestStatus.ARCHIVED.value,
        RequestStatus.CANCELLED.value
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
        RequestStatus.PENDING_REVIEW.value # Allow restoration
    ],
    RequestStatus.CANCELLED.value: [
        RequestStatus.ARCHIVED.value,
        RequestStatus.PENDING_REVIEW.value # Allow restoration
    ],
    RequestStatus.ARCHIVED.value: [
        RequestStatus.PENDING_REVIEW.value # Allow restoration
    ]
}

# Define valid transitions for Job
JOB_TRANSITIONS = {
    JobStatus.JOB_CREATED.value: [
        JobStatus.ASSIGNED.value,
        JobStatus.CANCELLED.value,
        JobStatus.ARCHIVED.value
    ],
    JobStatus.ASSIGNED.value: [
        JobStatus.COMPLETED.value,
        JobStatus.CANCELLED.value,
        JobStatus.ARCHIVED.value
    ],
    JobStatus.COMPLETED.value: [JobStatus.ARCHIVED.value],
    JobStatus.CANCELLED.value: [JobStatus.ARCHIVED.value],
    JobStatus.ARCHIVED.value: []
}

def is_valid_transition(entity_type, current_status, new_status):
    """
    Validates if a status transition is allowed.
    entity_type: 'REQUEST' or 'JOB'
    """
    # Allow archiving from any state for safety
    if new_status == 'ARCHIVED':
        return True

    if entity_type == 'REQUEST':
        transitions = REQUEST_TRANSITIONS
    elif entity_type == 'JOB':
        transitions = JOB_TRANSITIONS
    else:
        return False

    allowed_next = transitions.get(current_status, [])
    return new_status in allowed_next
