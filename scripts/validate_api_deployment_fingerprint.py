#!/usr/bin/env python3
"""Fail-closed static coverage checks for the API deployment semantic manifest."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
API_MAIN = ROOT / "modules" / "api" / "main.tf"
MANIFEST_PATH = ROOT / "modules" / "api" / "deployment-semantics.json"

BLOCK_HEADER = re.compile(
    r'^resource "(?P<type>aws_api_gateway_[^"]+)" "(?P<name>[^"]+)" \{',
    re.MULTILINE,
)


def fail(message: str) -> None:
    raise AssertionError(message)


def resource_blocks(source: str) -> dict[tuple[str, str], str]:
    """Return top-level resource bodies using the next resource header as a boundary."""
    matches = list(BLOCK_HEADER.finditer(source))
    blocks: dict[tuple[str, str], str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(source)
        blocks[(match.group("type"), match.group("name"))] = source[match.end() : end]
    return blocks


def expression(body: str, field: str) -> str:
    match = re.search(rf"(?m)^  {re.escape(field)}\s*=\s*(.+?)\s*$", body)
    if not match:
        fail(f"Missing {field!r} in API Gateway resource block")
    return match.group(1).split("#", 1)[0].strip()


def quoted(body: str, field: str) -> str:
    value = expression(body, field)
    match = re.match(r'^"((?:\\.|[^"])*)"$', value)
    if not match:
        fail(f"Expected a literal string for {field!r}, found {value!r}")
    return json.loads(value)


def referenced_name(value: str, resource_type: str, attribute: str) -> str:
    match = re.fullmatch(rf"{re.escape(resource_type)}\.([^.]+)\.{re.escape(attribute)}", value)
    if not match:
        fail(f"Expected {resource_type}.<name>.{attribute}, found {value!r}")
    return match.group(1)


def full_path(resources: dict[str, dict[str, object]], key: str) -> str:
    parts: list[str] = []
    visited: set[str] = set()
    while key != "root":
        if key in visited:
            fail(f"Cycle in semantic API resource ancestry at {key!r}")
        visited.add(key)
        if key not in resources:
            fail(f"Unknown semantic API resource parent {key!r}")
        resource = resources[key]
        parts.append(str(resource["path_part"]))
        key = str(resource["parent_key"])
    return "/" + "/".join(reversed(parts))


def assert_assignment(body: str, key: str, value: object) -> None:
    if isinstance(value, bool):
        expected = "true" if value else "false"
    else:
        expected = json.dumps(value, separators=(",", ":"))
    pattern = rf'(?m)^\s+{re.escape(json.dumps(key))}\s*=\s*{re.escape(expected)}(?:\s|$)'
    if not re.search(pattern, body):
        fail(f"Missing semantic assignment {key!r} = {value!r}")


def main() -> int:
    source = API_MAIN.read_text(encoding="utf-8")
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    blocks = resource_blocks(source)

    resource_type = "aws_api_gateway_resource"
    actual_resource_names = {name for kind, name in blocks if kind == resource_type}
    if actual_resource_names != set(manifest["resources"]):
        fail("Semantic resource manifest does not exactly cover aws_api_gateway_resource blocks")

    for name, semantic in manifest["resources"].items():
        body = blocks[(resource_type, name)]
        if quoted(body, "path_part") != semantic["path_part"]:
            fail(f"Path part mismatch for API resource {name!r}")
        parent = expression(body, "parent_id")
        if parent == "aws_api_gateway_rest_api.main.root_resource_id":
            parent_key = "root"
        else:
            parent_key = referenced_name(parent, resource_type, "id")
        if parent_key != semantic["parent_key"]:
            fail(f"Parent mismatch for API resource {name!r}")
        full_path(manifest["resources"], name)

    authorizer_type = "aws_api_gateway_authorizer"
    actual_authorizer_names = {name for kind, name in blocks if kind == authorizer_type}
    if actual_authorizer_names != set(manifest["authorizers"]):
        fail("Semantic authorizer manifest does not exactly cover API authorizers")
    for name, semantic in manifest["authorizers"].items():
        body = blocks[(authorizer_type, name)]
        if quoted(body, "type") != semantic["type"]:
            fail(f"Type mismatch for API authorizer {name!r}")
        provider_arns = expression(body, "provider_arns")
        if provider_arns != "[var.user_pool_arn]":
            fail(f"Provider reference mismatch for API authorizer {name!r}")
        if semantic["provider_reference_keys"] != ["user_pool_arn"]:
            fail(f"Canonical provider reference mismatch for API authorizer {name!r}")
        identity_match = re.search(r'(?m)^  identity_source\s*=\s*"([^"]+)"\s*$', body)
        actual_identity_source = (
            identity_match.group(1)
            if identity_match
            else "method.request.header.Authorization"
        )
        if actual_identity_source != semantic["identity_source"]:
            fail(f"Identity source mismatch for API authorizer {name!r}")
        ttl_match = re.search(
            r"(?m)^  authorizer_result_ttl_in_seconds\s*=\s*([0-9]+)\s*$", body
        )
        actual_ttl = int(ttl_match.group(1)) if ttl_match else 300
        if actual_ttl != semantic["result_ttl_seconds"]:
            fail(f"Result TTL mismatch for API authorizer {name!r}")

    method_type = "aws_api_gateway_method"
    actual_method_names = {
        name for kind, name in blocks if kind == method_type and name != "options"
    }
    if actual_method_names != set(manifest["methods"]):
        fail("Semantic method manifest does not exactly cover non-CORS API methods")

    unsupported_method_fields = (
        "authorization_scopes",
        "operation_name",
        "request_models",
        "request_parameters",
        "request_validator_id",
    )
    for name, semantic in manifest["methods"].items():
        body = blocks[(method_type, name)]
        resource_key = referenced_name(expression(body, "resource_id"), resource_type, "id")
        if resource_key != semantic["resource_key"]:
            fail(f"Resource binding mismatch for API method {name!r}")
        if quoted(body, "http_method") != semantic["http_method"]:
            fail(f"HTTP method mismatch for API method {name!r}")
        if quoted(body, "authorization") != semantic["authorization"]:
            fail(f"Authorization mismatch for API method {name!r}")
        authorizer_match = re.search(
            r"(?m)^  authorizer_id\s*=\s*aws_api_gateway_authorizer\.([^.]+)\.id\s*$",
            body,
        )
        authorizer_key = authorizer_match.group(1) if authorizer_match else ""
        if authorizer_key != semantic.get("authorizer_key", ""):
            fail(f"Authorizer mismatch for API method {name!r}")
        api_key_match = re.search(r"(?m)^  api_key_required\s*=\s*(true|false)\s*$", body)
        api_key_required = api_key_match and api_key_match.group(1) == "true"
        if bool(api_key_required) != semantic.get("api_key_required", False):
            fail(f"API-key requirement mismatch for API method {name!r}")
        for field in unsupported_method_fields:
            if re.search(rf"(?m)^  {field}\s*=", body):
                fail(f"Static validator must be extended for configured method field {field!r}")

    integration_type = "aws_api_gateway_integration"
    actual_integration_names = {
        name for kind, name in blocks if kind == integration_type and name != "options_mock"
    }
    if actual_integration_names != set(manifest["integrations"]):
        fail("Semantic integration manifest does not exactly cover non-CORS API integrations")

    unsupported_integration_fields = (
        "cache_key_parameters",
        "cache_namespace",
        "connection_id",
        "connection_type",
        "content_handling",
        "credentials",
        "passthrough_behavior",
        "request_parameters",
        "request_templates",
        "timeout_milliseconds",
        "tls_config",
    )
    for name, semantic in manifest["integrations"].items():
        body = blocks[(integration_type, name)]
        method_key = referenced_name(expression(body, "http_method"), method_type, "http_method")
        if method_key != semantic["method_key"]:
            fail(f"Method binding mismatch for API integration {name!r}")
        integration_resource = referenced_name(expression(body, "resource_id"), resource_type, "id")
        if integration_resource != manifest["methods"][method_key]["resource_key"]:
            fail(f"Resource binding mismatch for API integration {name!r}")
        if quoted(body, "type") != semantic["type"]:
            fail(f"Type mismatch for API integration {name!r}")
        if quoted(body, "integration_http_method") != semantic["integration_http_method"]:
            fail(f"Integration HTTP method mismatch for {name!r}")
        uri = expression(body, "uri")
        uri_match = re.fullmatch(r"var\.([A-Za-z0-9_]+)", uri)
        if not uri_match or uri_match.group(1) != semantic["target_reference"]:
            fail(f"Target reference mismatch for API integration {name!r}")
        for field in unsupported_integration_fields:
            if re.search(rf"(?m)^  {field}\s*=", body):
                fail(f"Static validator must be extended for configured integration field {field!r}")

    cors_body_match = re.search(
        r'(?ms)locals \{\s*cors_resources\s*=\s*\{(?P<body>.*?)\n  \}', source
    )
    if not cors_body_match:
        fail("Could not locate local.cors_resources")
    cors_resource_keys = set(re.findall(r'"([^"]+)"\s*:', cors_body_match.group("body")))
    if cors_resource_keys != set(manifest["cors"]["resource_keys"]):
        fail("CORS semantic resource coverage differs from local.cors_resources")

    options_body = blocks[(method_type, "options")]
    if quoted(options_body, "http_method") != manifest["cors"]["method"]["http_method"]:
        fail("CORS HTTP method differs from semantic manifest")
    if quoted(options_body, "authorization") != manifest["cors"]["method"]["authorization"]:
        fail("CORS authorization differs from semantic manifest")

    options_integration = blocks[(integration_type, "options_mock")]
    if quoted(options_integration, "type") != manifest["cors"]["integration"]["type"]:
        fail("CORS integration type differs from semantic manifest")
    request_template = manifest["cors"]["integration"]["request_templates"]["application/json"]
    assert_assignment(options_integration, "application/json", request_template)

    method_response = blocks[("aws_api_gateway_method_response", "options_200")]
    if quoted(method_response, "status_code") != manifest["cors"]["method_response"]["status_code"]:
        fail("CORS method response status differs from semantic manifest")
    for key, value in manifest["cors"]["method_response"]["response_models"].items():
        assert_assignment(method_response, key, value)
    for key, value in manifest["cors"]["method_response"]["response_parameters"].items():
        assert_assignment(method_response, key, value)

    integration_response = blocks[("aws_api_gateway_integration_response", "options_200")]
    integration_status = expression(integration_response, "status_code")
    if integration_status != "aws_api_gateway_method_response.options_200[each.key].status_code":
        fail("CORS integration response no longer follows the method response status")
    if (
        manifest["cors"]["integration_response"]["status_code"]
        != manifest["cors"]["method_response"]["status_code"]
    ):
        fail("CORS integration response status differs from semantic manifest")
    for key, value in manifest["cors"]["integration_response"]["response_parameters"].items():
        assert_assignment(integration_response, key, value)

    gateway_type = "aws_api_gateway_gateway_response"
    actual_gateway_names = {name for kind, name in blocks if kind == gateway_type}
    if actual_gateway_names != set(manifest["gateway_responses"]):
        fail("Gateway response semantic manifest coverage differs from Terraform resources")
    for name, semantic in manifest["gateway_responses"].items():
        body = blocks[(gateway_type, name)]
        if quoted(body, "response_type") != semantic["response_type"]:
            fail(f"Gateway response type mismatch for {name!r}")
        if quoted(body, "status_code") != semantic["status_code"]:
            fail(f"Gateway response status mismatch for {name!r}")
        for key, value in semantic["response_parameters"].items():
            assert_assignment(body, key, value)
        for key, value in semantic["response_templates"].items():
            assert_assignment(body, key, value)

    deployment_body = blocks[("aws_api_gateway_deployment", "main")]
    if "redeployment = module.deployment_fingerprint.sha1" not in deployment_body:
        fail("API deployment is not driven solely by the semantic fingerprint module")
    if "jsonencode([" in deployment_body:
        fail("Whole-resource deployment hashing remains in aws_api_gateway_deployment.main")
    dependency_integrations = set(
        re.findall(r"aws_api_gateway_integration\.([A-Za-z0-9_]+)", deployment_body)
    )
    dependency_integrations.discard("options_mock")
    if dependency_integrations != set(manifest["integrations"]):
        fail("Deployment depends_on does not exactly cover all non-CORS integrations")
    for forbidden in ("source_code_hash", "backend.zip", "last_modified"):
        if forbidden in deployment_body or forbidden in MANIFEST_PATH.read_text(encoding="utf-8"):
            fail(f"Non-API backend package field {forbidden!r} entered deployment semantics")

    e3a_cases = (
        ("admin_job_start", "/admin/job/start", "post_admin_job_start", "POST", "post_admin_job_start_lambda"),
        ("admin_request_id", "/admin/requests/{requestId}", "get_admin_request", "GET", "get_admin_request_lambda"),
    )
    for resource_key, path, method_key, verb, integration_key in e3a_cases:
        if full_path(manifest["resources"], resource_key) != path:
            fail(f"E3A semantic path {path!r} is not preserved")
        method = manifest["methods"][method_key]
        if method["resource_key"] != resource_key or method["http_method"] != verb:
            fail(f"E3A semantic method {verb} {path} is not preserved")
        if method.get("authorizer_key") != "cognito":
            fail(f"E3A semantic authorization for {verb} {path} is not preserved")
        if manifest["integrations"][integration_key]["method_key"] != method_key:
            fail(f"E3A semantic integration for {verb} {path} is not preserved")
        if resource_key not in manifest["cors"]["resource_keys"]:
            fail(f"E3A CORS coverage for {verb} {path} is not preserved")

    print(
        "API deployment semantic manifest validated: "
        f"{len(manifest['resources'])} resources, "
        f"{len(manifest['methods'])} methods, "
        f"{len(manifest['integrations'])} integrations, "
        f"{len(manifest['cors']['resource_keys'])} CORS resources, "
        f"{len(manifest['gateway_responses'])} gateway responses."
    )
    print("E3A semantic coverage validated; backend package metadata is excluded.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except AssertionError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
