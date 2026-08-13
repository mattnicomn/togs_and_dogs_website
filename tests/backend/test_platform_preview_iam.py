"""
tests/backend/test_platform_preview_iam.py
Static analysis test enforcing that infra/prod/platform_preview_iam.tf
contains ZERO DynamoDB write actions or administrative privileges.
"""

import os
import re
import pytest

IAM_TF_PATH = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        '../../infra/prod/platform_preview_iam.tf'
    )
)
LAMBDA_TF_PATH = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        '../../infra/prod/platform_preview_lambda.tf'
    )
)
API_TF_PATH = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        '../../modules/api/main.tf'
    )
)

FORBIDDEN_IAM_ACTIONS = [
    'dynamodb:PutItem',
    'dynamodb:UpdateItem',
    'dynamodb:DeleteItem',
    'dynamodb:BatchWriteItem',
    'dynamodb:TransactWriteItems',
    'dynamodb:CreateTable',
    'dynamodb:DeleteTable',
    'cognito-idp:',
    'secretsmanager:',
    'ses:',
    'lambda:InvokeFunction',
    'states:StartExecution',
]


class TestPlatformPreviewIAMStaticAnalysis:
    def test_iam_tf_file_exists(self):
        assert os.path.exists(IAM_TF_PATH), f"Missing IAM file: {IAM_TF_PATH}"

    def test_no_forbidden_write_actions_in_iam_tf(self):
        with open(IAM_TF_PATH, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # Filter out comment lines starting with # or //
        non_comment_lines = [
            line for line in lines
            if not line.strip().startswith('#') and not line.strip().startswith('//')
        ]
        code_content = ''.join(non_comment_lines)

        for forbidden in FORBIDDEN_IAM_ACTIONS:
            assert forbidden not in code_content, (
                f"SECURITY VIOLATION: Forbidden action '{forbidden}' found in {IAM_TF_PATH}!"
            )

    def test_allowed_actions_strictly_limited_to_getitem_and_scan(self):
        with open(IAM_TF_PATH, 'r', encoding='utf-8') as f:
            content = f.read()

        # Find all Action = [ ... ] blocks in the file
        actions = re.findall(r'"dynamodb:([A-Za-z]+)"', content)

        # Ensure only GetItem and Scan are present
        allowed = {'GetItem', 'Scan'}
        for action in actions:
            assert action in allowed, (
                f"SECURITY VIOLATION: Unexpected DynamoDB action 'dynamodb:{action}' found in {IAM_TF_PATH}. "
                f"Only GetItem and Scan are permitted."
            )

    def test_purpose_tag_identifies_readonly_role(self):
        with open(IAM_TF_PATH, 'r', encoding='utf-8') as f:
            content = f.read()

        assert 'platform-onboarding-preview-readonly' in content

    def test_preview_lambda_uses_dedicated_role_and_scoped_permissions(self):
        with open(LAMBDA_TF_PATH, 'r', encoding='utf-8') as f:
            content = f.read()

        assert 'role             = aws_iam_role.platform_preview_exec.arn' in content
        assert 'module.iam.lambda_role_arn' not in content
        assert '/*/POST/platform/onboarding/validate' in content
        assert '/*/POST/platform/onboarding/preview' in content

    def test_api_gateway_exposes_only_authenticated_validate_and_preview_routes(self):
        with open(API_TF_PATH, 'r', encoding='utf-8') as f:
            content = f.read()

        for suffix in ('validate', 'preview'):
            assert f'path_part   = "{suffix}"' in content
            method_name = f'post_platform_onboarding_{suffix}'
            method_match = re.search(
                rf'resource "aws_api_gateway_method" "{method_name}" \{{(.*?)\n\}}',
                content,
                re.DOTALL,
            )
            assert method_match, f'Missing API method {method_name}'
            method_body = method_match.group(1)
            assert 'http_method   = "POST"' in method_body
            assert 'authorization = "COGNITO_USER_POOLS"' in method_body
            assert 'authorizer_id = aws_api_gateway_authorizer.cognito.id' in method_body
            assert f'uri                     = var.platform_preview_handler_invoke_arn' in content

        for suffix in ('apply', 'approve', 'requests', 'create'):
            assert f'platform_onboarding_{suffix}' not in content
