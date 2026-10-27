import sys
import os

# Set required environment variables before any backend code is imported
os.environ.setdefault('DATA_TABLE_NAME', 'test-table')

# Add src/backend to sys.path so handlers and common can be imported
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src/backend'))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)


import pytest
from unittest.mock import Mock


@pytest.fixture
def primary_google_binding(monkeypatch):
    """Opt-in owned primary metadata fixture; real resolver, no caller fallback."""
    from common import db, google_calendar
    name = 'togs-and-dogs-prod/google/user-tokens'
    monkeypatch.setenv('GOOGLE_USER_TOKENS_NAME', name)
    row = {'PK': 'TENANT#tog_and_dogs', 'SK': 'METADATA',
           'company_id': 'tog_and_dogs', 'is_active': True,
           'subscription_status': 'active'}
    get = Mock(side_effect=lambda **kw: {'Item': row} if kw['Key'] == {
        'PK': row['PK'], 'SK': row['SK']} else {})
    monkeypatch.setattr(db.table, 'get_item', get)
    describe = Mock(return_value={
        'ARN': 'arn:aws:secretsmanager:us-east-1:123456789012:secret:' + name + '-Ab1234',
        'Name': name, 'Tags': [{'Key': 'CompanyId', 'Value': 'tog_and_dogs'}]})
    monkeypatch.setattr(google_calendar.secrets, 'describe_secret', describe)
    return get, describe


# --- Gate C3b: credential-free CI real-AWS-call guard -----------------------
# Session-scoped, autouse. Installs a botocore guard that blocks any real
# *.amazonaws.com call that is not served by moto, failing loudly BEFORE
# network egress. Opt-in: only active when CI_AWS_CALL_GUARD is truthy (CI
# sets it), so normal local test runs are unchanged. See tests/backend/_aws_guard.py.
import pytest as _pytest  # noqa: E402  (pytest already imported above)

# Import the guard module from this conftest's own directory, independent of
# whether `tests`/`tests.backend` is an importable package. The directory of
# this file is reliably present on sys.path during pytest collection.
_here = os.path.dirname(os.path.abspath(__file__))
if _here not in sys.path:
    sys.path.insert(0, _here)
import _aws_guard  # noqa: E402


@_pytest.fixture(scope="session", autouse=True)
def _ci_block_real_aws_calls():
    """Block real AWS calls for the whole backend session when CI-activated.

    No-op unless CI_AWS_CALL_GUARD is truthy, so local development/test behavior
    is unchanged. When active, an unmocked real AWS call raises
    RealAWSCallBlocked (loud failure), and moto-served calls pass through.
    """
    installed = _aws_guard.install()
    try:
        yield
    finally:
        if installed:
            _aws_guard.uninstall()
