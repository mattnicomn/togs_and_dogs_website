import boto3
import json
import logging
from botocore.exceptions import ClientError
from .config import NotificationConfig

logger = logging.getLogger(__name__)

class SESClient:
    """Wrapper for AWS SES with dry-run and logging support."""

    def __init__(self, config=None):
        self.config = config or NotificationConfig()
        self.region = "us-east-1"
        self.ses = None
        if not self.config.DRY_RUN:
            try:
                self.ses = boto3.client('ses', region_name=self.region)
            except Exception as e:
                logger.error(f"Failed to initialize SES client: {e}")

    def send_email(self, recipients, subject, body_text, body_html, event_key=None):
        """
        Sends email to recipients based on NOTIFICATION_MODE.
        Returns: { "delivered": bool, "mode": str, "message": str }
        """
        mode = self.config.NOTIFICATION_MODE
        
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
            "dry_run": self.config.DRY_RUN,
            "body_preview": body_text[:100] + "..." if body_text else ""
        }

        # 3. Dry Run / Disabled Global check
        if self.config.DRY_RUN or not self.config.ENABLED:
            print(f"NOTIFICATION_DRY_RUN_LOG: {json.dumps(log_payload)}")
            return {
                "delivered": False,
                "mode": mode,
                "message": "Notification logged only (Dry Run or Disabled)."
            }

        # 4. Handle Modes
        if mode == 'log_only':
            print(f"NOTIFICATION_LOG_ONLY: {json.dumps(log_payload)}")
            return {
                "delivered": False,
                "mode": mode,
                "message": "Notification logged only."
            }

        if mode == 'ses_sandbox':
            # Check allowlist
            allowed = self.config.SES_SANDBOX_ALLOWED_RECIPIENTS + [self.config.ADMIN_EMAIL.lower()]
            unverified = [r for r in final_recipients if r.lower() not in allowed]
            
            if unverified:
                print(f"NOTIFICATION_BLOCK: SES Sandbox blocked unverified recipients: {unverified}")
                return {
                    "delivered": False,
                    "mode": mode,
                    "message": "Email skipped because SES sandbox mode only allows verified recipients."
                }

        # 5. Live Send (ses_sandbox or ses_production)
        if not self.ses:
            logger.error("SES client not initialized. Cannot send live email.")
            return {
                "delivered": False,
                "mode": mode,
                "message": "Notification failed: SES client not initialized."
            }

        try:
            response = self.ses.send_email(
                Destination={'ToAddresses': final_recipients},
                Message={
                    'Body': {
                        'Html': {'Charset': "UTF-8", 'Data': body_html},
                        'Text': {'Charset': "UTF-8", 'Data': body_text},
                    },
                    'Subject': {'Charset': "UTF-8", 'Data': subject},
                },
                Source=self.config.EMAIL_FROM
            )
            print(f"NOTIFICATION_SUCCESS: Sent {event_key} to {final_recipients}. MessageId: {response['MessageId']}")
            return {
                "delivered": True,
                "mode": mode,
                "message": "Email sent."
            }

        except ClientError as e:
            logger.error(f"NOTIFICATION_FAILURE: Failed to send {event_key} to {final_recipients}. Error: {e}")
            return {
                "delivered": False,
                "mode": mode,
                "message": f"Notification failed: {str(e)}"
            }
        except Exception as e:
            logger.error(f"NOTIFICATION_ERROR: Unexpected error sending {event_key}. Error: {e}")
            return {
                "delivered": False,
                "mode": mode,
                "message": "Notification failed due to an unexpected error."
            }
