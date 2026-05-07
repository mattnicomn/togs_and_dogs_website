import json
import logging
from common.notifications.suppression import suppress_email

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def handler(event, context):
    """
    Processes SES Bounce/Complaint notifications from SNS.
    """
    try:
        for record in event.get('Records', []):
            sns_message = record.get('Sns', {}).get('Message')
            if not sns_message:
                continue
            
            data = json.loads(sns_message)
            notification_type = data.get('notificationType')
            
            if notification_type == 'Bounce':
                bounce = data.get('bounce', {})
                bounce_type = bounce.get('bounceType')
                
                # Only suppress for Hard Bounces (Permanent)
                if bounce_type == 'Permanent':
                    for recipient in bounce.get('bouncedRecipients', []):
                        email = recipient.get('emailAddress')
                        logger.info(f"SES_FEEDBACK: Hard bounce for {email}. Suppressing.")
                        suppress_email(email, reason="BOUNCE_PERMANENT")
                else:
                    logger.info(f"SES_FEEDBACK: Soft bounce ({bounce_type}) for recipients. No suppression.")
                    
            elif notification_type == 'Complaint':
                complaint = data.get('complaint', {})
                for recipient in complaint.get('complainedRecipients', []):
                    email = recipient.get('emailAddress')
                    logger.info(f"SES_FEEDBACK: Complaint from {email}. Suppressing.")
                    suppress_email(email, reason="COMPLAINT")
            
            else:
                logger.info(f"SES_FEEDBACK: Received {notification_type} notification. No action taken.")
                
        return {"statusCode": 200, "body": "Feedback processed successfully"}
        
    except Exception as e:
        logger.error(f"SES_FEEDBACK_ERROR: {e}")
        # Return 200 to avoid SNS retries if the error is non-recoverable
        return {"statusCode": 200, "body": f"Error: {str(e)}"}
