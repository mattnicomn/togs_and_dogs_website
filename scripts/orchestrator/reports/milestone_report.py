"""Structured milestone report + mandatory owner-gate rendering.

Produces both a machine-readable dict and a human-readable text block. All text
is passed through redaction before return, so a report can never carry a secret
or PII even if an upstream field was careless.
"""

from __future__ import annotations

from typing import Any

from .. import redaction
from ..loop import LoopResult


def build_report(result: LoopResult) -> dict[str, Any]:
    """Return a sanitized, serializable milestone report dict."""

    state = result.state
    pr = result.draft_pr
    report: dict[str, Any] = {
        "scope_id": state.scope_id,
        "repository": state.repository,
        "base_sha": state.base_sha,
        "target_branch": state.target_branch,
        "final_phase": state.phase,
        "stop_reason": result.stop_reason,
        "milestone_complete": result.milestone_complete,
        "iterations": state.iteration,
        "usage": result.usage,
        "performed_effects": list(state.performed_effects),
        "draft_pr": None
        if pr is None
        else {
            "number": pr.number,
            "url": pr.url,
            "is_draft": pr.is_draft,
            "is_open": pr.is_open,
            "is_merged": pr.is_merged,
            "base": pr.base,
            "head": pr.head,
        },
    }
    return redaction.redact_obj(report)


def render_text(result: LoopResult) -> str:
    """Render the human-readable milestone summary + owner gate."""

    r = build_report(result)
    pr = r["draft_pr"]
    pr_line = "none" if pr is None else f"#{pr['number']} {pr['url']} (draft={pr['is_draft']}, merged={pr['is_merged']})"
    gate = (
        "MANDATORY OWNER STOP: milestone complete — a fresh, separate owner "
        "approval is required before any further scope runs."
        if r["milestone_complete"]
        else f"STOPPED: {r['stop_reason']}"
    )
    lines = [
        f"MILESTONE SUMMARY  {r['scope_id']}",
        f"  repository:    {r['repository']}",
        f"  base_sha:      {r['base_sha']}",
        f"  target_branch: {r['target_branch']}",
        f"  final_phase:   {r['final_phase']}",
        f"  iterations:    {r['iterations']}",
        f"  usage:         {r['usage']}",
        f"  draft_pr:      {pr_line}",
        f"  effects:       {r['performed_effects']}",
        f"  {gate}",
    ]
    return redaction.redact("\n".join(lines))
