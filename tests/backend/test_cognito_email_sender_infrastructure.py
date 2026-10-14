"""Static safety checks for the isolated custom sender infrastructure."""

from pathlib import Path
import re


REPO_ROOT = Path(__file__).resolve().parents[2]
# OPS-3A.1D production-root hygiene (commit 626f36b) relocated this Terraform to
# infra/deferred/ (R100 rename, content unchanged); the feature is IMPLEMENTED
# but intentionally NOT DEPLOYED. The deferred location is the authoritative
# source for the static-safety checks below until a separately approved
# activation release. See infra/deferred/cognito-email-sender/README.md.
DEFERRED_DIR = REPO_ROOT / "infra" / "deferred" / "cognito-email-sender"
SENDER_TF = DEFERRED_DIR / "cognito_email_sender.tf"
PROD_SENDER_TF = REPO_ROOT / "infra" / "prod" / "cognito_email_sender.tf"
AUTH_TF = REPO_ROOT / "modules" / "auth" / "main.tf"
PROD_MAIN_TF = REPO_ROOT / "infra" / "prod" / "main.tf"
LOCK_FILE = REPO_ROOT / "src" / "cognito_email_sender" / "requirements.lock"
BUILD_SCRIPT = REPO_ROOT / "scripts" / "build_cognito_email_sender_package.py"


def _code_without_comments(path: Path) -> str:
    return "\n".join(
        line for line in path.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("#")
    )


def test_cognito_email_sender_terraform_is_deferred_and_isolated_from_prod_root():
    """The custom email sender is implemented-but-not-deployed. Its Terraform
    must live only under infra/deferred/ and must not be present or wired in the
    active infra/prod root. This guards both an accidental deletion and an
    unapproved production re-activation (either flips this test red)."""
    # 1. Canonical deferred source exists.
    assert SENDER_TF.exists(), f"Deferred Terraform missing at canonical path: {SENDER_TF}"
    # 2. Absent from the active production root.
    assert not PROD_SENDER_TF.exists(), (
        f"Deferred Terraform unexpectedly present in production root: {PROD_SENDER_TF}. "
        "Activation is a separately approved release; it must not appear in infra/prod without it."
    )
    # 3. The active production root does not instantiate/activate the deferred
    #    resources: module "auth" custom-email-sender inputs stay null and the
    #    prod root does not reference the deferred filename or sender resources.
    prod_main = _code_without_comments(PROD_MAIN_TF)
    assert "cognito_email_sender.tf" not in prod_main
    assert "aws_kms_key.cognito_email_sender" not in prod_main
    assert "aws_lambda_function.cognito_email_sender" not in prod_main
    assert "custom_email_sender_lambda_arn  = null" in prod_main
    assert "custom_email_sender_kms_key_arn = null" in prod_main


def test_sender_uses_dedicated_source_and_package_not_shared_backend_archive():
    sender_tf = _code_without_comments(SENDER_TF)
    prod_main = _code_without_comments(PROD_MAIN_TF)
    build_script = BUILD_SCRIPT.read_text(encoding="utf-8")

    assert 'source_dir  = "${path.module}/../../src/backend"' in prod_main
    assert "src/cognito_email_sender" not in prod_main
    assert "cognito-email-sender.zip" in sender_tf
    assert 'SOURCE_DIR = REPO_ROOT / "src" / "cognito_email_sender"' in build_script
    assert 'REPO_ROOT / "src" / "backend"' not in build_script


def test_sender_role_is_dedicated_and_has_only_required_service_actions():
    content = _code_without_comments(SENDER_TF)
    quoted_actions = set(re.findall(r'"([a-z][a-z0-9-]+:[A-Za-z*]+)"', content))

    assert "module.iam.lambda_role_arn" not in content
    assert quoted_actions == {
        "sts:AssumeRole",
        "kms:*",
        "kms:Decrypt",
        "logs:CreateLogStream",
        "logs:PutLogEvents",
        "secretsmanager:GetSecretValue",
        "lambda:InvokeFunction",
    }
    for forbidden_prefix in (
        "dynamodb:",
        "ses:",
        "sns:",
        "states:",
        "stripe:",
        "cognito-idp:Admin",
    ):
        assert forbidden_prefix not in content


def test_secret_and_decrypt_permissions_are_exact_resource_scoped():
    content = _code_without_comments(SENDER_TF)
    assert "resources = [module.secrets.postmark_token_arn]" in content
    assert "resources = [aws_kms_key.cognito_email_sender.arn]" in content
    assert 'variable = "kms:EncryptionContext:userpool-id"' in content
    assert 'values   = ["${var.aws_region}_*"]' in content


def test_cognito_configuration_uses_v1_sender_kms_and_scoped_invoke_permission():
    auth = _code_without_comments(AUTH_TF)
    sender_tf = _code_without_comments(SENDER_TF)

    assert "custom_email_sender" in auth
    assert 'lambda_version = "V1_0"' in auth
    assert "kms_key_id = var.custom_email_sender_kms_key_arn" in auth
    assert re.search(r'principal\s*=\s*"cognito-idp\.amazonaws\.com"', sender_tf)
    assert re.search(r"source_arn\s*=\s*module\.auth\.user_pool_arn", sender_tf)
    assert "source_account = data.aws_caller_identity.current.account_id" in sender_tf


def test_kms_key_is_symmetric_rotating_and_aliased():
    content = _code_without_comments(SENDER_TF)
    assert re.search(r'key_usage\s*=\s*"ENCRYPT_DECRYPT"', content)
    assert 'customer_master_key_spec = "SYMMETRIC_DEFAULT"' in content
    assert "enable_key_rotation" in content
    assert 'name          = "alias/${local.name_prefix}-cognito-email-sender"' in content


def test_deployment_dependency_versions_are_all_pinned():
    requirements = [
        line.strip()
        for line in LOCK_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert requirements
    assert all(re.fullmatch(r"[A-Za-z0-9_.-]+==[A-Za-z0-9_.+-]+", item) for item in requirements)
    assert "aws-encryption-sdk==4.0.6" in requirements


def test_missing_package_fails_before_plan_or_apply_and_hashes_when_present():
    content = _code_without_comments(SENDER_TF)
    assert "fileexists(local.cognito_email_sender_package_path)" in content
    assert "try(filebase64sha256(local.cognito_email_sender_package_path), null)" in content


def test_builder_removes_host_specific_nondeterministic_metadata():
    content = BUILD_SCRIPT.read_text(encoding="utf-8")
    assert 'shutil.rmtree(staging / "bin", ignore_errors=True)' in content
    assert 'staging.glob("*.dist-info/RECORD")' in content
