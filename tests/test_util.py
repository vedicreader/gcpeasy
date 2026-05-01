"""Tests for `_util` helpers (translate_error, update_iam_policy, labels_merge)."""

from unittest.mock import MagicMock

from gcpeasy._util import (
    labels_merge,
    translate_error,
    update_iam_policy,
    GcpEasyError,
)


def test_translate_error_recognises_service_disabled():
    err = Exception("403 SERVICE_DISABLED: API not enabled")
    out = translate_error(err, "preflight")
    assert isinstance(out, GcpEasyError)
    assert "enable-apis" in str(out)


def test_translate_error_recognises_permission_denied():
    err = Exception("PERMISSION_DENIED: missing role")
    out = translate_error(err)
    assert isinstance(out, GcpEasyError)


def test_translate_error_passthrough_for_unknown():
    err = ValueError("nothing to see")
    out = translate_error(err)
    assert out is err


def test_labels_merge_drops_empty_and_stringifies():
    out = labels_merge({'a': 1}, {'a': '2', 'b': None, 'c': ''}, {'d': 'ok'})
    assert out == {'a': '2', 'd': 'ok'}


def test_labels_merge_handles_none_inputs():
    assert labels_merge(None, {'x': 'y'}, None) == {'x': 'y'}


def _fake_crm(initial_policy):
    """Build a fake cloudresourcemanager client whose getIamPolicy returns
    ``initial_policy`` and whose setIamPolicy records the body."""
    crm = MagicMock()
    state = {'policy': dict(initial_policy)}
    set_calls = []

    def _get_exec(*a, **kw):
        # Return a deep-ish copy so the caller's mutations don't bleed back.
        import copy
        return copy.deepcopy(state['policy'])

    def _set_exec(*a, **kw):
        return state['policy']

    def get_iam_policy(resource, body):
        m = MagicMock()
        m.execute = _get_exec
        return m

    def set_iam_policy(resource, body):
        set_calls.append({'resource': resource, 'body': body})
        state['policy'] = body['policy']
        m = MagicMock()
        m.execute = _set_exec
        return m

    crm.projects().getIamPolicy.side_effect = get_iam_policy
    crm.projects().setIamPolicy.side_effect = set_iam_policy
    return crm, state, set_calls


def test_update_iam_policy_no_op_skips_set():
    crm, state, calls = _fake_crm({'bindings': [], 'etag': 'e1'})

    def mutate(p):
        return False  # nothing to do

    update_iam_policy(crm, 'proj', mutate)
    assert calls == []


def test_update_iam_policy_writes_with_v3_and_etag():
    crm, state, calls = _fake_crm({'bindings': [], 'etag': 'e1'})

    def mutate(p):
        p.setdefault('bindings', []).append(
            {'role': 'roles/viewer', 'members': ['user:a@x']}
        )
        return True

    update_iam_policy(crm, 'proj', mutate)
    assert len(calls) == 1
    pol = calls[0]['body']['policy']
    assert pol['version'] == 3
    assert pol['etag'] == 'e1'  # preserved from getIamPolicy
    assert any(b['role'] == 'roles/viewer' for b in pol['bindings'])


def test_update_iam_policy_get_uses_request_v3():
    crm, _, _ = _fake_crm({'bindings': [], 'etag': 'e1'})

    def mutate(p):
        return False

    update_iam_policy(crm, 'proj', mutate)
    # Inspect the actual call made to getIamPolicy
    call = crm.projects().getIamPolicy.call_args
    body = call.kwargs.get('body') or call.args[1]
    assert body['options']['requestedPolicyVersion'] == 3
