"""
tests/backend/test_platform_preview_iam.py
Static analysis test enforcing that infra/prod/platform_preview_iam.tf
contains ZERO DynamoDB write actions or administrative privileges.
"""

import os
import re
import pytest

# OPS-3A.1D production-root hygiene (commit 626f36b) relocated the platform
# preview Terraform to infra/deferred/ (R100 rename, content unchanged); the
# feature is IMPLEMENTED but intentionally NOT DEPLOYED, and its API-Gateway
# route resources were removed from the active modules/api graph. The deferred
# location is the authoritative source for the static-safety checks below until
# a separately approved activation release. See
# infra/deferred/platform-preview/README.md.
DEFERRED_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '../../infra/deferred/platform-preview')
)
IAM_TF_PATH = os.path.join(DEFERRED_DIR, 'platform_preview_iam.tf')
LAMBDA_TF_PATH = os.path.join(DEFERRED_DIR, 'platform_preview_lambda.tf')
PROD_IAM_TF_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '../../infra/prod/platform_preview_iam.tf')
)
PROD_LAMBDA_TF_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '../../infra/prod/platform_preview_lambda.tf')
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
        # Canonical deferred source exists AND is isolated from the active
        # production root. Deleting the deferred file, or re-adding either file
        # to infra/prod without an approved activation release, flips this red.
        assert os.path.exists(IAM_TF_PATH), f"Missing deferred IAM file: {IAM_TF_PATH}"
        assert os.path.exists(LAMBDA_TF_PATH), f"Missing deferred Lambda file: {LAMBDA_TF_PATH}"
        assert not os.path.exists(PROD_IAM_TF_PATH), (
            f"Deferred IAM Terraform unexpectedly present in production root: {PROD_IAM_TF_PATH}. "
            "Activation is a separately approved release."
        )
        assert not os.path.exists(PROD_LAMBDA_TF_PATH), (
            f"Deferred Lambda Terraform unexpectedly present in production root: {PROD_LAMBDA_TF_PATH}."
        )

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

    def test_api_gateway_onboarding_routes_are_deferred_not_in_active_graph(self):
        # The platform-preview feature is deferred: its API-Gateway onboarding
        # route resources were removed from the active modules/api graph by the
        # OPS-3A.1D hygiene correction and are NOT present in any active .tf.
        # Assert that isolation directly against the active modules/api/main.tf.
        with open(API_TF_PATH, 'r', encoding='utf-8') as f:
            api_lines = f.readlines()
        # Assert against ACTIVE CODE only — the hygiene correction left
        # explanatory comments in modules/api that name the removed symbols; a
        # comment is documentation, not an active route/wiring, so comment lines
        # (# or //) are excluded before the isolation check.
        api_code = ''.join(
            line for line in api_lines
            if not line.strip().startswith('#') and not line.strip().startswith('//')
        )

        for token in (
            'post_platform_onboarding_validate',
            'post_platform_onboarding_preview',
            'platform/onboarding/validate',
            'platform/onboarding/preview',
            'platform_preview_handler_invoke_arn',
        ):
            assert token not in api_code, (
                f"Deferred onboarding route token '{token}' unexpectedly present in active "
                f"{API_TF_PATH} code. Re-activation is a separately approved release."
            )

    def test_deferred_preview_lambda_scopes_invoke_only_to_validate_and_preview(self):
        # Security guarantee preserved against the authoritative deferred source:
        # the preview Lambda grants API-Gateway invoke permission ONLY for the
        # read-only validate/preview routes, and exposes no apply/approve/create/
        # requests routes.
        with open(LAMBDA_TF_PATH, 'r', encoding='utf-8') as f:
            lambda_content = f.read()

        assert '/*/POST/platform/onboarding/validate' in lambda_content
        assert '/*/POST/platform/onboarding/preview' in lambda_content
        assert 'role             = aws_iam_role.platform_preview_exec.arn' in lambda_content

        for suffix in ('apply', 'approve', 'requests', 'create'):
            assert f'platform/onboarding/{suffix}' not in lambda_content
            assert f'platform_onboarding_{suffix}' not in lambda_content
