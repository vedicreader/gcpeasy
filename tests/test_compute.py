"""Tests for `compute.create_instance` IP wiring + helper scripts."""

import sys
import types
from unittest.mock import MagicMock, patch

import pytest


# Build a fake compute_v1 module with the classes we need so we can run
# without the google-cloud-compute SDK installed.
class _Wrap:
    """Construct a generic stand-in class that records kwargs."""
    @classmethod
    def make(cls, name):
        return type(name, (cls,), {'__init__': cls._init, '__repr__': cls._repr})

    def _init(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)

    def _repr(self):  # pragma: no cover
        return f'<{type(self).__name__} {self.__dict__}>'


def _install_fake_compute_v1():
    mod = types.ModuleType('google.cloud.compute_v1')
    for name in [
        'AccessConfig', 'AttachedDisk', 'AttachedDiskInitializeParams',
        'Allowed', 'Firewall', 'ForwardingRule',
        'Instance', 'NetworkInterface', 'Network', 'NetworkRoutingConfig',
        'Subnetwork', 'Items', 'Metadata', 'Tags', 'ServiceAccount',
        'ShieldedInstanceConfig',
        'BackendBucket', 'BackendBucketCdnPolicy',
    ]:
        setattr(mod, name, _Wrap.make(name))

    # Clients are MagicMocks
    for name in [
        'NetworksClient', 'SubnetworksClient', 'FirewallsClient',
        'InstancesClient', 'ImagesClient', 'ForwardingRulesClient',
        'BackendBucketsClient',
    ]:
        setattr(mod, name, MagicMock(name=name))
    return mod


@pytest.fixture
def fake_compute(monkeypatch):
    mod = _install_fake_compute_v1()
    monkeypatch.setitem(sys.modules, 'google.cloud.compute_v1', mod)
    # Re-import compute to bind to the fake module
    import importlib
    import gcpeasy.compute as gc
    monkeypatch.setattr(gc, 'compute_v1', mod, raising=False)
    return mod


def test_create_instance_assigns_external_ip_by_default(fake_compute, auth):
    import gcpeasy.compute as gc

    # Simulate "instance does not exist" then "exists after insert"
    instances = MagicMock()
    fake_compute.InstancesClient.return_value = instances
    instances.get.side_effect = [
        Exception('not found'),  # first call: precheck
        MagicMock(  # post-insert: instance details
            status='RUNNING',
            network_interfaces=[MagicMock(
                network_i_p='10.0.0.5',
                access_configs=[MagicMock(nat_i_p='34.1.2.3')],
            )],
        ),
    ]
    op = MagicMock()
    op.result = MagicMock()
    op.done = MagicMock(return_value=True)
    instances.insert.return_value = op

    with patch('gcpeasy.compute._latest_debian_image', return_value='img'):
        out = gc.create_instance(auth, 'vm1')

    # Verify the NetworkInterface used for insert had access_configs (NAT).
    insert_kwargs = instances.insert.call_args.kwargs
    instance_resource = insert_kwargs['instance_resource']
    nic = instance_resource.network_interfaces[0]
    assert hasattr(nic, 'access_configs')
    assert len(nic.access_configs) == 1
    ac = nic.access_configs[0]
    assert ac.type_ == 'ONE_TO_ONE_NAT'

    # And the returned dict carries both internal and external IPs.
    assert out['internal_ip'] == '10.0.0.5'
    assert out['external_ip'] == '34.1.2.3'


def test_create_instance_no_external_ip_when_disabled(fake_compute, auth):
    import gcpeasy.compute as gc

    instances = MagicMock()
    fake_compute.InstancesClient.return_value = instances
    instances.get.side_effect = [
        Exception('not found'),
        MagicMock(
            status='RUNNING',
            network_interfaces=[MagicMock(
                network_i_p='10.0.0.7',
                access_configs=[],
            )],
        ),
    ]
    op = MagicMock(); op.result = MagicMock(); op.done = MagicMock(return_value=True)
    instances.insert.return_value = op

    with patch('gcpeasy.compute._latest_debian_image', return_value='img'):
        out = gc.create_instance(auth, 'vm2', external_ip=False)

    insert_kwargs = instances.insert.call_args.kwargs
    nic = insert_kwargs['instance_resource'].network_interfaces[0]
    # access_configs should NOT be present when external_ip=False
    assert not hasattr(nic, 'access_configs') or not nic.access_configs
    assert 'external_ip' not in out
    assert out['internal_ip'] == '10.0.0.7'


def test_create_instance_wires_startup_and_oslogin(fake_compute, auth):
    import gcpeasy.compute as gc

    instances = MagicMock()
    fake_compute.InstancesClient.return_value = instances
    instances.get.side_effect = [
        Exception('not found'),
        MagicMock(status='RUNNING', network_interfaces=[MagicMock(
            network_i_p='10', access_configs=[MagicMock(nat_i_p='1')]
        )]),
    ]
    op = MagicMock(); op.result = MagicMock(); op.done = MagicMock(return_value=True)
    instances.insert.return_value = op

    with patch('gcpeasy.compute._latest_debian_image', return_value='img'):
        gc.create_instance(auth, 'vm3', startup_script='echo hi',
                           service_account='sa@p.iam.gserviceaccount.com')

    res = instances.insert.call_args.kwargs['instance_resource']
    md_keys = {it.key: it.value for it in res.metadata.items}
    assert md_keys['startup-script'] == 'echo hi'
    assert md_keys['enable-oslogin'] == 'TRUE'
    assert md_keys['block-project-ssh-keys'] == 'TRUE'
    assert res.service_accounts[0].email == 'sa@p.iam.gserviceaccount.com'


def test_instance_ip_falls_back_to_internal(fake_compute, auth):
    import gcpeasy.compute as gc
    instances = MagicMock()
    fake_compute.InstancesClient.return_value = instances
    instances.get.return_value = MagicMock(network_interfaces=[
        MagicMock(network_i_p='10.0.0.9', access_configs=[]),
    ])
    assert gc.instance_ip(auth, 'x') == '10.0.0.9'


def test_vm_install_docker_returns_install_script(auth):
    from gcpeasy.compute import vm_install_docker
    s = vm_install_docker(auth)
    assert 'apt-get install' in s
    assert 'docker-ce' in s
    assert 'docker-compose-plugin' in s


def test_vm_run_compose_emits_runnable_script(auth):
    from gcpeasy.compute import vm_run_compose
    bundle = vm_run_compose(auth, 'vm', 'services:\n  web:\n    image: nginx\n',
                            env={'API_KEY': 'abc'}, workdir='/srv/app')
    s = bundle['startup_script']
    assert s.startswith('#!/usr/bin/env bash')
    assert 'set -euo pipefail' in s
    assert '/srv/app/docker-compose.yml' in s
    assert '/srv/app/.env' in s
    assert 'docker compose up -d' in s
    assert bundle['workdir'] == '/srv/app'
