# Release Notes: Workflow Status Map Hotfix

## Issue
Administrators experienced visibility constraints when reviewing application quotes. Records in Quoted states were visible only under “All Active” and lacked a sidebar selection. Additionally, the M&G verification mechanism failed to update target records adequately preventing correct lifecycle approvals.

## Correction
Normalized the status evaluation pipelines, injected a dedicated status navigation selector, and updated pet-level tracking requirements comprehensively.

## Scope
Modified dashboard rendering conditions and validation constraints.
- No Cognito schemas altered.
- No historical records modified.

## Verification
- Applied manual integration checks safely.
