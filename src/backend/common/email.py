import boto3
import os
import json
from botocore.exceptions import ClientError

def send_transactional_email(to_address, subject, body_html, body_text=None):
    """
    Sends a transactional email via AWS SES.
    Fails gracefully if SES is not configured, logging the attempt instead.
    """
    sender = os.environ.get('EMAIL_SENDER', 'support@toganddogs.usmissionhero.com')
    region = os.environ.get('AWS_REGION', 'us-east-1')

    print(f"INFO: Attempting to send email to {to_address} (Subject: {subject})")
    
    # Graceful fallback: If we know SES is not ready or in sandbox without verified address
    # we log the content to CloudWatch
    email_data = {
        "to": to_address,
        "from": sender,
        "subject": subject,
        "body_html": body_html
    }

    try:
        ses = boto3.client('ses', region_name=region)
        
        response = ses.send_email(
            Destination={
                'ToAddresses': [to_address],
            },
            Message={
                'Body': {
                    'Html': {
                        'Charset': "UTF-8",
                        'Data': body_html,
                    },
                    'Text': {
                        'Charset': "UTF-8",
                        'Data': body_text or "Please view this email in an HTML-compatible client.",
                    },
                },
                'Subject': {
                    'Charset': "UTF-8",
                    'Data': subject,
                },
            },
            Source=sender,
        )
        print(f"SUCCESS: Email sent! Message ID: {response['MessageId']}")
        return True

    except ClientError as e:
        error_msg = e.response['Error']['Message']
        if "Email address is not verified" in error_msg:
            print(f"INFO: SES Sandbox restriction: Recipient {to_address} is not verified. Email will not be delivered until production access is granted or recipient is verified.")
        elif "User is not authorized" in error_msg:
            print(f"ERROR: SES IAM Authorization failure for resource: {e.response['Error'].get('Resource', 'Unknown')}. Check Lambda execution role permissions.")
        else:
            print(f"WARNING: SES sending failed. Error: {error_msg}")
        
        print(f"LOGGED_EMAIL_CONTENT: {json.dumps(email_data)}")
        return False
    except Exception as e:
        print(f"ERROR: Unhandled exception in email utility: {e}")
        print(f"LOGGED_EMAIL_CONTENT: {json.dumps(email_data)}")
        return False

def get_approval_email_body(client_name, start_date, custom_message=""):
    """Returns HTML for approval notification."""
    message_section = f"<p><strong>A message from Ryan:</strong><br/>{custom_message}</p>" if custom_message else ""
    
    return f"""
    <html>
    <body>
        <h2>Great news, {client_name}!</h2>
        <p>Your pet sitting request for {start_date} has been <strong>APPROVED</strong>.</p>
        {message_section}
        <p>We've added this to our Master Scheduler and will see you soon!</p>
        <p>Best,<br/>Togs & Dogs Team</p>
    </body>
    </html>
    """

def get_rejection_email_body(client_name, start_date, custom_message=""):
    """Returns HTML for rejection notification."""
    message_section = f"<p><strong>Note from the team:</strong><br/>{custom_message}</p>" if custom_message else ""
    
    return f"""
    <html>
    <body>
        <h2>Update regarding your request</h2>
        <p>Hi {client_name}, we've reviewed your request for {start_date}.</p>
        <p>Unfortunately, we are <strong>unable to fulfill</strong> this specific booking at this time.</p>
        {message_section}
        <p>We apologize for the inconvenience and hope to see you and your furry friends in the future.</p>
        <p>Best,<br/>Togs & Dogs Team</p>
    </body>
    </html>
    """
