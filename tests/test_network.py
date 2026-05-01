"""Tests for `network`: firewall safe defaults, IAM etag binding, IAP brand."""

import sys
import types
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def fake_network_modules(monkeypatch):
    # Minimal compute_v1 stand-in (firewalls)
    mod = types.ModuleType('google.cloud.compute_v1')

    class _W:
        def __init__(self, **kw):
            for k, v in kw.items():
                setattr(self, k, v)

    for name in ['Firewall', 'Allowed', 'NetworkInterface', 'Network',
                 'NetworkRoutingConfig', 'Subnetwork', 'ForwardingRule',
                 'BackendBucket', 'BackendBucketCdnPolicy']:
        setattr(mod, name, type(name, (_W,), {}))
    for cli in ['NetworksClient', 'SubnetworksClient', 'FirewallsClient',
                'ForwardingRulesClient', 'BackendBucketsClient']:
        setattr(mod, cli, MagicMock(name=cli))
    monkeypatch.setitem(sys.modules, 'google.cloud.compute_v1', mod)
    import gcpeasy.network as gn
    monkeypatch.setattr(gn, 'compute_v1', mod, raising=False)
    return mod


# ---------------------------------------------------------------------------
# Firewall safe defaults (A5)
# ---------------------------------------------------------------------------

def test_firewall_ingress_requires_explicit_source(fake_network_modules, auth):
    from gcpeasy.network import create_firewall_rule
    fake_network_modules.FirewallsClient.return_value.get.side_effect = Exception('nf')
    with pytest.raises(ValueError, match='source_ranges'):
        create_firewall_rule(auth, 'open-22', network='default',
                             protocol='tcp', ports=['22'])


def test_firewall_iap_ssh_uses_iap_range(fake_network_modules, auth):
    from gcpeasy.network import create_firewall_rule, IAP_SSH_RANGE
    client = fake_network_modules.FirewallsClient.return_value
    client.get.side_effect = Exception('nf')
    op = MagicMock(); op.done = MagicMock(return_value=True); op.result = MagicMock()
    client.insert.return_value = op
    create_firewall_rule(auth, 'iap-ssh', network='default', iap_ssh=True)
    rule = client.insert.call_args.kwargs['firewall_resource']
    assert rule.source_ranges == [IAP_SSH_RANGE]
    # Default port 22 auto-filled
    assert rule.allowed[0].ports == ['22']


def test_firewall_allow_public_uses_open_range(fake_network_modules, auth):
    from gcpeasy.network import create_firewall_rule
    client = fake_network_modules.FirewallsClient.return_value
    client.get.side_effect = Exception('nf')
    op = MagicMock(); op.done = MagicMock(return_value=True); op.result = MagicMock()
    client.insert.return_value = op
    create_firewall_rule(auth, 'pub', network='default', ports=['443'],
                         allow_public=True)
    rule = client.insert.call_args.kwargs['firewall_resource']
    assert rule.source_ranges == ['0.0.0.0/0']


# ---------------------------------------------------------------------------
# bind_iam_role: etag-aware (A6)
# ---------------------------------------------------------------------------

def test_bind_iam_role_uses_etag_and_v3(auth):
    from gcpeasy.network import bind_iam_role

    initial = {'bindings': [], 'etag': 'etag-1'}
    state = {'set_calls': [], 'policy': dict(initial)}

    fake_crm = MagicMock()

    def get(resource, body):
        m = MagicMock()
        m.execute = lambda: dict(state['policy'])
        # capture body to verify v3 request
        state['get_body'] = body
        return m

    def set_(resource, body):
        state['set_calls'].append(body)
        state['policy'] = body['policy']
        m = MagicMock()
        m.execute = lambda: state['policy']
        return m

    fake_crm.projects().getIamPolicy.side_effect = get
    fake_crm.projects().setIamPolicy.side_effect = set_

    with patch('gcpeasy.network._crm', return_value=fake_crm):
        bind_iam_role(auth, 'sa@p.iam.gserviceaccount.com', 'roles/viewer')

    assert state['get_body']['options']['requestedPolicyVersion'] == 3
    assert len(state['set_calls']) == 1
    new = state['set_calls'][0]['policy']
    assert new['etag'] == 'etag-1'
    assert new['version'] == 3
    assert any(b['role'] == 'roles/viewer'
               and 'serviceAccount:sa@p.iam.gserviceaccount.com' in b['members']
               for b in new['bindings'])


def test_bind_iam_role_idempotent_when_member_already_present(auth):
    from gcpeasy.network import bind_iam_role
    state = {'set_calls': [], 'policy': {
        'bindings': [{'role': 'roles/viewer',
                      'members': ['serviceAccount:sa@p.iam.gserviceaccount.com']}],
        'etag': 'e', 'version': 3,
    }}
    fake_crm = MagicMock()
    fake_crm.projects().getIamPolicy.return_value.execute = lambda: dict(state['policy'])

    def set_(resource, body):
        state['set_calls'].append(body)
        m = MagicMock()
        m.execute = lambda: state['policy']
        return m
    fake_crm.projects().setIamPolicy.side_effect = set_

    with patch('gcpeasy.network._crm', return_value=fake_crm):
        bind_iam_role(auth, 'sa@p.iam.gserviceaccount.com', 'roles/viewer')

    # No write should happen
    assert state['set_calls'] == []


# ---------------------------------------------------------------------------
# OAuth brand (A9)
# ---------------------------------------------------------------------------

def test_get_or_create_oauth_brand_returns_existing(auth):
    from gcpeasy.network import get_or_create_oauth_brand
    fake_iap = MagicMock()
    fake_iap.projects().brands().list().execute.return_value = {
        'brands': [{'name': 'projects/123/brands/abc',
                    'supportEmail': 'admin@x.com'}]
    }
    with patch('googleapiclient.discovery.build', return_value=fake_iap):
        out = get_or_create_oauth_brand(auth, support_email='admin@x.com')
    assert out['status'] == 'exists'
    assert out['name'] == 'projects/123/brands/abc'


def test_get_or_create_oauth_brand_creates_when_absent(auth):
    from gcpeasy.network import get_or_create_oauth_brand
    fake_iap = MagicMock()
    fake_iap.projects().brands().list().execute.return_value = {'brands': []}
    fake_iap.projects().brands().create().execute.return_value = {
        'name': 'projects/123/brands/new', 'supportEmail': 'admin@x.com',
    }
    with patch('googleapiclient.discovery.build', return_value=fake_iap):
        out = get_or_create_oauth_brand(auth, support_email='admin@x.com')
    assert out['status'] == 'created'
