# Release Notes: Staff and Client Management Dark-Mode Visibility Fix

## Issue
Cognito-only virtual staff/client cards had poor contrast in dark mode, appearing with a pale yellow background and low-contrast text.

## Root Cause
Static `#fff9c4` styling violated accessible contrast requirements.

## Fix
Updated layouts in `AdminDashboard.jsx`.

## Scope
Frontend optimizations.

## Deployment Proof
- CloudFront: `I35GXKR5URTLTJ7Q421RVN5K6X`
- Production URI: https://toganddogs.usmissionhero.com/admin
