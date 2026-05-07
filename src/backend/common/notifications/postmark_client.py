import json
import logging
import urllib.request
import urllib.error
import boto3
from .config import NotificationConfig

logger = logging.getLogger(__name__)

class PostmarkClient:
    """Wrapper for Postmark transactional emails with dry-run and logging support."""

    def __init__(self, config=None):
        self.config = config or NotificationConfig()
        self.api_url = "https://api.postmarkapp.com/email"
        self._server_token = None

    def _get_server_token(self):
        """Fetches the Postmark Server Token from AWS Secrets Manager."""
        if self._server_token:
            return self._server_token

        secret_name = self.config.POSTMARK_TOKEN_SECRET_NAME
        if not secret_name:
            logger.error("POSTMARK_SERVER_TOKEN_SECRET_NAME not configured.")
            return None

        try:
            client = boto3.client('secretsmanager')
            response = client.get_secret_value(SecretId=secret_name)
            # If the secret is just a plain string (token), use it.
            # If it's a JSON string, try to parse it.
            secret_value = response.get('SecretString')
            try:
                # Try parsing as JSON first in case it's stored as {"token": "..."}
                data = json.loads(secret_value)
                if isinstance(data, dict):
                    self._server_token = data.get('token') or data.get('PostmarkServerToken') or secret_value
                else:
                    self._server_token = secret_value
            except json.JSONDecodeError:
                self._server_token = secret_value
            
            return self._server_token
        except Exception as e:
            logger.error(f"Failed to fetch Postmark token from Secrets Manager: {e}")
            return None

    def send_email(self, recipients, subject, body_text, body_html, event_key=None):
        """
        Sends email via Postmark based on NOTIFICATION_MODE.
        Returns normalized result: { "delivered": bool, "mode": str, "message": str, "message_id": str, "provider": "postmark" }
        """
        mode = self.config.NOTIFICATION_MODE
        provider = "postmark"
        
        # 1. Handle Recipient Override for testing
        final_recipients = recipients
        if self.config.TEST_RECIPIENT_OVERRIDE:
            print(f"NOTIFICATION_OVERRIDE: Overriding {recipients} with {self.config.TEST_RECIPIENT_OVERRIDE}")
            final_recipients = [self.config.TEST_RECIPIENT_OVERRIDE]

        # 2. Prepare Log Data
        log_payload = {
            "event_key": event_key,
            "from": self.config.EMAIL_FROM,
            "to": final_recipients,
            "subject": subject,
            "mode": mode,
            "provider": provider,
            "dry_run": self.config.DRY_RUN,
            "body_preview": body_text[:100] + "..." if body_text else ""
        }

        # 3. Dry Run / Disabled Global check
        if self.config.DRY_RUN or not self.config.ENABLED:
            print(f"NOTIFICATION_DRY_RUN_LOG: {json.dumps(log_payload)}")
            return {
                "delivered": False,
                "mode": mode,
                "provider": provider,
                "message": "Notification logged only (Dry Run or Disabled).",
                "message_id": None
            }

        # 4. Handle Modes
        if mode == 'log_only':
            print(f"NOTIFICATION_LOG_ONLY: {json.dumps(log_payload)}")
            return {
                "delivered": False,
                "mode": mode,
                "provider": provider,
                "message": "Notification logged only.",
                "message_id": None
            }

        # 5. Live Send
        token = self._get_server_token()
        if not token:
            logger.error("Postmark token missing. Cannot send live email.")
            return {
                "delivered": False,
                "mode": mode,
                "provider": provider,
                "message": "Notification failed: Postmark token not configured.",
                "message_id": None
            }

        # Postmark Payload
        # Supports multiple recipients by comma separating them in 'To'
        payload = {
            "From": self.config.EMAIL_FROM,
            "To": ",".join(final_recipients),
            "Subject": subject,
            "HtmlBody": body_html,
            "TextBody": body_text,
            "ReplyTo": self.config.REPLY_TO,
            "MessageStream": self.config.POSTMARK_MESSAGE_STREAM
        }

        try:
            req = urllib.request.Request(
                self.api_url,
                data=json.dumps(payload).encode('utf-8'),
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "X-Postmark-Server-Token": token
                },
                method="POST"
            )

            with urllib.request.urlopen(req, timeout=10) as response:
                resp_body = response.read().decode('utf-8')
                resp_json = json.loads(resp_body)
                
                message_id = resp_json.get('MessageID')
                print(f"NOTIFICATION_SUCCESS: Sent {event_key} via Postmark. MessageId: {message_id}")
                return {
                    "delivered": True,
                    "mode": mode,
                    "provider": provider,
                    "message": "Email sent.",
                    "message_id": message_id
                }

        except urllib.error.HTTPError as e:
            resp_body = e.read().decode('utf-8')
            logger.error(f"NOTIFICATION_FAILURE: Postmark API error: {e.code} - {resp_body}")
            try:
                error_json = json.loads(resp_body)
                reason = error_json.get('Message', str(e))
            except:
                reason = str(e)
            
            return {
                "delivered": False,
                "mode": mode,
                "provider": provider,
                "message": f"Notification failed: {reason}",
                "message_id": None
            }
        except Exception as e:
            logger.error(f"NOTIFICATION_ERROR: Unexpected error sending via Postmark: {e}")
            return {
                "delivered": False,
                "mode": mode,
                "provider": provider,
                "message": "Notification failed due to an unexpected error.",
                "message_id": None
            }
