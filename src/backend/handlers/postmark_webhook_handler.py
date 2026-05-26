"""
Release 6I Phase 1: Postmark Webhook Handler

Receives delivery event callbacks from Postmark and auto-suppresses
bounced/complained addresses using the existing suppression mechanism.

Authentication: Validates POSTMARK_WEBHOOK_SECRET header before processing.
Does NOT modify the notification send path or notify_event() behavior.
"""
import json
import os
from common.response import success, error, bad_request
from common.notifications.suppression import suppress_email


def handler(event, context):
    """
    POST /webhooks/postmark
    Receives Postmark webhook events (Bounce, SpamComplaint, Delivery, Open, Click).
    """
    try:
        # 1. Authenticate webhook request
        if not _validate_webhook_auth(event):
            return _raw_response(401, {"error": "Unauthorized"})

        # 2. Parse body
        body = event.get('body', '')
        is_base64 = event.get('isBase64Encoded', False)

        if body and is_base64 and isinstance(body, str):
            try:
                import base64
                body = base64.b64decode(body).decode('utf-8')
            except Exception as e:
                print(f"POSTMARK_WEBHOOK_PARSE_FAILED: Failed to decode base64 body: {e}")
                return _raw_response(400, {"error": "Failed to decode base64 body"})

        if isinstance(body, str):
            try:
                payload = json.loads(body)
            except (json.JSONDecodeError, TypeError) as e:
                print(f"POSTMARK_WEBHOOK_PARSE_FAILED: Could not parse JSON body: {e}")
                return _raw_response(400, {"error": "Invalid JSON payload"})
        elif isinstance(body, dict):
            payload = body
        else:
            print(f"POSTMARK_WEBHOOK_PARSE_FAILED: Unexpected body type: {type(body)}")
            return _raw_response(400, {"error": "Invalid payload format"})

        # 3. Validate required fields
        record_type = payload.get('RecordType') if isinstance(payload, dict) else None
        message_id = payload.get('MessageID') if isinstance(payload, dict) else None

        if not record_type:
            print(f"POSTMARK_WEBHOOK_PARSE_FAILED: Missing RecordType field.")
            return _raw_response(400, {"error": "Missing RecordType field"})

        # 4. Route by RecordType
        if record_type == 'Bounce':
            return _handle_bounce(payload, message_id)
        elif record_type == 'SpamComplaint':
            return _handle_spam_complaint(payload, message_id)
        elif record_type == 'Delivery':
            return _handle_delivery(payload, message_id)
        elif record_type in ('Open', 'Click'):
            print(f"POSTMARK_WEBHOOK_EVENT: {record_type} received for MessageID: {message_id}")
            return _raw_response(200, {"status": "acknowledged", "record_type": record_type})
        else:
            print(f"POSTMARK_WEBHOOK_UNKNOWN_TYPE: Unrecognized RecordType: {record_type}")
            return _raw_response(200, {"status": "ignored", "reason": f"Unrecognized RecordType: {record_type}"})

    except Exception as e:
        print(f"POSTMARK_WEBHOOK_ERROR: Unhandled error: {e}")
        return _raw_response(500, {"error": "Internal server error"})


def _validate_webhook_auth(event):
    """
    Validates the webhook request using POSTMARK_WEBHOOK_SECRET.
    Checks the X-Postmark-Webhook-Secret header against the configured secret.
    """
    expected_secret = os.environ.get('POSTMARK_WEBHOOK_SECRET', '')
    headers = event.get('headers', {}) or {}
    
    # Check case-insensitive header
    provided_secret = (
        headers.get('X-Postmark-Webhook-Secret') or
        headers.get('x-postmark-webhook-secret') or
        headers.get('X-POSTMARK-WEBHOOK-SECRET') or
        ''
    )

    expected_configured = bool(expected_secret.strip())
    print(f"POSTMARK_WEBHOOK_AUTH_STATE: configured={expected_configured}")

    if not expected_configured:
        print("POSTMARK_WEBHOOK_AUTH_FAILED: POSTMARK_WEBHOOK_SECRET not configured (empty or missing in Lambda variables).")
        return False

    if not provided_secret.strip():
        print("POSTMARK_WEBHOOK_AUTH_FAILED: Incoming X-Postmark-Webhook-Secret header is missing or empty.")
        return False

    is_valid = (provided_secret.strip() == expected_secret.strip())
    
    if not is_valid:
        print("POSTMARK_WEBHOOK_AUTH_FAILED: Provided secret does not match configured POSTMARK_WEBHOOK_SECRET.")
        
    return is_valid


def _handle_bounce(payload, message_id):
    """Processes a Bounce event. Hard bounces suppress the recipient."""
    recipient = (payload.get('Email') or '').lower().strip()
    bounce_type = payload.get('Type', 'Unknown')
    description = payload.get('Description', '')

    print(f"POSTMARK_WEBHOOK_BOUNCE: Type={bounce_type}, Email={_mask_email(recipient)}, MessageID={message_id}")

    if bounce_type == 'HardBounce':
        if recipient:
            suppress_email(recipient, reason=f"HARD_BOUNCE:{description[:100]}")
            print(f"POSTMARK_WEBHOOK_SUPPRESSED: Hard bounce suppressed {_mask_email(recipient)}")
        return _raw_response(200, {"status": "suppressed", "bounce_type": bounce_type})
    else:
        # Soft bounces — log but do NOT suppress
        print(f"POSTMARK_WEBHOOK_SOFT_BOUNCE: {bounce_type} for {_mask_email(recipient)} — not suppressed.")
        return _raw_response(200, {"status": "logged", "bounce_type": bounce_type})


def _handle_spam_complaint(payload, message_id):
    """Processes a SpamComplaint event. Always suppresses the recipient."""
    recipient = (payload.get('Email') or '').lower().strip()

    print(f"POSTMARK_WEBHOOK_SPAM_COMPLAINT: Email={_mask_email(recipient)}, MessageID={message_id}")

    if recipient:
        suppress_email(recipient, reason="SPAM_COMPLAINT")
        print(f"POSTMARK_WEBHOOK_SUPPRESSED: Spam complaint suppressed {_mask_email(recipient)}")

    return _raw_response(200, {"status": "suppressed", "reason": "spam_complaint"})


def _handle_delivery(payload, message_id):
    """Processes a Delivery event. Logs only — no suppression."""
    recipient = (payload.get('Recipient') or payload.get('Email') or '').lower().strip()
    print(f"POSTMARK_WEBHOOK_DELIVERY: Delivered to {_mask_email(recipient)}, MessageID={message_id}")
    return _raw_response(200, {"status": "delivered"})


def _mask_email(email):
    """Masks email for safe logging (shows domain only)."""
    if not email or '@' not in email:
        return '***'
    return f"***@{email.split('@')[1]}"


def _raw_response(status_code, body_dict):
    """Returns a raw API Gateway response (not using common.response to avoid CORS overhead for webhooks)."""
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body_dict)
    }
