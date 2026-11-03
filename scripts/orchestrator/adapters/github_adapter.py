"""Mock GitHub / Draft-PR adapter (A1 — fully offline).

NO ``gh``, NO ``git push``, NO GitHub API, NO merge. The adapter only records
that a Draft PR *would* be opened and returns a synthetic
:class:`DraftPRResult`. It deliberately refuses to model a merged or
non-draft PR: in A1 the orchestrator must never represent a merge.

The orchestrator itself never calls real git/gh. Delivery of the A1 branch and
its real Draft PR is a SEPARATE, explicitly owner-authorized manual git
workflow performed outside this package (see the A1 instructions), not
something this prototype automates.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .base import DraftPRResult


@dataclass
class MockGitHubAdapter:
    """Records Draft-PR open calls; returns a synthetic draft/open/unmerged PR."""

    next_number: int = 9001
    opened: list[DraftPRResult] = field(default_factory=list)

    def open_draft_pr(
        self, *, base: str, head: str, title: str, body: str
    ) -> DraftPRResult:
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
        self.opened.append(result)
        return result
