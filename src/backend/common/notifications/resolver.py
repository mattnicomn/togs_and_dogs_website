import logging

logger = logging.getLogger(__name__)

def get_client_email(record):
    """Extracts client email from the record."""
    return record.get('client_email') or record.get('email')

def get_client_name(record):
    """Extracts client name from the record."""
    return record.get('client_name') or record.get('name', 'Valued Client')

def get_staff_email(record):
    """Extracts assigned staff email from the record."""
    email = record.get('assigned_to_email') or record.get('worker_id')
    # Basic check if it looks like an email
    if email and '@' in str(email):
        return email
    return None

def get_staff_name(record):
    """Extracts assigned staff name from the record."""
    return record.get('assigned_to_name', 'Team Member')

def resolve_notification_recipients(event_type, record, previous_record=None, config=None):
    """
    Resolves a list of recipient emails based on event type and record state.
    Returns: list of strings (emails)
    """
    recipients = []
    
    # 1. Check for Data Issues / Malformed
    if record.get('is_data_issue') or not record.get('request_id'):
        logger.info(f"NOTIFICATION_SKIP: Skipping event {event_type} for malformed record.")
        return []

    # 2. Check for Deleted / Trash (unless cancellation)
    status = record.get('status', '').upper()
    if status in ['DELETED', 'TRASH', 'ARCHIVED'] and event_type != 'VISIT_CANCELLED':
        logger.info(f"NOTIFICATION_SKIP: Skipping event {event_type} for record in status {status}.")
        return []

    # 3. Event-based Routing
    if event_type == 'REQUEST_RECEIVED':
        # Primary: Admin
        if config and config.NOTIFY_ADMIN_ON_REQUEST_RECEIVED:
            recipients.append(config.ADMIN_EMAIL)
            
    elif event_type == 'CUSTOMER_APPROVED':
        # Primary: Client
        client_email = get_client_email(record)
        if client_email:
            recipients.append(client_email)
            
    elif event_type == 'VISIT_SCHEDULED':
        # Primary: Client
        client_email = get_client_email(record)
        if client_email:
            recipients.append(client_email)
            
    elif event_type == 'STAFF_ASSIGNED':
        # Primary: Staff
        staff_email = get_staff_email(record)
        if staff_email:
            recipients.append(staff_email)
            
    elif event_type == 'VISIT_CANCELLED':
        # Primary: Client + Admin (if configured)
        client_email = get_client_email(record)
        if client_email:
            recipients.append(client_email)
        if config and config.NOTIFY_ADMIN_ON_CANCELLED:
            recipients.append(config.ADMIN_EMAIL)
            
    elif event_type == 'VISIT_TIME_CHANGED':
        # Primary: Client
        client_email = get_client_email(record)
        if client_email:
            recipients.append(client_email)

    # Filter out empty/None values and de-duplicate (case-insensitive)
    unique_recipients = []
    seen = set()
    for r in recipients:
        if r and isinstance(r, str):
            r_lower = r.strip().lower()
            if r_lower not in seen:
                unique_recipients.append(r.strip())
                seen.add(r_lower)
    
    return unique_recipients
