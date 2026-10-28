import sys
import os

# Set required environment variables before any backend code is imported
os.environ.setdefault('DATA_TABLE_NAME', 'test-table')

# Add src/backend to sys.path so handlers and common can be imported
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src/backend'))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)


import pytest
from unittest.mock import Mock


@pytest.fixture
def primary_google_binding(monkeypatch):
    """Opt-in owned primary metadata fixture; real resolver, no caller fallback."""
    from common import db, google_calendar
    name = 'togs-and-dogs-prod/google/user-tokens'
    monkeypatch.setenv('GOOGLE_USER_TOKENS_NAME', name)
    row = {'PK': 'TENANT#tog_and_dogs', 'SK': 'METADATA',
           'company_id': 'tog_and_dogs', 'is_active': True,
           'subscription_status': 'active'}
    get = Mock(side_effect=lambda **kw: {'Item': row} if kw['Key'] == {
        'PK': row['PK'], 'SK': row['SK']} else {})
    monkeypatch.setattr(db.table, 'get_item', get)
    describe = Mock(return_value={
        'ARN': 'arn:aws:secretsmanager:us-east-1:123456789012:secret:' + name + '-Ab1234',
        'Name': name, 'Tags': [{'Key': 'CompanyId', 'Value': 'tog_and_dogs'}]})
    monkeypatch.setattr(google_calendar.secrets, 'describe_secret', describe)
    return get, describe


# --- Gate C3b: credential-free CI real-AWS-call guard -----------------------
# Session-scoped, autouse. Installs a botocore guard that blocks any real
# *.amazonaws.com call that is not served by moto, failing loudly BEFORE
# network egress. Opt-in: only active when CI_AWS_CALL_GUARD is truthy (CI
# sets it), so normal local test runs are unchanged. See tests/backend/_aws_guard.py.
import pytest as _pytest  # noqa: E402  (pytest already imported above)

# Import the guard module from this conftest's own directory, independent of
# whether `tests`/`tests.backend` is an importable package. The directory of
# this file is reliably present on sys.path during pytest collection.
_here = os.path.dirname(os.path.abspath(__file__))
if _here not in sys.path:
    sys.path.insert(0, _here)
import _aws_guard  # noqa: E402


@_pytest.fixture(scope="session", autouse=True)
def _ci_block_real_aws_calls():
    """Block real AWS calls for the whole backend session when CI-activated.

    No-op unless CI_AWS_CALL_GUARD is truthy, so local development/test behavior
    is unchanged. When active, an unmocked real AWS call raises
    RealAWSCallBlocked (loud failure), and moto-served calls pass through.
    """
    installed = _aws_guard.install()
    try:
        yield
    finally:
        if installed:
            _aws_guard.uninstall()


# --- Gate C3b DIAGNOSTIC (temporary; removed before merge) -------------------
# Lifecycle probes + a read-only transport-boundary observer to explain why a
# guarded CI run can still record AWS auth exceptions. Emits only fixed-marker,
# non-sensitive state (booleans, counters, node ids, service names, bare host).
# NEVER logs credentials, env values, raw identifiers, request params/headers/
# payloads, or full URLs. Changes NO protection logic and NO test assertions.
import sys as _sys_diag  # noqa: E402

# Files empirically observed to escape to AWS in CI (gated probing only).
_DIAG_WATCH = (
    "test_intake_validation",
    "test_r4a_intake",
    "test_r7s_terms_acceptance",
    "test_r7s_selected_dates",
    "test_rbac_and_purge_safety",
    "test_r11e_tenant_enforcement",
    "test_r19k_tenant_isolation",
    "test_r20e_disabled_tenant_enforcement",
    "test_r12g_stripe_checkout",
    "test_r12t_payment_email",
    "test_r6e_identity",
    "test_cognito_email_sender_infrastructure",
    "test_platform_preview_iam",
)


def pytest_configure(config):
    # Earliest pytest init point — BEFORE the session fixture installs the guard.
    # "installed=False" here is EXPECTED (not a failure); it reports config state.
    try:
        _aws_guard.diag("configure")
    except Exception:
        pass


def pytest_runtest_setup(item):
    if any(w in item.nodeid for w in _DIAG_WATCH):
        try:
            _sys_diag.stderr.write("GUARD_DIAG pre_test installed=%s node=%s\n"
                                   % (_aws_guard.assert_installed(), item.nodeid))
            _sys_diag.stderr.flush()
        except Exception:
            pass


def pytest_runtest_teardown(item, nextitem):
    if any(w in item.nodeid for w in _DIAG_WATCH):
        try:
            _sys_diag.stderr.write("GUARD_DIAG post_test installed=%s node=%s\n"
                                   % (_aws_guard.assert_installed(), item.nodeid))
            _sys_diag.stderr.flush()
        except Exception:
            pass


@_pytest.fixture(scope="session", autouse=True)
def _ci_transport_boundary_observer():
    """Read-only observer at the HTTP transport boundary.

    Wraps URLLib3Session.send to RECORD (not alter) when an amazonaws.com-bound
    request reaches transport — i.e. the guard was bypassed for that call. Always
    delegates to the real send; never blocks, rewrites, or inspects payload. Logs
    only the bare hostname. This is diagnostic evidence of real egress reach,
    distinct from pytest-captured exception text.
    """
    try:
        import botocore.httpsession as _hs
        from urllib.parse import urlparse as _urlparse
    except Exception:
        yield
        return

    _real_send = _hs.URLLib3Session.send

    def _observing_send(self, request):
        try:
            host = _urlparse(getattr(request, "url", "") or "").hostname or ""
            if "amazonaws.com" in host:
                _sys_diag.stderr.write("GUARD_DIAG transport_reached host=%s\n" % host)
                _sys_diag.stderr.flush()
        except Exception:
            pass
        return _real_send(self, request)

    _hs.URLLib3Session.send = _observing_send
    try:
        yield
    finally:
        _hs.URLLib3Session.send = _real_send
# -----------------------------------------------------------------------------
