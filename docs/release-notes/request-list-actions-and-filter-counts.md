# Release Notes - Admin Request List UI/UX Refinement
Date: 2026-05-01

## Overview
Improved the Admin Dashboard Request List with a more compact action menu and stable quick filter counts.

## Key Changes

### 1. Compact Row Actions
- Replaced vertically stacked action buttons with a single "Actions ▾" dropdown menu.
- Destructive actions (Cancel, Move to Trash, Permanent Delete) are now visually distinct with "dangerous" red styling inside the menu.
- All existing confirmation modals and safety gates remain intact.

### 2. Stable Filter Counts
- Fixed an issue where sidebar filter counts would reset or change when a specific filter was active.
- Counts are now calculated from the full loaded dataset in memory, ensuring they remain stable as you navigate between "Needs Action," "Approved," "Archived," etc.

### 3. Visual Spacing & Readability
- Increased vertical padding in table rows for better scanability.
- Implemented a "card-style" separation between rows using subtle borders and shadows.
- Added smooth fadeIn animations for action dropdowns.

### 4. Accessibility Improvements
- Added `aria-label` and `aria-expanded` attributes to the action triggers.
- Implemented a global click-listener to automatically close open menus when clicking outside.

## Verification Performed
- Verified that all lifecycle actions (Approve, Quote, Cancel, etc.) still trigger their respective backend workflows and modals.
- Confirmed that "Delete Permanently" still requires the "DELETE" text confirmation.
- Verified that sidebar counts do not change when toggling between filters.
- Build and deployment verified in production.
