import json
import os
import uuid
from datetime import datetime, timezone
from boto3.dynamodb.conditions import Key, Attr
from common.db import table, get_item, put_item, update_item
from common.response import success, bad_request, internal_error, not_found, error
from common.auth import get_claims, is_platform_admin
from common.billing import _build_entitlement, invalidate_entitlement_cache

def _handle_list_tenants(event):
    try:
        scan_kwargs = {
            "FilterExpression": Attr("PK").begins_with("TENANT#") & Attr("SK").eq("METADATA")
        }
        items = []
        response = table.scan(**scan_kwargs)
        items.extend(response.get('Items', []))
        while 'LastEvaluatedKey' in response:
            scan_kwargs['ExclusiveStartKey'] = response['LastEvaluatedKey']
            response = table.scan(**scan_kwargs)
            items.extend(response.get('Items', []))
            
        tenants = []
        for item in items:
            tenants.append({
                "company_id": item.get("company_id"),
                "display_name": item.get("display_name"),
                "subscription_tier": item.get("subscription_tier"),
                "subscription_status": item.get("subscription_status"),
                "created_at": item.get("created_at")
            })
            
        return success({"tenants": tenants}, event)
    except Exception as e:
        print(f"Error listing tenants: {e}")
        return internal_error(str(e), event)

def _handle_get_tenant(event, company_id):
    try:
        tenant = get_item(f"TENANT#{company_id}", "METADATA")
        if not tenant:
            return not_found(f"Tenant {company_id} not found", event)
            
        staff_resp = table.query(
            KeyConditionExpression=Key('PK').eq(f"COMPANY#{company_id}") & Key('SK').begins_with("STAFF#")
        )
        active_staff = sum(1 for item in staff_resp.get('Items', []) if item.get('is_active') is True)
        
        client_resp = table.query(
            KeyConditionExpression=Key('PK').eq(f"COMPANY#{company_id}") & Key('SK').begins_with("CLIENT#")
        )
        active_clients = sum(1 for item in client_resp.get('Items', []) if item.get('is_active') is True)
        
        current_month = datetime.now(timezone.utc).strftime("%Y-%m")
        scan_kwargs = {
            "FilterExpression": Attr("company_id").eq(company_id) & Attr("entity_type").eq("REQUEST") & Attr("created_at").begins_with(current_month)
        }
        bookings_count = 0
        resp = table.scan(**scan_kwargs)
        bookings_count += len(resp.get('Items', []))
        while 'LastEvaluatedKey' in resp:
            scan_kwargs['ExclusiveStartKey'] = resp['LastEvaluatedKey']
            resp = table.scan(**scan_kwargs)
            bookings_count += len(resp.get('Items', []))
            
        ent = _build_entitlement(tenant)
        ent_summary = ent.to_dict()
        
        profile = {
            "company_id": tenant.get("company_id"),
            "display_name": tenant.get("display_name"),
            "timezone": tenant.get("timezone"),
            "primary_color": tenant.get("primary_color"),
            "secondary_color": tenant.get("secondary_color"),
            "logo_url": tenant.get("logo_url"),
            "portal_url": tenant.get("portal_url"),
            "created_at": tenant.get("created_at"),
            "updated_at": tenant.get("updated_at"),
            "notes": tenant.get("notes"),
            "admin_override_until": tenant.get("admin_override_until")
        }
        
        subscription = {
            "tier": tenant.get("subscription_tier", "starter"),
            "status": tenant.get("subscription_status", "disabled")
        }
        
        return success({
            "company_id": company_id,
            "profile": profile,
            "subscription": subscription,
            "entitlement_summary": ent_summary,
            "usage_counts": {
                "active_staff": active_staff,
                "active_clients": active_clients,
                "monthly_bookings": bookings_count
            }
        }, event)
    except Exception as e:
        print(f"Error fetching tenant {company_id}: {e}")
        return internal_error(str(e), event)

def _handle_patch_tenant(event, company_id):
    try:
        try:
            body = json.loads(event.get('body', '{}') or '{}')
        except Exception:
            return bad_request("Invalid JSON body", event)
            
        tenant = get_item(f"TENANT#{company_id}", "METADATA")
        if not tenant:
            return not_found(f"Tenant {company_id} not found", event)
            
        ALLOWED_FIELDS = {'display_name', 'subscription_tier', 'subscription_status', 'admin_override_until', 'notes'}
        unsupported = [f for f in body.keys() if f not in ALLOWED_FIELDS]
        if unsupported:
            return bad_request(f"Unsupported fields: {', '.join(unsupported)}", event)
            
        updates = {}
        old_values = {}
        new_values = {}
        changed_fields = []
        
        if 'display_name' in body:
            display_name = body['display_name']
            if not isinstance(display_name, str):
                return bad_request("display_name must be a string", event)
            display_name = display_name.strip()
            if not display_name:
                return bad_request("display_name cannot be empty", event)
            if len(display_name) > 100:
                return bad_request("display_name cannot exceed 100 characters", event)
            
            old_val = tenant.get('display_name')
            if old_val != display_name:
                updates['display_name'] = display_name
                old_values['display_name'] = old_val
                new_values['display_name'] = display_name
                changed_fields.append('display_name')
                
        if 'subscription_tier' in body:
            tier = body['subscription_tier']
            VALID_TIERS = {'starter', 'professional', 'premium', 'enterprise'}
            if tier not in VALID_TIERS:
                return bad_request(f"subscription_tier must be one of: {', '.join(VALID_TIERS)}", event)
                
            old_val = tenant.get('subscription_tier')
            if old_val != tier:
                updates['subscription_tier'] = tier
                from common.billing import TIER_LIMITS
                new_limits = TIER_LIMITS.get(tier)
                updates['limits'] = new_limits
                old_values['subscription_tier'] = old_val
                new_values['subscription_tier'] = tier
                changed_fields.append('subscription_tier')
                
        if 'subscription_status' in body:
            status = body['subscription_status']
            VALID_STATUSES = {'active', 'trialing', 'past_due', 'canceled', 'paused', 'disabled'}
            if status not in VALID_STATUSES:
                return bad_request(f"subscription_status must be one of: {', '.join(VALID_STATUSES)}", event)
                
            old_val = tenant.get('subscription_status')
            if old_val != status:
                updates['subscription_status'] = status
                updates['billing_status_changed_at'] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
                old_values['subscription_status'] = old_val
                new_values['subscription_status'] = status
                changed_fields.append('subscription_status')
                
        if 'admin_override_until' in body:
            val = body['admin_override_until']
            if val is not None:
                if not isinstance(val, str):
                    return bad_request("admin_override_until must be a string or null", event)
                try:
                    dt = datetime.fromisoformat(val.replace('Z', '+00:00'))
                    if dt < datetime.now(timezone.utc):
                        return bad_request("admin_override_until must be a future timestamp", event)
                except ValueError:
                    return bad_request("admin_override_until must be a valid ISO 8601 timestamp", event)
                    
            old_val = tenant.get('admin_override_until')
            if old_val != val:
                updates['admin_override_until'] = val
                old_values['admin_override_until'] = old_val
                new_values['admin_override_until'] = val
                changed_fields.append('admin_override_until')
                
        if 'notes' in body:
            notes = body['notes']
            if notes is not None and not isinstance(notes, str):
                return bad_request("notes must be a string or null", event)
                
            old_val = tenant.get('notes')
            if old_val != notes:
                updates['notes'] = notes
                old_values['notes'] = old_val
                new_values['notes'] = notes
                changed_fields.append('notes')
                
        claims = get_claims(event)
        actor = claims.get('email') or claims.get('username') or 'unknown-platform-admin'
        
        if changed_fields:
            now_iso = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
            updates['updated_at'] = now_iso
            updates['updated_by'] = f"platform_admin:{actor}"
            
            if not update_item(f"TENANT#{company_id}", "METADATA", updates):
                return internal_error("Failed to update tenant metadata in database", event)
                
            invalidate_entitlement_cache(company_id)
            
            audit_id = str(uuid.uuid4())
            audit_record = {
                "PK": "PLATFORM_AUDIT",
                "SK": f"ACTION#{now_iso}#{audit_id}",
                "entity_type": "PLATFORM_AUDIT",
                "action": "UPDATE_TENANT",
                "target_company_id": company_id,
                "changed_fields": changed_fields,
                "old_values": old_values,
                "new_values": new_values,
                "actor": actor,
                "timestamp": now_iso
            }
            put_item(audit_record)
            
        return _handle_get_tenant(event, company_id)
    except Exception as e:
        print(f"Error patching tenant {company_id}: {e}")
        return internal_error(str(e), event)

def _handle_get_audit(event):
    try:
        query_params = event.get('queryStringParameters', {}) or {}
        limit = 50
        if 'limit' in query_params:
            try:
                limit = int(query_params['limit'])
                if limit <= 0 or limit > 100:
                    limit = 50
            except ValueError:
                pass
                
        query_kwargs = {
            "KeyConditionExpression": Key('PK').eq('PLATFORM_AUDIT') & Key('SK').begins_with('ACTION#'),
            "ScanIndexForward": False,
            "Limit": limit
        }
        
        if query_params and 'lastKey' in query_params:
            try:
                import base64
                last_key_str = base64.b64decode(query_params['lastKey'].encode('utf-8')).decode('utf-8')
                query_kwargs['ExclusiveStartKey'] = json.loads(last_key_str)
            except Exception:
                pass
                
        response = table.query(**query_kwargs)
        items = response.get('Items', [])
        
        last_key = response.get('LastEvaluatedKey')
        last_key_encoded = None
        if last_key:
            import base64
            last_key_encoded = base64.b64encode(json.dumps(last_key).encode('utf-8')).decode('utf-8')
            
        return success({
            "audits": items,
            "lastKey": last_key_encoded
        }, event)
    except Exception as e:
        print(f"Error querying platform audits: {e}")
        return internal_error(str(e), event)

def handler(event, context):
    try:
        if not is_platform_admin(event):
            return error(403, "Forbidden: Platform Admin access required", event)

        http_method = event.get('httpMethod')
        path_params = event.get('pathParameters', {}) or {}
        path = event.get('path', '')

        if http_method == 'GET' and path == '/platform/tenants':
            return _handle_list_tenants(event)
        elif http_method == 'GET' and path.startswith('/platform/tenants/'):
            company_id = path_params.get('company_id')
            if not company_id:
                return bad_request("company_id path parameter is required", event)
            return _handle_get_tenant(event, company_id)
        elif http_method == 'PATCH' and path.startswith('/platform/tenants/'):
            company_id = path_params.get('company_id')
            if not company_id:
                return bad_request("company_id path parameter is required", event)
            return _handle_patch_tenant(event, company_id)
        elif http_method == 'GET' and path == '/platform/audit':
            return _handle_get_audit(event)
        else:
            return error(404, "Not Found", event)
    except Exception as e:
        print(f"Platform handler unhandled error: {e}")
        return internal_error(str(e), event)
