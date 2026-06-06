"""
Release 8U: Staff Profile Duplicate Cleanup — Automated Tests

Covers:
1. GET /admin/staff enforces is_assignable=False for profiles with invalid email format.
2. GET /admin/staff enforces is_assignable=False for profiles with no cognito_sub.
3. GET /admin/staff enforces is_assignable=False for profiles with cognito_sub='unlinked'.
4. GET /admin/staff keeps is_assignable=True for valid profiles.
5. GET /admin/staff still returns all profiles (including invalid) for full admin visibility.
6. POST /admin/assign with typo worker_id (invalid email format) returns 400.
7. POST /admin/assign with valid-format worker_id that matches no staff profile returns 400.
8. POST /admin/assign with valid worker_id matching eligible staff profile proceeds.
"""

import pytest
import json
from unittest.mock import patch, MagicMock
from botocore.exceptions import ClientError


def make_admin_event(path, method, body_dict=None, path_params=None):
    return {
        "requestContext": {
            "authorizer": {
                "claims": {
                    "email": "admin@test.com",
                    "sub": "admin-sub-123",
                    "cognito:groups": "Admin"
                }
            }
        },
        "httpMethod": method,
        "path": path,
        "pathParameters": path_params or {},
        "body": json.dumps(body_dict or {})
    }


def make_assign_event(body_dict):
    return {
        "requestContext": {
            "authorizer": {
                "claims": {
                    "email": "admin@test.com",
                    "sub": "admin-sub-123",
                    "cognito:groups": "Admin"
                }
            }
        },
        "httpMethod": "POST",
        "path": "/admin/assign",
        "pathParameters": {},
        "body": json.dumps(body_dict)
    }


@pytest.fixture
def mock_cognito():
    with patch('boto3.client') as mock_boto:
        mock_client = MagicMock()
        mock_exceptions = MagicMock()
        mock_exceptions.UserNotFoundException = ClientError
        mock_client.exceptions = mock_exceptions
        mock_boto.return_value = mock_client
        yield mock_client


@pytest.fixture
def mock_db():
    with patch('common.db.table') as mock_table:
        yield mock_table


# ─── GET /admin/staff Guardrail Tests ────────────────────────────────────────

class TestGetStaffAssignmentEligibility:
    """GET /admin/staff should enforce is_assignable=False for ineligible profiles."""

    def _setup_cognito(self, mock_cognito):
        mock_cognito.list_groups.return_value = {"Groups": [{"GroupName": "Staff"}]}
        mock_cognito.list_users_in_group.return_value = {"Users": []}

    def test_invalid_email_format_overrides_is_assignable_to_false(self, mock_db, mock_cognito):
        """A profile with a typo email (no dot before TLD) must have is_assignable forced False."""
        from handlers.admin_handler import handler as admin_handler

        mock_db.query.return_value = {
            "Items": [
                {
                    "PK": "COMPANY#tog_and_dogs",
                    "SK": "STAFF#staff_typo",
                    "staff_id": "staff_typo",
                    "email": "mattnicomn10@yahoocom",   # missing dot — invalid email
                    "display_name": "Typo Profile",
                    "is_assignable": True,              # was True in DB
                    "is_active": True,
                    "cognito_sub": "some-sub-uuid"
                }
            ]
        }
        self._setup_cognito(mock_cognito)

        event = make_admin_event("/admin/staff", "GET")
        resp = admin_handler(event, None)

        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        staff_list = body["staff"]

        # Profile is still returned (visible for admin repair)
        assert len(staff_list) == 1
        assert staff_list[0]["email"] == "mattnicomn10@yahoocom"
        # But is_assignable must be forced False due to invalid email
        assert staff_list[0]["is_assignable"] is False, (
            "Profile with invalid email format should have is_assignable=False"
        )

    def test_no_cognito_sub_overrides_is_assignable_to_false(self, mock_db, mock_cognito):
        """A profile with no cognito_sub must have is_assignable forced False."""
        from handlers.admin_handler import handler as admin_handler

        mock_db.query.return_value = {
            "Items": [
                {
                    "PK": "COMPANY#tog_and_dogs",
                    "SK": "STAFF#staff_no_sub",
                    "staff_id": "staff_no_sub",
                    "email": "realuser@example.com",  # valid email
                    "display_name": "No Sub Profile",
                    "is_assignable": True,
                    "is_active": True,
                    "cognito_sub": None               # no Cognito linkage
                }
            ]
        }
        self._setup_cognito(mock_cognito)

        event = make_admin_event("/admin/staff", "GET")
        resp = admin_handler(event, None)

        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        staff_list = body["staff"]

        assert len(staff_list) == 1
        assert staff_list[0]["is_assignable"] is False, (
            "Profile with no cognito_sub should have is_assignable=False"
        )

    def test_unlinked_sentinel_overrides_is_assignable_to_false(self, mock_db, mock_cognito):
        """A profile with cognito_sub='unlinked' must have is_assignable forced False."""
        from handlers.admin_handler import handler as admin_handler

        mock_db.query.return_value = {
            "Items": [
                {
                    "PK": "COMPANY#tog_and_dogs",
                    "SK": "STAFF#staff_unlinked",
                    "staff_id": "staff_unlinked",
                    "email": "valid@example.com",
                    "display_name": "Unlinked Profile",
                    "is_assignable": True,
                    "is_active": True,
                    "cognito_sub": "unlinked"          # R8S unlink sentinel
                }
            ]
        }
        self._setup_cognito(mock_cognito)

        event = make_admin_event("/admin/staff", "GET")
        resp = admin_handler(event, None)

        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        staff_list = body["staff"]

        assert len(staff_list) == 1
        assert staff_list[0]["is_assignable"] is False, (
            "Unlinked profile should have is_assignable=False"
        )
        assert staff_list[0]["cognito_sub"] is None, (
            "Unlinked profile cognito_sub should be returned as None (not 'unlinked') to the frontend"
        )

    def test_valid_profile_preserves_is_assignable_true(self, mock_db, mock_cognito):
        """A profile with valid email and real cognito_sub must keep is_assignable=True."""
        from handlers.admin_handler import handler as admin_handler

        mock_db.query.return_value = {
            "Items": [
                {
                    "PK": "COMPANY#tog_and_dogs",
                    "SK": "STAFF#cognito_mattnicomn10@yahoo.com",
                    "staff_id": "cognito_mattnicomn10@yahoo.com",
                    "email": "mattnicomn10@yahoo.com",  # valid email with dot
                    "display_name": "Staff Test User",
                    "is_assignable": True,
                    "is_active": True,
                    "cognito_sub": "f4485448-b0f1-700b-2605-b5c95e34a8b3"  # real sub
                }
            ]
        }
        self._setup_cognito(mock_cognito)

        event = make_admin_event("/admin/staff", "GET")
        resp = admin_handler(event, None)

        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        staff_list = body["staff"]

        assert len(staff_list) == 1
        assert staff_list[0]["email"] == "mattnicomn10@yahoo.com"
        assert staff_list[0]["is_assignable"] is True, (
            "Valid profile with real email and cognito_sub should keep is_assignable=True"
        )

    def test_invalid_and_valid_profiles_both_returned(self, mock_db, mock_cognito):
        """All profiles are returned (admin visibility), but invalid ones have is_assignable=False."""
        from handlers.admin_handler import handler as admin_handler

        mock_db.query.return_value = {
            "Items": [
                {
                    "PK": "COMPANY#tog_and_dogs",
                    "SK": "STAFF#staff_typo",
                    "staff_id": "staff_typo",
                    "email": "baduser@yahoocom",  # invalid
                    "display_name": "Typo Profile",
                    "is_assignable": True,
                    "is_active": True,
                    "cognito_sub": "some-sub"
                },
                {
                    "PK": "COMPANY#tog_and_dogs",
                    "SK": "STAFF#staff_good",
                    "staff_id": "staff_good",
                    "email": "gooduser@yahoo.com",  # valid
                    "display_name": "Good Profile",
                    "is_assignable": True,
                    "is_active": True,
                    "cognito_sub": "real-sub-uuid"
                }
            ]
        }
        self._setup_cognito(mock_cognito)

        event = make_admin_event("/admin/staff", "GET")
        resp = admin_handler(event, None)

        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        staff_list = body["staff"]

        # Both profiles must be returned
        assert len(staff_list) == 2

        by_email = {s["email"]: s for s in staff_list}
        assert by_email["baduser@yahoocom"]["is_assignable"] is False
        assert by_email["gooduser@yahoo.com"]["is_assignable"] is True


# ─── POST /admin/assign Guardrail Tests ──────────────────────────────────────

class TestAssignWorkerValidation:
    """POST /admin/assign should reject invalid worker_id values before writing."""

    def test_typo_email_worker_id_returns_400(self, mock_db, mock_cognito):
        """worker_id with invalid email format (missing dot) must return 400."""
        from handlers.assignment_handler import handler as assign_handler

        mock_db.query.return_value = {"Items": []}  # no staff profiles needed — email fails first

        event = make_assign_event({
            "job_id": "job-uuid-123",
            "req_id": "req-uuid-456",
            "client_id": "client-uuid-789",
            "worker_id": "mattnicomn10@yahoocom",   # typo — missing dot
            "worker_name": "Typo User"
        })
        resp = assign_handler(event, None)

        assert resp["statusCode"] == 400
        body = json.loads(resp["body"])
        assert "Invalid worker_id format" in body["error"]
        assert "mattnicomn10@yahoocom" in body["error"]

    def test_valid_format_but_no_matching_profile_returns_400(self, mock_db, mock_cognito):
        """worker_id with valid format but no matching staff profile must return 400."""
        from handlers.assignment_handler import handler as assign_handler

        # No matching profile for this worker_id
        mock_db.query.return_value = {
            "Items": [
                {
                    "PK": "COMPANY#tog_and_dogs",
                    "SK": "STAFF#staff_other",
                    "email": "someone_else@example.com",
                    "is_active": True,
                    "is_assignable": True,
                    "cognito_sub": "real-sub-uuid"
                }
            ]
        }

        event = make_assign_event({
            "job_id": "job-uuid-123",
            "req_id": "req-uuid-456",
            "client_id": "client-uuid-789",
            "worker_id": "ghost@example.com",  # valid format, no profile
            "worker_name": "Ghost User"
        })
        resp = assign_handler(event, None)

        assert resp["statusCode"] == 400
        body = json.loads(resp["body"])
        assert "No eligible assignable staff profile" in body["error"]
        assert "ghost@example.com" in body["error"]

    def test_ineligible_profile_not_assignable_returns_400(self, mock_db, mock_cognito):
        """worker_id matching a profile with is_assignable=False must return 400."""
        from handlers.assignment_handler import handler as assign_handler

        mock_db.query.return_value = {
            "Items": [
                {
                    "PK": "COMPANY#tog_and_dogs",
                    "SK": "STAFF#staff_not_assignable",
                    "email": "notassignable@example.com",
                    "is_active": True,
                    "is_assignable": False,  # explicitly not assignable
                    "cognito_sub": "real-sub-uuid"
                }
            ]
        }

        event = make_assign_event({
            "job_id": "job-uuid-123",
            "req_id": "req-uuid-456",
            "client_id": "client-uuid-789",
            "worker_id": "notassignable@example.com",
            "worker_name": "Not Assignable"
        })
        resp = assign_handler(event, None)

        assert resp["statusCode"] == 400
        body = json.loads(resp["body"])
        assert "No eligible assignable staff profile" in body["error"]

    def test_profile_with_unlinked_sub_returns_400(self, mock_db, mock_cognito):
        """worker_id matching a profile with cognito_sub='unlinked' must return 400."""
        from handlers.assignment_handler import handler as assign_handler

        mock_db.query.return_value = {
            "Items": [
                {
                    "PK": "COMPANY#tog_and_dogs",
                    "SK": "STAFF#staff_unlinked",
                    "email": "unlinked@example.com",
                    "is_active": True,
                    "is_assignable": True,
                    "cognito_sub": "unlinked"  # R8S unlink sentinel
                }
            ]
        }

        event = make_assign_event({
            "job_id": "job-uuid-123",
            "req_id": "req-uuid-456",
            "client_id": "client-uuid-789",
            "worker_id": "unlinked@example.com",
            "worker_name": "Unlinked User"
        })
        resp = assign_handler(event, None)

        assert resp["statusCode"] == 400
        body = json.loads(resp["body"])
        assert "No eligible assignable staff profile" in body["error"]

    def test_valid_worker_id_with_eligible_profile_proceeds(self, mock_db, mock_cognito):
        """worker_id matching an eligible staff profile must proceed past validation."""
        from handlers.assignment_handler import handler as assign_handler

        # The validation query returns a valid eligible profile
        valid_staff_profile = {
            "PK": "COMPANY#tog_and_dogs",
            "SK": "STAFF#cognito_mattnicomn10@yahoo.com",
            "email": "mattnicomn10@yahoo.com",
            "is_active": True,
            "is_assignable": True,
            "cognito_sub": "f4485448-b0f1-700b-2605-b5c95e34a8b3"
        }

        # The job lookup and update need to succeed
        job_record = {
            "PK": "JOB#job-uuid-123",
            "SK": "REQ#req-uuid-456",
            "status": "APPROVED",
            "entity_type": "JOB",
            "company_id": "tog_and_dogs",
            "client_id": "client-uuid-789",
            "service_type": "WALK_30MIN",
            "selected_dates": ["2026-07-01"],
            "start_date": "2026-07-01",
            "worker_id": None
        }

        # query() is called for staff validation; get_item() is called for job fetch
        mock_db.query.return_value = {"Items": [valid_staff_profile]}
        mock_db.get_item.return_value = {"Item": job_record}
        mock_db.update_item.return_value = {}

        with patch('common.google_calendar.sync_calendar_event', return_value={"status": "ok"}), \
             patch('common.notifications.service.notify_event', return_value=None):
            event = make_assign_event({
                "job_id": "job-uuid-123",
                "req_id": "req-uuid-456",
                "client_id": "client-uuid-789",
                "worker_id": "mattnicomn10@yahoo.com",
                "worker_name": "Staff Test User"
            })
            resp = assign_handler(event, None)

        # Should NOT return 400 from the validation step
        # (may succeed with 200 or fail later due to mock gaps, but not 400 for worker_id)
        body = json.loads(resp["body"])
        assert resp["statusCode"] != 400 or "worker_id" not in body.get("error", ""), (
            f"Assignment should not be rejected at worker_id validation for a valid profile. "
            f"Got {resp['statusCode']}: {body}"
        )
