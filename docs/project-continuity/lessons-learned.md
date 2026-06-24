# Lessons Learned

---

## Process Lessons

| Lesson | Context |
|--------|---------|
| **Do not rely on long chat history** | Context is lost between sessions. Use docs/project-continuity/ instead. |
| **Keep plan and apply separated** | Planning is safe to commit. Apply requires explicit Matthew approval. |
| **Always remove .tfplan files from git** | Several were accidentally tracked; cleaned up in 18L hygiene. |
| **Use read-only reviews before enablement** | Enable feature flags only after confirming observability is ready (17F/17H). |
| **Do not run production smoke tests without exact data/action approval** | 18N showed that even "safe" test bookings have calendar/notification side effects. |
| **Targeted git add only** | `git add .` risks committing secrets, plans, scratch files. |
| **Document completion summaries without private data** | Counts and pass/fail only; no usernames, emails, or passwords. |

## Technical Lessons

| Lesson | Context |
|--------|---------|
| **Google Calendar cancellation race condition** | Found in 18N: child JOB# records may not inherit parent's `google_event_id` due to async timing. Fixed defensively in 18P. |
| **DEFAULT_COMPANY_ID fallback is dangerous for multi-tenant** | A Cognito user without `custom:company_id` silently routes to tog_and_dogs. Fixed via TENANT_RESOLUTION_MODE (17X/17Y). |
| **Cognito custom attributes must be added to pool schema before use** | Discovered in 17Z that the attribute didn't exist. Added in 18B. |
| **External notifications fire during admin test operations** | Omit client email on test records to prevent delivery. |
| **Stripe Checkout sessions expire in 30 minutes** | Payment links sent to clients have a 30-min window once opened. |
| **Admin offline bookings skip request-received email** | Safe path for internal testing (no notification to client). |
| **Calendar events ARE created for admin offline bookings** | Must account for cleanup when testing. |
| **Monthly booking counter uses creation date, not service date** | Simplest, most predictable billing model. |
| **Entitlement enforcement disabled by default is safe** | Phase 1 deployed with flag=false → zero production impact → enabled later. |
| **Platform admin routes use path parameters, not JWT company_id** | Platform Admin is not affected by TENANT_RESOLUTION_MODE. |

## Communication Lessons

| Lesson | Context |
|--------|---------|
| **Shared dev passwords were exposed in chat** | Must never include password values in any future doc/chat. Rotated in 17T/17U. |
| **AG should not handle or expose auth tokens** | Validated by deferring authenticated smoke to Matthew manual action. |
| **Duplicate email sends occurred due to browser + API double-action** | Documented in 12X: verify state after browser click before direct API call. |
| **Release docs should link to source release notes** | Avoid duplicating entire release content; link instead. |

---

## Anti-Patterns to Avoid

- ❌ Assuming a chat context carries forward to next session
- ❌ Running `terraform apply` without reviewing the plan output
- ❌ Committing `.tfplan` files
- ❌ Using `git add .`
- ❌ Creating bookings/clients without confirming notification behavior
- ❌ Enabling features before observability is ready
- ❌ Modifying production tenant tier/status for testing purposes
- ❌ Pasting real secrets/tokens in documentation or chat
