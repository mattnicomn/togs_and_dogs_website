import uuid
import json
from datetime import datetime, timezone
from common.db import put_item

def log_action(event, action, target_pk, target_sk=None, previous_status=None, new_status=None, bulk_op_id=None, success=True, failure_reason=None, metadata=None):
    """
    Logs a destructive or lifecycle action to the audit log.
    Storage pattern:
    PK = AUDIT#<id> (e.g. AUDIT#uuid)
    SK = <timestamp>#<audit_id>
    """
    from common.auth import get_claims, get_effective_role
    
    claims = get_claims(event)
    user_email = (claims.get('email') or "").lower().strip() or claims.get('username') or 'admin-api'
    user_role = get_effective_role(event)
    
    audit_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()
    
    # Extract identifier for PK
    # If target_pk is REQ#<uuid>, use the uuid for cleaner lookup, 
    # but for broad searchability we might just use the PK directly or a derivative.
    # The requirement said PK = AUDIT#<request_id>
    request_id = target_pk.replace("REQ#", "").replace("JOB#", "")
    
    audit_record = {
        "PK": f"AUDIT#{request_id}",
        "SK": f"{timestamp}#{audit_id}",
        "type": "AUDIT",
        "timestamp": timestamp,
        "user_email": user_email,
        "user_role": user_role,
        "action": action,
        "target_pk": target_pk,
        "target_sk": target_sk,
        "previous_status": previous_status,
        "new_status": new_status,
        "bulk_op_id": bulk_op_id,
        "success": success,
        "failure_reason": failure_reason,
        "metadata": metadata or {}, # e.g. {"client_name": "...", "pet_names": "..."}
        "source_endpoint": event.get('path', 'unknown'),
        "source_method": event.get('httpMethod', 'unknown')
    }
    
    print(f"AUDIT LOG: [{action}] by {user_email} on {target_pk}. Success: {success}")
    return put_item(audit_record)
