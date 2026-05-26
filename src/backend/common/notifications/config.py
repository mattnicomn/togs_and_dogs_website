import os

class NotificationConfig:
    """Central configuration for notifications."""
    ENABLED = os.environ.get('NOTIFICATIONS_ENABLED', 'false').lower() == 'true'
    DRY_RUN = os.environ.get('NOTIFICATION_DRY_RUN', 'true').lower() == 'true'
    EMAIL_FROM = os.environ.get('NOTIFICATION_EMAIL_FROM', 'support@usmissionhero.com')
    EMAIL_FROM_NAME = os.environ.get('NOTIFICATION_EMAIL_FROM_NAME', 'Tog & Dogs Support')
    ADMIN_EMAIL = os.environ.get('NOTIFICATION_ADMIN_EMAIL', 'mbn@usmissionhero.com')
    ROUTE_MODE = os.environ.get('NOTIFICATION_ROUTE_MODE', 'event_based')
    
    REPLY_TO = os.environ.get('NOTIFICATION_REPLY_TO', 'support@usmissionhero.com')
    PORTAL_URL = os.environ.get('NOTIFICATION_PORTAL_URL', 'https://toganddogs.usmissionhero.com')
    
    # Flags for specific events
    NOTIFY_ADMIN_ON_REQUEST_RECEIVED = os.environ.get('NOTIFY_ADMIN_ON_REQUEST_RECEIVED', 'true').lower() == 'true'
    NOTIFY_ADMIN_ON_CANCELLED = os.environ.get('NOTIFY_ADMIN_ON_CANCELLED', 'true').lower() == 'true'
    NOTIFY_ADMIN_ON_FAILED_DELIVERY = os.environ.get('NOTIFY_ADMIN_ON_FAILED_DELIVERY', 'true').lower() == 'true'
    NOTIFY_CLIENT_ON_APPROVAL = os.environ.get('NOTIFY_CLIENT_ON_APPROVAL', 'true').lower() == 'true'
    NOTIFY_CLIENT_ON_SCHEDULED = os.environ.get('NOTIFY_CLIENT_ON_SCHEDULED', 'true').lower() == 'true'
    NOTIFY_STAFF_ON_ASSIGNMENT = os.environ.get('NOTIFY_STAFF_ON_ASSIGNMENT', 'true').lower() == 'true'
    NOTIFY_CLIENT_ON_CANCELLED = os.environ.get('NOTIFY_CLIENT_ON_CANCELLED', 'true').lower() == 'true'
    NOTIFY_STAFF_ON_CANCELLED = os.environ.get('NOTIFY_STAFF_ON_CANCELLED', 'true').lower() == 'true'

    # Rate Governance (Track B)
    DAILY_CAP = int(os.environ.get('NOTIFICATION_DAILY_CAP', '100'))
    PER_MINUTE_CAP = int(os.environ.get('NOTIFICATION_PER_MINUTE_CAP', '5'))
    SES_PRODUCTION_MODE = os.environ.get('SES_PRODUCTION_MODE', 'false').lower() == 'true'

    # Delivery Mode Configuration
    # Modes: log_only | ses_sandbox | ses_production | external_provider
    NOTIFICATION_MODE = os.environ.get('NOTIFICATION_MODE', 'external_provider').lower()
    NOTIFICATION_PROVIDER = os.environ.get('NOTIFICATION_PROVIDER', 'postmark').lower()
    
    # Postmark Configuration
    POSTMARK_TOKEN_SECRET_NAME = os.environ.get('POSTMARK_SERVER_TOKEN_SECRET_NAME')
    POSTMARK_MESSAGE_STREAM = os.environ.get('POSTMARK_MESSAGE_STREAM', 'outbound')

    # Sandbox Safety
    _sandbox_allowed = os.environ.get('SES_SANDBOX_ALLOWED_RECIPIENTS', '')
    SES_SANDBOX_ALLOWED_RECIPIENTS = [email.strip().lower() for email in _sandbox_allowed.split(',') if email.strip()]

    # Testing
    TEST_RECIPIENT_OVERRIDE = os.environ.get('NOTIFICATION_TEST_RECIPIENT_OVERRIDE')

    # Postmark Quota Controls (Release 6J)
    POSTMARK_MONTHLY_LIMIT = int(os.environ.get('POSTMARK_MONTHLY_LIMIT', '100'))
    POSTMARK_QUOTA_WARN_THRESHOLD = int(os.environ.get('POSTMARK_QUOTA_WARN_THRESHOLD', '80'))
    POSTMARK_QUOTA_HARD_STOP = os.environ.get('POSTMARK_QUOTA_HARD_STOP', 'false').lower() == 'true'
