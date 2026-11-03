"""Adapter package: the orchestrator's pluggable boundaries to external agents.

In A1 every concrete adapter is a MOCK. The protocols in :mod:`base` define the
interface that an eventual live adapter (e.g. a headless ``kiro-cli`` adapter
driven over ``--output-format stream-json``, or a live OpenAI reviewer) would
implement in A2. No concrete adapter in A1 performs any network, filesystem
mutation of the repo, or process execution.
"""
