"""
Release 6A: Minimal local test for customer_approved template null-safety.
Verifies that normalize_context and customer_approved handle None values
without raising AttributeError or TypeError.
"""
import sys
import os

# Add backend to path so we can import the templates module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'backend'))

from common.notifications.templates import NotificationTemplates


def test_customer_approved_all_none():
    """All context fields are None — simulates worst-case missing data."""
    context = {
        "client_name": None,
        "staff_name": None,
        "request_id": None,
        "pet_names": None,
        "service_type": None,
        "start_date": None,
        "start_time": None,
        "details": None,
    }
    subject, body_text, body_html = NotificationTemplates.get_template('CUSTOMER_APPROVED', context)
    assert subject is not None, "Subject should not be None"
    assert body_text is not None, "body_text should not be None"
    assert body_html is not None, "body_html should not be None"
    assert "None" not in subject, f"Subject contains literal 'None': {subject}"
    # body may contain 'None' if a field leaks — check key fields
    assert "NoneType" not in body_text, "body_text contains NoneType reference"
    assert "NoneType" not in body_html, "body_html contains NoneType reference"
    print("PASS: test_customer_approved_all_none")


def test_customer_approved_happy_path():
    """Normal context with all fields populated."""
    context = {
        "client_name": "Jane Smith",
        "staff_name": "Ryan",
        "request_id": "abc-123",
        "pet_names": "Buddy, Max",
        "service_type": "WALK_30MIN",
        "start_date": "2026-06-01",
        "start_time": "09:00",
        "details": "Morning walk",
    }
    subject, body_text, body_html = NotificationTemplates.get_template('CUSTOMER_APPROVED', context)
    assert subject == "Your Tog & Dogs Request Has Been Approved!"
    assert "Jane Smith" in body_text
    assert "Buddy, Max" in body_text
    assert "30-Minute Walk" in body_text
    assert "2026-06-01 at 09:00" in body_text
    assert "Jane Smith" in body_html
    assert "Buddy, Max" in body_html
    print("PASS: test_customer_approved_happy_path")


def test_customer_approved_empty_strings():
    """Context with empty strings instead of None."""
    context = {
        "client_name": "",
        "staff_name": "",
        "request_id": "",
        "pet_names": "",
        "service_type": "",
        "start_date": "",
        "start_time": "",
        "details": "",
    }
    subject, body_text, body_html = NotificationTemplates.get_template('CUSTOMER_APPROVED', context)
    assert subject is not None
    assert body_text is not None
    assert body_html is not None
    assert "NoneType" not in body_text
    print("PASS: test_customer_approved_empty_strings")


def test_customer_approved_missing_keys():
    """Context dict is missing keys entirely."""
    context = {}
    subject, body_text, body_html = NotificationTemplates.get_template('CUSTOMER_APPROVED', context)
    assert subject is not None
    assert body_text is not None
    assert body_html is not None
    assert "NoneType" not in body_text
    print("PASS: test_customer_approved_missing_keys")


def test_normalize_context_none_service_type():
    """Specifically tests the .replace() crash scenario."""
    context = {"service_type": None}
    normalized = NotificationTemplates.normalize_context(context)
    assert normalized['service_label'] == 'Pet Sitting', f"Expected 'Pet Sitting', got '{normalized['service_label']}'"
    print("PASS: test_normalize_context_none_service_type")


def test_normalize_context_unknown_service_type():
    """Tests fallback .replace() path with a valid but unmapped service type."""
    context = {"service_type": "HOUSE_SITTING"}
    normalized = NotificationTemplates.normalize_context(context)
    assert normalized['service_label'] == 'House Sitting', f"Expected 'House Sitting', got '{normalized['service_label']}'"
    print("PASS: test_normalize_context_unknown_service_type")


if __name__ == '__main__':
    test_customer_approved_all_none()
    test_customer_approved_happy_path()
    test_customer_approved_empty_strings()
    test_customer_approved_missing_keys()
    test_normalize_context_none_service_type()
    test_normalize_context_unknown_service_type()
    print("\nAll Release 6A template tests PASSED.")
