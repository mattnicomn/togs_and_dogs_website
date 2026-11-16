"""CP-5J offline Terraform saved-plan JSON nested diff checker.

Pure data-analysis tool. It evaluates an *already materialized*, in-memory
Terraform plan JSON object (Terraform's documented JSON plan representation)
against an explicit, reviewed acceptance policy, and fails closed on anything
outside that policy.

What this module never does
---------------------------
* It never runs Terraform, the AWS CLI, Stripe APIs, or any subprocess.
* It never opens, discovers, scans, or fetches files or URLs. There is no
  default plan path and no command-line entry point.
* It never reads environment variables or credentials.
* It never reads the plan's ``variables``, ``planned_values``,
  ``prior_state`` or ``configuration`` sections.
* It never emits attribute values, Terraform variable values, environment
  maps, secrets, fingerprints/hashes of secrets, raw JSON, or whole resource
  objects. Reports contain sanitized addresses, sanitized attribute paths,
  booleans and fixed reason codes only.

A PASS is a technical policy match only. It grants no release, deployment,
plan or apply authority. Credential authority and rotation approval are
separate owner controls.

Usage (from code; ``scripts/cp5`` must be on ``sys.path``)::

    import plan_diff_checker as pdc
    result = pdc.check_plan(plan_obj)                       # strict default
    print(pdc.render_report(result))

    rotation = pdc.stripe_test_key_rotation_policy(
        rotation_separately_authorized=True)                # explicit opt-in
    result = pdc.check_plan(plan_obj, rotation)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Tuple

import nested_diff as nd
from nested_diff import MISSING, MalformedInput, Path

# ---------------------------------------------------------------------------
# Classifications
# ---------------------------------------------------------------------------

PASS_EXACT_ALLOWED_DIFF = "PASS_EXACT_ALLOWED_DIFF"
FAIL_UNEXPECTED_RESOURCE = "FAIL_UNEXPECTED_RESOURCE"
FAIL_UNEXPECTED_ACTION = "FAIL_UNEXPECTED_ACTION"
FAIL_UNEXPECTED_ATTRIBUTE = "FAIL_UNEXPECTED_ATTRIBUTE"
FAIL_UNEXPECTED_UNKNOWN = "FAIL_UNEXPECTED_UNKNOWN"
FAIL_MALFORMED_PLAN = "FAIL_MALFORMED_PLAN"
FAIL_POLICY_MISMATCH = "FAIL_POLICY_MISMATCH"

#: Deterministic precedence used to pick the headline classification when
#: several findings exist (first match wins).
FAIL_PRECEDENCE: Tuple[str, ...] = (
    FAIL_MALFORMED_PLAN,
    FAIL_UNEXPECTED_RESOURCE,
    FAIL_UNEXPECTED_ACTION,
    FAIL_UNEXPECTED_ATTRIBUTE,
    FAIL_UNEXPECTED_UNKNOWN,
    FAIL_POLICY_MISMATCH,
)

AUTHORITY_NOTICE = (
    "PASS is a technical policy match only; it grants no release, deployment, "
    "plan or apply authority. Credential authority and rotation approval are "
    "separate controls."
)

# ---------------------------------------------------------------------------
# Policy model
# ---------------------------------------------------------------------------

#: Approved CP-5 candidate backend ZIP ``source_code_hash`` (base64 SHA-256).
CP5_CANDIDATE_SOURCE_CODE_HASH = "861IQwFAXAIGW507wbNOgse3MCI12CIDbcsau8Ol5jc="

RELEASE_LAMBDA_ADDRESSES: Tuple[str, ...] = (
    "aws_lambda_function.admin",
    "aws_lambda_function.cancellation",
    "aws_lambda_function.review",
)

STRICT_POLICY_NAME = "strict-code-only-3-lambda"
ROTATION_POLICY_NAME = "stripe-test-key-rotation-3-lambda"

CONSTRAINT_EXACT_VALUE = "exact_value"
CONSTRAINT_STRIPE_TEST_SECRET_ROTATION = "stripe_test_secret_rotation"

_SOURCE_CODE_HASH: Path = ("source_code_hash",)
_LAST_MODIFIED: Path = ("last_modified",)
_STRIPE_SECRET_KEY: Path = ("environment", 0, "variables", "STRIPE_SECRET_KEY")

_BASE64_SHA256 = re.compile(r"^[A-Za-z0-9+/]{43}=$")
_STRIPE_TEST_SECRET_PREFIXES = ("sk_test_", "rk_test_")


@dataclass(frozen=True)
class Constraint:
    """A value constraint evaluated internally; its result is a boolean."""

    kind: str
    expected: Optional[str] = None


@dataclass(frozen=True)
class ResourceRule:
    address: str
    resource_type: str
    required_actions: Tuple[str, ...]
    required_changed: FrozenSet[Path]
    allowed_changed: FrozenSet[Path]
    allowed_unknown: FrozenSet[Path]
    constraints: Tuple[Tuple[Path, Constraint], ...] = ()

    def constraint_for(self, path: Path) -> Optional[Constraint]:
        for rule_path, constraint in self.constraints:
            if rule_path == path:
                return constraint
        return None


@dataclass(frozen=True)
class Policy:
    name: str
    rules: Tuple[ResourceRule, ...]
    allow_output_changes: bool = False

    def rule_for(self, address: str) -> Optional[ResourceRule]:
        for rule in self.rules:
            if rule.address == address:
                return rule
        return None


def _code_only_rule(address: str, candidate_hash: str) -> ResourceRule:
    return ResourceRule(
        address=address,
        resource_type="aws_lambda_function",
        required_actions=("update",),
        required_changed=frozenset({_SOURCE_CODE_HASH}),
        allowed_changed=frozenset({_SOURCE_CODE_HASH}),
        allowed_unknown=frozenset({_LAST_MODIFIED}),
        constraints=((_SOURCE_CODE_HASH, Constraint(CONSTRAINT_EXACT_VALUE, candidate_hash)),),
    )


def _validated_hash(candidate_hash: str) -> str:
    if type(candidate_hash) is not str or not _BASE64_SHA256.match(candidate_hash):
        raise ValueError("candidate_hash must be a base64-encoded SHA-256 digest")
    return candidate_hash


def strict_code_only_policy(candidate_hash: str = CP5_CANDIDATE_SOURCE_CODE_HASH) -> Policy:
    """Strict default: exactly 0 add / 3 change / 0 destroy, code-only.

    Per Lambda (cancellation, review, admin): action ``["update"]``;
    ``source_code_hash`` must change to exactly ``candidate_hash``;
    ``last_modified`` may become unknown; nothing else may change or be unknown.
    """
    candidate_hash = _validated_hash(candidate_hash)
    return Policy(
        name=STRICT_POLICY_NAME,
        rules=tuple(_code_only_rule(a, candidate_hash) for a in RELEASE_LAMBDA_ADDRESSES),
    )


def stripe_test_key_rotation_policy(
    *,
    rotation_separately_authorized: bool = False,
    candidate_hash: str = CP5_CANDIDATE_SOURCE_CODE_HASH,
) -> Policy:
    """Optional profile for a FUTURE owner-approved Stripe *test* key rotation.

    Never enabled by default. The caller must pass
    ``rotation_separately_authorized=True`` (the literal boolean ``True``) to
    acknowledge that credential rotation was separately authorized outside
    this tool. Plan content can never select this profile.

    Identical to the strict policy except that ``aws_lambda_function.admin``
    may additionally change exactly
    ``environment[0].variables.STRIPE_SECRET_KEY``, provided the key exists
    before and after as a non-empty string and the new value carries a Stripe
    *test-mode* prefix. The checker verifies the change path and mode only,
    never the legitimacy of any credential.
    """
    if rotation_separately_authorized is not True:
        raise ValueError(
            "rotation policy requires explicit caller selection "
            "(rotation_separately_authorized=True)"
        )
    candidate_hash = _validated_hash(candidate_hash)
    rules: List[ResourceRule] = []
    for address in RELEASE_LAMBDA_ADDRESSES:
        rule = _code_only_rule(address, candidate_hash)
        if address == "aws_lambda_function.admin":
            rule = ResourceRule(
                address=rule.address,
                resource_type=rule.resource_type,
                required_actions=rule.required_actions,
                required_changed=rule.required_changed,
                allowed_changed=rule.allowed_changed | {_STRIPE_SECRET_KEY},
                allowed_unknown=rule.allowed_unknown,
                constraints=rule.constraints
                + ((_STRIPE_SECRET_KEY, Constraint(CONSTRAINT_STRIPE_TEST_SECRET_ROTATION)),),
            )
        rules.append(rule)
    return Policy(name=ROTATION_POLICY_NAME, rules=tuple(rules))


# ---------------------------------------------------------------------------
# Result model (sanitized: paths, booleans and fixed codes only)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PathReport:
    path: str
    kind: str  # "configured" | "unknown"
    sensitive: bool
    verdict: str  # "allowed" | "rejected"


@dataclass(frozen=True)
class ResourceReport:
    address: str
    actions: Tuple[str, ...]
    expected: bool
    paths: Tuple[PathReport, ...] = ()


@dataclass(frozen=True)
class Finding:
    classification: str
    reason: str
    address: Optional[str] = None
    path: Optional[str] = None
    sensitive: Optional[bool] = None


@dataclass(frozen=True)
class CheckResult:
    classification: str
    policy_name: str
    counts: Tuple[Tuple[str, int], ...]
    resources: Tuple[ResourceReport, ...]
    findings: Tuple[Finding, ...]
    notice: str = AUTHORITY_NOTICE

    @property
    def passed(self) -> bool:
        return self.classification == PASS_EXACT_ALLOWED_DIFF

    def to_dict(self) -> Dict[str, Any]:
        """Sanitized, JSON-serializable summary (no attribute values)."""
        return {
            "classification": self.classification,
            "passed": self.passed,
            "policy": self.policy_name,
            "counts": {k: v for k, v in self.counts},
            "resources": [
                {
                    "address": r.address,
                    "actions": list(r.actions),
                    "expected": r.expected,
                    "paths": [
                        {
                            "path": p.path,
                            "kind": p.kind,
                            "sensitive": p.sensitive,
                            "verdict": p.verdict,
                        }
                        for p in r.paths
                    ],
                }
                for r in self.resources
            ],
            "findings": [
                {
                    "classification": f.classification,
                    "reason": f.reason,
                    "address": f.address,
                    "path": f.path,
                    "sensitive": f.sensitive,
                }
                for f in self.findings
            ],
            "notice": self.notice,
        }


# ---------------------------------------------------------------------------
# Sanitization
# ---------------------------------------------------------------------------

_ADDRESS_RE = re.compile(r'^[A-Za-z0-9_\-.\[\]"]{1,512}$')
_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_\-]{0,63}$")
# Key shapes that look like credential material are never echoed, even as keys.
_CREDENTIAL_LIKE_KEY = re.compile(
    r"^(sk_|rk_|pk_|whsec_|AKIA|ASIA|ghp_|gho_|github_pat_|xox[abpr]-|eyJ)",
)
_SENSITIVE_NAME = re.compile(
    r"(SECRET|TOKEN|PASSWORD|PASSWD|CREDENTIAL|PRIVATE|APIKEY|API_KEY|_KEY$|^KEY$)",
    re.IGNORECASE,
)
REDACTED_KEY = "<redacted-key>"


def _sanitize_key(key: str) -> str:
    if _KEY_RE.match(key) and not _CREDENTIAL_LIKE_KEY.match(key):
        return key
    return REDACTED_KEY


def format_path(path: Path) -> str:
    """Render a path as ``a.b[0].c`` with unsafe keys redacted."""
    if not path:
        return "<root>"
    out = ""
    for seg in path:
        if type(seg) is int:
            out += "[%d]" % seg
        else:
            safe = _sanitize_key(seg)
            out += safe if not out else "." + safe
    return out


def _is_sensitive(path: Path, before_sensitive: Any, after_sensitive: Any) -> bool:
    if nd.marker_covers(before_sensitive, path) or nd.marker_covers(after_sensitive, path):
        return True
    # Conservative overrides independent of Terraform's markers.
    if path and path[0] == "environment":
        return True
    return any(type(seg) is str and _SENSITIVE_NAME.search(seg) for seg in path)


# ---------------------------------------------------------------------------
# Plan structure validation
# ---------------------------------------------------------------------------

_KNOWN_ACTIONS = frozenset({"no-op", "create", "read", "update", "delete", "forget"})
_CHANGE_KEYS = ("before", "after", "after_unknown", "before_sensitive", "after_sensitive")


@dataclass
class _Entry:
    address: str
    mode: str
    rtype: str
    actions: Tuple[str, ...]
    # Value-bearing fields are excluded from repr so they can never leak.
    change: Dict[str, Any] = field(repr=False)
    raw: Dict[str, Any] = field(repr=False)


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise MalformedInput(reason)


def _parse_entries(plan: Any) -> List[_Entry]:
    _require(type(plan) is dict, "plan_not_object")
    if "errored" in plan:
        _require(type(plan["errored"]) is bool, "plan_errored_invalid")
        _require(plan["errored"] is False, "plan_errored")
    if "complete" in plan:
        _require(type(plan["complete"]) is bool, "plan_complete_invalid")
        _require(plan["complete"] is True, "plan_incomplete")
    _require("resource_changes" in plan, "resource_changes_missing")
    changes = plan["resource_changes"]
    _require(type(changes) is list, "resource_changes_not_list")

    entries: List[_Entry] = []
    seen: set = set()
    for rc in changes:
        _require(type(rc) is dict, "resource_change_not_object")
        address = rc.get("address")
        _require(type(address) is str and bool(_ADDRESS_RE.match(address)), "address_invalid")
        _require(address not in seen, "address_duplicate")
        seen.add(address)
        mode = rc.get("mode")
        _require(mode in ("managed", "data"), "mode_invalid")
        rtype = rc.get("type")
        _require(type(rtype) is str and bool(_KEY_RE.match(rtype)), "type_invalid")
        change = rc.get("change")
        _require(type(change) is dict, "change_missing")
        actions = change.get("actions")
        _require(type(actions) is list and len(actions) > 0, "actions_invalid")
        for action in actions:
            _require(type(action) is str and action in _KNOWN_ACTIONS, "actions_invalid")
        for key in _CHANGE_KEYS:
            _require(key in change, "change_field_missing")
        nd.validate_json_value(change["before"])
        nd.validate_json_value(change["after"])
        nd.validate_marker(change["after_unknown"])
        nd.validate_marker(change["before_sensitive"])
        nd.validate_marker(change["after_sensitive"])
        entries.append(_Entry(address, mode, rtype, tuple(actions), change, rc))
    return entries


def _output_findings(plan: Dict[str, Any], policy: Policy) -> List[Finding]:
    findings: List[Finding] = []
    if "output_changes" not in plan:
        return findings
    outputs = plan["output_changes"]
    _require(type(outputs) is dict, "output_changes_invalid")
    for name in sorted(outputs):
        _require(type(name) is str, "output_changes_invalid")
        oc = outputs[name]
        _require(type(oc) is dict, "output_changes_invalid")
        actions = oc.get("actions")
        _require(type(actions) is list and len(actions) > 0, "output_changes_invalid")
        for action in actions:
            _require(type(action) is str and action in _KNOWN_ACTIONS, "output_changes_invalid")
        if actions != ["no-op"] and not policy.allow_output_changes:
            findings.append(
                Finding(FAIL_POLICY_MISMATCH, "unexpected_output_change",
                        address="output." + _sanitize_key(name))
            )
    return findings


# ---------------------------------------------------------------------------
# Constraint evaluation (boolean results only; values never retained)
# ---------------------------------------------------------------------------


def _constraint_ok(constraint: Constraint, before: Any, after: Any, path: Path) -> Tuple[bool, str]:
    before_v = nd.value_at(before, path)
    after_v = nd.value_at(after, path)
    if constraint.kind == CONSTRAINT_EXACT_VALUE:
        ok = type(after_v) is str and after_v == constraint.expected
        return ok, "allowed" if ok else "expected_value_mismatch"
    if constraint.kind == CONSTRAINT_STRIPE_TEST_SECRET_ROTATION:
        if type(before_v) is not str or not before_v:
            return False, "rotation_before_missing_or_invalid"
        if type(after_v) is not str or not after_v:
            return False, "rotation_after_missing_or_invalid"
        if "_live_" in after_v or not after_v.startswith(_STRIPE_TEST_SECRET_PREFIXES):
            return False, "rotation_not_test_mode"
        return True, "allowed"
    return False, "unknown_constraint"


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def _counts(entries: List[_Entry]) -> Tuple[Tuple[str, int], ...]:
    add = change = destroy = replace = read = 0
    for e in entries:
        acts = set(e.actions)
        if "create" in acts and "delete" in acts:
            replace += 1
        if "create" in acts:
            add += 1
        if "delete" in acts:
            destroy += 1
        if "update" in acts:
            change += 1
        if "read" in acts:
            read += 1
    return (("add", add), ("change", change), ("destroy", destroy),
            ("replace", replace), ("read", read))


def _headline(findings: List[Finding]) -> str:
    if not findings:
        return PASS_EXACT_ALLOWED_DIFF
    present = {f.classification for f in findings}
    for code in FAIL_PRECEDENCE:
        if code in present:
            return code
    return FAIL_POLICY_MISMATCH


def _malformed(policy_name: str, reason: str) -> CheckResult:
    return CheckResult(
        classification=FAIL_MALFORMED_PLAN,
        policy_name=policy_name,
        counts=(),
        resources=(),
        findings=(Finding(FAIL_MALFORMED_PLAN, reason),),
    )


def check_plan(plan: Any, policy: Optional[Policy] = None) -> CheckResult:
    """Evaluate an in-memory Terraform plan JSON object against ``policy``.

    ``policy`` defaults to :func:`strict_code_only_policy`. Never raises for
    bad plan input; every uncertainty yields a FAIL classification.
    """
    if policy is None:
        policy = strict_code_only_policy()
    if not isinstance(policy, Policy):
        return CheckResult(FAIL_POLICY_MISMATCH, "<invalid-policy>", (), (),
                           (Finding(FAIL_POLICY_MISMATCH, "policy_invalid"),))
    try:
        return _check(plan, policy)
    except MalformedInput as exc:
        return _malformed(policy.name, exc.reason)
    except RecursionError:
        return _malformed(policy.name, "depth_exceeded")
    except Exception:  # noqa: BLE001 - fail closed without exposing anything
        return _malformed(policy.name, "internal_error")


def _check(plan: Any, policy: Policy) -> CheckResult:
    entries = _parse_entries(plan)
    findings: List[Finding] = []
    reports: List[ResourceReport] = []
    present: set = set()

    for e in entries:
        rule = policy.rule_for(e.address) if e.mode == "managed" else None
        if rule is not None:
            present.add(e.address)
            reports.append(_check_expected(e, rule, findings))
            continue

        is_noop = e.actions == ("no-op",)
        if is_noop:
            diff = nd.diff_values(e.change["before"], e.change["after"],
                                  e.change["after_unknown"])
            _require(not diff.changed and not diff.unknown, "noop_with_diff")
            continue
        reason = "pending_data_source_read" if e.mode == "data" else "unexpected_resource_change"
        findings.append(Finding(FAIL_UNEXPECTED_RESOURCE, reason, address=e.address))
        reports.append(ResourceReport(e.address, e.actions, expected=False))

    for rule in policy.rules:
        if rule.address not in present:
            findings.append(Finding(FAIL_POLICY_MISMATCH, "expected_resource_absent",
                                    address=rule.address))

    findings.extend(_output_findings(plan, policy))

    if "deferred_changes" in plan:
        deferred = plan["deferred_changes"]
        _require(type(deferred) is list, "deferred_changes_invalid")
        if deferred:
            findings.append(Finding(FAIL_UNEXPECTED_RESOURCE, "deferred_changes_present"))

    findings.sort(key=lambda f: (FAIL_PRECEDENCE.index(f.classification),
                                 f.address or "", f.path or "", f.reason))
    reports.sort(key=lambda r: r.address)
    return CheckResult(
        classification=_headline(findings),
        policy_name=policy.name,
        counts=_counts(entries),
        resources=tuple(reports),
        findings=tuple(findings),
    )


def _check_expected(e: _Entry, rule: ResourceRule, findings: List[Finding]) -> ResourceReport:
    addr = e.address
    if e.rtype != rule.resource_type:
        findings.append(Finding(FAIL_UNEXPECTED_RESOURCE, "resource_type_mismatch", address=addr))
        return ResourceReport(addr, e.actions, expected=True)
    for marker_key in ("previous_address", "importing", "deposed"):
        if marker_key in e.raw and e.raw[marker_key] not in (None, False):
            findings.append(Finding(FAIL_UNEXPECTED_ACTION, "unexpected_" + marker_key,
                                    address=addr))
            return ResourceReport(addr, e.actions, expected=True)
    if e.actions != rule.required_actions:
        reason = ("replacement" if {"create", "delete"} <= set(e.actions)
                  else "action_not_allowed")
        findings.append(Finding(FAIL_UNEXPECTED_ACTION, reason, address=addr))
        return ResourceReport(addr, e.actions, expected=True)
    replace_paths = e.change.get("replace_paths", MISSING)
    if replace_paths is not MISSING and replace_paths not in (None, []):
        findings.append(Finding(FAIL_UNEXPECTED_ACTION, "replace_paths_present", address=addr))
        return ResourceReport(addr, e.actions, expected=True)

    before = e.change["before"]
    after = e.change["after"]
    _require(type(before) is dict and type(after) is dict, "update_values_not_objects")
    diff = nd.diff_values(before, after, e.change["after_unknown"])
    bs, as_ = e.change["before_sensitive"], e.change["after_sensitive"]

    path_reports: List[PathReport] = []
    for path in sorted(diff.changed, key=nd.path_sort_key):
        sensitive = _is_sensitive(path, bs, as_)
        shown = format_path(path)
        verdict = "rejected"
        if path in rule.allowed_changed:
            constraint = rule.constraint_for(path)
            if constraint is None:
                verdict = "allowed"
            else:
                ok, reason = _constraint_ok(constraint, before, after, path)
                if ok:
                    verdict = "allowed"
                else:
                    findings.append(Finding(FAIL_POLICY_MISMATCH, reason, address=addr,
                                            path=shown, sensitive=sensitive))
        else:
            findings.append(Finding(FAIL_UNEXPECTED_ATTRIBUTE, "configured_change_not_allowed",
                                    address=addr, path=shown, sensitive=sensitive))
        path_reports.append(PathReport(shown, "configured", sensitive, verdict))

    for path in sorted(diff.unknown, key=nd.path_sort_key):
        sensitive = _is_sensitive(path, bs, as_)
        shown = format_path(path)
        if path in rule.allowed_unknown:
            verdict = "allowed"
        else:
            verdict = "rejected"
            findings.append(Finding(FAIL_UNEXPECTED_UNKNOWN, "unknown_not_allowed",
                                    address=addr, path=shown, sensitive=sensitive))
        path_reports.append(PathReport(shown, "unknown", sensitive, verdict))

    for path in sorted(rule.required_changed, key=nd.path_sort_key):
        if path not in diff.changed and path not in diff.unknown:
            findings.append(Finding(FAIL_POLICY_MISMATCH, "required_change_absent",
                                    address=addr, path=format_path(path)))

    return ResourceReport(addr, e.actions, expected=True, paths=tuple(path_reports))


# ---------------------------------------------------------------------------
# Text rendering
# ---------------------------------------------------------------------------


def render_report(result: CheckResult) -> str:
    """Human-readable sanitized report (paths, booleans and codes only)."""
    lines = [
        "CP-5J plan diff check",
        "classification: %s" % result.classification,
        "policy: %s" % result.policy_name,
        "counts: %s" % ", ".join("%s=%d" % (k, v) for k, v in result.counts),
    ]
    for r in result.resources:
        lines.append("resource: %s actions=%s expected=%s"
                     % (r.address, "/".join(r.actions), str(r.expected).lower()))
        for p in r.paths:
            lines.append("  %s %s sensitive=%s verdict=%s"
                         % (p.kind, p.path, str(p.sensitive).lower(), p.verdict))
    for f in result.findings:
        lines.append("finding: %s reason=%s address=%s path=%s"
                     % (f.classification, f.reason, f.address or "-", f.path or "-"))
    lines.append("notice: %s" % result.notice)
    return "\n".join(lines)
