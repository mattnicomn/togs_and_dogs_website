"""Owner-controlled approval manifest: parsing and fail-closed verification.

A manifest authorizes exactly ONE task scope: a specific task id, repository,
branch, immutable base SHA, an explicit path allowlist, and an explicit set of
allowed actions. Nothing is inferred and nothing is defaulted permissively.

Trust boundary (critical):
    :func:`load_manifest` refuses to read a manifest that resolves to a path
    inside any agent-writable (untrusted) root from :class:`config.Config`.
    This is what makes "an AI-generated file can never be authorization" an
    enforced property rather than a promise.

Manifest file format (JSON): a single object with these required fields::

    {
      "scope_id":       "A1_SYNTHETIC_TASK_001",
      "repository":     "mattnicomn/togs_and_dogs_website",
      "base_sha":       "<40-char hex>",
      "target_branch":  "codex/ai-dev-orchestrator-a1",
      "allowed_paths":  ["scripts/orchestrator/**", "tests/orchestrator/**"],
      "allowed_actions":["implement", "review", "correct", "draft_pr"],
      "authorized_by":  "Matthew",
      "authorized_at":  "<ISO-8601 timestamp>",
      "base_branch":    "main"
    }

``base_branch`` is optional (defaults to ``"main"``) and is the PR base used by
the mock Draft-PR step. Any missing/empty/wrong-typed REQUIRED field raises
``ApprovalInvalid``. A manifest
is matched against a requested :class:`TaskRequest` with
:meth:`ApprovalManifest.verify`, which raises the precise typed stop on the
first failing check (scope, SHA, branch).
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import errors
from .config import Config

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")

_REQUIRED_FIELDS = (
    "scope_id",
    "repository",
    "base_sha",
    "target_branch",
    "allowed_paths",
    "allowed_actions",
    "authorized_by",
    "authorized_at",
)


# Closed action vocabulary (A2-A). An approval manifest may only grant actions
# from this fixed, in-code set. There is deliberately NO merge, ready-for-review,
# deploy, terraform, permission-grant or approve action: such operations cannot
# be authorized by configuration because they do not exist as actions at all.
KNOWN_ACTIONS = frozenset(
    {"implement", "review", "correct", "draft_pr", "observe_pr", "review_evidence"}
)

_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
_MAX_APPROVED_PRS = 50
_MAX_REPLACEMENT_ENTRIES = 200


@dataclass(frozen=True)
class ApprovedPullRequest:
    """One owner-approved pull request for read-only observation/review.

    ``head_sha`` pins the exact head that was approved. ``baseline_ids_sha256``
    binds the baseline failing-test set (so a swapped baseline is detected).
    ``declared_replacements`` lets the OWNER declare that a baseline test id was
    deliberately replaced by new ids; PR text and CI logs can never declare it.
    """

    number: int
    head_sha: str
    baseline_ids_sha256: str | None = None
    declared_replacements: tuple[tuple[str, tuple[str, ...]], ...] = ()

    def canonical(self) -> dict[str, Any]:
        return {
            "number": self.number,
            "head_sha": self.head_sha,
            "baseline_ids_sha256": self.baseline_ids_sha256,
            "declared_replacements": [
                [old, sorted(new)] for old, new in sorted(self.declared_replacements)
            ],
        }


@dataclass(frozen=True)
class TaskRequest:
    """A request to run a task; checked against a manifest before any work."""

    scope_id: str
    repository: str
    base_sha: str
    target_branch: str


@dataclass(frozen=True)
class ApprovalManifest:
    """A parsed, structurally valid owner approval for one scope."""

    scope_id: str
    repository: str
    base_sha: str
    target_branch: str
    allowed_paths: tuple[str, ...]
    allowed_actions: frozenset[str]
    authorized_by: str
    authorized_at: str
    source_path: Path
    base_branch: str = "main"
    # A2-A: owner-approved pull requests for read-only observation. Empty for
    # every A1 manifest (and then excluded from the fingerprint).
    approved_pull_requests: tuple[ApprovedPullRequest, ...] = ()

    # --- scope verification ------------------------------------------------

    def verify(self, request: TaskRequest) -> None:
        """Raise the precise typed stop if ``request`` is not authorized.

        Order: repository + scope id (SCOPE_MISMATCH), then branch
        (UNKNOWN_BRANCH), then SHA (SHA_MISMATCH). Fail-closed throughout.
        """

        if request.scope_id != self.scope_id or request.repository != self.repository:
            raise errors.ScopeMismatch(
                f"request scope={request.scope_id!r}/{request.repository!r} "
                f"!= manifest {self.scope_id!r}/{self.repository!r}"
            )
        if request.target_branch != self.target_branch:
            raise errors.UnknownBranch(
                f"request branch={request.target_branch!r} != manifest {self.target_branch!r}"
            )
        if request.base_sha != self.base_sha:
            raise errors.ShaMismatch(
                f"request sha={request.base_sha!r} != manifest {self.base_sha!r}"
            )

    # --- identity / integrity (Finding 2: resume authorization) -----------

    def fingerprint(self) -> str:
        """Stable content digest binding the authorizing scope.

        Covers every authorization-bearing field (NOT ``authorized_by`` /
        ``authorized_at``, which are audit metadata, nor ``source_path``). The
        loop persists this at authorize time and re-computes it on every
        resume; any drift means the manifest was swapped or edited and the run
        must be re-authorized.
        """

        payload: dict[str, Any] = {
            "scope_id": self.scope_id,
            "repository": self.repository,
            "base_sha": self.base_sha,
            "target_branch": self.target_branch,
            "base_branch": self.base_branch,
            "allowed_paths": sorted(self.allowed_paths),
            "allowed_actions": sorted(self.allowed_actions),
        }
        # A2-A: only present when PRs are approved, so every pre-existing A1
        # manifest keeps its exact historical fingerprint.
        if self.approved_pull_requests:
            payload["approved_pull_requests"] = [
                p.canonical()
                for p in sorted(self.approved_pull_requests, key=lambda p: p.number)
            ]
        canonical = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def assert_owner_source_permissions(self, *, enforce: bool) -> list[str]:
        """Advisory (A1) / enforced (future A2) OS-permission boundary check.

        Returns a list of human-readable warnings about the approvals source
        being writable by non-owners. In A1 (``enforce=False``) this is
        advisory only and the warnings are logged. A future A2 deployment can
        call with ``enforce=True`` to turn a world/group-writable owner source
        into a hard :class:`errors.ApprovalUntrustedSource` stop. The check is
        intentionally conservative and best-effort across platforms.
        """

        warnings: list[str] = []
        try:
            st = os.stat(self.source_path)
            mode = st.st_mode
            # POSIX group/other write bits (meaningful on POSIX; on Windows the
            # bits are not authoritative, so this stays advisory there).
            if mode & 0o022:
                warnings.append(
                    f"approval source {self.source_path} is group/other-writable "
                    f"(mode {oct(mode & 0o777)})"
                )
        except OSError as exc:  # pragma: no cover - platform dependent
            warnings.append(f"could not stat approval source: {exc}")

        if enforce and warnings:
            raise errors.ApprovalUntrustedSource(
                "owner approval source fails OS-permission boundary: " + "; ".join(warnings)
            )
        return warnings

    # --- path / action scope ----------------------------------------------

    def path_allowed(self, repo_rel_path: str) -> bool:
        """True iff ``repo_rel_path`` matches at least one allowed glob.

        Any absolute path or a path containing a ``..`` traversal segment is
        rejected outright (fail-closed), regardless of allowlist prefix, so a
        claimed path can never escape the repository scope.
        """

        norm = repo_rel_path.replace("\\", "/").lstrip("/")
        segments = norm.split("/")
        if ".." in segments or repo_rel_path.replace("\\", "/").startswith("/"):
            return False
        # Reject Windows-style absolute/drive paths too (e.g. C:/...).
        if ":" in segments[0]:
            return False
        for pattern in self.allowed_paths:
            pat = pattern.replace("\\", "/")
            if fnmatch.fnmatch(norm, pat):
                return True
            # Support "dir/**" meaning "any depth under dir".
            if pat.endswith("/**") and (
                norm == pat[:-3] or norm.startswith(pat[:-2])
            ):
                return True
        return False

    def assert_paths_allowed(self, repo_rel_paths: list[str]) -> None:
        """Raise ``UnauthorizedPath`` on the first path outside the allowlist."""

        for p in repo_rel_paths:
            if not self.path_allowed(p):
                raise errors.UnauthorizedPath(f"path outside allowlist: {p}")

    def assert_action_allowed(self, action: str) -> None:
        if action not in self.allowed_actions:
            raise errors.UnauthorizedOperation(f"action not authorized: {action}")

    def assert_pull_request_approved(self, number: int, head_sha: str) -> ApprovedPullRequest:
        """Return the approval for PR ``number`` at exactly ``head_sha``.

        An unlisted PR is ``PullRequestNotApproved``; a listed PR whose head
        differs from the approved head is ``ObservedHeadChanged``.
        """

        for approval in self.approved_pull_requests:
            if approval.number == number:
                if approval.head_sha != head_sha:
                    raise errors.ObservedHeadChanged(
                        f"PR #{number} head {head_sha[:12]} != approved {approval.head_sha[:12]}"
                    )
                return approval
        raise errors.PullRequestNotApproved(f"PR #{number} is not in the owner-approved manifest")


def load_manifest(path: Path | str, config: Config) -> ApprovalManifest:
    """Load and structurally validate a manifest from an owner-controlled path.

    Fail-closed checks, in order (Finding 1 — owner approval trust):
      1a. The fully real-path-resolved manifest must be CONTAINED within the
          configured owner approvals dir (positive allowlist), after resolving
          every symlink -> ``ApprovalUntrustedSource`` if it escapes.
      1b. The resolved path must NOT be inside any untrusted (agent-writable)
          root -> ``ApprovalUntrustedSource``.
      1c. Neither the manifest's own real path nor the approvals dir's real
          path may traverse a symlink that lands inside an untrusted root.
      2. The file must exist -> ``ApprovalMissing``.
      3. The file must be valid JSON object with all required fields of the
         right type -> ``ApprovalInvalid``.

    ``authorized_by`` is recorded for audit only and is NEVER treated as proof
    of authorization: trust derives entirely from the file's owner-controlled
    *location* plus (at resume) the integrity binding, not from its contents.
    """

    # Resolve symlinks fully (strict=False so a missing file still yields a
    # canonical path we can range-check before the existence check).
    resolved = _realpath(path)
    approvals_root = _realpath(config.approvals_dir)

    # (1a) Positive containment: the manifest must live under the configured
    # owner-controlled approvals directory, even after symlink resolution.
    if not _is_within(resolved, approvals_root):
        raise errors.ApprovalUntrustedSource(
            f"manifest {resolved} is not within the configured owner approvals "
            f"dir {approvals_root}"
        )

    # (1b) Negative exclusion: never inside an agent-writable tree.
    for untrusted in config.untrusted_roots:
        if _is_within(resolved, untrusted):
            raise errors.ApprovalUntrustedSource(
                f"manifest {resolved} is inside untrusted root {untrusted}"
            )

    # (1c) Symlink boundary: the approvals dir itself must not be a symlink
    # that resolves into an untrusted tree (defense against a redirected dir).
    for untrusted in config.untrusted_roots:
        if _is_within(approvals_root, untrusted):
            raise errors.ApprovalUntrustedSource(
                f"approvals dir {approvals_root} resolves inside untrusted root {untrusted}"
            )

    # (2) Existence.
    if not resolved.is_file():
        raise errors.ApprovalMissing(f"no manifest at {resolved}")

    # (3) Structure.
    try:
        raw: Any = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise errors.ApprovalInvalid(f"manifest unreadable/not JSON: {exc}") from exc

    if not isinstance(raw, dict):
        raise errors.ApprovalInvalid("manifest root must be a JSON object")

    for field_name in _REQUIRED_FIELDS:
        if field_name not in raw:
            raise errors.ApprovalInvalid(f"missing required field: {field_name}")

    scope_id = _require_nonempty_str(raw, "scope_id")
    repository = _require_nonempty_str(raw, "repository")
    base_sha = _require_nonempty_str(raw, "base_sha").lower()
    target_branch = _require_nonempty_str(raw, "target_branch")
    authorized_by = _require_nonempty_str(raw, "authorized_by")
    authorized_at = _require_nonempty_str(raw, "authorized_at")

    if not _SHA_RE.match(base_sha):
        raise errors.ApprovalInvalid("base_sha must be a 40-char lowercase hex SHA")

    allowed_paths = _require_str_list(raw, "allowed_paths")
    allowed_actions = _require_str_list(raw, "allowed_actions")

    # Closed vocabulary: an unknown action (including anything like "merge",
    # "mark_ready" or "deploy") is rejected outright, never silently ignored.
    unknown_actions = sorted(set(allowed_actions) - KNOWN_ACTIONS)
    if unknown_actions:
        raise errors.ApprovalInvalid(
            "manifest lists unknown or forbidden action(s): " + ", ".join(unknown_actions)
        )

    # Optional field with a safe default; if present it must be a non-empty str.
    base_branch = "main"
    if "base_branch" in raw:
        base_branch = _require_nonempty_str(raw, "base_branch")

    approved_prs = _parse_approved_pull_requests(raw)

    return ApprovalManifest(
        scope_id=scope_id,
        repository=repository,
        base_sha=base_sha,
        target_branch=target_branch,
        allowed_paths=tuple(allowed_paths),
        allowed_actions=frozenset(allowed_actions),
        authorized_by=authorized_by,
        authorized_at=authorized_at,
        source_path=resolved,
        base_branch=base_branch,
        approved_pull_requests=approved_prs,
    )


def _parse_approved_pull_requests(raw: dict[str, Any]) -> tuple[ApprovedPullRequest, ...]:
    """Strictly parse the optional ``approved_pull_requests`` list (A2-A)."""

    if "approved_pull_requests" not in raw:
        return ()
    items = raw["approved_pull_requests"]
    if not isinstance(items, list) or not items or len(items) > _MAX_APPROVED_PRS:
        raise errors.ApprovalInvalid(
            f"approved_pull_requests must be a non-empty list of at most {_MAX_APPROVED_PRS}"
        )
    allowed_keys = {"number", "head_sha", "baseline_ids_sha256", "declared_replacements"}
    out: list[ApprovedPullRequest] = []
    seen: set[int] = set()
    for item in items:
        if not isinstance(item, dict):
            raise errors.ApprovalInvalid("approved_pull_requests entries must be objects")
        extra = sorted(set(item) - allowed_keys)
        if extra:
            raise errors.ApprovalInvalid(f"approved_pull_requests entry has unknown key(s): {extra}")
        number = item.get("number")
        if not isinstance(number, int) or isinstance(number, bool) or number <= 0:
            raise errors.ApprovalInvalid("approved PR number must be a positive integer")
        if number in seen:
            raise errors.ApprovalInvalid(f"approved PR #{number} listed more than once")
        seen.add(number)
        head_sha = item.get("head_sha")
        if not isinstance(head_sha, str) or not _SHA_RE.match(head_sha):
            raise errors.ApprovalInvalid("approved PR head_sha must be a 40-char lowercase hex SHA")
        baseline = item.get("baseline_ids_sha256")
        if baseline is not None and (not isinstance(baseline, str) or not _HEX64_RE.match(baseline)):
            raise errors.ApprovalInvalid("baseline_ids_sha256 must be 64-char lowercase hex")
        replacements: list[tuple[str, tuple[str, ...]]] = []
        raw_repl = item.get("declared_replacements", {})
        if not isinstance(raw_repl, dict) or len(raw_repl) > _MAX_REPLACEMENT_ENTRIES:
            raise errors.ApprovalInvalid("declared_replacements must be an object (bounded size)")
        for old, new in raw_repl.items():
            if (
                not isinstance(old, str) or not old.strip()
                or not isinstance(new, list) or not new
                or any(not isinstance(n, str) or not n.strip() for n in new)
            ):
                raise errors.ApprovalInvalid("declared_replacements entries must map id -> non-empty id list")
            replacements.append((old.strip(), tuple(n.strip() for n in new)))
        out.append(
            ApprovedPullRequest(
                number=number,
                head_sha=head_sha,
                baseline_ids_sha256=baseline,
                declared_replacements=tuple(sorted(replacements)),
            )
        )
    return tuple(out)


def _realpath(path: Path | str) -> Path:
    """Fully resolve a path, following symlinks (Finding 1 boundary check).

    Uses ``os.path.realpath`` so every symlinked component is collapsed to its
    real target, then normalizes. Does not require the path to exist.
    """

    return Path(os.path.realpath(Path(path).expanduser()))


def _is_within(child: Path, parent: Path) -> bool:
    """True iff ``child`` is ``parent`` or nested under it (no path escaping)."""

    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def _require_nonempty_str(raw: dict[str, Any], key: str) -> str:
    value = raw[key]
    if not isinstance(value, str) or not value.strip():
        raise errors.ApprovalInvalid(f"field {key} must be a non-empty string")
    return value.strip()


def _require_str_list(raw: dict[str, Any], key: str) -> list[str]:
    value = raw[key]
    if not isinstance(value, list) or not value:
        raise errors.ApprovalInvalid(f"field {key} must be a non-empty list")
    out: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise errors.ApprovalInvalid(f"field {key} must contain non-empty strings")
        out.append(item.strip())
    return out
