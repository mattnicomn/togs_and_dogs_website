# Release Note: Process Workflow Guided Actions

## Summary
The Admin Process Workflow modal has been refined to provide a more intuitive, guided experience. Instead of presenting all possible lifecycle transitions as equal-weight buttons, the interface now prioritizes the most logical next step while organizing alternatives into a structured menu.

## Changes
- **Guided UI**: The Process Workflow modal now identifies and displays one recommended "Primary" action (e.g., "Approve" or "Mark M&G Complete") as a prominent button.
- **More Actions Dropdown**: Exception paths, rework actions (going backward), and destructive actions are now neatly organized within a "More Actions" dropdown.
- **Clarified Terminology**:
  - Modal dismissal has been renamed from **Cancel** to **Close** to avoid ambiguity.
  - The lifecycle status action **Cancel** has been renamed to **Cancel Request**.
- **Dangerous Action Visibility**: Actions like "Cancel Request" and "Move to Trash" are now visually distinct within the "More Actions" menu.
- **Preserved Safety**: All existing backend validation rules, status transition gates (M&G, Quoting), and confirmation safeguards remain fully in effect.

## Scope
- Affected Component: AdminDashboard (Process Workflow Modal)
- Environment: Production
- URL: [https://toganddogs.usmissionhero.com/admin](https://toganddogs.usmissionhero.com/admin)

## Technical Details
- No changes to infrastructure, APIs, or database schema.
- Deployment via S3 frontend sync and CloudFront invalidation.
