"""OPS-3A.2B — Static tests for the client quote Accept/Decline API Gateway routes.

Validates the Terraform SOURCE (no terraform init/validate/plan/apply, no AWS):

  POST /client/quotes/{requestId}/accept
  POST /client/quotes/{requestId}/decline

against both the semantic deployment manifest (modules/api/deployment-semantics.tf.json)
and modules/api/main.tf. Mirrors the OPS-3A.1C validation approach: parse the manifest
as JSON, reconstruct full paths from parent chains, and assert auth / integration /
CORS / fingerprint / depends_on membership. Confirms no duplicate {requestId} resource.
"""
import json
import os
import re

HERE = os.path.dirname(__file__)
API_DIR = os.path.abspath(os.path.join(HERE, '..', '..', 'modules', 'api'))
MANIFEST_PATH = os.path.join(API_DIR, 'deployment-semantics.tf.json')
MAIN_TF_PATH = os.path.join(API_DIR, 'main.tf')

ACCEPT_RES = 'client_quote_accept'
DECLINE_RES = 'client_quote_decline'
ACCEPT_METHOD = 'post_client_quote_accept'
DECLINE_METHOD = 'post_client_quote_decline'
ACCEPT_INTEG = 'post_client_quote_accept_lambda'
DECLINE_INTEG = 'post_client_quote_decline_lambda'
PARENT_RES = 'client_quote_id'


def _manifest():
    with open(MANIFEST_PATH, encoding='utf-8') as f:
        return json.load(f)


def _semantics(m):
    # The manifest wraps the semantic model under local.api_deployment_semantics;
    # tolerate either a top-level dict or a nested 'locals' shape.
    if 'resources' in m:
        return m
    # find the first object that has a 'resources' key
    for v in m.values():
        if isinstance(v, dict) and 'resources' in v:
            return v
        if isinstance(v, dict):
            for vv in v.values():
                if isinstance(vv, dict) and 'resources' in vv:
                    return vv
    raise AssertionError('could not locate semantic model with resources in manifest')


def _reconstruct_path(sem, resource_key):
    """Walk parent_key chain to build the full path for a resource."""
    resources = sem['resources']
    parts = []
    key = resource_key
    seen = set()
    while key is not None and key in resources and key not in seen:
        seen.add(key)
        parts.append(resources[key]['path_part'])
        key = resources[key].get('parent_key')
    return '/' + '/'.join(reversed(parts))


# ---------------------------------------------------------------------------
# Manifest JSON validity
# ---------------------------------------------------------------------------

def test_manifest_is_valid_json():
    m = _manifest()
    assert isinstance(m, dict)


# ---------------------------------------------------------------------------
# 1-3: resources exist and parent from client_quote_id
# ---------------------------------------------------------------------------

def test_accept_resource_exists_and_parented():
    sem = _semantics(_manifest())
    assert ACCEPT_RES in sem['resources']
    assert sem['resources'][ACCEPT_RES]['parent_key'] == PARENT_RES
    assert sem['resources'][ACCEPT_RES]['path_part'] == 'accept'


def test_decline_resource_exists_and_parented():
    sem = _semantics(_manifest())
    assert DECLINE_RES in sem['resources']
    assert sem['resources'][DECLINE_RES]['parent_key'] == PARENT_RES
    assert sem['resources'][DECLINE_RES]['path_part'] == 'decline'


# ---------------------------------------------------------------------------
# 4-6: POST methods, Cognito auth, existing authorizer
# ---------------------------------------------------------------------------

def test_methods_are_post_cognito_with_existing_authorizer():
    sem = _semantics(_manifest())
    for mkey, rkey in ((ACCEPT_METHOD, ACCEPT_RES), (DECLINE_METHOD, DECLINE_RES)):
        meth = sem['methods'][mkey]
        assert meth['resource_key'] == rkey
        assert meth['http_method'] == 'POST'
        assert meth['authorization'] == 'COGNITO_USER_POOLS'
        assert meth['authorizer_key'] == 'cognito'


# ---------------------------------------------------------------------------
# 7-8: AWS_PROXY integration to the existing admin Lambda
# ---------------------------------------------------------------------------

def test_integrations_are_aws_proxy_to_admin_lambda():
    sem = _semantics(_manifest())
    for ikey, mkey in ((ACCEPT_INTEG, ACCEPT_METHOD), (DECLINE_INTEG, DECLINE_METHOD)):
        integ = sem['integrations'][ikey]
        assert integ['method_key'] == mkey
        assert integ['type'] == 'AWS_PROXY'
        assert integ['integration_http_method'] == 'POST'
        assert integ['target_reference'] == 'admin_handler_invoke_arn'


# ---------------------------------------------------------------------------
# 9: both included in CORS
# ---------------------------------------------------------------------------

def test_both_resources_in_cors():
    sem = _semantics(_manifest())
    cors_keys = sem['cors']['resource_keys']
    assert ACCEPT_RES in cors_keys
    assert DECLINE_RES in cors_keys


# ---------------------------------------------------------------------------
# 10: both represented in the deployment fingerprint (manifest IS the fingerprint
#     input; prove all route objects are present together)
# ---------------------------------------------------------------------------

def test_route_objects_present_in_fingerprint_manifest():
    sem = _semantics(_manifest())
    assert ACCEPT_RES in sem['resources'] and DECLINE_RES in sem['resources']
    assert ACCEPT_METHOD in sem['methods'] and DECLINE_METHOD in sem['methods']
    assert ACCEPT_INTEG in sem['integrations'] and DECLINE_INTEG in sem['integrations']
    assert ACCEPT_RES in sem['cors']['resource_keys']
    assert DECLINE_RES in sem['cors']['resource_keys']


# ---------------------------------------------------------------------------
# 12: exact reconstructed paths; no duplicate {requestId}
# ---------------------------------------------------------------------------

def test_reconstructed_paths_exact():
    sem = _semantics(_manifest())
    assert _reconstruct_path(sem, ACCEPT_RES) == '/client/quotes/{requestId}/accept'
    assert _reconstruct_path(sem, DECLINE_RES) == '/client/quotes/{requestId}/decline'


def test_no_duplicate_request_id_resource():
    sem = _semantics(_manifest())
    # Exactly one resource with path_part '{requestId}' under client_quotes.
    reqid = [k for k, v in sem['resources'].items()
             if v.get('path_part') == '{requestId}' and v.get('parent_key') == 'client_quotes']
    assert reqid == [PARENT_RES]


# ---------------------------------------------------------------------------
# main.tf cross-checks (resources/methods/integrations + depends_on)
# ---------------------------------------------------------------------------

def _main_tf():
    with open(MAIN_TF_PATH, encoding='utf-8') as f:
        return f.read()


def test_main_tf_declares_resources_methods_integrations():
    tf = _main_tf()
    for name in (ACCEPT_RES, DECLINE_RES):
        assert f'resource "aws_api_gateway_resource" "{name}"' in tf
    for name in (ACCEPT_METHOD, DECLINE_METHOD):
        assert f'resource "aws_api_gateway_method" "{name}"' in tf
    for name in (ACCEPT_INTEG, DECLINE_INTEG):
        assert f'resource "aws_api_gateway_integration" "{name}"' in tf


def test_main_tf_methods_use_cognito_authorizer():
    tf = _main_tf()
    # Each new method block references the cognito authorizer and POST.
    for name in (ACCEPT_METHOD, DECLINE_METHOD):
        block = re.search(
            r'resource "aws_api_gateway_method" "' + re.escape(name) + r'" \{(.*?)\n\}',
            tf, re.S)
        assert block, f'method block {name} not found'
        body = block.group(1)
        assert 'http_method   = "POST"' in body
        assert 'authorization = "COGNITO_USER_POOLS"' in body
        assert 'authorizer_id = aws_api_gateway_authorizer.cognito.id' in body


def test_main_tf_integrations_target_admin_lambda():
    tf = _main_tf()
    for name in (ACCEPT_INTEG, DECLINE_INTEG):
        block = re.search(
            r'resource "aws_api_gateway_integration" "' + re.escape(name) + r'" \{(.*?)\n\}',
            tf, re.S)
        assert block, f'integration block {name} not found'
        body = block.group(1)
        assert 'type                    = "AWS_PROXY"' in body
        assert 'uri                     = var.admin_handler_invoke_arn' in body


# ---------------------------------------------------------------------------
# 11: both POST integrations represented in deployment depends_on
# ---------------------------------------------------------------------------

def test_integrations_in_deployment_depends_on():
    tf = _main_tf()
    # Anchor on the aws_api_gateway_deployment "main" resource specifically; there is
    # also a smaller depends_on on a CORS integration_response resource.
    dep_block = re.search(
        r'resource "aws_api_gateway_deployment" "main" \{(.*?)\n\}', tf, re.S)
    assert dep_block, 'deployment "main" resource not found'
    dep = re.search(r'depends_on\s*=\s*\[(.*?)\]', dep_block.group(1), re.S)
    assert dep, 'deployment depends_on block not found'
    body = dep.group(1)
    assert 'aws_api_gateway_integration.post_client_quote_accept_lambda' in body
    assert 'aws_api_gateway_integration.post_client_quote_decline_lambda' in body


def test_both_resources_in_cors_resources_map_in_main_tf():
    tf = _main_tf()
    assert '"client_quote_accept" : aws_api_gateway_resource.client_quote_accept.id' in tf
    assert '"client_quote_decline" : aws_api_gateway_resource.client_quote_decline.id' in tf
