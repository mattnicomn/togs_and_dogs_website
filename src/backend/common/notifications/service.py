import logging
import json
from .config import NotificationConfig
from .templates import NotificationTemplates
from .resolver import resolve_notification_recipients, get_client_name, get_staff_name
from .ses_client import SESClient
from .postmark_client import PostmarkClient

logger = logging.getLogger(__name__)

from datetime import datetime, timezone
from common.db import table

def get_notification_client(config):
    """
    Factory to get the appropriate notification client based on provider.
    Strictly prioritizes Postmark in production.
    """
    provider = config.NOTIFICATION_PROVIDER
    
    if provider == 'postmark':
        return PostmarkClient(config)
    elif provider == 'ses':
        # SES is currently restricted to sandbox/explicit enablement
        return SESClient(config)
    elif provider == 'log_only':
        return SESClient(config)
    else:
        # If unknown, default to log_only via SESClient to prevent accidental delivery
        logger.warning(f"NOTIFICATION_CONFIG_WARNING: Unknown provider '{provider}'. Defaulting to log_only.")
        config.NOTIFICATION_MODE = 'log_only'
        return SESClient(config)

def _get_monthly_send_count(month_key):
    """Retrieves the current monthly send count from DynamoDB. Non-blocking."""
    try:
        from common.db import get_item
        item = get_item("QUOTA#tog_and_dogs", f"MONTH#{month_key}")
        if item:
            return int(item.get('sent_count', 0))
        return 0
    except Exception as e:
        print(f"WARNING: Failed to fetch monthly send quota count: {e}")
        return 0


def _increment_monthly_send_count(month_key):
    """Atomically increments the monthly send count in DynamoDB. Non-blocking."""
    try:
        from common.db import table
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        table.update_item(
            Key={"PK": "QUOTA#tog_and_dogs", "SK": f"MONTH#{month_key}"},
            UpdateExpression="ADD sent_count :inc SET updated_at = :now, entity_type = :type",
            ExpressionAttributeValues={
                ":inc": 1,
                ":now": now,
                ":type": "QUOTA_COUNTER"
            }
        )
    except Exception as e:
        print(f"WARNING: Failed to increment monthly send quota count: {e}")


def _write_ledger_entry(request_id, event_type, recipient, status, provider=None, provider_message_id=None, error_message=None, record=None):
    """
    Writes a single audit record to the Notification Ledger (DynamoDB).
    Completely isolated and non-blocking.
    """
    try:
        import uuid
        from datetime import datetime, timezone
        from common.db import put_item

        # Use provider_message_id as notification_id if present to make webhook queries trivial!
        notification_id = provider_message_id if provider_message_id else str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        month_key = created_at[:7] # YYYY-MM

        company_id = "tog_and_dogs"
        if record and isinstance(record, dict):
            company_id = record.get('company_id') or "tog_and_dogs"

        ledger_item = {
            "PK": f"NOTIF#{notification_id}",
            "SK": f"REQUEST#{request_id or 'UNKNOWN'}",
            "entity_type": "NOTIFICATION_LEDGER",
            "notification_id": notification_id,
            "request_id": request_id or "UNKNOWN",
            "event_type": event_type,
            "recipient_email": recipient.strip().lower() if recipient else "unknown",
            "status": status,
            "provider": provider or "log_only",
            "provider_message_id": provider_message_id,
            "error_message": error_message,
            "company_id": company_id,
            "month_key": month_key,
            "created_at": created_at
        }

        put_item(ledger_item)
        return notification_id
    except Exception as e:
        print(f"WARNING: Notification Ledger write failed: {e}")
        return None


def _is_recent_duplicate(event_type, recipient, request_id, window_minutes=5):
    """
    Checks the notification ledger for a recent send matching the same
    event_type + recipient + request_id within the dedup window.
    Returns True if a duplicate exists (should skip), False otherwise.
    Fail-open: if the query fails, returns False (allow send).
    """
    if not request_id or not recipient or not event_type:
        return False
        
    try:
        from common.db import table
        from boto3.dynamodb.conditions import Key, Attr
        from datetime import datetime, timezone, timedelta
        
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=window_minutes)).isoformat()
        recipient_clean = recipient.strip().lower()
        
        # Check for 'sent' status
        resp = table.query(
            IndexName='StatusIndex',
            KeyConditionExpression=Key('status').eq('sent'),
            FilterExpression=Attr('request_id').eq(request_id) & 
                             Attr('event_type').eq(event_type) & 
                             Attr('recipient_email').eq(recipient_clean) & 
                             Attr('created_at').gt(cutoff)
        )
        if len(resp.get('Items', [])) > 0:
            return True
            
        # Also check for dry-run/disabled skips
        resp_skip = table.query(
            IndexName='StatusIndex',
            KeyConditionExpression=Key('status').eq('skipped_disabled'),
            FilterExpression=Attr('request_id').eq(request_id) & 
                             Attr('event_type').eq(event_type) & 
                             Attr('recipient_email').eq(recipient_clean) & 
                             Attr('created_at').gt(cutoff)
        )
        if len(resp_skip.get('Items', [])) > 0:
            return True
            
        return False
    except Exception as e:
        print(f"WARNING: Dedup check failed (fail-open): {e}")
        return False

def _resolve_potential_recipients_with_reasons(event_type, record, config):
    """
    Analyzes potential recipients for an event type and identifies
    which ones are active, suppressed, or disabled.
    """
    from .resolver import get_client_email, get_staff_email
    from .suppression import is_suppressed
    
    potential = []
    
    def add_pot(email, pref_enabled, role):
        if not email or not isinstance(email, str) or '@' not in email:
            return
        email_clean = email.strip().lower()
        
        # 1. Check suppression
        if is_suppressed(email_clean):
            potential.append({
                "email": email_clean,
                "status": "suppressed",
                "reason": f"Recipient suppressed: {email_clean}"
            })
            return
            
        # 2. Check preference
        if not pref_enabled:
            potential.append({
                "email": email_clean,
                "status": "skipped_disabled",
                "reason": f"Notification preference disabled for {role}."
            })
            return
            
        # 3. Active (even if dry-run/disabled, let it proceed to post-dispatch logging)
        potential.append({
            "email": email_clean,
            "status": "active",
            "reason": "Active recipient"
        })

    is_welcome_event = event_type in ['WELCOME_INVITE_CLIENT', 'WELCOME_INVITE_STAFF', 'WELCOME_INVITE']
    
    # Basic data issue checks
    if record.get('is_data_issue') or (not is_welcome_event and not record.get('request_id')):
        return []

    # Check for deleted/trash unless cancelled
    status = record.get('status', '').upper()
    if status in ['DELETED', 'TRASH', 'ARCHIVED'] and event_type != 'VISIT_CANCELLED':
        return []

    if event_type == 'REQUEST_RECEIVED':
        add_pot(config.ADMIN_EMAIL, config.NOTIFY_ADMIN_ON_REQUEST_RECEIVED, "admin")
        
    elif event_type == 'CUSTOMER_APPROVED':
        add_pot(get_client_email(record), config.NOTIFY_CLIENT_ON_APPROVAL, "client")
        
    elif event_type == 'VISIT_SCHEDULED':
        add_pot(get_client_email(record), config.NOTIFY_CLIENT_ON_SCHEDULED, "client")
        
    elif event_type == 'STAFF_ASSIGNED':
        add_pot(get_staff_email(record), config.NOTIFY_STAFF_ON_ASSIGNMENT, "staff")
        
    elif event_type == 'VISIT_CANCELLED':
        add_pot(get_client_email(record), config.NOTIFY_CLIENT_ON_CANCELLED, "client")
        add_pot(get_staff_email(record), config.NOTIFY_STAFF_ON_CANCELLED, "staff")
        add_pot(config.ADMIN_EMAIL, config.NOTIFY_ADMIN_ON_CANCELLED, "admin")
        
    elif event_type == 'VISIT_TIME_CHANGED':
        add_pot(get_client_email(record), True, "client")
        
    elif event_type in ['WELCOME_INVITE_CLIENT', 'WELCOME_INVITE_STAFF', 'WELCOME_INVITE']:
        add_pot(get_client_email(record), True, "recipient")
        
    return potential


def notify_event(event_type, record=None, previous_record=None, **kwargs):
    """
    Main entry point for dispatching notifications.
    Safe and non-blocking.
    Returns: { "success": bool, "message": str }
    """
    try:
        config = NotificationConfig()
        
        # Support both positional 'record' and keyword 'context' (used for welcomes)
        if record is None and 'context' in kwargs:
            record = kwargs.get('context')
            
        if not record:
            msg = f"Notification skipped: No record or context provided for {event_type}."
            print(f"NOTIFICATION_IDLE: {msg}")
            return {"success": False, "message": msg}

        request_id = record.get('request_id')
        client_id = record.get('client_id')
        
        # 1. Duplicate Prevention for Approval
        if event_type == 'CUSTOMER_APPROVED':
            prev_status = record.get('approval_notification_status')
            if prev_status in ['Email sent.', 'Notification logged only.']:
                msg = f"Approved. Notification already sent via {record.get('approval_notification_mode', 'unknown')}."
                print(f"NOTIFICATION_SKIP: {msg}")
                # Log duplicate skip to ledger
                _write_ledger_entry(
                    request_id=request_id,
                    event_type=event_type,
                    recipient=record.get('client_email') or record.get('email') or 'unknown',
                    status='skipped_duplicate',
                    provider='unknown',
                    record=record
                )
                return {"success": True, "message": msg}

        # 1.5 Quota Check & Warning Logic (Release 6J)
        # Quota check is audit-only and non-blocking unless hard stop is enabled
        from datetime import datetime, timezone
        now_dt = datetime.now(timezone.utc)
        month_key = now_dt.isoformat()[:7] # YYYY-MM
        
        sent_count = _get_monthly_send_count(month_key)
        
        # Log quota warnings on standard warning threshold crossings
        limit = config.POSTMARK_MONTHLY_LIMIT
        threshold = config.POSTMARK_QUOTA_WARN_THRESHOLD
        
        if limit > 0:
            usage_pct = (sent_count / limit) * 100
            if usage_pct >= threshold:
                print(f"NOTIFICATION_QUOTA_WARNING: Month {month_key} quota usage is at {usage_pct:.1f}% ({sent_count}/{limit}).")
                
        # Optional hard stop check
        if config.POSTMARK_QUOTA_HARD_STOP and limit > 0 and sent_count >= limit:
            msg = f"Notification skipped: Monthly Postmark quota limit of {limit} reached (current: {sent_count})."
            print(f"NOTIFICATION_QUOTA_HARD_STOP_ACTIVE: {msg}")
            # Write skipped_quota_exceeded to ledger representing the quota skip
            _write_ledger_entry(
                request_id=request_id,
                event_type=event_type,
                recipient=record.get('client_email') or record.get('email') or 'unknown',
                status='skipped_quota_exceeded',
                provider='postmark',
                error_message=msg,
                record=record
            )
            return {"success": True, "message": msg}

        # 2. Pre-Dispatch Ledger Logging
        # Analyze potential recipients and record any skips/suppressions immediately
        potential_recipients = _resolve_potential_recipients_with_reasons(event_type, record, config)
        for pot in potential_recipients:
            if pot["status"] != "active":
                _write_ledger_entry(
                    request_id=request_id,
                    event_type=event_type,
                    recipient=pot["email"],
                    status=pot["status"],
                    provider="log_only" if (config.DRY_RUN or not config.ENABLED) else None,
                    error_message=pot["reason"],
                    record=record
                )

        # 3. Resolve Active Recipients
        recipients = resolve_notification_recipients(event_type, record, previous_record, config)
        if not recipients:
            msg = f"Approved. No recipients resolved for {event_type}."
            print(f"NOTIFICATION_IDLE: {msg}")
            return {"success": True, "message": msg}

        # Multi-day dedup guard (Release 7F)
        if event_type in ['STAFF_ASSIGNED', 'VISIT_SCHEDULED']:
            valid_recipients = []
            for r in recipients:
                if _is_recent_duplicate(event_type, r, request_id):
                    _write_ledger_entry(
                        request_id=request_id,
                        event_type=event_type,
                        recipient=r,
                        status='skipped_duplicate_window',
                        provider='dedup',
                        error_message='Skipped: recent duplicate notification in window',
                        record=record
                    )
                else:
                    valid_recipients.append(r)
            recipients = valid_recipients
            
            if not recipients:
                return {"success": True, "message": "Skipped: recent duplicate notification."}

        # 4. Get Templates
        is_welcome_event = event_type in ['WELCOME_INVITE_CLIENT', 'WELCOME_INVITE_STAFF', 'WELCOME_INVITE']
        
        if is_welcome_event:
            # For welcome events, the 'record' (or context) already contains the necessary fields
            context = record
        else:
            # For standard booking events, we build the context from the DynamoDB record
            from .resolver import get_pet_names
            context = {
                "client_name": get_client_name(record),
                "client_email": record.get('client_email') or record.get('email') or '',
                "client_phone": record.get('client_phone') or '',
                "staff_name": get_staff_name(record),
                "worker_id": record.get('worker_id') or '',
                "worker_name": record.get('worker_name') or record.get('assigned_to_name') or '',
                "request_id": request_id,
                "pet_names": get_pet_names(record),
                "service_type": record.get('service_type'),
                "start_date": record.get('start_date'),
                "start_time": record.get('start_time'),
                "details": record.get('details', 'No details provided.'),
                "portal_url": config.PORTAL_URL if config else 'https://toganddogs.usmissionhero.com',
                "cancellation_reason": record.get('cancellation_reason') or '',
            }
        
        subject, body_text, body_html = NotificationTemplates.get_template(event_type, context)
        if not subject:
            msg = f"Notification failed: No template for {event_type}."
            print(f"NOTIFICATION_MISSING_TEMPLATE: {msg}")
            return {"success": False, "message": msg}

        # 5. Dispatch
        client = get_notification_client(config)
        event_key = f"{request_id}_{event_type}_{record.get('updated_at', 'v1')}"
        
        result = client.send_email(
            recipients=recipients,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            event_key=event_key
        )

        # 6. Post-Dispatch Ledger Logging for Active Recipients
        for r in recipients:
            if result.get('delivered'):
                _write_ledger_entry(
                    request_id=request_id,
                    event_type=event_type,
                    recipient=r,
                    status='sent',
                    provider=result.get('provider'),
                    provider_message_id=result.get('message_id'),
                    record=record
                )
                # Increment monthly send count atomically (Release 6J)
                _increment_monthly_send_count(month_key)
            else:
                is_dry_run_or_log = (
                    "logged only" in result.get('message', '').lower() or
                    "dry run" in result.get('message', '').lower() or
                    config.DRY_RUN or
                    not config.ENABLED or
                    config.NOTIFICATION_MODE == 'log_only'
                )
                if is_dry_run_or_log:
                    _write_ledger_entry(
                        request_id=request_id,
                        event_type=event_type,
                        recipient=r,
                        status='skipped_disabled',
                        provider='log_only',
                        error_message=result.get('message'),
                        record=record
                    )
                else:
                    _write_ledger_entry(
                        request_id=request_id,
                        event_type=event_type,
                        recipient=r,
                        status='failed',
                        provider=result.get('provider'),
                        error_message=result.get('message'),
                        record=record
                    )

        # 7. Metadata Update for Approval
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

        # 8. Log Safe Metadata
        try:
            recipient_domains = list(set([r.split('@')[-1] for r in recipients if '@' in r]))
            log_meta = {
                "event_type": event_type,
                "provider": result.get('provider', 'unknown'),
                "mode": result.get('mode', 'unknown'),
                "recipient_domains": recipient_domains,
                "status": "success" if result.get('delivered') else "failed",
                "message_id": result.get('message_id') if result.get('delivered') else None
            }
            print(f"NOTIFICATION_METADATA: {json.dumps(log_meta)}")
        except Exception as log_err:
            print(f"WARNING: Failed to log notification metadata: {log_err}")
            
        return {"success": result.get('delivered', False) or 'logged' in result.get('message', '').lower(), "message": result['message']}

    except Exception as e:
        # Crucial safety: notification failures must not block the main workflow
        err_msg = f"Notification failed but approval was completed."
        logger.error(f"NOTIFICATION_CRITICAL_FAILURE: {e}")
        return {"success": False, "message": err_msg}
