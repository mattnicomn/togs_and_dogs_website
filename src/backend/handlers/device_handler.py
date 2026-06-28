import json
import uuid
import datetime
from common.db import table, put_item
from common.response import success, bad_request, internal_error, error
from common.auth import get_effective_role, get_claims, get_current_company_id, resolve_client_identity
from boto3.dynamodb.conditions import Key, Attr

def handler(event, context):
    try:
        from common.entitlement import require_active_tenant
        block_resp = require_active_tenant(event)
        if block_resp:
            return block_resp

        http_method = event.get('httpMethod')
        path_params = event.get('pathParameters', {}) or {}
        device_id = path_params.get('device_id')
        
        claims = get_claims(event)
        cognito_sub = claims.get('sub')
        if not cognito_sub:
            return error(401, "Unauthorized", event)
            
        role = get_effective_role(event)
        if role == 'unknown':
            return error(403, "Forbidden", event)
            
        company_id = get_current_company_id(event)
        
        if http_method == 'POST':
            body = json.loads(event.get('body') or '{}')
            push_token = body.get('push_token')
            if not push_token:
                return bad_request("Missing push_token", event)
                
            # Basic validation for Expo token format
            if not push_token.startswith("ExponentPushToken[") and not push_token.startswith("ExpoPushToken["):
                return bad_request("Invalid push_token format", event)
                
            # Resolve profile_id
            profile_id = None
            if role == 'client':
                profile_id = resolve_client_identity(event)
            elif role in ['owner', 'admin', 'staff']:
                resp = table.query(
                    KeyConditionExpression=Key('PK').eq(f"COMPANY#{company_id}") & Key('SK').begins_with("STAFF#")
                )
                for staff in resp.get('Items', []):
                    if staff.get('cognito_sub') == cognito_sub:
                        profile_id = staff.get('staff_id')
                        break
                        
            # Find existing devices with this token
            # Note: This table scan is acceptable for initial scale. 
            # A GSI on push_token should be considered if device records grow significantly.
            resp = table.scan(
                FilterExpression=Attr('entity_type').eq('PUSH_DEVICE') & Attr('push_token').eq(push_token) & Attr('PK').begins_with('DEVICE#')
            )
            existing_devices = resp.get('Items', [])
            
            target_device = None
            for d in existing_devices:
                if d.get('cognito_sub') == cognito_sub:
                    target_device = d
                else:
                    # Token reassignment: deactivate it for other users
                    d['is_active'] = False
                    d['updated_at'] = datetime.datetime.utcnow().isoformat()
                    put_item(d)
                    
            now_iso = datetime.datetime.utcnow().isoformat()
            if target_device:
                target_device['updated_at'] = now_iso
                target_device['app_version'] = body.get('app_version', target_device.get('app_version'))
                target_device['platform'] = body.get('platform', target_device.get('platform'))
                target_device['device_name'] = body.get('device_name', target_device.get('device_name'))
                target_device['is_active'] = True
                target_device['user_role'] = role
                target_device['profile_id'] = profile_id
                put_item(target_device)
                return success({"device_id": target_device['device_id'], "status": "updated"}, event)
            else:
                new_device_id = str(uuid.uuid4())
                device_record = {
                    'PK': f"DEVICE#{new_device_id}",
                    'SK': f"USER#{cognito_sub}",
                    'entity_type': 'PUSH_DEVICE',
                    'device_id': new_device_id,
                    'cognito_sub': cognito_sub,
                    'user_role': role,
                    'profile_id': profile_id,
                    'company_id': company_id,
                    'push_token': push_token,
                    'platform': body.get('platform'),
                    'app_version': body.get('app_version'),
                    'device_name': body.get('device_name'),
                    'is_active': True,
                    'created_at': now_iso,
                    'updated_at': now_iso,
                    'last_used_at': None
                }
                put_item(device_record)
                return success({"device_id": new_device_id, "status": "registered"}, event)
                
        elif http_method == 'DELETE':
            if not device_id:
                return bad_request("Missing device_id", event)
                
            resp = table.query(
                KeyConditionExpression=Key('PK').eq(f"DEVICE#{device_id}")
            )
            items = resp.get('Items', [])
            if not items:
                return success({"status": "removed"}, event)
                
            device = items[0]
            if device.get('cognito_sub') != cognito_sub and role not in ['owner', 'admin']:
                return error(403, "Forbidden", event)
                
            # Soft delete
            device['is_active'] = False
            device['updated_at'] = datetime.datetime.utcnow().isoformat()
            put_item(device)
            
            return success({"status": "removed"}, event)
            
        return bad_request(f"Unsupported method: {http_method}", event)
        
    except Exception as e:
        print(f"Unhandled error in device_handler: {e}")
        return internal_error(str(e), event)
