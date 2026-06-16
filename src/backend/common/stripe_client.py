"""
Release 12G: Stripe Client Integration
Provides:
  - create_checkout_session(...) to create Stripe Checkout Sessions without SDK
"""
import os
import json
import urllib.request
import urllib.parse
import urllib.error

class StripeAPIError(Exception):
    """Exception raised for errors in the Stripe API."""
    def __init__(self, message, status_code=None, raw_body=None):
        super().__init__(message)
        self.status_code = status_code
        self.raw_body = raw_body

def create_checkout_session(company_id, request_id, client_id, amount_cents, environment="sandbox"):
    """
    Creates a Stripe Checkout Session in 'payment' mode for booking requests.
    Uses Python's built-in urllib to avoid external dependencies.
    """
    secret_key = os.environ.get("STRIPE_SECRET_KEY")
    if not secret_key:
        raise StripeAPIError("STRIPE_SECRET_KEY is not configured in environment variables.")

    # Get success and cancel URLs from environment or use sensible defaults
    default_success = "https://toganddogs.usmissionhero.com/booking/{request_id}/success?session_id={{CHECKOUT_SESSION_ID}}"
    default_cancel = "https://toganddogs.usmissionhero.com/booking/{request_id}/cancel"
    
    success_url_template = os.environ.get("STRIPE_SUCCESS_URL_TEMPLATE", default_success)
    cancel_url_template = os.environ.get("STRIPE_CANCEL_URL_TEMPLATE", default_cancel)

    success_url = success_url_template.format(request_id=request_id)
    cancel_url = cancel_url_template.format(request_id=request_id)

    payload = {
        'mode': 'payment',
        'payment_method_types[0]': 'card',
        'success_url': success_url,
        'cancel_url': cancel_url,
        'line_items[0][price_data][currency]': 'usd',
        'line_items[0][price_data][product_data][name]': f"Booking Payment for Request #{request_id}",
        'line_items[0][price_data][unit_amount]': str(amount_cents),
        'line_items[0][quantity]': '1',
        'metadata[company_id]': company_id,
        'metadata[request_id]': request_id,
        'metadata[client_id]': client_id,
        'metadata[payment_type]': 'booking',
        'metadata[environment]': environment,
    }

    data = urllib.parse.urlencode(payload).encode('utf-8')
    req = urllib.request.Request(
        "https://api.stripe.com/v1/checkout/sessions",
        data=data,
        method="POST"
    )
    req.add_header("Authorization", f"Bearer {secret_key}")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            res_body = response.read().decode('utf-8')
            return json.loads(res_body)
    except urllib.error.HTTPError as e:
        status_code = e.code
        err_body = e.read().decode('utf-8')
        print(f"STRIPE_API_ERROR: HTTP {status_code} - {err_body}")
        try:
            err_json = json.loads(err_body)
            err_msg = err_json.get('error', {}).get('message', 'Unknown Stripe API error')
        except Exception:
            err_msg = err_body or str(e)
        raise StripeAPIError(f"Stripe API error: {err_msg}", status_code=status_code, raw_body=err_body)
    except Exception as e:
        print(f"STRIPE_API_ERROR: {e}")
        raise StripeAPIError(f"Failed to communicate with Stripe: {e}")
