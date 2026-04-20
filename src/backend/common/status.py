from enum import Enum

class RequestStatus(Enum):
    PENDING_REVIEW = "PENDING_REVIEW"
    MEET_GREET_REQUIRED = "MEET_GREET_REQUIRED"
    READY_FOR_APPROVAL = "READY_FOR_APPROVAL"
    APPROVED = "APPROVED"
    DECLINED = "DECLINED"

class JobStatus(Enum):
    JOB_CREATED = "JOB_CREATED"
    ASSIGNED = "ASSIGNED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"

# Define valid transitions for Request
REQUEST_TRANSITIONS = {
    RequestStatus.PENDING_REVIEW.value: [
        RequestStatus.MEET_GREET_REQUIRED.value,
        RequestStatus.READY_FOR_APPROVAL.value,
        RequestStatus.APPROVED.value, # Support direct approval for existing clients
        RequestStatus.DECLINED.value
    ],
    RequestStatus.MEET_GREET_REQUIRED.value: [
        RequestStatus.READY_FOR_APPROVAL.value,
        RequestStatus.DECLINED.value
    ],
    RequestStatus.READY_FOR_APPROVAL.value: [
        RequestStatus.APPROVED.value,
        RequestStatus.DECLINED.value
    ]
}

# Define valid transitions for Job
JOB_TRANSITIONS = {
    JobStatus.JOB_CREATED.value: [
        JobStatus.ASSIGNED.value,
        JobStatus.CANCELLED.value
    ],
    JobStatus.ASSIGNED.value: [
        JobStatus.COMPLETED.value,
        JobStatus.CANCELLED.value
    ]
}

def is_valid_transition(entity_type, current_status, new_status):
    """
    Validates if a status transition is allowed.
    entity_type: 'REQUEST' or 'JOB'
    """
    if entity_type == 'REQUEST':
        transitions = REQUEST_TRANSITIONS
    elif entity_type == 'JOB':
        transitions = JOB_TRANSITIONS
    else:
        return False

    allowed_next = transitions.get(current_status, [])
    return new_status in allowed_next
