# Release Notes: Staff Portal New Password Challenge

## Issue
Initial login sessions were blocked by missing support for setting permanent passwords across Cognito parameters. Sending pre-existing attributes like `phone_number` caused challenge rejections.

## Resolution
Enabled secure reset challenges:
- Password fields mapped directly.
- Emptied mutation constraints to enforce structural stability.

Production Context: https://toganddogs.usmissionhero.com/admin
