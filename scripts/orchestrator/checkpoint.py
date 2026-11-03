"""Crash-safe, tamper-evident checkpoints.

A checkpoint is a snapshot of :class:`state.RunState` plus an integrity digest.
The digest is an HMAC-SHA256 over the canonical JSON of the snapshot, keyed by
a per-runtime integrity key. On load, the digest is recomputed and compared; a
mismatch (content edited without re-signing, or signed with the wrong key)
raises :class:`errors.CheckpointTampered` and halts fail-closed.

Threat model note (honest scope): the integrity key lives in the runtime dir.
If an attacker can both edit the checkpoint AND read the key, they could
re-sign a forged checkpoint. This control detects accidental corruption and
naive tampering (the overwhelmingly likely A1 failure modes) and gives a clean
seam to later bind the key to an owner-controlled secret store. A1 does not
claim it is a defense against a fully privileged local attacker.

Writes are atomic (temp + fsync + os.replace), so a crash mid-write cannot
leave a half-written checkpoint that would later read as "tampered".
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import errors
from .state import RunState, atomic_write_json

_KEY_FILENAME = "integrity.key"
_DIGEST_FIELD = "_integrity_hmac_sha256"
_PAYLOAD_FIELD = "state"


@dataclass
class CheckpointStore:
    """Reads/writes a single tamper-evident checkpoint for a runtime dir."""

    checkpoint_path: Path

    @property
    def key_path(self) -> Path:
        return self.checkpoint_path.parent / _KEY_FILENAME

    # --- integrity key -----------------------------------------------------

    def _load_or_create_key(self) -> bytes:
        """Return the runtime integrity key, creating it once if absent.

        The key is created with 0600-style intent (best effort on Windows) and
        never logged or placed in the diff (the runtime dir is gitignored).
        """

        self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        if self.key_path.is_file():
            return self.key_path.read_bytes()
        key = secrets.token_bytes(32)
        # Write atomically-ish; key file is in the gitignored runtime dir.
        fd = os.open(str(self.key_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as fh:
            fh.write(key)
            fh.flush()
            os.fsync(fh.fileno())
        return key

    # --- sign / verify -----------------------------------------------------

    @staticmethod
    def _canonical(payload: dict[str, Any]) -> bytes:
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def _digest(self, payload: dict[str, Any], key: bytes) -> str:
        return hmac.new(key, self._canonical(payload), hashlib.sha256).hexdigest()

    def save(self, state: RunState) -> None:
        key = self._load_or_create_key()
        payload = state.to_dict()
        envelope = {
            _PAYLOAD_FIELD: payload,
            _DIGEST_FIELD: self._digest(payload, key),
        }
        atomic_write_json(self.checkpoint_path, envelope)

    def exists(self) -> bool:
        return self.checkpoint_path.is_file()

    def load(self) -> RunState:
        """Load, verifying integrity. Raise typed stop on corruption/tamper."""

        if not self.key_path.is_file():
            # No key means we cannot trust any checkpoint -> fail closed.
            raise errors.CheckpointTampered("integrity key missing; cannot verify checkpoint")
        key = self.key_path.read_bytes()

        try:
            envelope = json.loads(self.checkpoint_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise errors.CheckpointCorrupt(f"checkpoint unreadable: {exc}") from exc

        if not isinstance(envelope, dict) or _PAYLOAD_FIELD not in envelope or _DIGEST_FIELD not in envelope:
            raise errors.CheckpointCorrupt("checkpoint envelope malformed")

        payload = envelope[_PAYLOAD_FIELD]
        stored_digest = envelope[_DIGEST_FIELD]
        if not isinstance(payload, dict) or not isinstance(stored_digest, str):
            raise errors.CheckpointCorrupt("checkpoint fields wrong type")

        expected = self._digest(payload, key)
        if not hmac.compare_digest(expected, stored_digest):
            raise errors.CheckpointTampered("checkpoint digest mismatch")

        try:
            return RunState.from_dict(payload)
        except (TypeError, ValueError) as exc:
            raise errors.CheckpointCorrupt(f"checkpoint payload invalid: {exc}") from exc
