"""
Release 7S: Unit tests for public intake `selected_dates` processing.

The public intake handler (handler() in intake_handler.py) processes
`selected_dates` when it is a list with more than one entry:
  - Filters out invalid/non-string values
  - Deduplicates dates
  - Sorts dates
  - Derives start_date = first valid date, end_date = last valid date
  - Stores the cleaned list as `selected_dates` on the saved item

If selected_dates is absent, None, not a list, or has <= 1 valid entry,
the handler falls through to use the explicit start_date / end_date fields
(or leaves selected_dates as None on the saved item).

These tests exercise the intake handler directly with mocked DB/SFN to avoid
any real AWS calls.
"""
import json
import pytest
from unittest.mock import patch
from handlers.intake_handler import handler as intake_handler


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db():
    with patch('handlers.intake_handler.put_item') as mock_put:
        mock_put.return_value = True
        yield mock_put


@pytest.fixture
def mock_sfn():
    with patch('handlers.intake_handler.sfn') as mock_sfn_client:
        yield mock_sfn_client


def _intake_event(body_overrides=None):
    """Build a valid public-intake event; caller can override body fields."""
    body = {
        "client_name": "Dates Test Client",
        "client_email": "dates@example.com",
        "start_date": "2026-07-01",       # explicit fallback
        "pet_names": "Biscuit",
        "accepted_terms": True,
        "accepted_privacy": True,
        "terms_version": "1.0",
        "privacy_version": "1.0",
    }
    if body_overrides:
        body.update(body_overrides)
    return {"body": json.dumps(body)}


def _saved_item(mock_db):
    """Return the item dict that was passed to put_item()."""
    assert mock_db.called, "put_item was not called"
    return mock_db.call_args[0][0]


# ---------------------------------------------------------------------------
# selected_dates absent / null / single-entry (fallback path)
# ---------------------------------------------------------------------------

def test_no_selected_dates_uses_explicit_start_date(mock_db, mock_sfn):
    """When selected_dates is absent, start_date comes from the explicit field."""
    event = _intake_event()
    resp = intake_handler(event, None)
    assert resp["statusCode"] == 200
    saved = _saved_item(mock_db)
    assert saved["start_date"] == "2026-07-01"
    assert saved["selected_dates"] is None


def test_null_selected_dates_uses_explicit_start_date(mock_db, mock_sfn):
    """selected_dates=None is treated the same as absent."""
    event = _intake_event({"selected_dates": None})
    resp = intake_handler(event, None)
    assert resp["statusCode"] == 200
    saved = _saved_item(mock_db)
    assert saved["start_date"] == "2026-07-01"
    assert saved["selected_dates"] is None


def test_empty_list_selected_dates_uses_explicit_start_date(mock_db, mock_sfn):
    """selected_dates=[] (empty list) falls through to explicit start_date."""
    event = _intake_event({"selected_dates": []})
    resp = intake_handler(event, None)
    assert resp["statusCode"] == 200
    saved = _saved_item(mock_db)
    assert saved["start_date"] == "2026-07-01"
    assert saved["selected_dates"] is None


def test_single_selected_date_does_not_override_start_date(mock_db, mock_sfn):
    """selected_dates with exactly 1 entry: handler only processes lists with
    len > 1, so start_date stays as the explicit field value.
    The single-date list is stored as-is if truthy, otherwise None."""
    event = _intake_event({
        "start_date": "2026-07-10",
        "selected_dates": ["2026-08-01"],
    })
    resp = intake_handler(event, None)
    assert resp["statusCode"] == 200
    saved = _saved_item(mock_db)
    # Single entry: override logic NOT triggered, explicit start_date kept
    assert saved["start_date"] == "2026-07-10"


# ---------------------------------------------------------------------------
# Multi-date processing (len > 1)
# ---------------------------------------------------------------------------

def test_two_selected_dates_derives_start_and_end(mock_db, mock_sfn):
    """Two valid dates → start_date=first, end_date=last, selected_dates stored sorted."""
    event = _intake_event({
        "selected_dates": ["2026-08-05", "2026-08-03"],
        "start_date": "2026-07-01",   # should be overridden
    })
    resp = intake_handler(event, None)
    assert resp["statusCode"] == 200
    saved = _saved_item(mock_db)
    assert saved["start_date"] == "2026-08-03"   # sorted first
    assert saved["end_date"] == "2026-08-05"     # sorted last
    assert saved["selected_dates"] == ["2026-08-03", "2026-08-05"]


def test_multiple_selected_dates_sorted_and_stored(mock_db, mock_sfn):
    """Multiple dates in arbitrary order → sorted, correct start/end."""
    dates = ["2026-09-10", "2026-09-01", "2026-09-05", "2026-09-03"]
    event = _intake_event({
        "selected_dates": dates,
        "start_date": "2026-07-01",
    })
    resp = intake_handler(event, None)
    assert resp["statusCode"] == 200
    saved = _saved_item(mock_db)
    assert saved["selected_dates"] == sorted(dates)
    assert saved["start_date"] == "2026-09-01"
    assert saved["end_date"] == "2026-09-10"


def test_non_consecutive_selected_dates_stored_correctly(mock_db, mock_sfn):
    """Non-consecutive dates (e.g. Mon/Wed/Fri) are all preserved."""
    dates = ["2026-09-07", "2026-09-09", "2026-09-11"]  # Mon/Wed/Fri
    event = _intake_event({
        "selected_dates": dates,
        "start_date": "2026-07-01",
    })
    resp = intake_handler(event, None)
    assert resp["statusCode"] == 200
    saved = _saved_item(mock_db)
    assert saved["selected_dates"] == dates  # already sorted
    assert saved["start_date"] == "2026-09-07"
    assert saved["end_date"] == "2026-09-11"


def test_selected_dates_deduplication(mock_db, mock_sfn):
    """Duplicate dates are deduplicated before storage."""
    dates = ["2026-08-01", "2026-08-01", "2026-08-03", "2026-08-03"]
    event = _intake_event({
        "selected_dates": dates,
        "start_date": "2026-07-01",
    })
    resp = intake_handler(event, None)
    assert resp["statusCode"] == 200
    saved = _saved_item(mock_db)
    assert saved["selected_dates"] == ["2026-08-01", "2026-08-03"]
    assert saved["start_date"] == "2026-08-01"
    assert saved["end_date"] == "2026-08-03"


# ---------------------------------------------------------------------------
# Invalid / malformed selected_dates handling
# ---------------------------------------------------------------------------

def test_selected_dates_with_invalid_strings_filtered(mock_db, mock_sfn):
    """Non-date strings are filtered out; valid dates are processed."""
    event = _intake_event({
        "selected_dates": ["2026-08-01", "not-a-date", "2026-08-03", "garbage"],
        "start_date": "2026-07-01",
    })
    resp = intake_handler(event, None)
    assert resp["statusCode"] == 200
    saved = _saved_item(mock_db)
    # After filtering, 2 valid dates remain → override triggered
    assert saved["selected_dates"] == ["2026-08-01", "2026-08-03"]
    assert saved["start_date"] == "2026-08-01"
    assert saved["end_date"] == "2026-08-03"


def test_selected_dates_with_none_values_filtered(mock_db, mock_sfn):
    """None values inside the list are filtered out."""
    event = _intake_event({
        "selected_dates": [None, "2026-08-01", None, "2026-08-05"],
        "start_date": "2026-07-01",
    })
    resp = intake_handler(event, None)
    assert resp["statusCode"] == 200
    saved = _saved_item(mock_db)
    assert saved["selected_dates"] == ["2026-08-01", "2026-08-05"]
    assert saved["start_date"] == "2026-08-01"


def test_selected_dates_with_integer_values_filtered(mock_db, mock_sfn):
    """Integer values inside the list are filtered out (must be strings)."""
    event = _intake_event({
        "selected_dates": [20260801, "2026-08-01", "2026-08-03"],
        "start_date": "2026-07-01",
    })
    resp = intake_handler(event, None)
    assert resp["statusCode"] == 200
    saved = _saved_item(mock_db)
    assert saved["selected_dates"] == ["2026-08-01", "2026-08-03"]


def test_selected_dates_all_invalid_falls_back_to_explicit_start_date(mock_db, mock_sfn):
    """If all entries are invalid, valid_dates is empty → override NOT triggered.

    The handler only replaces start_date/end_date when at least one valid date
    is found. When no valid dates exist, start_date stays as the explicit field.

    Note: the raw list is still stored in selected_dates on the item because the
    handler does not blank it out in this case — only the start_date/end_date
    override is skipped. This documents current handler behavior.
    """
    event = _intake_event({
        "selected_dates": ["not-a-date", "also-bad", "2026-13-99"],
        "start_date": "2026-07-01",
    })
    resp = intake_handler(event, None)
    assert resp["statusCode"] == 200
    saved = _saved_item(mock_db)
    # start_date is NOT overridden because no valid dates were found
    assert saved["start_date"] == "2026-07-01"
    # The raw list is stored as-is (handler does not blank it when all invalid)
    assert saved["selected_dates"] == ["not-a-date", "also-bad", "2026-13-99"]


def test_selected_dates_not_a_list_falls_back(mock_db, mock_sfn):
    """If selected_dates is a string (not a list), no processing occurs."""
    event = _intake_event({
        "selected_dates": "2026-08-01",
        "start_date": "2026-07-01",
    })
    resp = intake_handler(event, None)
    assert resp["statusCode"] == 200
    saved = _saved_item(mock_db)
    assert saved["start_date"] == "2026-07-01"
    assert saved["selected_dates"] is None
