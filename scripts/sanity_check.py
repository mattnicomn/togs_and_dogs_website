# Local sanity check for backend logic
import sys
import os

# Add src/backend to path
sys.path.append(os.path.join(os.getcwd(), 'src', 'backend'))

from common.status import RequestStatus, JobStatus, is_valid_transition
from common.auth import get_effective_role, sanitize_booking_for_role


def test_status_transitions():
    print("Testing Status Transitions...")
    # Valid Request transitions
    assert is_valid_transition('REQUEST', 'PENDING_REVIEW', 'APPROVED') == True
    assert is_valid_transition('REQUEST', 'PENDING_REVIEW', 'DECLINED') == True
    assert is_valid_transition('REQUEST', 'MEET_GREET_REQUIRED', 'READY_FOR_APPROVAL') == True
    
    # Invalid Request transitions
    assert is_valid_transition('REQUEST', 'APPROVED', 'PENDING_REVIEW') == False
    assert is_valid_transition('REQUEST', 'DECLINED', 'APPROVED') == False

    
    # Valid Job transitions
    assert is_valid_transition('JOB', 'JOB_CREATED', 'ASSIGNED') == True
    assert is_valid_transition('JOB', 'ASSIGNED', 'COMPLETED') == True
    
    # Invalid Job transitions
    assert is_valid_transition('JOB', 'COMPLETED', 'PENDING_REVIEW') == False


    print("Status transitions: PASS")

def test_auth_helpers():
    print("Testing Auth Helpers...")
    # Test role priority
    event_owner = {'requestContext': {'authorizer': {'claims': {'cognito:groups': ['owner']}}}}
    event_admin = {'requestContext': {'authorizer': {'claims': {'cognito:groups': ['admin', 'staff']}}}}
    event_staff = {'requestContext': {'authorizer': {'claims': {'cognito:groups': ['staff']}}}}
    event_client = {'requestContext': {'authorizer': {'claims': {'cognito:groups': ['client']}}}}
    event_none = {'requestContext': {'authorizer': {'claims': {}}}}
    
    assert get_effective_role(event_owner) == 'owner'
    assert get_effective_role(event_admin) == 'admin'
    assert get_effective_role(event_staff) == 'staff'
    assert get_effective_role(event_client) == 'client'
    assert get_effective_role(event_none) == 'unknown'
    
    # Test sanitization
    record = {
        'PK': 'REQ#123',
        'meet_and_greet_notes': 'Sensitive info',
        'care_instructions': 'Feed the dog'
    }
    
    owner_sanitized = sanitize_booking_for_role(record, 'owner')
    assert owner_sanitized['meet_and_greet_notes'] == 'Sensitive info'
    
    staff_sanitized = sanitize_booking_for_role(record, 'staff')
    assert staff_sanitized['meet_and_greet_notes'] is None
    assert staff_sanitized['care_instructions'] == 'Feed the dog'
    assert staff_sanitized['notes_redacted'] == True
    
    print("Auth helpers: PASS")


if __name__ == "__main__":
    try:
        test_status_transitions()
        test_auth_helpers()

        print("\nAll local sanity checks passed!")
    except AssertionError as e:
        import traceback
        traceback.print_exc()
        print(f"\nSanity check FAILED: {e}")
        sys.exit(1)

