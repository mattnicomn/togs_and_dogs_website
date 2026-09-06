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
