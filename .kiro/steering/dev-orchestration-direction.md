---
inclusion: fileMatch
fileMatchPattern: ["scripts/orchestrator/**", "tests/orchestrator/**", ".github/workflows/orchestrator-ci.yml", "docs/planning/*orchestrat*"]
---

# Development orchestration direction (Issue #94)

- **Preferred direction (PROPOSED, not authorized):** use Kiro Crew for development-agent coordination, with a small, independently enforced governance layer. See `docs/planning/petcare-dev-orchestration-kiro-crew-adr-proposal.md`.
- **Separation:** this initiative is separate from Togs & Dogs product milestones. Never mix it into pilot PRs.
- **Preserve prior work:** orchestrator PRs #60, #63, #64, #65 and #66 (and #61, merged into #60's branch) stay open and unmerged as reference. Do not delete, retarget or replace them until the reuse map (ADR phase M2) is approved.
- **Without explicit owner authorization, do not:**
  - install or run Kiro Crew
  - start unattended agents
  - read secrets
  - change AWS, GitHub protection or IAM settings
  - merge or deploy
- **Approvals:** merge and deployment are separate owner approvals. No agent approves its own work or edits its own guards or manifests.
