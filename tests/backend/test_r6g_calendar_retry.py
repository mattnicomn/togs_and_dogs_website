"""
Release 6G Phase 4: Tests for calendar sync retry mechanism.
"""
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'backend'))

from unittest.mock import patch, MagicMock, call
import urllib.error
from common.google_calendar import sync_calendar_event, _is_retryable_error


VALID_ITEM = {
    "request_id": "req-retry-001",
    "client_name": "Retry Test",
    "pet_names": "Buddy",
    "service_type": "WALK_30MIN",
    "start_date": "2026-08-01",
    "scheduled_time": "10:00",
}


def _make_http_error(code, body=""):
    err = urllib.error.HTTPError(
        url="https://www.googleapis.com/calendar/v3/calendars/primary/events",
        code=code, msg="Error", hdrs={}, fp=None
    )
    err.read = lambda: body.encode() if isinstance(body, str) else body
    return err


# --- _is_retryable_error tests ---

def test_retryable_500():
    assert _is_retryable_error(_make_http_error(500)) == True
    print("PASS: test_retryable_500")

def test_retryable_429():
    assert _is_retryable_error(_make_http_error(429)) == True
    print("PASS: test_retryable_429")

def test_retryable_503():
    assert _is_retryable_error(_make_http_error(503)) == True
    print("PASS: test_retryable_503")

def test_not_retryable_400():
    assert _is_retryable_error(_make_http_error(400)) == False
    print("PASS: test_not_retryable_400")

def test_not_retryable_401():
    assert _is_retryable_error(_make_http_error(401)) == False
    print("PASS: test_not_retryable_401")

def test_retryable_timeout():
    assert _is_retryable_error(TimeoutError("timed out")) == True
    print("PASS: test_retryable_timeout")

def test_retryable_os_error():
    assert _is_retryable_error(OSError("Connection reset")) == True
    print("PASS: test_retryable_os_error")


# --- Retry behavior tests ---

def test_transient_failure_succeeds_on_retry():
    """First attempt fails with 503, second attempt succeeds."""
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps({"id": "event_123"}).encode()
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)

    call_count = [0]
    def side_effect(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            raise _make_http_error(503, "Service Unavailable")
        return mock_response

    with patch('common.google_calendar._get_valid_token', return_value="fake_token"), \
         patch('common.google_calendar.time.sleep') as mock_sleep, \
         patch('urllib.request.urlopen', side_effect=side_effect):
        result = sync_calendar_event(VALID_ITEM)

    assert result["status"] == "calendar_created"
    assert result["event_id"] == "event_123"
    assert call_count[0] == 2
    mock_sleep.assert_called_once()  # One retry backoff
    print("PASS: test_transient_failure_succeeds_on_retry")


def test_transient_failure_exhausts_retries():
    """All attempts fail with 500 — returns calendar_failed."""
    def side_effect(*args, **kwargs):
        raise _make_http_error(500, "Internal Server Error")

    with patch('common.google_calendar._get_valid_token', return_value="fake_token"), \
         patch('common.google_calendar.time.sleep'), \
         patch('urllib.request.urlopen', side_effect=side_effect):
        result = sync_calendar_event(VALID_ITEM)

    assert result["status"] == "calendar_failed"
    assert "500" in result["message"]
    print("PASS: test_transient_failure_exhausts_retries")


def test_permanent_error_does_not_retry():
    """400 error should not retry."""
    call_count = [0]
    def side_effect(*args, **kwargs):
        call_count[0] += 1
        raise _make_http_error(400, "Bad Request")

    with patch('common.google_calendar._get_valid_token', return_value="fake_token"), \
         patch('common.google_calendar.time.sleep') as mock_sleep, \
         patch('urllib.request.urlopen', side_effect=side_effect):
        result = sync_calendar_event(VALID_ITEM)

    assert result["status"] == "calendar_failed"
    assert call_count[0] == 1  # Only one attempt, no retry
    mock_sleep.assert_not_called()
    print("PASS: test_permanent_error_does_not_retry")


def test_network_timeout_retries():
    """TimeoutError should trigger retry."""
    call_count = [0]
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps({"id": "event_456"}).encode()
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)

    def side_effect(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            raise TimeoutError("Connection timed out")
        return mock_response

    with patch('common.google_calendar._get_valid_token', return_value="fake_token"), \
         patch('common.google_calendar.time.sleep'), \
         patch('urllib.request.urlopen', side_effect=side_effect):
        result = sync_calendar_event(VALID_ITEM)

    assert result["status"] == "calendar_created"
    assert call_count[0] == 2
    print("PASS: test_network_timeout_retries")


def test_validation_skip_does_not_retry():
    """Missing fields causing skip should not trigger retry."""
    item = {"request_id": "req-skip"}  # Missing required fields

    with patch('common.google_calendar._get_valid_token', return_value="fake_token"), \
         patch('urllib.request.urlopen') as mock_url:
        result = sync_calendar_event(item)

    assert "skipped" in result["status"]
    mock_url.assert_not_called()
    print("PASS: test_validation_skip_does_not_retry")


def test_revoked_token_does_not_retry():
    """Revoked token should fail immediately without retry."""
    revoked_tokens = {"token_status": "revoked", "refresh_token": "dead"}

    with patch('common.google_calendar._get_stored_tokens', return_value=revoked_tokens), \
         patch('urllib.request.urlopen') as mock_url:
        result = sync_calendar_event(VALID_ITEM)

    assert result["status"] == "calendar_failed"
    assert "disconnected" in result["message"].lower() or "expired" in result["message"].lower()
    mock_url.assert_not_called()
    print("PASS: test_revoked_token_does_not_retry")


def test_business_flow_nonblocking():
    """Calendar retry failure must not raise exceptions to caller."""
    def side_effect(*args, **kwargs):
        raise _make_http_error(502, "Bad Gateway")

    with patch('common.google_calendar._get_valid_token', return_value="fake_token"), \
         patch('common.google_calendar.time.sleep'), \
         patch('urllib.request.urlopen', side_effect=side_effect):
        # Must not raise — returns a result dict
        result = sync_calendar_event(VALID_ITEM)

    assert result is not None
    assert isinstance(result, dict)
    assert result["status"] == "calendar_failed"
    print("PASS: test_business_flow_nonblocking")


if __name__ == '__main__':
    test_retryable_500()
    test_retryable_429()
    test_retryable_503()
    test_not_retryable_400()
    test_not_retryable_401()
    test_retryable_timeout()
    test_retryable_os_error()
    test_transient_failure_succeeds_on_retry()
    test_transient_failure_exhausts_retries()
    test_permanent_error_does_not_retry()
    test_network_timeout_retries()
    test_validation_skip_does_not_retry()
    test_revoked_token_does_not_retry()
    test_business_flow_nonblocking()
    print("\nAll Release 6G calendar retry tests PASSED.")
