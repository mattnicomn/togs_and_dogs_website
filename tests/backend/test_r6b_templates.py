"""
Release 6B: Tests for polished visit_scheduled and staff_assigned templates.
Verifies null-safety and correct rendering for all field combinations.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'backend'))

from common.notifications.templates import NotificationTemplates


# --- visit_scheduled tests ---

def test_visit_scheduled_happy_path():
    """Full context renders all fields correctly."""
    context = {
        "client_name": "Jane Smith",
        "pet_names": "Buddy, Max",
        "service_type": "WALK_30MIN",
        "start_date": "2026-06-01",
        "start_time": "09:00",
        "staff_name": "Ryan",
        "worker_name": "Ryan",
        "portal_url": "https://toganddogs.usmissionhero.com",
    }
    subject, body_text, body_html = NotificationTemplates.get_template('VISIT_SCHEDULED', context)
    assert "Jane Smith" in body_text
    assert "Buddy, Max" in body_text
    assert "30-Minute Walk" in body_text
    assert "Jun 1, 2026 at 09:00" in body_text
    assert "Ryan" in body_text
    assert "Confirmed" in subject
    assert "Jane Smith" in body_html
    assert "Ryan" in body_html
    assert "View in Portal" in body_html
    print("PASS: test_visit_scheduled_happy_path")


def test_visit_scheduled_all_none():
    """All fields None — must not crash or show 'None'."""
    context = {
        "client_name": None,
        "pet_names": None,
        "service_type": None,
        "start_date": None,
        "start_time": None,
        "staff_name": None,
        "worker_name": None,
        "portal_url": None,
    }
    subject, body_text, body_html = NotificationTemplates.get_template('VISIT_SCHEDULED', context)
    assert subject is not None
    assert "None" not in subject
    assert "NoneType" not in body_text
    assert "NoneType" not in body_html
    # Should use defaults
    assert "Valued Client" in body_text
    assert "your pets" in body_text
    assert "Pet Sitting" in body_text
    print("PASS: test_visit_scheduled_all_none")


def test_visit_scheduled_no_sitter():
    """No staff_name or worker_name — sitter row should not appear."""
    context = {
        "client_name": "Test Client",
        "pet_names": "Fido",
        "service_type": "PET_SITTING",
        "start_date": "2026-07-01",
    }
    subject, body_text, body_html = NotificationTemplates.get_template('VISIT_SCHEDULED', context)
    assert subject is not None
    assert "Your Sitter:" not in body_html
    assert "Test Client" in body_text
    print("PASS: test_visit_scheduled_no_sitter")


def test_visit_scheduled_empty_strings():
    """Empty strings for all fields."""
    context = {
        "client_name": "",
        "pet_names": "",
        "service_type": "",
        "start_date": "",
        "start_time": "",
        "staff_name": "",
        "worker_name": "",
    }
    subject, body_text, body_html = NotificationTemplates.get_template('VISIT_SCHEDULED', context)
    assert subject is not None
    assert "NoneType" not in body_text
    assert "NoneType" not in body_html
    print("PASS: test_visit_scheduled_empty_strings")


# --- staff_assigned tests ---

def test_staff_assigned_happy_path():
    """Full context renders all fields correctly."""
    context = {
        "staff_name": "Ryan",
        "worker_name": "Ryan",
        "client_name": "Jane Smith",
        "client_phone": "555-1234",
        "pet_names": "Buddy, Max",
        "service_type": "OVERNIGHT",
        "start_date": "2026-06-15",
        "start_time": "18:00",
        "details": "Back gate code: 1234. Dogs are friendly.",
        "portal_url": "https://toganddogs.usmissionhero.com",
    }
    subject, body_text, body_html = NotificationTemplates.get_template('STAFF_ASSIGNED', context)
    assert "Jane Smith" in subject
    assert "Overnight Care" in subject
    assert "Ryan" in body_text
    assert "Jane Smith" in body_text
    assert "555-1234" in body_text
    assert "Buddy, Max" in body_text
    assert "Back gate code" in body_text
    assert "555-1234" in body_html
    assert "Back gate code" in body_html
    assert "View in Staff Portal" in body_html
    print("PASS: test_staff_assigned_happy_path")


def test_staff_assigned_all_none():
    """All fields None — must not crash or show 'None'."""
    context = {
        "staff_name": None,
        "worker_name": None,
        "client_name": None,
        "client_phone": None,
        "pet_names": None,
        "service_type": None,
        "start_date": None,
        "start_time": None,
        "details": None,
        "portal_url": None,
    }
    subject, body_text, body_html = NotificationTemplates.get_template('STAFF_ASSIGNED', context)
    assert subject is not None
    assert "None" not in subject
    assert "NoneType" not in body_text
    assert "NoneType" not in body_html
    assert "Team Member" in body_text
    print("PASS: test_staff_assigned_all_none")


def test_staff_assigned_no_phone_no_details():
    """No phone or details — those sections should not appear."""
    context = {
        "staff_name": "Sarah",
        "client_name": "Test Client",
        "pet_names": "Luna",
        "service_type": "WALK_60MIN",
        "start_date": "2026-08-01",
    }
    subject, body_text, body_html = NotificationTemplates.get_template('STAFF_ASSIGNED', context)
    assert "Client Phone:" not in body_html
    assert "Care Notes:" not in body_html
    assert "Sarah" in body_text
    assert "Test Client" in body_text
    assert "Luna" in body_text
    print("PASS: test_staff_assigned_no_phone_no_details")


def test_staff_assigned_empty_strings():
    """Empty strings for all fields."""
    context = {
        "staff_name": "",
        "worker_name": "",
        "client_name": "",
        "client_phone": "",
        "pet_names": "",
        "service_type": "",
        "start_date": "",
        "start_time": "",
        "details": "",
    }
    subject, body_text, body_html = NotificationTemplates.get_template('STAFF_ASSIGNED', context)
    assert subject is not None
    assert "NoneType" not in body_text
    assert "NoneType" not in body_html
    print("PASS: test_staff_assigned_empty_strings")


def test_staff_assigned_details_default_skipped():
    """details='No details provided.' should not render the notes section."""
    context = {
        "staff_name": "Ryan",
        "client_name": "Client",
        "pet_names": "Dog",
        "service_type": "PET_SITTING",
        "start_date": "2026-09-01",
        "details": "No details provided.",
    }
    subject, body_text, body_html = NotificationTemplates.get_template('STAFF_ASSIGNED', context)
    assert "Care Notes:" not in body_html
    assert "No details provided." not in body_html
    print("PASS: test_staff_assigned_details_default_skipped")


# --- visit_cancelled tests ---

def test_visit_cancelled_happy_path():
    """Full context with reason, staff, date — all fields render."""
    context = {
        "client_name": "Joey Rockwell",
        "pet_names": "Buddy, Max",
        "service_type": "OVERNIGHT",
        "start_date": "2026-06-15",
        "start_time": "18:00",
        "worker_name": "Ryan",
        "cancellation_reason": "Client travel plans changed.",
        "portal_url": "https://toganddogs.usmissionhero.com",
    }
    subject, body_text, body_html = NotificationTemplates.get_template('VISIT_CANCELLED', context)
    assert "Joey Rockwell" in subject
    assert "Overnight Care" in subject
    assert "Hello," in body_text
    assert "Joey Rockwell" in body_text
    assert "Buddy, Max" in body_text
    assert "Overnight Care" in body_text
    assert "Jun 15, 2026 at 18:00" in body_text
    assert "Ryan" in body_text
    assert "Client travel plans changed." in body_text
    assert "Hello," in body_html
    assert "Joey Rockwell" in body_html
    assert "Ryan" in body_html
    assert "Client travel plans changed." in body_html
    assert "View in Portal" in body_html
    # Must NOT greet as if recipient is the client
    assert "Hi Joey Rockwell" not in body_text
    assert "Hi <strong>Joey Rockwell</strong>" not in body_html
    print("PASS: test_visit_cancelled_happy_path")


def test_visit_cancelled_all_none():
    """All fields None — must not crash or show 'None'."""
    context = {
        "client_name": None,
        "pet_names": None,
        "service_type": None,
        "start_date": None,
        "start_time": None,
        "worker_name": None,
        "staff_name": None,
        "cancellation_reason": None,
        "portal_url": None,
    }
    subject, body_text, body_html = NotificationTemplates.get_template('VISIT_CANCELLED', context)
    assert subject is not None
    assert "None" not in subject
    assert "NoneType" not in body_text
    assert "NoneType" not in body_html
    assert "Hello," in body_text
    print("PASS: test_visit_cancelled_all_none")


def test_visit_cancelled_no_reason():
    """No cancellation reason — reason section should not appear."""
    context = {
        "client_name": "Test Client",
        "pet_names": "Fido",
        "service_type": "WALK_30MIN",
        "start_date": "2026-07-01",
        "cancellation_reason": "",
    }
    subject, body_text, body_html = NotificationTemplates.get_template('VISIT_CANCELLED', context)
    assert "Cancellation Reason:" not in body_html
    assert "Reason:" not in body_text
    assert "Test Client" in body_text
    print("PASS: test_visit_cancelled_no_reason")


def test_visit_cancelled_no_staff():
    """No assigned worker — sitter row should not appear."""
    context = {
        "client_name": "Test Client",
        "pet_names": "Luna",
        "service_type": "PET_SITTING",
        "start_date": "2026-08-01",
        "worker_name": "",
        "staff_name": "",
        "cancellation_reason": "Schedule conflict.",
    }
    subject, body_text, body_html = NotificationTemplates.get_template('VISIT_CANCELLED', context)
    assert "Assigned Sitter:" not in body_html
    assert "Assigned Sitter:" not in body_text
    assert "Schedule conflict." in body_text
    print("PASS: test_visit_cancelled_no_staff")


def test_visit_cancelled_empty_strings():
    """Empty strings for all fields."""
    context = {
        "client_name": "",
        "pet_names": "",
        "service_type": "",
        "start_date": "",
        "start_time": "",
        "worker_name": "",
        "staff_name": "",
        "cancellation_reason": "",
        "portal_url": "",
    }
    subject, body_text, body_html = NotificationTemplates.get_template('VISIT_CANCELLED', context)
    assert subject is not None
    assert "NoneType" not in body_text
    assert "NoneType" not in body_html
    assert "Hello," in body_text
    print("PASS: test_visit_cancelled_empty_strings")


def test_visit_cancelled_default_reason_skipped():
    """'No reason provided.' should not render the reason section."""
    context = {
        "client_name": "Client",
        "pet_names": "Dog",
        "service_type": "PET_SITTING",
        "start_date": "2026-09-01",
        "cancellation_reason": "No reason provided.",
    }
    subject, body_text, body_html = NotificationTemplates.get_template('VISIT_CANCELLED', context)
    assert "Cancellation Reason:" not in body_html
    assert "Reason:" not in body_text
    print("PASS: test_visit_cancelled_default_reason_skipped")


def test_visit_cancelled_no_client_greeting():
    """Template must not greet the recipient as the client (shared audience)."""
    context = {
        "client_name": "Jane Smith",
        "pet_names": "Buddy",
        "service_type": "WALK_60MIN",
        "start_date": "2026-10-01",
    }
    subject, body_text, body_html = NotificationTemplates.get_template('VISIT_CANCELLED', context)
    # Must use neutral greeting, not "Hi Jane Smith"
    assert "Hi Jane Smith" not in body_text
    assert "Hi <strong>Jane Smith</strong>" not in body_html
    assert "Hello," in body_text
    assert "Hello,</p>" in body_html
    print("PASS: test_visit_cancelled_no_client_greeting")


if __name__ == '__main__':
    test_visit_scheduled_happy_path()
    test_visit_scheduled_all_none()
    test_visit_scheduled_no_sitter()
    test_visit_scheduled_empty_strings()
    test_staff_assigned_happy_path()
    test_staff_assigned_all_none()
    test_staff_assigned_no_phone_no_details()
    test_staff_assigned_empty_strings()
    test_staff_assigned_details_default_skipped()
    test_visit_cancelled_happy_path()
    test_visit_cancelled_all_none()
    test_visit_cancelled_no_reason()
    test_visit_cancelled_no_staff()
    test_visit_cancelled_empty_strings()
    test_visit_cancelled_default_reason_skipped()
    test_visit_cancelled_no_client_greeting()
    print("\nAll Release 6B template tests PASSED.")
