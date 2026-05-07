# Operations: Email Deliverability Controls

## 1. Overview
To maintain a high sender reputation and ensure reliable delivery of transactional notifications, Tog and Dogs implements strict deliverability controls. These controls are designed to meet AWS SES production requirements and prevent spam or abuse.

## 2. Deliverability Strategy
- **Transactional Only**: We only send emails triggered by specific user actions (e.g., booking requests) or administrative lifecycle changes (e.g., visit assignment).
- **No Marketing**: We do not use SES for newsletters, marketing campaigns, or cold outreach.
- **Opt-In by Relationship**: Recipients are limited to registered clients and staff with an active business relationship.

## 3. Feedback Loop & Suppression
### Bounce Handling
- **Soft Bounces**: Retried automatically by SES.
- **Hard Bounces**: Trigger an immediate suppression. The recipient email is added to our internal `Suppression` table, and all future sends to that address are blocked at the application level.

### Complaint Handling
- Any recipient marking an email as spam triggers a permanent suppression in our system.

### Suppression Management
- **Table**: DynamoDB `Suppression` records (PK: `SUPPRESSION#<email>`).
- **Enforcement**: The `resolver` component checks the suppression list before any email is dispatched.
- **Manual Review**: Admins can view and manage suppressions via the internal dashboard (planned).

## 4. Rate & Volume Governance
To prevent accidental spikes in volume, we enforce the following application-level limits:
- **Daily Cap**: Initially set to 100 emails/day during the staged rollout.
- **Rate Limit**: Max 5 emails per minute to ensure smooth processing.

## 5. Authentication Posture (DNS)
- **DKIM**: Enabled via AWS SES domain identity.
- **SPF**: Configured via TXT record on `toganddogs.usmissionhero.com`.
- **DMARC**: Policy set to `v=DMARC1; p=none;` initially, moving to `p=quarantine` as reputation stabilizes.
- **MAIL FROM**: Using `notifications.toganddogs.usmissionhero.com` to align with the root domain.

## 6. Staged Rollout
1. **Stage 1A**: Admin-only notifications to verified addresses.
2. **Stage 1B**: Internal staff notifications (verified accounts).
3. **Stage 2**: Limited client notifications for a subset of approved users.
4. **Stage 3**: Full production delivery.
