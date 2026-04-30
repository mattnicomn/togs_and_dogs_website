# Release Notes: Admin Quick Filter Simplification

## Overview
- **Issue**: The admin quick-filter sidebar grew too crowded, mixing active operational tasks, granular meet-and-greet sub-states, and terminal/history workflows.
- **Solution**: Reorganized filter controls into consolidated functional groupings.

## Component Breakdowns

### 1. The "Needs Action" Aggregator
The sidebar introduces a derived **Needs Action** navigation node combining:
- `PENDING_REVIEW` / `NEEDS_REVIEW`
- `MEET_GREET_REQUIRED` / `NEEDS_MG`
- `QUOTE_NEEDED`
- `APPROVED` / `BOOKED`
- `CANCELLATION_REQUESTED`

### 2. M&G / Quote Lifecycle Sub-States
`MG_SCHEDULED`, `MG_COMPLETED`, and separate quote checks have been completely removed from sidebar persistence. Visibility is supported naturally through underlying card details.

## Build and Deployment Details
- **Build Outcome**: Successful compilation without asset warnings.
- **CloudFront Invalidations**: N/A.
