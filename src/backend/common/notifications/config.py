import os

class NotificationConfig:
    """Central configuration for notifications."""
    ENABLED = os.environ.get('NOTIFICATIONS_ENABLED', 'false').lower() == 'true'
    DRY_RUN = os.environ.get('NOTIFICATION_DRY_RUN', 'true').lower() == 'true'
    EMAIL_FROM = os.environ.get('NOTIFICATION_EMAIL_FROM', 'notifications@toganddogs.usmissionhero.com')
    ADMIN_EMAIL = os.environ.get('NOTIFICATION_ADMIN_EMAIL', 'mbn@usmissionhero.com')
    ROUTE_MODE = os.environ.get('NOTIFICATION_ROUTE_MODE', 'event_based')
    
    # Flags for specific events
    NOTIFY_ADMIN_ON_REQUEST_RECEIVED = os.environ.get('NOTIFY_ADMIN_ON_REQUEST_RECEIVED', 'true').lower() == 'true'
    NOTIFY_ADMIN_ON_CANCELLED = os.environ.get('NOTIFY_ADMIN_ON_CANCELLED', 'true').lower() == 'true'
    NOTIFY_ADMIN_ON_FAILED_DELIVERY = os.environ.get('NOTIFY_ADMIN_ON_FAILED_DELIVERY', 'true').lower() == 'true'
    NOTIFY_CLIENT_ON_APPROVAL = os.environ.get('NOTIFY_CLIENT_ON_APPROVAL', 'true').lower() == 'true'
    NOTIFY_CLIENT_ON_SCHEDULED = os.environ.get('NOTIFY_CLIENT_ON_SCHEDULED', 'true').lower() == 'true'
    NOTIFY_STAFF_ON_ASSIGNMENT = os.environ.get('NOTIFY_STAFF_ON_ASSIGNMENT', 'true').lower() == 'true'

    # Testing
    TEST_RECIPIENT_OVERRIDE = os.environ.get('NOTIFICATION_TEST_RECIPIENT_OVERRIDE')
