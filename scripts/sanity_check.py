# Local sanity check for backend logic
import sys
import os

# Add src/backend to path
sys.path.append(os.path.join(os.getcwd(), 'src', 'backend'))

from common.status import RequestStatus, JobStatus, is_valid_transition

def test_status_transitions():
    print("Testing Status Transitions...")
    # Valid Request transitions
    assert is_valid_transition('REQUEST', 'REQUEST_SUBMITTED', 'REQUEST_APPROVED') == True
    assert is_valid_transition('REQUEST', 'REQUEST_SUBMITTED', 'REQUEST_DECLINED') == True
    assert is_valid_transition('REQUEST', 'REQUEST_UNDER_REVIEW', 'REQUEST_APPROVED') == True
    
    # Invalid Request transitions
    assert is_valid_transition('REQUEST', 'REQUEST_APPROVED', 'REQUEST_SUBMITTED') == False
    assert is_valid_transition('REQUEST', 'REQUEST_DECLINED', 'REQUEST_APPROVED') == False
    
    # Valid Job transitions
    assert is_valid_transition('JOB', 'JOB_CREATED', 'JOB_ASSIGNED') == True
    assert is_valid_transition('JOB', 'JOB_ASSIGNED', 'JOB_COMPLETED') == True
    
    # Invalid Job transitions
    assert is_valid_transition('JOB', 'JOB_COMPLETED', 'JOB_CREATED') == False
    print("Status transitions: PASS")

if __name__ == "__main__":
    try:
        test_status_transitions()
        print("\nAll local sanity checks passed!")
    except AssertionError as e:
        print(f"\nSanity check FAILED: {e}")
        sys.exit(1)
