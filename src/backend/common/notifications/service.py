import logging
from .config import NotificationConfig
from .templates import NotificationTemplates
from .resolver import resolve_notification_recipients, get_client_name, get_staff_name
from .ses_client import SESClient

logger = logging.getLogger(__name__)

def notify_event(event_type, record, previous_record=None):
    """
    Main entry point for dispatching notifications.
    Safe and non-blocking.
    """
    try:
        config = NotificationConfig()
        
        # 1. Resolve Recipients
        recipients = resolve_notification_recipients(event_type, record, previous_record, config)
        if not recipients:
            print(f"NOTIFICATION_IDLE: No recipients resolved for {event_type}")
            return

        # 2. Build Context (Phase 3B Expanded)
        context = {
            "client_name": get_client_name(record),
            "staff_name": get_staff_name(record),
            "request_id": record.get('request_id'),
            "pet_names": record.get('pet_names'),
            "service_type": record.get('service_type'),
            "start_date": record.get('start_date'),
            "start_time": record.get('start_time'),
            "details": record.get('details', 'No details provided.')
        }

        # 3. Get Templates
        subject, body_text, body_html = NotificationTemplates.get_template(event_type, context)
        if not subject:
            print(f"NOTIFICATION_MISSING_TEMPLATE: No template for {event_type}")
            return

        # 4. Dispatch
        client = SESClient(config)
        event_key = f"{record.get('request_id')}_{event_type}_{record.get('updated_at', 'v1')}"
        
        client.send_email(
            recipients=recipients,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            event_key=event_key
        )

    except Exception as e:
        # Crucial safety: notification failures must not block the main workflow
        logger.error(f"NOTIFICATION_CRITICAL_FAILURE: Unhandled error in notification service for {event_type}. Error: {e}")
