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
    _aws_guard.install()
    try:
        yield
    finally:
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
