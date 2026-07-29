"""
Release 6H: Configurable Protected Admin Accounts

Provides a shared interface for checking whether an email or Cognito sub
belongs to a protected admin/owner/platform account.

Configuration:
- PROTECTED_ADMIN_EMAILS: comma-separated list of protected emails (env var)
- PROTECTED_ADMIN_SUBS: comma-separated list of protected Cognito subs (env var)

Hardcoded fallback defaults are ALWAYS included regardless of env var configuration.
This ensures core platform accounts can never be accidentally unprotected.
"""
import os

# Hardcoded fallback defaults — these are ALWAYS protected.
_FALLBACK_EMAILS = [
    "admin@toganddogs.com",
    "mbn@usmissionhero.com",
    "support@usmissionhero.com",
]
_FALLBACK_SUBS = [
    "74b86488-1011-7029-bb6d-dad984e1463c",
]


def get_protected_emails():
    """Returns the full list of protected emails (env var + fallback defaults)."""
    raw = os.environ.get('PROTECTED_ADMIN_EMAILS', '')
    configured = [e.strip().lower() for e in raw.split(',') if e.strip()]
    combined = set(configured) | set(_FALLBACK_EMAILS)
    return list(combined)


def get_protected_subs():
    """Returns the full list of protected Cognito subs (env var + fallback defaults)."""
    raw = os.environ.get('PROTECTED_ADMIN_SUBS', '')
    configured = [s.strip() for s in raw.split(',') if s.strip()]
    combined = set(configured) | set(_FALLBACK_SUBS)
    return list(combined)


def is_protected_email(email):
    """Returns True if the email belongs to a protected account."""
    if not email:
        return False
    return email.lower().strip() in get_protected_emails()


def is_protected_sub(sub):
    """Returns True if the Cognito sub belongs to a protected account."""
    if not sub:
        return False
    return sub.strip() in get_protected_subs()


def is_config_protected(profile):
    """Returns True if the profile matches any env/fallback config protected identifier."""
    if not profile:
        return False
    if is_protected_sub(profile.get('cognito_sub')):
        return True
    if is_protected_email(profile.get('email')):
        return True
    return False


def is_platform_protected(profile):
    """Returns True if the profile record has is_platform_protected set to True in DynamoDB."""
    if not profile:
        return False
    return profile.get('is_platform_protected') is True


def is_protected_profile(profile):
    """Returns True if the profile matches any protected identifier (data-driven DB flag or config fallback)."""
    if not profile:
        return False
    if is_platform_protected(profile):
        return True
    return is_config_protected(profile)
