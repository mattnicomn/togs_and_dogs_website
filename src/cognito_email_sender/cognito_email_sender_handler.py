"""Cognito Custom Email Sender for branded password-recovery email delivery.

This module is packaged independently from ``src/backend`` so adding or updating
the sender cannot change the shared archive used by the existing Lambda fleet.
"""

from __future__ import annotations

import base64
import html
import json
import logging
import os
import re
import urllib.error
import urllib.request
from typing import Any

import boto3


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)

SUPPORTED_TRIGGER = "CustomEmailSender_ForgotPassword"
KNOWN_TRIGGER_SOURCES = {
    "CustomEmailSender_SignUp",
    "CustomEmailSender_ResendCode",
    SUPPORTED_TRIGGER,
    "CustomEmailSender_UpdateUserAttribute",
    "CustomEmailSender_VerifyUserAttribute",
    "CustomEmailSender_AdminCreateUser",
    "CustomEmailSender_AccountTakeOverNotification",
    "CustomEmailSender_Authentication",
}
EVENT_VERSION = "1"
POSTMARK_ENDPOINT = "https://api.postmarkapp.com/email"
FROM_HEADER = "Togs & Dogs <support@usmissionhero.com>"
REPLY_TO = "support@usmissionhero.com"
SUBJECT = "Togs & Dogs — Your password reset code"
DEFAULT_MESSAGE_STREAM = "outbound"
MAX_CODE_LENGTH = 2048
EMAIL_PATTERN = re.compile(r"^[^@\s,<>\r\n]+@[^@\s,<>\r\n]+\.[^@\s,<>\r\n]+$")


class CognitoEmailSenderError(RuntimeError):
    """Safe, non-secret-bearing custom sender failure."""


def _safe_trigger_source(value: Any) -> str:
    return value if value in KNOWN_TRIGGER_SOURCES else "<unknown>"


def _required_environment(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise CognitoEmailSenderError(f"Required configuration is missing: {name}")
    return value


def _validate_event(event: Any) -> tuple[str, str, str]:
    if not isinstance(event, dict):
        raise CognitoEmailSenderError("Malformed Cognito custom sender event")

    trigger_source = event.get("triggerSource")
    if trigger_source != SUPPORTED_TRIGGER:
        LOGGER.warning(
            "Unsupported Cognito custom email trigger: %s",
            _safe_trigger_source(trigger_source),
        )
        raise CognitoEmailSenderError("Unsupported Cognito custom email trigger")

    if event.get("version") != EVENT_VERSION:
        raise CognitoEmailSenderError("Unsupported Cognito custom sender event version")

    user_pool_id = event.get("userPoolId")
    request = event.get("request")
    if not isinstance(user_pool_id, str) or not user_pool_id.strip():
        raise CognitoEmailSenderError("Cognito user pool identifier is missing")
    if not isinstance(request, dict):
        raise CognitoEmailSenderError("Cognito custom sender request is missing")

    encrypted_code = request.get("code")
    attributes = request.get("userAttributes")
    if not isinstance(encrypted_code, str) or not encrypted_code.strip():
        raise CognitoEmailSenderError("Encrypted verification code is missing")
    if not isinstance(attributes, dict):
        raise CognitoEmailSenderError("Cognito user attributes are missing")

    recipient = attributes.get("email")
    if not isinstance(recipient, str) or not EMAIL_PATTERN.fullmatch(recipient):
        raise CognitoEmailSenderError("A valid single recipient email is required")

    return user_pool_id, encrypted_code, recipient


def _decrypt_code(encrypted_code: str, user_pool_id: str) -> str:
    """Decrypt a Cognito envelope using the AWS Encryption SDK, never raw KMS."""
    try:
        ciphertext = base64.b64decode(encrypted_code, validate=True)
    except (ValueError, TypeError) as exc:
        raise CognitoEmailSenderError("Encrypted verification code is invalid") from exc

    if not ciphertext:
        raise CognitoEmailSenderError("Encrypted verification code is empty")

    # Imported lazily so unit tests can exercise all non-cryptographic behavior
    # without installing the deployment-only package locally.
    import aws_encryption_sdk
    from aws_encryption_sdk import CommitmentPolicy

    key_arn = _required_environment("COGNITO_EMAIL_SENDER_KMS_KEY_ARN")
    client = aws_encryption_sdk.EncryptionSDKClient(
        commitment_policy=CommitmentPolicy.REQUIRE_ENCRYPT_ALLOW_DECRYPT
    )
    key_provider = aws_encryption_sdk.StrictAwsKmsMasterKeyProvider(key_ids=[key_arn])
    try:
        plaintext, header = client.decrypt(
            source=ciphertext,
            key_provider=key_provider,
        )
    except Exception as exc:
        raise CognitoEmailSenderError("Verification code decryption failed") from exc

    encryption_context = getattr(header, "encryption_context", {})
    if encryption_context.get("userpool-id") != user_pool_id:
        raise CognitoEmailSenderError("Verification code context did not match the user pool")

    try:
        code = plaintext.decode("utf-8")
    except (AttributeError, UnicodeDecodeError) as exc:
        raise CognitoEmailSenderError("Decrypted verification code is invalid") from exc

    if not code or len(code) > MAX_CODE_LENGTH:
        raise CognitoEmailSenderError("Decrypted verification code has an invalid length")
    return code


def _get_postmark_token() -> str:
    secret_arn = _required_environment("POSTMARK_SERVER_TOKEN_SECRET_ARN")
    client = boto3.client("secretsmanager")
    try:
        response = client.get_secret_value(SecretId=secret_arn)
    except Exception as exc:
        raise CognitoEmailSenderError("Postmark credential retrieval failed") from exc

    secret_string = response.get("SecretString")
    if not isinstance(secret_string, str) or not secret_string.strip():
        raise CognitoEmailSenderError("Postmark credential is unavailable")

    token = secret_string.strip()
    if token.startswith("{"):
        try:
            parsed = json.loads(token)
        except json.JSONDecodeError as exc:
            raise CognitoEmailSenderError("Postmark credential format is invalid") from exc
        token = str(parsed.get("token") or parsed.get("PostmarkServerToken") or "").strip()

    if not token:
        raise CognitoEmailSenderError("Postmark credential is unavailable")
    return token


def _render_email(code: str) -> tuple[str, str]:
    safe_code = html.escape(code)
    html_body = f"""\
<!doctype html>
<html>
  <body style="margin:0;padding:24px;background:#f7f5f2;color:#252525;font-family:Arial,sans-serif;line-height:1.5;">
    <div style="max-width:600px;margin:0 auto;background:#ffffff;border:1px solid #e5e0da;border-radius:8px;padding:28px;">
      <p>Hi there,</p>
      <p>We received a request to reset the password for your Togs &amp; Dogs account.</p>
      <p>Your verification code:</p>
      <p style="font-size:28px;font-weight:700;letter-spacing:4px;margin:20px 0;">{safe_code}</p>
      <p>Enter this code on the Togs &amp; Dogs password reset screen to choose a new password.</p>
      <p><strong>For your security:</strong></p>
      <ul>
        <li>This code expires shortly.</li>
        <li>Don't share this code with anyone.</li>
        <li>If you didn't request this reset, you can safely ignore this email.</li>
        <li>Your password won't change unless the reset is completed.</li>
      </ul>
      <p>Thanks,<br>The Togs &amp; Dogs Team</p>
      <p style="font-size:12px;color:#666666;">Togs &amp; Dogs is operated by usmissionhero LLC.</p>
    </div>
  </body>
</html>
"""
    text_body = f"""Hi there,

We received a request to reset the password for your Togs & Dogs account.

Your verification code:

{code}

Enter this code on the Togs & Dogs password reset screen to choose a new password.

For your security:
- This code expires shortly.
- Don't share this code with anyone.
- If you didn't request this reset, you can safely ignore this email.
- Your password won't change unless the reset is completed.

Thanks,
The Togs & Dogs Team

Togs & Dogs is operated by usmissionhero LLC.
"""
    return html_body, text_body


def _send_postmark(token: str, recipient: str, code: str) -> None:
    html_body, text_body = _render_email(code)
    payload = {
        "From": FROM_HEADER,
        "To": recipient,
        "ReplyTo": REPLY_TO,
        "Subject": SUBJECT,
        "HtmlBody": html_body,
        "TextBody": text_body,
        "MessageStream": os.environ.get(
            "POSTMARK_MESSAGE_STREAM", DEFAULT_MESSAGE_STREAM
        ).strip()
        or DEFAULT_MESSAGE_STREAM,
    }
    request = urllib.request.Request(
        POSTMARK_ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Postmark-Server-Token": token,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            status = getattr(response, "status", None)
            if status is None:
                status = response.getcode()
            response_body = response.read()
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
        raise CognitoEmailSenderError("Postmark delivery failed") from exc

    if status < 200 or status >= 300:
        raise CognitoEmailSenderError("Postmark delivery failed")
    try:
        result = json.loads(response_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CognitoEmailSenderError("Postmark returned an invalid response") from exc
    if result.get("ErrorCode") != 0:
        raise CognitoEmailSenderError("Postmark rejected the message")


def handler(event: Any, context: Any) -> None:
    """Send only supported Cognito password-recovery messages via Postmark."""
    trigger_source = _safe_trigger_source(
        event.get("triggerSource") if isinstance(event, dict) else None
    )
    try:
        user_pool_id, encrypted_code, recipient = _validate_event(event)
        code = _decrypt_code(encrypted_code, user_pool_id)
        token = _get_postmark_token()
        _send_postmark(token, recipient, code)
        LOGGER.info("Cognito custom email delivered: trigger=%s", trigger_source)
    except Exception as exc:
        # Deliberately omit exception text and event data: either could contain
        # provider or Cognito details that do not belong in logs.
        LOGGER.error(
            "Cognito custom email failed: trigger=%s error_type=%s",
            trigger_source,
            type(exc).__name__,
        )
        raise
