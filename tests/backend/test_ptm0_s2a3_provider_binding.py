"""Offline ownership contract tests; all SDK/value/provider operations mocked."""
import json
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock

import pytest
from common import db, google_calendar as gc

PRIMARY = 'tog_and_dogs'
ALPHA = 'test_tenant_alpha'
NAME = 'unrelated/opaque.connection'
PREFIX = 'arn:aws:secretsmanager:us-east-1:123456789012:secret:'
ARN = PREFIX + NAME + '-Ab1234'
LEGACY_NAME = 'togs-and-dogs-prod/google/user-tokens'
LEGACY_ARN = PREFIX + LEGACY_NAME + '-Ab1234'


@pytest.fixture
def binding(monkeypatch):
    row = {'PK': 'TENANT#' + ALPHA, 'SK': 'METADATA', 'company_id': ALPHA,
           'calendar_secret_ref': NAME}
    description = {'ARN': ARN, 'Name': NAME,
                   'Tags': [{'Key': 'CompanyId', 'Value': ALPHA}]}
    table = Mock()
    table.get_item.return_value = {'Item': row}
    secrets = Mock()
    secrets.meta.region_name = 'us-east-1'
    secrets.describe_secret.return_value = description
    secrets.get_secret_value.return_value = {'SecretString': '{}'}
    monkeypatch.setattr(db, 'table', table)
    monkeypatch.setattr(gc, 'secrets', secrets)
    monkeypatch.setenv('GOOGLE_USER_TOKENS_NAME', LEGACY_ARN)
    provider = Mock(side_effect=AssertionError('unexpected provider access'))
    monkeypatch.setattr(gc.urllib.request, 'urlopen', provider)
    config = Mock(side_effect=AssertionError('unexpected app-secret access'))
    monkeypatch.setattr(gc, '_get_google_config', config)
    return row, description, table, secrets, provider, config


def resolve():
    return gc.resolve_google_token_secret_name(ALPHA)


@pytest.mark.parametrize('tenant', [None, '', ' ', '\t', ' x ', 'Aaa', 'aa', 'a-b',
                                         'a/b', 'a#b', 'a\nb', 'x' * 65, 1, False, [], {}])
def test_invalid_tenant_has_no_io(binding, tenant):
    with pytest.raises(gc.ProviderBindingError, match='^INVALID_TENANT_PROVIDER_BINDING$'):
        gc.resolve_google_token_secret_name(tenant)
    binding[2].get_item.assert_not_called()
    binding[3].describe_secret.assert_not_called()


@pytest.mark.parametrize('field,value', [('PK', 'TENANT#other'), ('SK', 'OTHER'),
                                       ('company_id', PRIMARY), ('company_id', None)])
def test_wrong_metadata_denied(binding, field, value):
    binding[0][field] = value
    with pytest.raises(gc.ProviderBindingError, match='INVALID_TENANT_PROVIDER_BINDING'):
        resolve()
    binding[3].describe_secret.assert_not_called()


@pytest.mark.parametrize('response', [{}, {'Item': None}, {'Item': []}, None])
def test_missing_metadata_denied(binding, response):
    binding[2].get_item.return_value = response
    with pytest.raises(gc.ProviderBindingError):
        resolve()


@pytest.mark.parametrize('where', ['tenant', 'secret'])
def test_metadata_inaccessible_is_sanitized(binding, where, capsys):
    operation = binding[2].get_item if where == 'tenant' else binding[3].describe_secret
    operation.side_effect = RuntimeError('sensitive ' + ARN)
    with pytest.raises(gc.ProviderBindingError) as exc:
        resolve()
    assert str(exc.value) == 'PROVIDER_METADATA_INACCESSIBLE'
    assert ARN not in capsys.readouterr().out
    binding[3].get_secret_value.assert_not_called()


@pytest.mark.parametrize('value', [None, '', ' ', False, [], {}, 123, 'bad:name',
                                  'https://secret', 'bad\nname', 'a' * 513])
def test_present_invalid_reference_never_falls_back(binding, value):
    binding[0].update(PK='TENANT#' + PRIMARY, company_id=PRIMARY, calendar_secret_ref=value)
    with pytest.raises(gc.ProviderBindingError):
        gc.resolve_google_token_secret_name(PRIMARY)
    binding[3].describe_secret.assert_not_called()


@pytest.mark.parametrize('tags', [None, [], {}, [{'Key': 'CompanyId', 'Value': ''}],
    [{'Key': 'companyid', 'Value': ALPHA}], [{'Key': 'CompanyId', 'Value': None}],
    [{'Key': 'CompanyId', 'Value': ALPHA}] * 2,
    [{'Key': 'CompanyId', 'Value': ALPHA}, {'Key': 'companyid', 'Value': PRIMARY}],
    [{'Key': 'CompanyId', 'Value': ALPHA}, None]])
def test_malformed_or_conflicting_ownership_denied(binding, tags):
    binding[1]['Tags'] = tags
    with pytest.raises(gc.ProviderBindingError, match='INVALID_TENANT_PROVIDER_BINDING'):
        resolve()


@pytest.mark.parametrize('owner', [PRIMARY, 'future_tenant', ' ', ALPHA.upper()])
def test_cross_tenant_reference_denied(binding, owner):
    binding[1]['Tags'][0]['Value'] = owner
    with pytest.raises(gc.ProviderBindingError, match='^PROVIDER_OWNERSHIP_MISMATCH$'):
        gc._get_stored_tokens(ALPHA)
    binding[3].get_secret_value.assert_not_called()


@pytest.mark.parametrize('tenant', [PRIMARY, ALPHA, 'future_tenant'])
def test_explicit_owned_arbitrary_name(binding, tenant):
    binding[0].update(PK='TENANT#' + tenant, company_id=tenant)
    binding[1]['Tags'][0]['Value'] = tenant
    assert gc.resolve_google_token_secret_name(tenant) == NAME
    binding[2].get_item.assert_called_once_with(
        Key={'PK': 'TENANT#' + tenant, 'SK': 'METADATA'}, ConsistentRead=True,
        ProjectionExpression='PK, SK, company_id, calendar_secret_ref')
    binding[3].get_secret_value.assert_not_called()


@pytest.mark.parametrize('tenant', [ALPHA, 'future_tenant'])
def test_absent_reference_is_unconfigured_even_if_enabled(binding, tenant):
    binding[0].update(PK='TENANT#' + tenant, company_id=tenant,
                      calendar_provider='google', calendar_enabled=True)
    del binding[0]['calendar_secret_ref']
    assert gc.resolve_google_token_secret_name(tenant) is None
    assert gc._get_stored_tokens(tenant) == {}
    assert gc._save_tokens({}, tenant) is False
    binding[3].describe_secret.assert_not_called()
    binding[3].get_secret_value.assert_not_called()
    binding[3].put_secret_value.assert_not_called()


@pytest.mark.parametrize('use_name', [False, True])
def test_primary_absent_reference_compatibility(binding, monkeypatch, use_name):
    binding[0].update(PK='TENANT#' + PRIMARY, company_id=PRIMARY)
    del binding[0]['calendar_secret_ref']
    binding[1].update(ARN=LEGACY_ARN, Name=LEGACY_NAME,
                      Tags=[{'Key': 'CompanyId', 'Value': PRIMARY}])
    locator = LEGACY_NAME if use_name else LEGACY_ARN
    monkeypatch.setenv('GOOGLE_USER_TOKENS_NAME', locator)
    assert gc.resolve_google_token_secret_name(PRIMARY) == locator
    gc._get_stored_tokens(PRIMARY)
    binding[3].get_secret_value.assert_called_once_with(SecretId=LEGACY_ARN)
    binding[1]['Tags'][0]['Value'] = ALPHA
    with pytest.raises(gc.ProviderBindingError, match='PROVIDER_OWNERSHIP_MISMATCH'):
        gc.resolve_google_token_secret_name(PRIMARY)


def test_secret_name_is_not_owner_proof(binding):
    name = 'togs-and-dogs-prod/calendar/' + ALPHA + '/tokens'
    binding[0]['calendar_secret_ref'] = name
    binding[1].update(Name=name, ARN=PREFIX + name + '-Ab1234', Tags=[])
    with pytest.raises(gc.ProviderBindingError):
        resolve()


@pytest.mark.parametrize('mutation', ['account', 'region', 'partition', 'name', 'arn', 'deleted'])
def test_canonical_metadata_boundaries(binding, mutation):
    if mutation == 'account':
        binding[1]['ARN'] = ARN.replace('123456789012', '987654321012')
    elif mutation == 'region':
        binding[1]['ARN'] = ARN.replace('us-east-1', 'us-west-2')
    elif mutation == 'partition':
        binding[1]['ARN'] = ARN.replace('arn:aws:', 'arn:aws-cn:')
    elif mutation == 'name':
        binding[1]['Name'] = 'different'
    elif mutation == 'arn':
        binding[1]['ARN'] = NAME
    else:
        binding[1]['DeletedDate'] = datetime.now(timezone.utc)
    with pytest.raises(gc.ProviderBindingError):
        resolve()


@pytest.mark.parametrize('ref', [ARN.replace('123456789012', '987654321012'),
                               ARN.replace('us-east-1', 'us-west-2'), ARN[:-7]])
def test_bad_arn_rejected_before_describe(binding, ref):
    binding[0]['calendar_secret_ref'] = ref
    with pytest.raises(gc.ProviderBindingError):
        resolve()
    binding[3].describe_secret.assert_not_called()


def test_full_arn_allowed_with_boundary_anchor(binding):
    binding[0]['calendar_secret_ref'] = ARN
    assert resolve() == ARN


def test_arn_without_account_anchor_is_rejected(binding, monkeypatch):
    monkeypatch.setenv('GOOGLE_USER_TOKENS_NAME', LEGACY_NAME)
    binding[0]['calendar_secret_ref'] = ARN
    with pytest.raises(gc.ProviderBindingError):
        resolve()


@pytest.mark.parametrize('operation', ['read', 'save', 'refresh', 'revoke', 'valid', 'sync', 'delete'])
@pytest.mark.parametrize('tenant', [None, ALPHA])
def test_denial_precedes_all_token_and_provider_access(binding, operation, tenant):
    binding[1]['Tags'][0]['Value'] = PRIMARY
    operations = {
        'read': lambda: gc._get_stored_tokens(tenant),
        'save': lambda: gc._save_tokens({'access_token': 'fake'}, tenant),
        'refresh': lambda: gc._refresh_access_token({'refresh_token': 'fake'}, company_id=tenant),
        'revoke': lambda: gc._mark_token_revoked(company_id=tenant),
        'valid': lambda: gc._get_valid_token(company_id=tenant),
        'sync': lambda: gc.sync_calendar_event({'company_id': tenant}),
        'delete': lambda: gc.delete_event_detailed('fake-event', company_id=tenant),
    }
    if operation == 'sync':
        result = operations[operation]()
        assert result['status'] == 'calendar_failed'
        assert ARN not in json.dumps(result) and PRIMARY not in json.dumps(result)
    elif operation == 'delete':
        result = operations[operation]()
        assert result[:2] == (False, False)
        assert ARN not in result[2]
    else:
        with pytest.raises(gc.ProviderBindingError):
            operations[operation]()
    for method in ('get_secret_value', 'put_secret_value'):
        getattr(binding[3], method).assert_not_called()
    binding[4].assert_not_called()
    binding[5].assert_not_called()


def test_read_order_and_save_pin_one_canonical_binding(binding):
    parent = Mock()
    parent.attach_mock(binding[2].get_item, 'tenant')
    parent.attach_mock(binding[3].describe_secret, 'describe')
    parent.attach_mock(binding[3].get_secret_value, 'value')
    parent.attach_mock(binding[3].put_secret_value, 'save')
    binding[3].get_secret_value.return_value = {'SecretString': '{"refresh_token":"fake"}'}
    assert gc._save_tokens({'access_token': 'new'}, ALPHA)
    assert [c[0] for c in parent.mock_calls] == ['tenant', 'describe', 'value', 'save']
    assert binding[3].get_secret_value.call_args.kwargs['SecretId'] == ARN
    assert binding[3].put_secret_value.call_args.kwargs['SecretId'] == ARN
    assert json.loads(binding[3].put_secret_value.call_args.kwargs['SecretString'])['refresh_token'] == 'fake'


def test_cached_token_validated_before_use(binding):
    binding[3].get_secret_value.return_value = {'SecretString': json.dumps({
        'access_token': 'fake', 'updated_at': datetime.now(timezone.utc).isoformat(),
        'expires_in': 3600})}
    assert gc._get_valid_token(company_id=ALPHA) == 'fake'
    binding[3].describe_secret.assert_called_once()
    binding[4].assert_not_called()


@pytest.mark.parametrize('tenant', [PRIMARY, ALPHA, 'future_tenant'])
def test_missing_metadata_never_inherits_legacy(binding, tenant):
    binding[2].get_item.return_value = {}
    with pytest.raises(gc.ProviderBindingError):
        gc.resolve_google_token_secret_name(tenant)
    binding[3].describe_secret.assert_not_called()


def test_default_company_environment_cannot_change_primary_branch(binding, monkeypatch):
    monkeypatch.setenv('DEFAULT_COMPANY_ID', ALPHA)
    del binding[0]['calendar_secret_ref']
    assert resolve() is None
    with pytest.raises(gc.ProviderBindingError):
        gc.resolve_google_token_secret_name()


def test_no_ownership_cache_across_operations(binding):
    assert resolve() == NAME
    binding[1]['Tags'][0]['Value'] = PRIMARY
    with pytest.raises(gc.ProviderBindingError):
        gc._save_tokens({}, ALPHA)
    assert binding[3].describe_secret.call_count == 2
    binding[3].put_secret_value.assert_not_called()


@pytest.mark.parametrize('invalid_grant', [False, True])
def test_refresh_pins_binding_before_exchange_and_save(binding, invalid_grant):
    import urllib.error
    binding[3].get_secret_value.return_value = {'SecretString': '{"refresh_token":"fake"}'}
    binding[5].side_effect = None
    binding[5].return_value = {'client_id': 'fake', 'client_secret': 'fake'}
    response = MagicMock()
    response.__enter__.return_value.read.return_value = b'{"access_token":"new","expires_in":3600}'

    def exchange(*args, **kwargs):
        binding[3].describe_secret.assert_called_once()
        # A concurrent reference edit cannot redirect this operation's write.
        binding[0]['calendar_secret_ref'] = 'other/reference'
        if invalid_grant:
            from io import BytesIO
            raise urllib.error.HTTPError('https://offline.invalid', 400, 'invalid_grant', {},
                                         BytesIO(b'{"error":"invalid_grant"}'))
        return response

    binding[4].side_effect = exchange
    result = gc._get_valid_token(company_id=ALPHA)
    assert result == (None if invalid_grant else 'new')
    binding[2].get_item.assert_called_once()
    binding[3].describe_secret.assert_called_once()
    binding[3].put_secret_value.assert_called_once()
    assert binding[3].put_secret_value.call_args.kwargs['SecretId'] == ARN
    saved = json.loads(binding[3].put_secret_value.call_args.kwargs['SecretString'])
    assert saved['refresh_token'] == 'fake'
    if invalid_grant:
        assert saved['token_status'] == 'revoked'
        assert 'access_token' not in saved


def test_delete_wrapper_does_not_claim_denial_is_success(binding):
    assert gc.delete_event('fake-event') is False
    binding[3].get_secret_value.assert_not_called()
    binding[4].assert_not_called()
