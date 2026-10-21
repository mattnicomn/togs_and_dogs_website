# M4-C — Client Decline Acceptance (one controlled production Decline)

**Disposition:** `M4_C_DECLINE_ACCEPTANCE_PASS`
**Date:** 2026-10-21
**Authoritative checkpoint:** `main == origin/main == e5366df02905d89b9e612c62aa1fbb9fe9765348`

## Summary

Owner-authorized, one-time client **Decline** of the established safe M4 production test
quote was performed by Matthew in the mobile app and accepted via owner-supplied on-device
evidence. Exactly one Decline occurred; no Accept, no Send/Resend, no second Decline.
`M4_C_DECLINE_AUTHORIZED` is now **CONSUMED** — no further client mutation is authorized.

## Authorization scope

- Authorized: exactly one `SENT → DECLINED` client Decline on the existing safe M4 test quote,
  plus read-only verification.
- NOT authorized (and not performed): Accept, Send/Resend, quote-amount edit, booking approval,
  payment mutation, Stripe change, scheduling work, Ryan testing, second tenant, tenant-resolution
  change, mobile distribution, Terraform, Lambda/API deployment, production test-data creation.

## Pre-Decline state (recorded)

Prior to the action the safe M4 test quote was (per M4-B PASS, 2026-10-20): status SENT,
amount `$200.00` (20000 cents), payment requirement NONE, Accept + Decline visible, no crash.

## Action

Matthew pressed **Decline exactly once** in the already-installed mobile client on the safe M4
test request. No Accept pressed; no automatic retry; no second mutation.

## Verification — evidence basis and results

Evidence basis: owner-supplied **mobile (on-device) post-Decline observation** plus the owner's
attestation of the single action. No independent backend/DynamoDB record read was performed
(no request PK/SK, client ID, or auth token was requested, provided, or used).

UI / owner-observed results:

- `M4_C_DECLINE_TRANSITION=PASS` — quote now shows the **DECLINED** state.
- Amount remains `$200.00` (unchanged).
- Payment requirement remains NONE / "No payment required".
- `M4_C_MOBILE_DECLINED_STATE=PASS` — mobile renders the declined state; no crash.
- Accept / Decline are no longer presented as valid second actions (first-action-wins reflected
  in the UI). No second mutation was attempted to test the 409 path in production.
- No booking became APPROVED; no payment record/mutation; no Stripe mutation; no unexpected
  notification/payment side effect was observed from the available evidence.

### Evidence limitation (explicit, not independently proven by the agent)

The following contract expectations are **attested by the backend contract + owner observation**,
NOT independently verified by the agent from non-sensitive evidence (no backend record was read):
`quote_revision` unchanged on decline; exact `quote_declined_at` timestamp present / `quote_accepted_at`
absent at the record level. These are expected per `common/quote_contract.apply_quote_decline`
(SENT→DECLINED, revision not incremented, acceptance fields not set) but are recorded here as
contract-expected rather than agent-verified.

## Result

- `M4_C_RESULT=PASS`
- `M4_C_DECLINE_AUTHORIZED=CONSUMED` (the one approved Decline is used; no further client mutation authorized)
- No Accept performed, before or after.

## Gates preserved

- `M4_B_RESULT=PASS` (unchanged).
- Scheduling parked: `SCHEDULING_WORKSTREAM_STATUS=DRAFT_PR_DELIVERY_CHECKPOINT`,
  `SCHEDULING_PR_MERGE_AUTHORIZED=NO`.
- Stripe sandbox-only; Ryan testing NO; no second tenant; no tenant-resolution change; no mobile
  distribution; no production test data; no Terraform / Lambda / API deployment.
- Production backend remains the PR #19 release (13 Lambdas on
  `QgEdTeYYMYF3k+b4f22NoHv2I7GEowtO1ynQ7ISafVk=`); rollback (`ce6b724` + `gBjdlXDUn0…`) preserved.
