"""Gate C3b — centralized guard that blocks real AWS network calls in tests.

Rationale
---------
The backend suite constructs real boto3 clients at import (``common/db.py``,
``common/tenant_read_adapter.py``, ``common/google_calendar.py``, SES/Secrets
in notifications). Tests that exercise an unmocked path would otherwise send a
real signed request to ``*.amazonaws.com``. With dummy CI credentials AWS
rejects these at authentication (``UnrecognizedClientException``) — no data
access and no mutation is possible — but the request still egresses. This guard
stops the call *before* egress and fails loudly, so a missing mock is a clear
test failure rather than silent network traffic.

Mechanism (validated by PoC under boto3/botocore 1.37.1 & 1.42.56, moto 5.0/5.1)
--------------------------------------------------------------------------------
Wrap ``botocore.client.BaseClient._make_api_call`` — the single chokepoint every
client call passes through, which covers clients built BEFORE the guard installs.
Block the call when the resolved endpoint host contains ``amazonaws.com`` AND
moto is not actively mocking. Moto does NOT rewrite the endpoint away from
``amazonaws.com``; it intercepts lower, so endpoint-host matching alone would
break moto. We therefore gate on a positive "moto active" signal.

Fail-closed (requirement 8)
---------------------------
If the moto-active signal cannot be resolved (import error / moto internals
moved), we treat moto as NOT active and BLOCK the real call. That errs toward
blocking egress, never toward silently allowing a real AWS call.

Limitations (requirement 9)
---------------------------
This is NOT a network firewall. It keys on the botocore endpoint host containing
``amazonaws.com`` (covers standard commercial endpoints used by this repo). It
does not by itself block non-AWS egress, custom endpoints, or a determined call
that bypasses ``_make_api_call``. For defense-in-depth, pair with a CI network
egress restriction if ever required. The regression test uses a socket tripwire
to prove no egress for the covered services.
"""
import os
import botocore.client

_REAL_MAKE_API_CALL = botocore.client.BaseClient._make_api_call
_STATE = {"installed": False, "blocks": 0}

# --- DIAGNOSTIC (Gate C3b, temporary; removed before merge) ------------------
# Emits fixed-marker, non-sensitive state lines to stderr so a CI run reveals
# the guard's activation/installation lifecycle. NEVER logs credentials, env
# values, raw identifiers, request params, headers, payloads, or full URLs.
import sys as _sys


def assert_installed():
    """Return True iff the live _make_api_call is our guarded wrapper."""
    return botocore.client.BaseClient._make_api_call is _guarded_make_api_call


def diag(marker):
    """Print a safe one-line GUARD_DIAG state marker (booleans/counters only)."""
    try:
        _sys.stderr.write(
            "GUARD_DIAG %s active=%s installed=%s state_flag=%s blocks=%d\n"
            % (marker, is_active(), assert_installed(), _STATE["installed"], _STATE["blocks"])
        )
        _sys.stderr.flush()
    except Exception:
        pass
# -----------------------------------------------------------------------------

#: Opt-in activation. The guard only installs when this env var is truthy, so
#: normal local development/test runs are unchanged unless CI (or a developer)
#: explicitly enables it. CI sets this in .github/workflows/ci.yml.
ACTIVATION_ENV = "CI_AWS_CALL_GUARD"


class RealAWSCallBlocked(RuntimeError):
    """Raised when a test attempts a real AWS API call (no mock / no moto)."""


def _moto_active():
    """Return True iff moto is actively mocking.

    Fail-closed: any failure to resolve the signal returns False (-> the caller
    BLOCKS the real call), never True.
    """
    try:
        from moto.core.models import botocore_stubber
        return bool(getattr(botocore_stubber, "enabled", False))
    except Exception:
        return False


def _endpoint_host(client):
    try:
        return client.meta.endpoint_url or ""
    except Exception:
        # If we cannot introspect the endpoint, fail closed by returning a
        # sentinel that triggers a block (treated as a real AWS host).
        return "amazonaws.com"


def _guarded_make_api_call(self, operation_name, api_params):
    host = _endpoint_host(self)
    if "amazonaws.com" in host and not _moto_active():
        _STATE["blocks"] += 1  # DIAGNOSTIC counter only; behavior unchanged
        svc_model = getattr(getattr(self, "meta", None), "service_model", None)
        svc_name = getattr(svc_model, "service_name", "unknown") if svc_model else "unknown"
        raise RealAWSCallBlocked(
            f"Real AWS call blocked in tests: {svc_name}.{operation_name} -> {host}. "
            f"Add a mock (unittest.mock) or wrap the test in moto's mock_aws."
        )
    return _REAL_MAKE_API_CALL(self, operation_name, api_params)


def is_active():
    return os.environ.get(ACTIVATION_ENV, "").strip().lower() in ("1", "true", "yes", "on")


def install():
    """Install the guard (idempotent). No-op unless ACTIVATION_ENV is truthy."""
    if not is_active():
        return False
    if not _STATE["installed"]:
        botocore.client.BaseClient._make_api_call = _guarded_make_api_call
        _STATE["installed"] = True
    diag("install")  # DIAGNOSTIC (temporary)
    return True


def uninstall():
    if _STATE["installed"]:
        botocore.client.BaseClient._make_api_call = _REAL_MAKE_API_CALL
        _STATE["installed"] = False
