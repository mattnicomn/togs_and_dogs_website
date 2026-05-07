import logging
from .config import NotificationConfig
from .templates import NotificationTemplates
from .resolver import resolve_notification_recipients, get_client_name, get_staff_name
from .ses_client import SESClient
from .postmark_client import PostmarkClient

logger = logging.getLogger(__name__)

from datetime import datetime, timezone
from common.db import table

def get_notification_client(config):
    """Factory to get the appropriate notification client based on provider."""
    provider = config.NOTIFICATION_PROVIDER
    
    if provider == 'ses':
        return SESClient(config)
    elif provider == 'postmark':
        return PostmarkClient(config)
    else:
        # Default to SESClient which handles log_only naturally
        return SESClient(config)

def notify_event(event_type, record, previous_record=None):
    """
    Main entry point for dispatching notifications.
    Safe and non-blocking.
    Returns: { "success": bool, "message": str }
    """
    try:
        config = NotificationConfig()
        request_id = record.get('request_id')
        client_id = record.get('client_id')
        
        # 1. Duplicate Prevention for Approval
        if event_type == 'CUSTOMER_APPROVED':
            prev_status = record.get('approval_notification_status')
            if prev_status in ['Email sent.', 'Notification logged only.']:
                msg = f"Approved. Notification already sent via {record.get('approval_notification_mode', 'unknown')}."
                print(f"NOTIFICATION_SKIP: {msg}")
                return {"success": True, "message": msg}

        # 2. Resolve Recipients
        recipients = resolve_notification_recipients(event_type, record, previous_record, config)
        if not recipients:
            msg = f"Approved. No recipients resolved for {event_type}."
            print(f"NOTIFICATION_IDLE: {msg}")
            return {"success": True, "message": msg}

        from .resolver import get_pet_names
        context = {
            "client_name": get_client_name(record),
            "staff_name": get_staff_name(record),
            "request_id": request_id,
            "pet_names": get_pet_names(record),
            "service_type": record.get('service_type'),
            "start_date": record.get('start_date'),
            "start_time": record.get('start_time'),
            "details": record.get('details', 'No details provided.')
        }

        # 3. Get Templates
        subject, body_text, body_html = NotificationTemplates.get_template(event_type, context)
        if not subject:
            msg = f"Notification failed: No template for {event_type}."
            print(f"NOTIFICATION_MISSING_TEMPLATE: {msg}")
            return {"success": False, "message": msg}

        # 4. Dispatch
        client = get_notification_client(config)
        event_key = f"{request_id}_{event_type}_{record.get('updated_at', 'v1')}"
        
        result = client.send_email(
            recipients=recipients,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            event_key=event_key
        )

        # 5. Metadata Update for Approval
        if event_type == 'CUSTOMER_APPROVED' and request_id and client_id:
            try:
                now = datetime.now(timezone.utc).isoformat()
                table.update_item(
                    Key={'PK': f"REQ#{request_id}", 'SK': f"CLIENT#{client_id}"},
                    UpdateExpression="SET approval_notification_status = :s, approval_notification_sent_at = :t, approval_notification_mode = :m, approval_notification_provider = :p, approval_notification_last_message = :msg",
                    ExpressionAttributeValues={
                        ":s": result['message'],
                        ":t": now,
                        ":m": result['mode'],
                        ":p": result.get('provider', 'unknown'),
                        ":msg": result['message']
                    }
                )
            except Exception as db_err:
                print(f"WARNING: Failed to update notification metadata for {request_id}: {db_err}")

        return {"success": result.get('delivered', False) or 'logged' in result.get('message', '').lower(), "message": result['message']}

    except Exception as e:
        # Crucial safety: notification failures must not block the main workflow
        err_msg = f"Notification failed but approval was completed."
        logger.error(f"NOTIFICATION_CRITICAL_FAILURE: {e}")
        return {"success": False, "message": err_msg}
