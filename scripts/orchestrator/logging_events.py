"""Structured, sanitized event logging.

Every event is a JSON object written as one line (JSONL) to the run's event
log. All string content is passed through :func:`redaction.redact_obj` before
it is written, so the log can never contain a secret or obvious PII even if a
caller is careless.

The logger also keeps an in-memory list of emitted events so reports and tests
can assert on the exact event sequence without re-reading the file.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import redaction


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


@dataclass
class EventLogger:
    """Append-only JSONL logger with mandatory redaction.

    Parameters
    ----------
    log_path:
        Destination file. Parent directories are created on first write.
    clock:
        Injectable timestamp function (tests pass a deterministic clock).
    """

    log_path: Path
    clock: Any = _utc_now_iso
    events: list[dict[str, Any]] = field(default_factory=list)

    def emit(self, event_type: str, **fields: Any) -> dict[str, Any]:
        """Record a single structured event and append it to the log file."""

        record: dict[str, Any] = {
            "ts": self.clock(),
            "event": event_type,
        }
        # Redact caller-supplied fields (both keys-as-sensitive and values).
        record.update(redaction.redact_obj(fields))
        self.events.append(record)
        self._append(record)
        return record

    def _append(self, record: dict[str, Any]) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, ensure_ascii=False, sort_keys=True)
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def events_of(self, event_type: str) -> list[dict[str, Any]]:
        return [e for e in self.events if e.get("event") == event_type]
