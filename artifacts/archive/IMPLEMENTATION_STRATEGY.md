# Implementation Strategy - Togs and Dogs

Building a serverless, automated pet sitting client intake and scheduling system for Ryan York.

## Project Overview
This system provides a private intake and approval workflow that captures client and pet data, manages service requests, and synchronizes approved bookings with Google Calendar while maintaining worker coordination as a first-class feature.

## Business Goals
- **Automate Intake**: Replace manual phone/text/email intake with a structured form.
- **Privacy by Design**: Allow requests without showing Ryan's actual calendar availability.
- **Worker Coordination**: Support manual and eventually assisted assignments for Ryan, his wife, and nephews.
- **Operational Simplicity**: Minimize overhead using AWS Serverless technologies.

## Non-Goals (MVP)
- Public customer accounts/login.
- Worker self-service portal.
- Payment processing.
- Automated route optimization.

## Tagging & Billing Standard
We enforce a strict tagging standard for cost allocation and billing transparency.

| Tag Key | Purpose | Required | Example |
|---|---|---|---|
| `Environment` | SDLC Stage | Yes | `prod`, `sandbox` |
| `ManagedBy` | Infrastructure Tool | Yes | `terraform` |
| `Name` | Resource Identity | Yes | `ClientTable`, `IntakeLambda` |
| `Repo` | Source Control Link | Yes | `togs_and_dogs_website` |
| `Usage` | Technical Purpose | Yes | `data`, `api`, `observability` |
| `Client` | Business Owner | Yes | `TogAndDogs` |
| `Application` | Project Name | Yes | `PetScheduling` |
| `Component` | Architectural Layer | Yes | `frontend-hosting`, `api`, `workflow`, `data`, `auth`, `secrets`, `notifications`, `observability` |
| `CostCenter` | Financial Allocation | Yes | `ClientBillable` |
| `BillingModel` | Revenue Model | Yes | `Direct` |

## Deployment Strategy
- **Infrastructure as Code**: Terraform 1.5+.
- **Profiles**: Using `usmissionhero-website-prod` (Workload) and `website-infra-sandbox` (DNS).
- **Remote State**: Dedicated S3 bucket and DynamoDB lock table in the `usmissionhero-website-prod` account.
- **Backend Runtime**: Python 3.11+.
- **Frontend**: S3 Static Website + CloudFront.
- **CI/CD**: Manual first-pass deployment from local desktop via SSO.

## Definition of Done (MVP)
- [ ] Clients can submit an unauthenticated intake form.
- [ ] Ryan receives a notification for new requests.
- [ ] Ryan can approve/decline requests via a Cognito-secured dashboard.
- [ ] Approved requests automatically create a Google Calendar event.
- [ ] Approved requests are assigned to a worker and tracked in DynamoDB.
