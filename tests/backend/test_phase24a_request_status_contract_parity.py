"""
Phase 24A-2C.1A: Request-Status Contract & Parity Hardening Tests

Validates canonical request-status contract integrity, exact 17 canonical status keys,
exact key order, label metadata, categories, flags, synonyms, generated web and mobile adapters,
backend RequestStatus enum parity, and absence of runtime consumer wiring.
"""

import json
import re
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
STATUSES_JSON_PATH = ROOT_DIR / "shared" / "constants" / "request-statuses.json"
WEB_ADAPTER_PATH = ROOT_DIR / "web" / "src" / "generated" / "contracts.js"
MOBILE_ADAPTER_PATH = ROOT_DIR / "mobile" / "src" / "contracts" / "generatedContracts.ts"
STATUS_PY_PATH = ROOT_DIR / "src" / "backend" / "common" / "status.py"

CANONICAL_KEYS_IN_ORDER = [
    "PENDING_REVIEW",
    "MEET_GREET_REQUIRED",
    "MG_SCHEDULED",
    "MG_COMPLETED",
    "PROFILE_CREATED",
    "READY_FOR_APPROVAL",
    "QUOTE_NEEDED",
    "QUOTE_SENT",
    "APPROVED",
    "ASSIGNED",
    "DECLINED",
    "CANCELLATION_REQUESTED",
    "CANCELLATION_DENIED",
    "CANCELLED",
    "COMPLETED",
    "ARCHIVED",
    "DELETED",
]

APPROVED_LABEL_MAP = {
    "PENDING_REVIEW": "Pending Review",
    "MEET_GREET_REQUIRED": "Meet & Greet Required",
    "MG_SCHEDULED": "Meet & Greet Scheduled",
    "MG_COMPLETED": "Meet & Greet Completed",
    "PROFILE_CREATED": "Profile Created",
    "READY_FOR_APPROVAL": "Ready for Approval",
    "QUOTE_NEEDED": "Quote Needed",
    "QUOTE_SENT": "Quote Sent",
    "APPROVED": "Approved",
    "ASSIGNED": "Assigned",
    "DECLINED": "Declined",
    "CANCELLATION_REQUESTED": "Cancellation Requested",
    "CANCELLATION_DENIED": "Cancellation Denied",
    "CANCELLED": "Cancelled",
    "COMPLETED": "Completed",
    "ARCHIVED": "Archived",
    "DELETED": "Deleted",
}

EXPECTED_CATEGORIES = {"neutral", "informational", "success", "warning", "danger"}


def load_canonical_statuses():
    with open(STATUSES_JSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_clean_canonical_statuses():
    raw = load_canonical_statuses()
    return {k: v for k, v in raw.items() if not k.startswith("_")}


def parse_export_from_source(source: str, export_name: str, terminator_name: str) -> dict:
    pattern = rf"export const {export_name} = ([\s\S]*?)(?: as const)?;\r?\n(?:\r?\n)?export const {terminator_name}"
    match = re.search(pattern, source)
    assert match is not None, f"Unable to parse export {export_name} up to {terminator_name}"
    return json.loads(match.group(1))


def test_canonical_contract_file_exists_and_parses():
    assert STATUSES_JSON_PATH.exists(), "request-statuses.json missing"
    data = load_canonical_statuses()
    assert "statuses" in data
    assert "categories" in data
    assert data["_contract"] == "Togs & Dogs request status identifiers"


def test_canonical_17_keys_and_exact_order():
    data = load_canonical_statuses()
    statuses = data["statuses"]
    actual_keys = list(statuses.keys())
    assert len(actual_keys) == 17, f"Expected 17 canonical keys, got {len(actual_keys)}"
    assert actual_keys == CANONICAL_KEYS_IN_ORDER, "Canonical status key order differs"


def test_canonical_status_entry_fields_and_order():
    data = load_canonical_statuses()
    statuses = data["statuses"]
    expected_field_names = ["label", "category", "terminal", "customerVisible", "staffSettable", "synonyms"]

    for status_id, entry in statuses.items():
        field_keys = list(entry.keys())
        assert field_keys == expected_field_names, f"Field names or order for {status_id} differs: {field_keys}"
        assert field_keys[0] == "label", f"label is not first property in {status_id}"


def test_canonical_status_labels_match_approved_map():
    data = load_canonical_statuses()
    statuses = data["statuses"]

    for status_id, expected_label in APPROVED_LABEL_MAP.items():
        assert status_id in statuses
        actual_label = statuses[status_id]["label"]
        assert actual_label == expected_label, f"Label mismatch for {status_id}: got '{actual_label}', expected '{expected_label}'"
        assert isinstance(actual_label, str)
        assert len(actual_label.strip()) > 0, f"Empty label string for {status_id}"


def test_canonical_categories_flags_and_synonyms():
    data = load_canonical_statuses()
    statuses = data["statuses"]

    for status_id, entry in statuses.items():
        assert entry["category"] in EXPECTED_CATEGORIES, f"Invalid category for {status_id}"
        assert isinstance(entry["terminal"], bool)
        assert isinstance(entry["customerVisible"], bool)
        assert isinstance(entry["staffSettable"], bool)
        assert isinstance(entry["synonyms"], list)

    # Spot-check explicit synonyms
    assert "NEEDS_REVIEW" in statuses["PENDING_REVIEW"]["synonyms"]
    assert "NEEDS_MG" in statuses["MEET_GREET_REQUIRED"]["synonyms"]
    assert "NEW_REQUEST" in statuses["READY_FOR_APPROVAL"]["synonyms"]
    assert "QUOTED" in statuses["QUOTE_SENT"]["synonyms"]
    assert "BOOKED" in statuses["APPROVED"]["synonyms"]
    assert "JOB_CREATED" in statuses["ASSIGNED"]["synonyms"]
    assert "SCHEDULED" in statuses["ASSIGNED"]["synonyms"]


def test_web_adapter_request_statuses_parity():
    clean_canonical = get_clean_canonical_statuses()
    web_source = WEB_ADAPTER_PATH.read_text(encoding="utf-8")
    web_statuses = parse_export_from_source(web_source, "REQUEST_STATUSES", "SERVICE_TYPES")

    assert web_statuses == clean_canonical, "Web generated REQUEST_STATUSES adapter differs from canonical"
    assert list(web_statuses["statuses"].keys()) == CANONICAL_KEYS_IN_ORDER


def test_mobile_adapter_request_statuses_parity():
    clean_canonical = get_clean_canonical_statuses()
    mobile_source = MOBILE_ADAPTER_PATH.read_text(encoding="utf-8")
    mobile_statuses = parse_export_from_source(mobile_source, "REQUEST_STATUSES", "SERVICE_TYPES")

    assert mobile_statuses == clean_canonical, "Mobile generated REQUEST_STATUSES adapter differs from canonical"
    assert list(mobile_statuses["statuses"].keys()) == CANONICAL_KEYS_IN_ORDER


def test_web_and_mobile_adapters_equal_each_other():
    web_source = WEB_ADAPTER_PATH.read_text(encoding="utf-8")
    mobile_source = MOBILE_ADAPTER_PATH.read_text(encoding="utf-8")

    web_statuses = parse_export_from_source(web_source, "REQUEST_STATUSES", "SERVICE_TYPES")
    mobile_statuses = parse_export_from_source(mobile_source, "REQUEST_STATUSES", "SERVICE_TYPES")

    assert web_statuses == mobile_statuses, "Web and Mobile generated REQUEST_STATUSES adapters differ"


def test_backend_request_status_enum_contains_17_canonical_keys():
    from common.status import RequestStatus

    enum_members = {member.value for member in RequestStatus}

    for key in CANONICAL_KEYS_IN_ORDER:
        assert key in enum_members, f"Canonical key {key} missing from backend RequestStatus enum"


def test_backend_aliases_characterized_and_excluded_from_canonical():
    from common.status import RequestStatus

    # Characterize documented backend RequestStatus synonyms / aliases
    known_backend_synonyms = {"NEEDS_REVIEW", "NEEDS_MG", "NEW_REQUEST", "QUOTED", "BOOKED"}

    for alias in known_backend_synonyms:
        assert alias in RequestStatus.__members__, f"Documented alias {alias} missing from backend enum"
        assert alias not in CANONICAL_KEYS_IN_ORDER, f"Alias {alias} unexpectedly included as canonical contract key"


def test_job_status_domain_separated_from_request_contract():
    from common.status import JobStatus

    job_members = {member.value for member in JobStatus}
    assert "JOB_CREATED" in job_members

    # JobStatus is a separate 6-member enum
    assert len(job_members) == 6
    assert "PENDING_REVIEW" not in job_members
    assert "MEET_GREET_REQUIRED" not in job_members
    assert "QUOTE_SENT" not in job_members


def test_pseudo_actions_and_ui_values_excluded_from_canonical_contract():
    data = load_canonical_statuses()
    canonical_keys = set(data["statuses"].keys())

    non_canonical_candidates = [
        "VERIFY_MEET_GREET",  # Payload action in review_handler
        "IN_PROGRESS",        # MasterScheduler UI filter
        "RESCHEDULED",        # MasterScheduler UI filter
        "REJECTED",           # Mobile StatusBadge UI label alias
        "PENDING REVIEW",     # Mobile raw text fallback
    ]

    for candidate in non_canonical_candidates:
        assert candidate not in canonical_keys, f"Non-canonical status '{candidate}' wrongly present in contract"


def test_no_backend_generated_request_status_adapter_exists():
    backend_adapter = ROOT_DIR / "src" / "backend" / "common" / "generated_request_statuses.py"
    assert not backend_adapter.exists(), "Backend generated_request_statuses.py adapter should not exist in 2C.1A"
