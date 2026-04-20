# Task Checklist - Togs and Dogs

## Phase 0: Discovery & Scaffolding
- [x] Assess repository and desktop environment
- [x] Define folder structure and module layout
- [x] Initialize IMPLEMENTATION_STRATEGY.md
- [ ] Initialize TASK_CHECKLIST.md (current)
- [ ] Initialize ARCHITECTURE.md
- [ ] Initialize DECISIONS_LOG.md

## Phase 1 & 2: Core Infrastructure [x]
- [x] Setup S3 Backend & DynamoDB Lock for Terraform
- [x] Define Provider configuration (Global & Aliased)
- [x] Define Tags in `locals.tf`
- [x] Deploy DynamoDB Table (Single-table design)
- [x] Deploy Cognito User Pool for Admin Dashboard
- [x] Deploy SNS Topics for Notifications

## Phase 3: Workflow & Business Logic [x]
- [x] Implement Python Lambda handlers (Intake, Review, Job, Assign)
- [x] Implement Step Functions state machine (Request Lifecycle)
- [x] Deploy API Gateway with Cognito Authorizer
- [x] Trigger Step Functions from intake submission
- [x] Refactor API Gateway to dedicated stage resource

## Phase 4: Frontend Development
- [ ] UI: Client Intake Form (Public)
- [ ] UI: Ryan's Approval Dashboard (Private/Cognito)
- [ ] UI: Basic Worker View (Private/Internal)

## Phase 5: External Integrations
- [ ] Implement Google Calendar Sync Lambda
- [ ] Setup Secrets Manager for Google API Credentials
- [ ] End-to-end testing of Intake -> Approval -> Sync flow
