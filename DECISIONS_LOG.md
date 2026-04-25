# Decisions Log - Togs and Dogs

| Date | Decision | Reason | Impact |
|---|---|---|---|
| 2026-04-17 | Standalone Repo | Separates pet sitting business logic from sandbox infrastructure patterns. | Cleaner codebase, independent versioning. |
| 2026-04-17 | Python Runtime | Better support for future AI/ML and Bedrock integrations; extensive AWS support. | Future-proof application logic. |
| 2026-04-17 | Cognito for Admin | Simplest secure production-safe approach for Ryan's private dashboard. | High security with low implementation overhead. |
| 2026-04-17 | Unauthenticated Intake | Maximizes conversion rate for new clients; no friction for initial request. | Requires validation and rate-limiting at the API layer. |
| 2026-04-17 | Extended Tagging | Facilitates deep cost-allocation reporting for client-billable hours. | Enhanced financial visibility for direct and indirect costs. |
| 2026-04-17 | Provider Aliasing | Leverages DNS hosted zone in sandbox account for production compute. | Avoids redundant DNS migrations; maintains central DNS control. |
| 2026-04-17 | Responsibility-based Modules | Aligned modules to functional responsibilities (data, auth, api, etc.) instead of service names. | Enhanced maintainability and clearer architectural boundaries. |
| 2026-04-17 | Admin-only Auth (MVP) | Cognito scope limited to Ryan/Admin to reduce complexity in the first phase. | Faster rollout of core coordination features. |
| 2026-04-17 | Shared Status Model | Unified workflow states (REQUEST_*, JOB_*) across DynamoDB and logic. | Prevents status drift and simplifies state machine implementation. |
| 2026-04-25 | Domain Separation | Keep toganddogs.com for marketing and toganddogs.usmissionhero.com for operations. | Preserves Ryan's marketing SEO while maintaining USMH control of the app. |
| 2026-04-25 | Portal Pivot | Replaced public marketing landing page with a lightweight branded Portal Gateway. | Clearer positioning as a professional client/admin operations platform. |
| 2026-04-25 | Multi-step Intake | Transitioned single long form to a 3-step guided experience with progress tracking. | Improved user experience and higher conversion potential for new requests. |
