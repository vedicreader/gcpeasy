"""Tests for `core` (compliance, audit defaults, list_labeled_resources, GenAIStack)."""

from unittest.mock import MagicMock, patch

from gcpeasy import core
from gcpeasy.core import (
    HIPAA, ISO27001, SOC2,
    REQUIRED_APIS, GENAI_APIS,
    enable_data_access_audit,
    DEFAULT_AUDIT_SERVICES,
)


def test_compliance_profiles_have_required_keys():
    for p in (HIPAA, ISO27001, SOC2):
        assert p['encryption'] is True
        assert 'labels' in p
    assert HIPAA['audit_all_services'] is True
    assert ISO27001.get('audit_all_services') is None  # not set: services list only


def test_required_apis_subset_of_genai():
    assert set(REQUIRED_APIS).issubset(set(GENAI_APIS))


def test_audit_default_services_avoid_all_services(auth):
    """Default behavior should target a curated list, NOT 'allServices'."""
    captured = {}

    def fake_update(crm, resource, mutate):
        policy = {'bindings': [], 'etag': 'e', 'auditConfigs': []}
        mutate(policy)
        captured['policy'] = policy
        return policy

    fake_crm = MagicMock()
    with patch('gcpeasy.core.update_iam_policy', side_effect=fake_update), \
         patch('googleapiclient.discovery.build', return_value=fake_crm):
        result = enable_data_access_audit(auth)

    services = {c['service'] for c in captured['policy']['auditConfigs']}
    assert 'allServices' not in services
    assert services == set(DEFAULT_AUDIT_SERVICES)
    # All three log types are present
    for cfg in captured['policy']['auditConfigs']:
        types = {t['logType'] for t in cfg['auditLogConfigs']}
        assert types == {'ADMIN_READ', 'DATA_READ', 'DATA_WRITE'}
    assert all(s in result['services'] for s in DEFAULT_AUDIT_SERVICES)


def test_audit_all_services_explicit(auth):
    captured = {}

    def fake_update(crm, resource, mutate):
        policy = {'bindings': [], 'etag': 'e', 'auditConfigs': []}
        mutate(policy)
        captured['policy'] = policy
        return policy

    fake_crm = MagicMock()
    with patch('gcpeasy.core.update_iam_policy', side_effect=fake_update), \
         patch('googleapiclient.discovery.build', return_value=fake_crm):
        enable_data_access_audit(auth, all_services=True)

    services = {c['service'] for c in captured['policy']['auditConfigs']}
    assert services == {'allServices'}


def test_audit_idempotent_when_already_configured(auth):
    """If all 3 log types are already present, no write should happen."""
    starting = {'bindings': [], 'etag': 'e', 'auditConfigs': [
        {'service': s, 'auditLogConfigs': [
            {'logType': 'ADMIN_READ'},
            {'logType': 'DATA_READ'},
            {'logType': 'DATA_WRITE'},
        ]}
        for s in DEFAULT_AUDIT_SERVICES
    ]}
    state = {'wrote': False}

    def fake_update(crm, resource, mutate):
        policy = dict(starting)
        policy['auditConfigs'] = list(starting['auditConfigs'])
        if mutate(policy):
            state['wrote'] = True
        return policy

    fake_crm = MagicMock()
    with patch('gcpeasy.core.update_iam_policy', side_effect=fake_update), \
         patch('googleapiclient.discovery.build', return_value=fake_crm):
        result = enable_data_access_audit(auth)
    assert state['wrote'] is False
    for s in DEFAULT_AUDIT_SERVICES:
        assert result['services'][s] == 'already_configured'


def test_list_labeled_resources_omits_empty_query(auth):
    """Regression: previously sent query='' which the API rejects."""
    fake_client = MagicMock()
    fake_client.search_all_resources.return_value = []
    captured = {}

    class FakeRequest:
        def __init__(self, **kw):
            captured.update(kw)

    fake_module = MagicMock()
    fake_module.AssetServiceClient = MagicMock(return_value=fake_client)
    fake_module.SearchAllResourcesRequest = FakeRequest

    with patch.dict('sys.modules', {'google.cloud.asset_v1': fake_module}), \
         patch('google.cloud.asset_v1', fake_module, create=True):
        from gcpeasy.core import list_labeled_resources
        list_labeled_resources(auth)

    assert 'query' not in captured
    assert captured.get('scope') == f'projects/{auth.project}'
