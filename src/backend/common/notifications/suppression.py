import logging
from common.db import get_item, put_item
from datetime import datetime

logger = logging.getLogger(__name__)

def is_suppressed(email):
    """
    Checks if an email is in the suppression list.
    Fails safe: If an error occurs, assumes NOT suppressed but logs the error.
    """
    if not email:
        return False
    
    try:
        email = email.lower().strip()
        # Using PK/SK pattern consistent with the rest of the app
        item = get_item(f"SUPPRESSION#{email}", "METADATA")
        if item:
            logger.warning(f"SUPPRESSION_MATCH: {email} is suppressed. Reason: {item.get('reason')}")
            return True
        return False
    except Exception as e:
        logger.error(f"SUPPRESSION_CHECK_ERROR: Failed to check suppression for {email}. Error: {e}")
        # Fail safe: allow sending if the lookup fails, but log it.
        return False

def suppress_email(email, reason="BOUNCE"):
    """
    Adds an email to the suppression list.
    """
    if not email:
        return False
    
    try:
        email = email.lower().strip()
        item = {
            "PK": f"SUPPRESSION#{email}",
            "SK": "METADATA",
            "email": email,
            "reason": reason,
            "suppressed_at": datetime.utcnow().isoformat(),
            "entity_type": "SUPPRESSION"
        }
        return put_item(item)
    except Exception as e:
        logger.error(f"SUPPRESSION_WRITE_ERROR: Failed to suppress {email}. Error: {e}")
        return False
