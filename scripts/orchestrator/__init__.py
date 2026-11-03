"""PetCare Hero AI Development Orchestrator (A1 isolated offline prototype).

This package is an isolated, fully offline supervised-development orchestrator
prototype. In A1 every external agent (Kiro, OpenAI, GitHub) is MOCKED. There
are no network calls, no installs, no live agent execution, and no production
actions anywhere in this package.

Security posture (enforced in code, not prompt text):
  * Authorization originates only from an owner-controlled approval manifest
    that lives OUTSIDE agent-writable paths (see ``manifest`` and ``config``).
  * An AI-produced file, PR comment, repo document, or mock result can NEVER
    constitute authorization.
  * Fail-closed: anything missing, ambiguous, out-of-scope, over-budget, or
    tampered halts the loop.

See ``docs/planning/petcare-hero-ai-dev-orchestrator-a0-architecture.md`` for the
architecture and the A0/A0.1 readiness findings this prototype is built on.
"""

__all__ = ["__version__"]

# A1 prototype version. Independent of any product/release version.
__version__ = "0.1.0-a1"
