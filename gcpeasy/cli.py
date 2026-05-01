"""Minimal command-line interface for gcpeasy.

Designed to be the surface that ``vr-deploy gcp-vm`` / ``vr-deploy gcp-cloudrun``
can shell out to.  Each subcommand is a thin wrapper over the library.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any


def _auth(args):
    from .core import GCPAuth
    return GCPAuth(
        project=getattr(args, 'project', None) or os.environ.get('GOOGLE_CLOUD_PROJECT'),
        region=getattr(args, 'region', None) or os.environ.get('GOOGLE_CLOUD_REGION'),
    )


def _print(obj: Any) -> None:
    if isinstance(obj, (dict, list)):
        print(json.dumps(obj, indent=2, default=str))
    else:
        print(obj)


# ---------------------------------------------------------------------------
# Subcommand implementations
# ---------------------------------------------------------------------------

def cmd_preflight(args) -> int:
    from .core import preflight, GENAI_APIS, REQUIRED_APIS
    auth = _auth(args)
    apis = GENAI_APIS if args.full else REQUIRED_APIS
    try:
        result = preflight(auth, apis=apis,
                           require_billing=not args.skip_billing)
    except Exception as e:  # noqa: BLE001
        print(f'preflight failed: {e}', file=sys.stderr)
        return 1
    _print(result)
    return 0


def cmd_enable_apis(args) -> int:
    from .core import enable_apis, GENAI_APIS, REQUIRED_APIS
    auth = _auth(args)
    apis = list(args.apis) if args.apis else (GENAI_APIS if args.full else REQUIRED_APIS)
    _print(enable_apis(auth, apis))
    return 0


def cmd_vm_create(args) -> int:
    from .compute import create_instance, vm_install_docker
    auth = _auth(args)
    ssh_keys = {}
    if args.ssh_key:
        for spec in args.ssh_key:
            user, _, key = spec.partition(':')
            if not key:
                # treat as path to public key file with current user
                with open(spec, 'r', encoding='utf-8') as f:
                    key = f.read().strip()
                user = os.environ.get('USER', 'gcpeasy')
            ssh_keys[user] = key
    startup = None
    if args.startup:
        with open(args.startup, 'r', encoding='utf-8') as f:
            startup = f.read()
    elif args.install_docker:
        startup = vm_install_docker(auth)
    result = create_instance(
        auth, args.name,
        machine_type=args.machine_type,
        zone=args.zone,
        ssh_keys=ssh_keys or None,
        startup_script=startup,
        service_account=args.service_account,
        tags=args.tag,
        external_ip=not args.no_external_ip,
        enable_os_login=not bool(ssh_keys),  # OS Login is incompatible with metadata SSH keys
        block_project_ssh_keys=not bool(ssh_keys),
    )
    _print(result)
    return 0


def cmd_vm_deploy(args) -> int:
    from .compute import (
        wait_for_ssh, vm_run_compose, instance_ip, create_instance,
    )
    auth = _auth(args)
    with open(args.compose, 'r', encoding='utf-8') as f:
        compose_yaml = f.read()
    env = {}
    if args.env:
        with open(args.env, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                k, _, v = line.partition('=')
                env[k.strip()] = v.strip().strip('"').strip("'")
    bundle = vm_run_compose(auth, args.name, compose_yaml, env=env)
    if args.create:
        create_instance(auth, args.name,
                        machine_type=args.machine_type,
                        startup_script=bundle['startup_script'],
                        external_ip=True)
    else:
        # Apply via SSH: print the script so vr-deploy / a wrapper can ship it.
        # We deliberately avoid embedding an SSH client here.
        sys.stderr.write(
            '[gcpeasy] Run the printed startup script on the VM (e.g. via '
            '`gcloud compute ssh ' + args.name + ' --command="bash -s" < startup.sh`)\n'
        )
        sys.stdout.write(bundle['startup_script'])
        return 0
    wait_for_ssh(auth, args.name, timeout=args.ssh_timeout)
    _print({'name': args.name, 'ip': instance_ip(auth, args.name),
            'workdir': bundle['workdir']})
    return 0


def cmd_run_deploy(args) -> int:
    from .compute import deploy_cloudrun, build_image_cloudbuild
    auth = _auth(args)
    image = args.image
    if args.source:
        if not image:
            print('--image is required when using --source', file=sys.stderr)
            return 2
        build = build_image_cloudbuild(auth, args.source, image,
                                       dockerfile=args.dockerfile)
        image = build['image_digest'] or image
        sys.stderr.write(f'[gcpeasy] built {image}\n')
    if not image:
        print('one of --image or --source is required', file=sys.stderr)
        return 2
    secrets = {}
    for spec in args.secret or []:
        if '=' not in spec:
            print('invalid --secret value: expected KEY=secret-ref', file=sys.stderr)
            return 2
        k, v = spec.split('=', 1)
        secrets[k] = v
    env_vars = {}
    for spec in args.env or []:
        if '=' in spec:
            k, v = spec.split('=', 1)
            env_vars[k] = v
    result = deploy_cloudrun(
        auth, args.name, image=image,
        service_account=args.service_account,
        env_vars=env_vars or None,
        secrets=secrets or None,
        allow_unauthenticated=args.allow_unauthenticated,
        cpu=args.cpu, memory=args.memory, port=args.port,
        min_instances=args.min_instances, max_instances=args.max_instances,
    )
    _print(result)
    return 0


def cmd_stack_provision(args) -> int:
    from .core import GCPAuth, GenAIStack, HIPAA, ISO27001, SOC2
    auth = _auth(args)
    profile = {'hipaa': HIPAA, 'iso27001': ISO27001, 'soc2': SOC2}.get(
        (args.profile or '').lower())
    stack = GenAIStack(auth, args.name, compliance=profile)
    res = stack.provision(
        gke=args.gke, cloud_sql=args.cloud_sql,
        vector_search=args.vector_search,
    )
    _print(res)
    return 0


def cmd_stack_destroy(args) -> int:
    from .core import GenAIStack
    auth = _auth(args)
    # Reconstruct enough state to call destroy().  The user must supply
    # resource identifiers in the same shape provision() returned, via JSON.
    stack = GenAIStack(auth, args.name)
    if args.resources:
        with open(args.resources, 'r', encoding='utf-8') as f:
            stack._resources = json.load(f)
    _print(stack.destroy())
    return 0


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog='gcpeasy', description='gcpeasy CLI')
    p.add_argument('--project', help='GCP project ID (defaults to GOOGLE_CLOUD_PROJECT)')
    p.add_argument('--region', help='GCP region (defaults to GOOGLE_CLOUD_REGION)')
    sub = p.add_subparsers(dest='cmd', required=True)

    # preflight
    pf = sub.add_parser('preflight', help='check ADC, billing, and required APIs')
    pf.add_argument('--full', action='store_true', help='check the full GenAI API set')
    pf.add_argument('--skip-billing', action='store_true')
    pf.set_defaults(func=cmd_preflight)

    # enable-apis
    ea = sub.add_parser('enable-apis', help='enable required GCP APIs on the project')
    ea.add_argument('--full', action='store_true')
    ea.add_argument('apis', nargs='*')
    ea.set_defaults(func=cmd_enable_apis)

    # vm
    vm = sub.add_parser('vm', help='Compute Engine VM operations')
    vm_sub = vm.add_subparsers(dest='vm_cmd', required=True)

    vmc = vm_sub.add_parser('create', help='create a VM')
    vmc.add_argument('name')
    vmc.add_argument('--machine-type', default='e2-medium')
    vmc.add_argument('--zone')
    vmc.add_argument('--ssh-key', action='append',
                     help='user:public-key OR a path to a public key file. May repeat.')
    vmc.add_argument('--startup', help='path to a startup script')
    vmc.add_argument('--install-docker', action='store_true',
                     help='install Docker + Compose plugin via startup script')
    vmc.add_argument('--service-account', help='service account email')
    vmc.add_argument('--tag', action='append', help='network tag (repeatable)')
    vmc.add_argument('--no-external-ip', action='store_true')
    vmc.set_defaults(func=cmd_vm_create)

    vmd = vm_sub.add_parser('deploy', help='deploy a docker-compose app to a VM')
    vmd.add_argument('name')
    vmd.add_argument('--compose', required=True)
    vmd.add_argument('--env', help='path to .env file')
    vmd.add_argument('--create', action='store_true',
                     help='also create the VM with a startup script (one-shot deploy)')
    vmd.add_argument('--machine-type', default='e2-medium')
    vmd.add_argument('--ssh-timeout', type=int, default=300)
    vmd.set_defaults(func=cmd_vm_deploy)

    # run
    run = sub.add_parser('run', help='Cloud Run operations')
    run_sub = run.add_subparsers(dest='run_cmd', required=True)
    rd = run_sub.add_parser('deploy', help='deploy a Cloud Run service')
    rd.add_argument('name')
    rd.add_argument('--image')
    rd.add_argument('--source', help='path to source dir to build via Cloud Build')
    rd.add_argument('--dockerfile', default='Dockerfile')
    rd.add_argument('--service-account')
    rd.add_argument('--env', action='append',
                    help='KEY=VALUE env var (repeatable)')
    rd.add_argument('--secret', action='append',
                    help='KEY=secret-ref env-from-secret (repeatable)')
    rd.add_argument('--cpu', default='1')
    rd.add_argument('--memory', default='512Mi')
    rd.add_argument('--port', type=int, default=8080)
    rd.add_argument('--min-instances', type=int, default=0)
    rd.add_argument('--max-instances', type=int, default=10)
    rd.add_argument('--allow-unauthenticated', action='store_true')
    rd.set_defaults(func=cmd_run_deploy)

    # stack
    st = sub.add_parser('stack', help='GenAIStack operations')
    st_sub = st.add_subparsers(dest='stack_cmd', required=True)
    sp = st_sub.add_parser('provision')
    sp.add_argument('name')
    sp.add_argument('--profile', choices=['hipaa', 'iso27001', 'soc2'])
    sp.add_argument('--gke', action='store_true')
    sp.add_argument('--cloud-sql', action='store_true')
    sp.add_argument('--vector-search', action='store_true')
    sp.set_defaults(func=cmd_stack_provision)

    sd = st_sub.add_parser('destroy')
    sd.add_argument('name')
    sd.add_argument('--resources', help='path to JSON file from `provision`')
    sd.set_defaults(func=cmd_stack_destroy)

    return p


def main(argv: list = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == '__main__':  # pragma: no cover
    sys.exit(main())
