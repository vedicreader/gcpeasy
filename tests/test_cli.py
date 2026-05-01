"""Tests for the gcpeasy CLI parser + smoke tests of subcommands."""

import json
import sys
from unittest.mock import patch

import pytest


def test_parser_help_does_not_crash():
    from gcpeasy.cli import build_parser
    p = build_parser()
    assert p.prog == 'gcpeasy'


def test_preflight_subcommand_invokes_core(patched_env, capsys):
    from gcpeasy import cli
    with patch('gcpeasy.core.preflight', return_value={'ok': True}) as mock_pf, \
         patch('gcpeasy.core.GCPAuth') as mock_auth:
        mock_auth.return_value.project = 'p'
        rc = cli.main(['preflight'])
    assert rc == 0
    mock_pf.assert_called_once()
    out = capsys.readouterr().out
    assert json.loads(out) == {'ok': True}


def test_enable_apis_subcommand(patched_env, capsys):
    from gcpeasy import cli
    with patch('gcpeasy.core.enable_apis',
               return_value={'compute.googleapis.com': 'enabled'}), \
         patch('gcpeasy.core.GCPAuth'):
        rc = cli.main(['enable-apis'])
    assert rc == 0


def test_run_deploy_requires_image_or_source(patched_env, capsys):
    from gcpeasy import cli
    with patch('gcpeasy.core.GCPAuth'):
        rc = cli.main(['run', 'deploy', 'svc'])
    assert rc == 2


def test_run_deploy_parses_secrets_and_env(patched_env, capsys):
    from gcpeasy import cli
    with patch('gcpeasy.compute.deploy_cloudrun', return_value={'name': 'x', 'uri': 'u'}) as dc, \
         patch('gcpeasy.core.GCPAuth'):
        rc = cli.main([
            'run', 'deploy', 'svc',
            '--image', 'us-docker.pkg.dev/p/r/i:latest',
            '--secret', 'DB_PASS=projects/p/secrets/s/versions/1',
            '--env', 'FOO=bar',
            '--cpu', '2', '--memory', '1Gi', '--port', '9000',
        ])
    assert rc == 0
    kwargs = dc.call_args.kwargs
    assert kwargs['secrets'] == {'DB_PASS': 'projects/p/secrets/s/versions/1'}
    assert kwargs['env_vars'] == {'FOO': 'bar'}
    assert kwargs['cpu'] == '2'
    assert kwargs['memory'] == '1Gi'
    assert kwargs['port'] == 9000


def test_vm_deploy_without_create_prints_script(patched_env, tmp_path, capsys):
    from gcpeasy import cli
    compose = tmp_path / 'docker-compose.yml'
    compose.write_text('services:\n  web:\n    image: nginx\n')
    with patch('gcpeasy.core.GCPAuth'):
        rc = cli.main(['vm', 'deploy', 'vm1', '--compose', str(compose)])
    assert rc == 0
    out = capsys.readouterr().out
    assert '#!/usr/bin/env bash' in out
    assert 'docker compose up -d' in out
