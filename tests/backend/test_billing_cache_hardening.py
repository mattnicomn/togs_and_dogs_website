"""
Focused test suite for billing cache expiration handling against TypeError exceptions in src/backend/common/billing.py
"""

import pytest
from common.billing import _is_cache_expired


class DummyEntitlement:
    def __init__(self, cached_at):
        self.cached_at = cached_at


def test_is_cache_expired_handles_type_error_safely():
    # 1. cached_at is None (calling .replace('Z', ...) raises AttributeError, fromisoformat raises TypeError)
    e_none = DummyEntitlement(None)
    assert _is_cache_expired(e_none) is True

    # 2. cached_at is non-string object (e.g. integer or list)
    e_int = DummyEntitlement(12345)
    assert _is_cache_expired(e_int) is True

    # 3. cached_at is invalid ISO string
    e_invalid = DummyEntitlement("not-a-date")
    assert _is_cache_expired(e_invalid) is True

    # 4. cached_at is valid ISO string (recent)
    from datetime import datetime, timezone
    now_iso = datetime.now(timezone.utc).isoformat()
    e_valid = DummyEntitlement(now_iso)
    assert _is_cache_expired(e_valid) is False
