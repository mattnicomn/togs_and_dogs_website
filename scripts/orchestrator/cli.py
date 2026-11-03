"""Local CLI for the A1 orchestrator prototype: dry-run / status / resume.

Everything here is OFFLINE and MOCKED. ``dry-run`` executes the full mocked
loop against synthetic fixtures; ``status`` prints the durable state; ``resume``
re-enters the loop from the persisted checkpoint (used to demonstrate crash
recovery and the mandatory owner gate after restart).

This CLI never calls real kiro-cli, OpenAI, gh, git, or the network.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import errors
from .adapters.base import Task
from .adapters.github_adapter import MockGitHubAdapter
from .adapters.kiro_adapter import MockKiroAdapter
from .adapters.openai_adapter import MockOpenAIReviewer
from .config import Budgets, load_config
from .loop import Orchestrator
from .manifest import TaskRequest, load_manifest
from .reports import milestone_report
from .state import StateStore


def _build_orchestrator(args: argparse.Namespace):
    config = load_config(
        runtime_dir=args.runtime_dir,
        approvals_dir=args.approvals_dir,
    )
    if args.max_corrections is not None:
        config = config.with_budgets(Budgets(max_correction_retries=args.max_corrections))
    manifest = load_manifest(args.manifest, config)
    request = TaskRequest(
        scope_id=manifest.scope_id,
        repository=manifest.repository,
        base_sha=manifest.base_sha,
        target_branch=manifest.target_branch,
    )
    task = Task(
        scope_id=manifest.scope_id,
        description=args.task_description,
        target_paths=tuple(args.target_path or ()),
        acceptance_key=args.acceptance_key,
    )
    orch = Orchestrator(
        config=config,
        manifest=manifest,
        kiro=MockKiroAdapter(fixture_path=Path(args.kiro_fixture)),
        reviewer=MockOpenAIReviewer(fixture_path=Path(args.openai_fixture)),
        github=MockGitHubAdapter(),
    )
    return orch, request, task


def _run_loop(args: argparse.Namespace) -> int:
    try:
        orch, request, task = _build_orchestrator(args)
    except errors.OrchestratorStop as stop:
        # Authorization/manifest failures happen before a loop exists.
        print(f"STOP: {stop.reason_code}: {stop.detail}", file=sys.stderr)
        return 2
    try:
        result = orch.run(request, task)
        print(milestone_report.render_text(result))
        return 0
    except errors.MilestoneOwnerStop:
        # Expected success terminal: render from persisted state.
        result = orch.build_result(orch.state_store.load(), "MILESTONE_OWNER_STOP")
        print(milestone_report.render_text(result))
        return 0
    except errors.OrchestratorStop as stop:
        print(f"STOP: {stop.reason_code}: {stop.detail}", file=sys.stderr)
        return 2


def cmd_dry_run(args: argparse.Namespace) -> int:
    return _run_loop(args)


def cmd_resume(args: argparse.Namespace) -> int:
    return _run_loop(args)


def cmd_status(args: argparse.Namespace) -> int:
    # status reads local state only and never loads a manifest, so it does not
    # require an owner-controlled approvals source to be configured.
    config = load_config(
        runtime_dir=args.runtime_dir,
        approvals_dir=args.approvals_dir,
        require_approvals=False,
    )
    store = StateStore(config.state_path)
    if not store.exists():
        print("no state found", file=sys.stderr)
        return 1
    print(json.dumps(store.load().to_dict(), indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="petcare-orchestrator", description=__doc__)
    p.add_argument("--runtime-dir", default=None, help="agent-writable runtime dir (.orchestrator/)")
    p.add_argument("--approvals-dir", default=None, help="owner-controlled approvals dir")
    sub = p.add_subparsers(dest="command", required=True)

    def add_common(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--manifest", required=True, help="path to owner approval manifest")
        sp.add_argument("--kiro-fixture", required=True, help="synthetic kiro JSONL fixture")
        sp.add_argument("--openai-fixture", required=True, help="synthetic openai review fixture")
        sp.add_argument("--task-description", default="A1 synthetic task")
        sp.add_argument("--target-path", action="append", help="repo-relative path (repeatable)")
        sp.add_argument("--acceptance-key", default="needs_marker")
        sp.add_argument("--max-corrections", type=int, default=None)

    sp_dry = sub.add_parser("dry-run", help="run the full mocked loop")
    add_common(sp_dry)
    sp_dry.set_defaults(func=cmd_dry_run)

    sp_res = sub.add_parser("resume", help="resume from the persisted checkpoint")
    add_common(sp_res)
    sp_res.set_defaults(func=cmd_resume)

    sp_stat = sub.add_parser("status", help="print durable state")
    sp_stat.set_defaults(func=cmd_status)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
