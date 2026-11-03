"""Mock GitHub / Draft-PR adapter (A1 — fully offline).

NO ``gh``, NO ``git push``, NO GitHub API, NO merge. The adapter only records
that a Draft PR *would* be opened and returns a synthetic
:class:`DraftPRResult`. It deliberately refuses to model a merged or
non-draft PR: in A1 the orchestrator must never represent a merge.

Finding 3 (side-effect recovery): the adapter supports an **idempotency key**
so the orchestrator can (a) avoid creating a duplicate when it is uncertain
whether a prior call succeeded, and (b) reconcile a "pending" operation after a
crash by looking the PR up by that key. ``open_draft_pr`` is idempotent on the
key: calling it twice with the same key returns the same recorded PR instead of
opening a second one.

The orchestrator itself never calls real git/gh. Delivery of the A1 branch and
its real Draft PR is a SEPARATE, explicitly owner-authorized manual git
workflow performed outside this package (see the A1 instructions).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .base import DraftPRResult


@dataclass
class MockGitHubAdapter:
    """Records Draft-PR open calls keyed by idempotency key.

    ``fail_before_record`` / ``fail_after_record`` let tests simulate a crash
    at the two dangerous instants (before the external effect is recorded, and
    after the effect succeeded but before the caller confirmed it).
    """

    next_number: int = 9001
    opened: list[DraftPRResult] = field(default_factory=list)
    # idempotency_key -> DraftPRResult (the adapter's own server-side record)
    by_key: dict[str, DraftPRResult] = field(default_factory=dict)
    # Test hooks to simulate a crash inside the external call.
    fail_before_record: bool = False
    fail_after_record: bool = False

    def open_draft_pr(
        self, *, base: str, head: str, title: str, body: str, idempotency_key: str
    ) -> DraftPRResult:
        # Idempotent on the key: a repeat call returns the existing record and
        # never opens a second PR (this is what makes reconciliation safe).
        existing = self.by_key.get(idempotency_key)
        if existing is not None:
            return existing

        if self.fail_before_record:
            raise RuntimeError("simulated crash BEFORE the PR was recorded")

        number = self.next_number
        self.next_number += 1
        result = DraftPRResult(
            number=number,
            url=f"mock://pull/{number}",
            is_draft=True,
            is_open=True,
            is_merged=False,  # A1 never models a merged PR
            base=base,
            head=head,
        )
        # Record the server-side effect FIRST (this is the durable side effect).
        self.by_key[idempotency_key] = result
        self.opened.append(result)

        if self.fail_after_record:
            # The effect succeeded on the "server" but the caller never learns
            # the result (crash in transit). Reconciliation must recover it.
            raise RuntimeError("simulated crash AFTER success, before confirmation")

        return result

    def find_by_idempotency_key(self, idempotency_key: str) -> DraftPRResult | None:
        """Reconciliation lookup: did a PR for this key already get created?"""

        return self.by_key.get(idempotency_key)
