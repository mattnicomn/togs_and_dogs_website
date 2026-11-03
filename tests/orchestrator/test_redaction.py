"""Log/report redaction tests: secrets and PII never reach durable output."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.orchestrator import redaction
from scripts.orchestrator.logging_events import EventLogger


def test_redacts_openai_key():
    out = redaction.redact("key is sk-proj-ABCD1234efgh5678IJKL here")
    assert "sk-proj-ABCD1234" not in out
    assert redaction.PLACEHOLDER in out


def test_redacts_stripe_and_webhook_secrets():
    assert "sk_live_" not in redaction.redact("sk_live_abcd1234EFGH")
    assert "whsec_" not in redaction.redact("whsec_abcd1234EFGH")


def test_redacts_github_token():
    assert "ghp_" not in redaction.redact("ghp_" + "a" * 36)


def test_redacts_jwt_and_aws_key():
    jwt = "eyJhbGciOi.eyJzdWIiOi.SflKxwRJSM"
    assert redaction.PLACEHOLDER in redaction.redact(jwt)
    assert "AKIA" not in redaction.redact("AKIAIOSFODNN7EXAMPLE")


def test_redacts_email_and_phone_pii():
    assert "@" not in redaction.redact("contact person@example.com")
    assert redaction.PLACEHOLDER in redaction.redact("call 404-555-0199 now")


def test_redacts_sensitive_kv_keeps_key_label():
    out = redaction.redact('api_key=supersecretvalue123456')
    assert "supersecretvalue" not in out
    assert "api_key" in out


def test_redact_obj_handles_nested_and_sensitive_keys():
    obj = {
        "password": "hunter2hunter2",
        "nested": {"token": "ghp_" + "b" * 36, "safe": "ok"},
        "list": ["sk_test_zzzz1111", "plain"],
    }
    red = redaction.redact_obj(obj)
    assert red["password"] == redaction.PLACEHOLDER
    assert red["nested"]["token"] == redaction.PLACEHOLDER
    assert red["nested"]["safe"] == "ok"
    assert "sk_test_zzzz1111" not in json.dumps(red)


def test_event_logger_writes_redacted_jsonl(tmp_path: Path):
    log_path = tmp_path / "events.log"
    logger = EventLogger(log_path=log_path, clock=lambda: "T0")
    logger.emit("test", secret="sk-proj-TOPSECRET1234567890", note="person@example.com did x")

    written = log_path.read_text(encoding="utf-8").strip()
    assert "sk-proj-TOPSECRET" not in written
    assert "person@example.com" not in written
    # Still valid JSON lines.
    record = json.loads(written)
    assert record["event"] == "test"
    assert record["ts"] == "T0"
