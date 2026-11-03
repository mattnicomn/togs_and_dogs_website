"""Sanitization of anything written to disk (logs, reports, checkpoints).

Fail-safe rule: every string that could reach durable storage or a report is
passed through :func:`redact` first. The orchestrator must never persist a
token, key, JWT, OAuth code, AWS secret, or obvious PII, even in a prototype.

The redactor is intentionally conservative (it over-redacts rather than risk a
leak) and uses only the standard library.
"""

from __future__ import annotations

import re
from typing import Any

# Placeholder emitted in place of any redacted value.
PLACEHOLDER = "[REDACTED]"

# Ordered list of (name, compiled pattern) rules. Order matters: more specific
# patterns run first so a generic rule does not mangle a specific match.
_RULES: list[tuple[str, re.Pattern[str]]] = [
    # OpenAI-style secret keys: sk-... / sk-proj-...
    ("openai_key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_\-]{12,}\b")),
    # Stripe keys (live or test) and webhook signing secrets.
    ("stripe_key", re.compile(r"\b(?:sk|pk|rk)_(?:live|test)_[A-Za-z0-9]{8,}\b")),
    ("stripe_whsec", re.compile(r"\bwhsec_[A-Za-z0-9]{8,}\b")),
    # GitHub tokens: ghp_, gho_, ghu_, ghs_, ghr_, github_pat_...
    ("github_token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b")),
    # AWS access key id.
    ("aws_akid", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    # Google OAuth client / refresh tokens.
    ("google_oauth", re.compile(r"\b(?:ya29\.[A-Za-z0-9._\-]+|1//[A-Za-z0-9._\-]{20,})")),
    # JWTs (three base64url segments).
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\b")),
    # Bearer tokens in Authorization headers.
    ("bearer", re.compile(r"(?i)\b(bearer|token|authorization)\s*[:=]\s*\S+")),
    # key=value / "key": "value" where the key name looks sensitive.
    (
        "sensitive_kv",
        re.compile(
            r"(?i)\b(api[_\-]?key|secret|password|passwd|pwd|access[_\-]?key|"
            r"secret[_\-]?key|private[_\-]?key|refresh[_\-]?token|client[_\-]?secret)\b"
            r"\s*[:=]\s*(\"[^\"]*\"|'[^']*'|\S+)"
        ),
    ),
    # Email addresses (PII).
    ("email", re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")),
    # US-style phone numbers (PII).
    ("phone", re.compile(r"\b(?:\+?1[\s.\-]?)?\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}\b")),
]


def redact(text: str) -> str:
    """Return ``text`` with every sensitive pattern replaced by a placeholder."""

    if not text:
        return text
    out = text
    for name, pattern in _RULES:
        if name in ("sensitive_kv", "bearer"):
            # Preserve the key label; redact only the value side.
            out = pattern.sub(lambda m: _redact_kv(m), out)
        else:
            out = pattern.sub(PLACEHOLDER, out)
    return out


def _redact_kv(match: re.Match[str]) -> str:
    """Helper for key/value rules: keep the key token, hide the value."""

    key = match.group(1)
    return f"{key}={PLACEHOLDER}"


def redact_obj(obj: Any) -> Any:
    """Recursively redact strings inside dicts/lists/tuples for structured logs.

    Keys are also checked: a value under a sensitive-looking key is fully
    replaced regardless of its own content (e.g. a numeric secret).
    """

    sensitive_key = re.compile(
        r"(?i)(api[_\-]?key|secret|password|passwd|pwd|token|access[_\-]?key|"
        r"private[_\-]?key|client[_\-]?secret|authorization)"
    )
    if isinstance(obj, dict):
        result: dict[Any, Any] = {}
        for k, v in obj.items():
            if isinstance(k, str) and sensitive_key.search(k):
                result[k] = PLACEHOLDER
            else:
                result[k] = redact_obj(v)
        return result
    if isinstance(obj, list):
        return [redact_obj(v) for v in obj]
    if isinstance(obj, tuple):
        return tuple(redact_obj(v) for v in obj)
    if isinstance(obj, str):
        return redact(obj)
    return obj
