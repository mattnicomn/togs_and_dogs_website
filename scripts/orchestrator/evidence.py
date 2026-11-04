"""Deterministic evidence packaging (A2-A G1 — pure functions, no I/O).

Turns UNTRUSTED observations (a PR record and CI logs) into a versioned,
size-bounded, fingerprinted evidence packet that an advisory reviewer can read.

Design rules:
  * Pure and deterministic: the same inputs always yield the same packet and the
    same fingerprint. No clocks, no randomness, no network, no filesystem.
  * Fail closed: malformed, inconsistent, missing or oversized evidence raises a
    typed stop. Evidence is never truncated (truncation could hide a failure)
    and a missing input is never read as "no problems".
  * Counts are reconciled: the failing test ids parsed from a log must equal the
    count in pytest's own summary line, or the evidence is rejected.
  * PR text and CI log text are untrusted. Only validated test ids, counts and a
    redacted, length-capped title enter the packet. The PR body and log text are
    scanned for authorization/instruction-looking content; only COUNTS of such
    markers are recorded, never the text.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from . import errors, redaction
from .adapters.github_observer import (
    JobObservation,
    PullRequestObservation,
    WorkflowRunObservation,
)
from .manifest import ApprovedPullRequest

SCHEMA_VERSION = "petcare.evidence.packet/v1"

MAX_IDS = 500
MAX_ID_LEN = 300
MAX_LOG_BYTES = 2_000_000
MAX_PACKET_BYTES = 65_536
MAX_TITLE = 200
MAX_PATHS = 300

_ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
_TS_PREFIX = re.compile(r"^\d{4}-\d{2}-\d{2}T[\d:.]+Z\s+")
_FAIL_LINE = re.compile(r"^(FAILED|ERROR) (\S+)(?: - .*)?$")
_NODE_ID = re.compile(r"^[A-Za-z0-9_./\-]+\.py::[A-Za-z0-9_\[\]\-:.,=+/]+$")
_SUMMARY = re.compile(r"^=+ (.+?) in ([0-9]+(?:\.[0-9]+)?)s(?: \([^)]*\))? =+$")
_COUNT = re.compile(r"(\d+) (failed|passed|skipped|errors?|warnings?|deselected|xfailed|xpassed|rerun)")
_COLLECTED = re.compile(r"^collected (\d+) items?")
_WEB = re.compile(r"(\d+) problems? \((\d+) errors?, (\d+) warnings?\)")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")

# Authorization/instruction-looking content. Used on untrusted PR/log text and
# (by the reviewer module) on model output, so a response can never launder an
# approval-looking block. Only counts are ever recorded.
INJECTION_PATTERNS: dict[str, re.Pattern[str]] = {
    "merge_authorization": re.compile(r"merge\s+authori[sz]ation", re.I),
    "instruction_override": re.compile(
        r"(ignore|disregard|forget)\s+(all\s+|any\s+|the\s+)?"
        r"(previous|prior|above|earlier)\s+(instructions|rules|messages)",
        re.I,
    ),
    "approval_claim": re.compile(
        r"authori[sz]ed_by\s*[:=]|approved\s+by\s+matthew|owner\s+(has\s+)?approved", re.I
    ),
    "role_override": re.compile(r"(you\s+are\s+now|new\s+system\s+prompt|system\s+prompt\s*:)", re.I),
}


# --- canonical form + fingerprint ------------------------------------------


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def ids_sha256(ids: Sequence[str]) -> str:
    """Stable digest of a set of test ids (order- and duplicate-insensitive)."""

    return sha256_hex("\n".join(sorted(set(ids))))


def packet_fingerprint(packet_without_fingerprint: Mapping[str, Any]) -> str:
    return sha256_hex(canonical_json(dict(packet_without_fingerprint)))


# --- log parsing ------------------------------------------------------------


@dataclass(frozen=True)
class ParsedPytestLog:
    failed_ids: tuple[str, ...]
    error_ids: tuple[str, ...]
    counts: Mapping[str, int]
    collected: int | None
    log_sha256: str


def _clean_line(raw: str) -> str:
    line = _ANSI.sub("", raw.rstrip("\r\n"))
    if "\t" in line:
        line = line.split("\t")[-1]
    return _TS_PREFIX.sub("", line).strip()


def _normalize_count_key(word: str) -> str:
    if word.startswith("error"):
        return "errors"
    if word.startswith("warning"):
        return "warnings"
    return word


def is_valid_node_id(ident: str) -> bool:
    return len(ident) <= MAX_ID_LEN and bool(_NODE_ID.match(ident))


def parse_pytest_log(text: str) -> ParsedPytestLog:
    """Extract failing ids + pytest's own counts, and reconcile them."""

    if len(text.encode("utf-8", errors="replace")) > MAX_LOG_BYTES:
        raise errors.EvidenceTooLarge("log exceeds the evidence size limit")
    failed: set[str] = set()
    errored: set[str] = set()
    summaries: list[str] = []
    collected: int | None = None
    rejected = 0
    for raw in text.splitlines():
        line = _clean_line(raw)
        m = _FAIL_LINE.match(line)
        if m:
            kind, ident = m.groups()
            if not is_valid_node_id(ident):
                rejected += 1
                continue
            (failed if kind == "FAILED" else errored).add(ident)
            continue
        sm = _SUMMARY.match(line)
        if sm:
            summaries.append(sm.group(1))
            continue
        cm = _COLLECTED.match(line)
        if cm:
            collected = int(cm.group(1))
    if rejected:
        raise errors.EvidenceInvalid(f"{rejected} failure line(s) have an unparseable test id")
    if not summaries:
        raise errors.EvidenceIncomplete("no pytest summary line found in the log")
    if len(summaries) > 1:
        raise errors.EvidenceInvalid("multiple pytest summary lines found")
    counts: dict[str, int] = {}
    for number, word in _COUNT.findall(summaries[0]):
        counts[_normalize_count_key(word)] = int(number)
    if len(failed) != counts.get("failed", 0):
        raise errors.EvidenceInvalid(
            f"parsed {len(failed)} failing id(s) but the summary reports {counts.get('failed', 0)}"
        )
    if len(errored) != counts.get("errors", 0):
        raise errors.EvidenceInvalid(
            f"parsed {len(errored)} error id(s) but the summary reports {counts.get('errors', 0)}"
        )
    if collected is not None and "deselected" not in counts:
        total = sum(counts.get(k, 0) for k in ("passed", "failed", "errors", "skipped", "xfailed", "xpassed"))
        if total != collected:
            raise errors.EvidenceInvalid(f"summary totals {total} != collected {collected}")
    return ParsedPytestLog(
        failed_ids=tuple(sorted(failed)),
        error_ids=tuple(sorted(errored)),
        counts=dict(counts),
        collected=collected,
        log_sha256=sha256_hex(text),
    )


def parse_web_summary(text: str) -> dict[str, int] | None:
    """Parse an eslint 'N problems (E errors, W warnings)' line, if present."""

    found: dict[str, int] | None = None
    for raw in text.splitlines():
        m = _WEB.search(_clean_line(raw))
        if m:
            problems, errs, warns = (int(g) for g in m.groups())
            if problems != errs + warns:
                raise errors.EvidenceInvalid("web summary counts are inconsistent")
            found = {"problems": problems, "errors": errs, "warnings": warns}
    return found


def scan_untrusted(*texts: str) -> dict[str, int]:
    """Count authorization/instruction-looking markers. Never returns the text."""

    counts = {name: 0 for name in INJECTION_PATTERNS}
    for text in texts:
        for name, pattern in INJECTION_PATTERNS.items():
            counts[name] += len(pattern.findall(text or ""))
    return counts


# --- baseline comparison ----------------------------------------------------


@dataclass(frozen=True)
class Comparison:
    remaining_original: tuple[str, ...]
    new_failures: tuple[str, ...]
    recovered_verified: tuple[str, ...]
    replaced_declared: tuple[tuple[str, tuple[str, ...]], ...]
    absent_unverified: tuple[str, ...]
    replacement_targets_failing: tuple[str, ...]
    presence_verified: bool


def compare_to_baseline(
    baseline_ids: Sequence[str],
    current_failed_ids: Sequence[str],
    *,
    declared_replacements: Mapping[str, Sequence[str]],
    collected_ids: frozenset[str] | None = None,
) -> Comparison:
    """Classify every baseline id against the current failing set.

    A baseline id absent from the current failures is NOT assumed recovered:
      * it is ``replaced_declared`` only if the OWNER-approved manifest declared
        the replacement (PR text and logs can never declare one);
      * it is ``recovered_verified`` only if the collected test ids prove it
        still exists and is not failing;
      * otherwise it is ``absent_unverified`` (it may have been deleted or
        renamed) and the packet says so explicitly.
    """

    baseline = set(baseline_ids)
    current = set(current_failed_ids)
    for ident in baseline | current:
        if not is_valid_node_id(ident):
            raise errors.EvidenceInvalid("a test id in the baseline or current set is malformed")
    unknown_decl = sorted(set(declared_replacements) - baseline)
    if unknown_decl:
        raise errors.EvidenceInvalid("a declared replacement refers to an id not in the baseline")

    remaining = sorted(baseline & current)
    new_failures = sorted(current - baseline)
    recovered: list[str] = []
    replaced: list[tuple[str, tuple[str, ...]]] = []
    unverified: list[str] = []
    targets_failing: set[str] = set()
    for ident in sorted(baseline - current):
        if ident in declared_replacements:
            targets = tuple(sorted(declared_replacements[ident]))
            replaced.append((ident, targets))
            targets_failing.update(t for t in targets if t in current)
        elif collected_ids is not None and ident in collected_ids:
            recovered.append(ident)
        else:
            unverified.append(ident)
    return Comparison(
        remaining_original=tuple(remaining),
        new_failures=tuple(new_failures),
        recovered_verified=tuple(recovered),
        replaced_declared=tuple(replaced),
        absent_unverified=tuple(unverified),
        replacement_targets_failing=tuple(sorted(targets_failing)),
        presence_verified=collected_ids is not None,
    )


# --- packet -----------------------------------------------------------------


def _bounded(name: str, items: Sequence[Any]) -> list[Any]:
    if len(items) > MAX_IDS:
        raise errors.EvidenceTooLarge(f"{name} has {len(items)} entries (limit {MAX_IDS})")
    return list(items)


def _sanitize_title(title: str) -> str:
    cleaned = _CONTROL.sub(" ", title)
    return redaction.redact(cleaned)[:MAX_TITLE]


def build_packet(
    *,
    pr: PullRequestObservation,
    approval: ApprovedPullRequest,
    runs: Sequence[WorkflowRunObservation],
    backend: tuple[WorkflowRunObservation, JobObservation],
    backend_log: str,
    web_log: str | None,
    baseline_ids: Sequence[str],
    collected_ids: frozenset[str] | None = None,
    observer_name: str,
) -> dict[str, Any]:
    """Assemble the versioned, fingerprinted evidence packet."""

    if ids_sha256(baseline_ids) != approval.baseline_ids_sha256:
        raise errors.EvidenceInvalid("baseline ids do not match the owner-bound baseline hash")
    parsed = parse_pytest_log(backend_log)
    comparison = compare_to_baseline(
        baseline_ids,
        parsed.failed_ids + parsed.error_ids,
        declared_replacements=dict(approval.declared_replacements),
        collected_ids=collected_ids,
    )
    web = parse_web_summary(web_log) if web_log is not None else None
    markers = scan_untrusted(pr.title, pr.body, backend_log, web_log or "")
    if len(pr.files) > MAX_PATHS:
        raise errors.EvidenceTooLarge("changed path list exceeds the limit")

    backend_run, backend_job = backend
    run_rows = []
    for run in sorted(runs, key=lambda r: r.run_id):
        if run.head_sha != pr.head_sha:
            continue
        run_rows.append(
            {
                "run_id": run.run_id,
                "workflow": run.workflow,
                "event": run.event,
                "status": run.status,
                "conclusion": run.conclusion,
                "jobs": [
                    {"job_id": j.job_id, "name": j.name, "status": j.status, "conclusion": j.conclusion}
                    for j in sorted(run.jobs, key=lambda j: j.job_id)
                ],
            }
        )

    counts = {
        "remaining_original": len(comparison.remaining_original),
        "new_failures": len(comparison.new_failures),
        "recovered_verified": len(comparison.recovered_verified),
        "replaced_declared": len(comparison.replaced_declared),
        "absent_unverified": len(comparison.absent_unverified),
    }
    packet: dict[str, Any] = {
        "schema": SCHEMA_VERSION,
        "repository": pr.repository,
        "pull_request": {
            "number": pr.number,
            "state": pr.state,
            "is_draft": pr.is_draft,
            "base_ref": pr.base_ref,
            "head_ref": pr.head_ref,
            "head_sha": pr.head_sha,
            "title": _sanitize_title(pr.title),
        },
        "base_sha": pr.base_sha,
        "changed_paths": sorted(pr.files),
        "runs": run_rows,
        "backend": {
            "run_id": backend_run.run_id,
            "job_id": backend_job.job_id,
            "job_conclusion": backend_job.conclusion,
            "log_sha256": parsed.log_sha256,
            "tests": {
                "collected": parsed.collected,
                "passed": parsed.counts.get("passed", 0),
                "failed": parsed.counts.get("failed", 0),
                "errors": parsed.counts.get("errors", 0),
                "skipped": parsed.counts.get("skipped", 0),
            },
            "failed_ids": _bounded("failed_ids", parsed.failed_ids),
            "error_ids": _bounded("error_ids", parsed.error_ids),
        },
        "baseline": {"ids_sha256": ids_sha256(baseline_ids), "failed_count": len(set(baseline_ids))},
        "comparison": {
            "presence_verified": comparison.presence_verified,
            "remaining_original": _bounded("remaining_original", comparison.remaining_original),
            "new_failures": _bounded("new_failures", comparison.new_failures),
            "recovered_verified": _bounded("recovered_verified", comparison.recovered_verified),
            "replaced_declared": [
                {"old": old, "new": list(new)}
                for old, new in _bounded("replaced_declared", comparison.replaced_declared)
            ],
            "absent_unverified": _bounded("absent_unverified", comparison.absent_unverified),
            "replacement_targets_failing": list(comparison.replacement_targets_failing),
            "counts": counts,
        },
        "web": web,
        "untrusted_content": {
            "injection_markers": markers,
            "pr_body_present": bool(pr.body.strip()),
        },
        "provenance": {
            "observer": observer_name,
            "evidence_schema": SCHEMA_VERSION,
            "approved_head_sha": approval.head_sha,
        },
    }
    packet["fingerprint"] = packet_fingerprint(packet)
    if len(canonical_json(packet).encode("utf-8")) > MAX_PACKET_BYTES:
        raise errors.EvidenceTooLarge("evidence packet exceeds the size limit")
    return packet


def verify_packet(packet: Mapping[str, Any]) -> None:
    """Re-verify a packet's schema tag, size and integrity fingerprint."""

    if not isinstance(packet, Mapping) or packet.get("schema") != SCHEMA_VERSION:
        raise errors.EvidenceInvalid("evidence packet schema mismatch")
    claimed = packet.get("fingerprint")
    body = {k: v for k, v in packet.items() if k != "fingerprint"}
    if not isinstance(claimed, str) or claimed != packet_fingerprint(body):
        raise errors.EvidenceInvalid("evidence packet fingerprint mismatch")
    if len(canonical_json(dict(packet)).encode("utf-8")) > MAX_PACKET_BYTES:
        raise errors.EvidenceTooLarge("evidence packet exceeds the size limit")


def deterministic_counts(packet: Mapping[str, Any]) -> dict[str, int]:
    cmp_ = packet["comparison"]
    return {
        "remaining_original_count": len(cmp_["remaining_original"]),
        "new_failure_count": len(cmp_["new_failures"]),
    }


_PACKET_SECTIONS = (
    "pull_request", "changed_paths", "runs", "backend", "baseline",
    "comparison", "web", "untrusted_content", "provenance",
)


def reference_universe(packet: Mapping[str, Any]) -> frozenset[str]:
    """Every reference a reviewer is allowed to cite (anti-hallucination)."""

    refs: set[str] = {f"packet:{s}" for s in _PACKET_SECTIONS}
    cmp_ = packet["comparison"]
    for key in ("remaining_original", "new_failures", "recovered_verified", "absent_unverified"):
        refs.update(f"test:{i}" for i in cmp_[key])
    for row in cmp_["replaced_declared"]:
        refs.add(f"test:{row['old']}")
        refs.update(f"test:{n}" for n in row["new"])
    for run in packet["runs"]:
        refs.update(f"job:{j['job_id']}" for j in run["jobs"])
    refs.update(f"path:{p}" for p in packet["changed_paths"])
    return frozenset(refs)
