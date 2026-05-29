# Tog & Dogs Operations Portal — Documentation

**Last Updated:** Release 7U  
**Latest Closed Release:** Release 7T — Matthew Production Monitoring Checklist  

This hub is the starting point for navigating all operational guides, monitoring checklists, validation checklists, release notes, and project-control documents for the Tog & Dogs Operations Portal.

---

## Quick Start by Role

### 👤 Ryan — Business Owner / Admin

| Document | Purpose |
|---|---|
| [Admin Operations Quick Reference](operations/admin-quick-reference.md) | Daily admin workflows, status guide, booking lifecycle |
| [Ryan Production Trial Handoff](operations/ryan-production-trial-handoff.md) | Controlled rollout plan and Week 1/Week 2 trial checklist |
| [Emergency Response Checklist](operations/emergency-response-checklist.md) | Step-by-step incident response for outages, sync failures, and data issues |
| [Offline Client Management Guide](operations/offline-client-management-guide.md) | Managing clients who prefer phone/text — manual booking workflows |

---

### 🛠️ Matthew — Developer / Technical Support

| Document | Purpose |
|---|---|
| [Matthew's Monitoring Checklist](operations/matthew-monitoring-checklist.md) | Daily/weekly production monitoring with exact AWS commands and action thresholds |
| [Release Checklist](project-control/release-checklist.md) | Pre-deploy and post-deploy validation steps for every code release |
| [Notification System Runbook](operations/notification-system-runbook.md) | Postmark quota, suppression management, and notification kill switches |
| [Google Calendar Reauthorization](operations/google-calendar-reauthorization.md) | How to reconnect Google Calendar after token expiry |
| [Postmark Setup](operations/postmark-setup.md) | Postmark account and stream configuration reference |
| [Email Deliverability Controls](operations/email-deliverability-controls.md) | Suppression, bounce management, and deliverability settings |
| [Terraform Drift Reconciliation](operations/terraform-drift-reconciliation.md) | How to detect and resolve Terraform state drift |

---

### 🤖 Development Agents — AG / Kiro

| Document | Purpose |
|---|---|
| [Agent Operating Model](project-control/agent-operating-model.md) | Guardrails, release workflow, and agent operating rules |
| [Validation Playbook](project-control/validation-playbook.md) | How to run pre-deploy and post-deploy validation passes |
| [Production Smoke Test Checklist](validation/production-smoke-test-checklist.md) | Repeatable E2E manual smoke test for all core booking scenarios |
| [Task Tracker](project-control/task-tracker.md) | Active and backlog task tracking |
| [Decision Log](project-control/decision-log.md) | Key architectural and operational decisions with rationale |
| [Lessons Learned](project-control/lessons-learned.md) | Post-release observations and process improvements |

---

## Directory Guide

| Directory | Contents | Primary Audience |
|---|---|---|
| `operations/` | Runbooks, monitoring checklists, emergency response, offline client guide, Google Calendar and Postmark guides | Ryan, Matthew |
| `planning/` | Release planning documents, implementation plans, backlog items, strategy docs | AG, Kiro, Matthew |
| `release-notes/` | Validation closeout notes, release summaries, and the full project history index | All |
| `validation/` | Production smoke test checklists and production validation reports | Matthew, AG, Kiro |
| `project-control/` | Agent operating model, release checklist, task tracker, decision log, lessons learned | AG, Kiro, Matthew |
| `archive/` | Historical notes, superseded documents, and legacy branding updates | Reference only |

---

## Key Operational Guides

| Guide | Link |
|---|---|
| Admin Operations Quick Reference | [operations/admin-quick-reference.md](operations/admin-quick-reference.md) |
| Offline Client Management | [operations/offline-client-management-guide.md](operations/offline-client-management-guide.md) |
| Notification System Runbook | [operations/notification-system-runbook.md](operations/notification-system-runbook.md) |
| Emergency Response Checklist | [operations/emergency-response-checklist.md](operations/emergency-response-checklist.md) |
| Matthew's Monitoring Checklist | [operations/matthew-monitoring-checklist.md](operations/matthew-monitoring-checklist.md) |
| Terraform Drift Reconciliation | [operations/terraform-drift-reconciliation.md](operations/terraform-drift-reconciliation.md) |

---

## Architecture & Data Model

| Document | Link |
|---|---|
| Data Model Reference | [datamodel.md](datamodel.md) |
| Mobile App Strategy | [planning/mobile-app-strategy.md](planning/mobile-app-strategy.md) |

---

## Release History

Full release history: **[release-notes/index.md](release-notes/index.md)**

**Latest closed release:** Release 7T — Matthew Production Monitoring Checklist (`e998a82`)

Recent closed releases (newest first):

| Release | Description | Type |
|---|---|---|
| [7T](release-notes/release-7t-validation-closeout.md) | Matthew Production Monitoring Checklist | Docs only |
| [7S](release-notes/release-7s-validation-closeout.md) | Internal Hardening Tests + gitignore cleanup | Tests + gitignore |
| [7Q](release-notes/release-7q-validation-closeout.md) | Production Operations Readiness | Docs only |
| [7P](release-notes/release-7p-validation-closeout.md) | Admin/Mobile UX Polish + accessibility | Frontend |
| [7N](release-notes/release-7n-validation-closeout.md) | Terms & Privacy Policy Content | Frontend |
| [7M](release-notes/release-7m-validation-closeout.md) | Planning & Strategy Consolidation | Docs only |
| [7L](release-notes/release-7l-admin-request-list-compact-date-display-polish-validation.md) | Admin Request List Compact Date Display | Frontend |
