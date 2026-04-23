import json
from decimal import Decimal

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            if obj % 1 == 0:
                return int(obj)
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "https://toganddogs.usmissionhero.com",  # Primary production domain (US Mission Hero managed)
    "https://toganddogs.com",                 # Client-owned domain (future migration target)
    "https://www.toganddogs.com",
    "https://app.toganddogs.com"              # Legacy reference — preserved for transition
]

def format_response(status_code, body, event=None):
    # Default to the first allowed origin for safety, or reflect if in whitelist
    origin = "*"
    if event and isinstance(event, dict):
        headers = event.get('headers') or {}
        # Case-insensitive check for Origin header
        request_origin = headers.get('origin') or headers.get('Origin')
        if request_origin in ALLOWED_ORIGINS:
            origin = request_origin
        else:
            # If not in whitelist, return the primary production domain
            origin = ALLOWED_ORIGINS[1]  # toganddogs.usmissionhero.com

    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
            "Access-Control-Allow-Methods": "GET,POST,PUT,PATCH,DELETE,OPTIONS"
        },
        "body": json.dumps(body, cls=DecimalEncoder)
    }

def success(body, event=None):
    return format_response(200, body, event)

def error(status_code, message, event=None):
    return format_response(status_code, {"error": message}, event)

def bad_request(message, event=None):
    return error(400, message, event)

def not_found(message, event=None):
    return error(404, message, event)

def internal_error(message="Internal server error", event=None):
    return error(500, message, event)
