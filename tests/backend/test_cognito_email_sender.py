"""Unit coverage for the isolated Cognito Custom Email Sender."""

from __future__ import annotations

import base64
import importlib.util
import json
import logging
from pathlib import Path
import sys
import types

import pytest


MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "cognito_email_sender"
    / "cognito_email_sender_handler.py"
)
SPEC = importlib.util.spec_from_file_location("cognito_email_sender_handler", MODULE_PATH)
sender = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = sender
SPEC.loader.exec_module(sender)


def _event(**overrides):
    event = {
        "version": "1",
        "triggerSource": "CustomEmailSender_ForgotPassword",
        "userPoolId": "us-east-1_example",
        "request": {
            "code": base64.b64encode(b"ciphertext").decode("ascii"),
            "userAttributes": {"email": "customer@example.com", "sub": "private-sub"},
        },
    }
    event.update(overrides)
    return event


@pytest.fixture(autouse=True)
def _sender_environment(monkeypatch):
    monkeypatch.setenv(
        "COGNITO_EMAIL_SENDER_KMS_KEY_ARN",
        "arn:aws:kms:us-east-1:123456789012:key/example",
    )
    monkeypatch.setenv(
        "POSTMARK_SERVER_TOKEN_SECRET_ARN",
        "arn:aws:secretsmanager:us-east-1:123456789012:secret:postmark",
    )
    monkeypatch.setenv("POSTMARK_MESSAGE_STREAM", "outbound")


def test_forgot_password_happy_path_uses_expected_recipient_and_code(monkeypatch):
    calls = {}
    monkeypatch.setattr(sender, "_decrypt_code", lambda encrypted, pool: "731904")
    monkeypatch.setattr(sender, "_get_postmark_token", lambda: "server-token")

    def capture_send(token, recipient, code):
        calls.update(token=token, recipient=recipient, code=code)

    monkeypatch.setattr(sender, "_send_postmark", capture_send)

    assert sender.handler(_event(), None) is None
    assert calls == {
        "token": "server-token",
        "recipient": "customer@example.com",
        "code": "731904",
    }


def test_postmark_payload_has_exact_branding_content_and_stream(monkeypatch):
    captured = {}

    class Response:
        status = 200

        def getcode(self):
            return self.status

        def read(self):
            return b'{"ErrorCode":0,"Message":"OK"}'

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr(sender.urllib.request, "urlopen", fake_urlopen)
    sender._send_postmark("do-not-log-this-token", "customer@example.com", "731904")

    request = captured["request"]
    payload = json.loads(request.data.decode("utf-8"))
    assert request.full_url == "https://api.postmarkapp.com/email"
    assert captured["timeout"] == 10
    assert payload["From"] == "Togs & Dogs <support@usmissionhero.com>"
    assert payload["To"] == "customer@example.com"
    assert payload["ReplyTo"] == "support@usmissionhero.com"
    assert payload["Subject"] == "Togs & Dogs — Your password reset code"
    assert payload["MessageStream"] == "outbound"
    assert "731904" in payload["HtmlBody"]
    assert "731904" in payload["TextBody"]
    assert "reset link" not in payload["HtmlBody"].lower()
    assert "customer@example.com" not in payload["HtmlBody"]
    assert request.get_header("X-postmark-server-token") == "do-not-log-this-token"


def test_unsupported_trigger_fails_closed_before_decrypt_or_send(monkeypatch, caplog):
    monkeypatch.setattr(
        sender,
        "_decrypt_code",
        lambda *args: pytest.fail("decrypt must not be called"),
    )
    monkeypatch.setattr(
        sender,
        "_send_postmark",
        lambda *args: pytest.fail("Postmark must not be called"),
    )

    with caplog.at_level(logging.INFO), pytest.raises(
        sender.CognitoEmailSenderError, match="Unsupported"
    ):
        sender.handler(_event(triggerSource="CustomEmailSender_AdminCreateUser"), None)

    assert "CustomEmailSender_AdminCreateUser" in caplog.text
    assert "customer@example.com" not in caplog.text


def test_postmark_failure_is_not_reported_as_success(monkeypatch):
    monkeypatch.setattr(sender, "_decrypt_code", lambda *args: "731904")
    monkeypatch.setattr(sender, "_get_postmark_token", lambda: "server-token")
    monkeypatch.setattr(
        sender,
        "_send_postmark",
        lambda *args: (_ for _ in ()).throw(sender.CognitoEmailSenderError("failed")),
    )

    with pytest.raises(sender.CognitoEmailSenderError):
        sender.handler(_event(), None)


def test_secret_retrieval_failure_fails_safely(monkeypatch):
    class SecretsManager:
        def get_secret_value(self, **kwargs):
            raise RuntimeError("provider detail")

    monkeypatch.setattr(sender.boto3, "client", lambda service: SecretsManager())

    with pytest.raises(sender.CognitoEmailSenderError, match="credential retrieval failed"):
        sender._get_postmark_token()


def test_decrypt_failure_and_logs_do_not_expose_code_or_token(monkeypatch, caplog):
    encrypted_marker = "encrypted-private-marker"
    token_marker = "postmark-private-marker"
    event = _event()
    event["request"]["code"] = encrypted_marker

    def fail_decrypt(*args):
        raise sender.CognitoEmailSenderError(
            f"decryption failed {encrypted_marker} {token_marker}"
        )

    monkeypatch.setattr(sender, "_decrypt_code", fail_decrypt)

    with caplog.at_level(logging.INFO), pytest.raises(sender.CognitoEmailSenderError):
        sender.handler(event, None)

    log_text = caplog.text
    assert encrypted_marker not in log_text
    assert token_marker not in log_text
    assert "private-sub" not in log_text


@pytest.mark.parametrize(
    "event",
    [
        None,
        {},
        {"triggerSource": "CustomEmailSender_ForgotPassword"},
        _event(version="2"),
        _event(request=None),
    ],
)
def test_malformed_events_fail_safely(event):
    with pytest.raises(sender.CognitoEmailSenderError):
        sender.handler(event, None)


@pytest.mark.parametrize(
    "recipient",
    [None, "", "two@example.com,other@example.com", "Name <person@example.com>", "bad\n@example.com"],
)
def test_missing_or_unsafe_recipient_fails_before_decrypt(monkeypatch, recipient):
    event = _event()
    event["request"]["userAttributes"]["email"] = recipient
    monkeypatch.setattr(
        sender,
        "_decrypt_code",
        lambda *args: pytest.fail("decrypt must not be called"),
    )

    with pytest.raises(sender.CognitoEmailSenderError, match="recipient"):
        sender.handler(event, None)


def test_decrypt_uses_encryption_sdk_and_verifies_user_pool_context(monkeypatch):
    observed = {}

    class CommitmentPolicy:
        REQUIRE_ENCRYPT_ALLOW_DECRYPT = object()

    class Header:
        encryption_context = {"userpool-id": "us-east-1_example"}

    class Client:
        def __init__(self, commitment_policy):
            observed["commitment_policy"] = commitment_policy

        def decrypt(self, source, key_provider):
            observed["source"] = source
            observed["key_provider"] = key_provider
            return b"731904", Header()

    fake_sdk = types.ModuleType("aws_encryption_sdk")
    fake_sdk.CommitmentPolicy = CommitmentPolicy
    fake_sdk.EncryptionSDKClient = Client
    fake_sdk.StrictAwsKmsMasterKeyProvider = lambda key_ids: {"key_ids": key_ids}
    monkeypatch.setitem(sys.modules, "aws_encryption_sdk", fake_sdk)

    result = sender._decrypt_code(
        base64.b64encode(b"ciphertext").decode("ascii"),
        "us-east-1_example",
    )

    assert result == "731904"
    assert observed["source"] == b"ciphertext"
    assert observed["commitment_policy"] is CommitmentPolicy.REQUIRE_ENCRYPT_ALLOW_DECRYPT
    assert observed["key_provider"] == {
        "key_ids": ["arn:aws:kms:us-east-1:123456789012:key/example"]
    }


def test_decrypt_rejects_mismatched_user_pool_context(monkeypatch):
    class CommitmentPolicy:
        REQUIRE_ENCRYPT_ALLOW_DECRYPT = object()

    class Header:
        encryption_context = {"userpool-id": "us-east-1_other"}

    class Client:
        def __init__(self, commitment_policy):
            pass

        def decrypt(self, source, key_provider):
            return b"731904", Header()

    fake_sdk = types.ModuleType("aws_encryption_sdk")
    fake_sdk.CommitmentPolicy = CommitmentPolicy
    fake_sdk.EncryptionSDKClient = Client
    fake_sdk.StrictAwsKmsMasterKeyProvider = lambda key_ids: object()
    monkeypatch.setitem(sys.modules, "aws_encryption_sdk", fake_sdk)

    with pytest.raises(sender.CognitoEmailSenderError, match="context"):
        sender._decrypt_code(
            base64.b64encode(b"ciphertext").decode("ascii"),
            "us-east-1_example",
        )


def test_postmark_error_response_fails_closed(monkeypatch):
    class Response:
        status = 200

        def getcode(self):
            return self.status

        def read(self):
            return b'{"ErrorCode":300,"Message":"Inactive recipient"}'

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(sender.urllib.request, "urlopen", lambda *args, **kwargs: Response())

    with pytest.raises(sender.CognitoEmailSenderError, match="rejected"):
        sender._send_postmark("server-token", "customer@example.com", "731904")
