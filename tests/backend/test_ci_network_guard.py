"""Gate C3b regression tests for the real-AWS-call guard.

These tests install the guard directly (independent of the CI_AWS_CALL_GUARD
env gate) so they verify the guard mechanism itself on every run. A socket
tripwire proves no real network egress occurs for the blocked services.

No skips / xfail / continue-on-error / weakened assertions.
"""
import socket
import boto3
import pytest

import _aws_guard


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """Tripwire: fail loudly if any test attempts a real socket connection."""
    def _blocked_connect(self, address):
        raise AssertionError(f"NETWORK EGRESS ATTEMPTED to {address!r}")
    monkeypatch.setattr(socket.socket, "connect", _blocked_connect)
    yield


# Client built BEFORE the guard installs (covers import-time clients).
_PRE_GUARD_CLIENT = boto3.client(
    "dynamodb", region_name="us-east-1",
    aws_access_key_id="testing", aws_secret_access_key="testing",
)


@pytest.fixture(autouse=True)
def _force_guard(monkeypatch):
    # Activate regardless of the CI env gate, so this regression always runs.
    monkeypatch.setenv(_aws_guard.ACTIVATION_ENV, "1")
    # Ownership: the session-scoped conftest fixture may already own an
    # installed guard. This function-scoped fixture must only undo its OWN
    # installation. If the guard was already installed (by the session fixture
    # or an outer scope), leave it installed on teardown so later tests in the
    # session stay guarded. Tearing it down unconditionally would disable the
    # session guard for every subsequent test.
    was_installed = _aws_guard._STATE["installed"]
    _aws_guard.install()
    try:
        yield
    finally:
        # Only uninstall if THIS fixture transitioned the guard from
        # not-installed to installed. If it was already installed, preserve it.
        if not was_installed:
            _aws_guard.uninstall()


def test_pre_existing_client_is_blocked():
    with pytest.raises(_aws_guard.RealAWSCallBlocked):
        _PRE_GUARD_CLIENT.describe_table(TableName="nope")


def test_dynamodb_real_call_blocked():
    c = boto3.client("dynamodb", region_name="us-east-1",
                     aws_access_key_id="x", aws_secret_access_key="y")
    with pytest.raises(_aws_guard.RealAWSCallBlocked):
        c.get_item(TableName="t", Key={"PK": {"S": "a"}})


def test_secretsmanager_real_call_blocked():
    c = boto3.client("secretsmanager", region_name="us-east-1",
                     aws_access_key_id="x", aws_secret_access_key="y")
    with pytest.raises(_aws_guard.RealAWSCallBlocked):
        c.describe_secret(SecretId="nope")


def test_ses_real_call_blocked():
    c = boto3.client("ses", region_name="us-east-1",
                     aws_access_key_id="x", aws_secret_access_key="y")
    with pytest.raises(_aws_guard.RealAWSCallBlocked):
        c.get_send_quota()


def test_moto_crud_allowed():
    from moto import mock_aws
    with mock_aws():
        c = boto3.client("dynamodb", region_name="us-east-1")
        c.create_table(
            TableName="t",
            KeySchema=[{"AttributeName": "PK", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "PK", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        c.put_item(TableName="t", Item={"PK": {"S": "x"}})
        assert c.get_item(TableName="t", Key={"PK": {"S": "x"}})["Item"]["PK"]["S"] == "x"


def test_moto_transact_write_items_allowed():
    from moto import mock_aws
    with mock_aws():
        c = boto3.client("dynamodb", region_name="us-east-1")
        c.create_table(
            TableName="t",
            KeySchema=[{"AttributeName": "PK", "KeyType": "HASH"},
                       {"AttributeName": "SK", "KeyType": "RANGE"}],
            AttributeDefinitions=[{"AttributeName": "PK", "AttributeType": "S"},
                                  {"AttributeName": "SK", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        c.transact_write_items(TransactItems=[
            {"Put": {"TableName": "t", "Item": {"PK": {"S": "r"}, "SK": {"S": "e"}}}},
        ])
        assert c.get_item(TableName="t",
                          Key={"PK": {"S": "r"}, "SK": {"S": "e"}})["Item"]["SK"]["S"] == "e"


def test_real_call_reblocked_after_moto_context():
    from moto import mock_aws
    with mock_aws():
        boto3.client("dynamodb", region_name="us-east-1").list_tables()
    c = boto3.client("dynamodb", region_name="us-east-1",
                     aws_access_key_id="x", aws_secret_access_key="y")
    with pytest.raises(_aws_guard.RealAWSCallBlocked):
        c.get_item(TableName="t", Key={"PK": {"S": "a"}})


def test_guard_fails_closed_when_moto_signal_unavailable(monkeypatch):
    # Simulate moto-detection failure -> _moto_active() returns False -> block.
    monkeypatch.setattr(_aws_guard, "_moto_active", lambda: False)
    c = boto3.client("dynamodb", region_name="us-east-1",
                     aws_access_key_id="x", aws_secret_access_key="y")
    with pytest.raises(_aws_guard.RealAWSCallBlocked):
        c.get_item(TableName="t", Key={"PK": {"S": "a"}})


# --- Guard-ownership regression (Gate C3b) -----------------------------------
# These tests pin the fixture-ownership contract that previously regressed:
# the function-scoped `_force_guard` fixture must NOT tear down a guard that was
# already installed by the session-scoped conftest fixture. If it does, every
# test scheduled AFTER the guard tests runs unguarded and a missing mock
# silently egresses to real AWS instead of failing.


@pytest.fixture
def _guard_state_sandbox():
    """Snapshot the global guard install-state and the live _make_api_call, and
    fully restore both on exit. Lets a regression test drive install/uninstall
    directly without corrupting the session guard that the surrounding
    autouse fixtures depend on."""
    import botocore.client
    saved_installed = _aws_guard._STATE["installed"]
    saved_method = botocore.client.BaseClient._make_api_call
    try:
        yield
    finally:
        botocore.client.BaseClient._make_api_call = saved_method
        _aws_guard._STATE["installed"] = saved_installed


def _run_force_guard_cycle(monkeypatch):
    """Drive the function-scoped _force_guard fixture body through one full
    setup/teardown cycle, returning nothing. Uses an isolated MonkeyPatch whose
    finalizers are flushed here so env changes don't leak."""
    from _pytest.monkeypatch import MonkeyPatch
    mp = MonkeyPatch()
    try:
        gen = _force_guard.__wrapped__(mp)
        next(gen)  # setup
        assert _aws_guard.assert_installed(), "guard not installed during test body"
        with pytest.raises(StopIteration):
            next(gen)  # teardown
    finally:
        mp.undo()


def test_force_guard_preserves_already_installed_session_guard(
    monkeypatch, _guard_state_sandbox
):
    """When the guard is already installed on entry, _force_guard must leave it
    installed after teardown (it only undoes its own installation)."""
    monkeypatch.setenv(_aws_guard.ACTIVATION_ENV, "1")

    # Simulate the session-scoped conftest fixture having installed the guard.
    _aws_guard.install()
    assert _aws_guard.assert_installed(), "precondition: session guard installed"

    _run_force_guard_cycle(monkeypatch)

    assert _aws_guard.assert_installed(), (
        "session guard was torn down by function-scoped fixture; later tests "
        "would run unguarded"
    )


def test_force_guard_undoes_only_its_own_installation(
    monkeypatch, _guard_state_sandbox
):
    """When the guard is NOT installed on entry, _force_guard installs it for
    the test and uninstalls it on teardown (restores the prior state)."""
    monkeypatch.setenv(_aws_guard.ACTIVATION_ENV, "1")

    # Establish a not-installed baseline on entry.
    _aws_guard.uninstall()
    assert not _aws_guard.assert_installed(), "precondition: guard not installed"

    _run_force_guard_cycle(monkeypatch)

    assert not _aws_guard.assert_installed(), (
        "fixture failed to restore the not-installed baseline it inherited"
    )
