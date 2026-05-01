"""Tests for `compute.deploy_cloudrun` IAM merge + ingress defaults."""

import sys
import types
from unittest.mock import MagicMock, patch

import pytest


def test_grant_invoker_public_is_additive():
    """Regression: setting allow_unauthenticated must NOT clobber existing bindings."""
    from gcpeasy.compute import _grant_cloudrun_invoker_public

    # Build a minimal fake policy/protobuf type system
    class _Binding:
        def __init__(self, role, members):
            self.role = role
            self.members = list(members)

    class _Policy:
        def __init__(self, bindings=None, etag=b''):
            self.bindings = list(bindings or [])
            self.etag = etag

    fake_iam_policy_pb2 = types.SimpleNamespace(
        GetIamPolicyRequest=lambda **kw: types.SimpleNamespace(**kw),
        SetIamPolicyRequest=lambda **kw: types.SimpleNamespace(**kw),
    )
    fake_policy_pb2 = types.SimpleNamespace(
        Binding=_Binding, Policy=_Policy,
    )

    existing_binding = _Binding('roles/run.invoker',
                                ['serviceAccount:other@p.iam.gserviceaccount.com'])
    other_binding = _Binding('roles/viewer', ['user:auditor@x.com'])
    starting_policy = _Policy(bindings=[existing_binding, other_binding], etag=b'e')

    captured = {}

    fake_client = MagicMock()
    fake_client.get_iam_policy.return_value = starting_policy

    def set_iam_policy(request):
        captured['policy'] = request.policy
        return request.policy
    fake_client.set_iam_policy.side_effect = set_iam_policy

    with patch.dict(sys.modules, {
        'google.iam.v1': types.ModuleType('google.iam.v1'),
        'google.iam.v1.iam_policy_pb2': fake_iam_policy_pb2,
        'google.iam.v1.policy_pb2': fake_policy_pb2,
    }):
        # The function does its own imports of google.iam.v1.iam_policy_pb2
        sys.modules['google.iam.v1.iam_policy_pb2'] = fake_iam_policy_pb2
        sys.modules['google.iam.v1.policy_pb2'] = fake_policy_pb2
        _grant_cloudrun_invoker_public(fake_client, 'projects/p/locations/r/services/s')

    new_policy = captured['policy']
    # Original viewer binding preserved.
    roles = {b.role for b in new_policy.bindings}
    assert 'roles/viewer' in roles
    assert 'roles/run.invoker' in roles
    # allUsers added without clobbering the previous run.invoker member
    invoker = next(b for b in new_policy.bindings if b.role == 'roles/run.invoker')
    assert 'allUsers' in invoker.members
    assert 'serviceAccount:other@p.iam.gserviceaccount.com' in invoker.members
    # Etag round-tripped
    assert new_policy.etag == b'e'
