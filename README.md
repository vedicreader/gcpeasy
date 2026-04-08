# gcpeasy

> GCP cloud provisioning for GenAI workloads — made easy.

## Installation

```sh
pip install gcpeasy
```

## Overview

`gcpeasy` is the GCP member of the `vedicreader` cloud tool ecosystem:

| Tool | Purpose |
|---|---|
| dockeasy | Docker / Compose config generation |
| cfeasy | Cloudflare DNS + Zero Trust tunnels |
| vpseasy | Hetzner VPS provisioning + deployment |
| gheasy | GitHub automation |
| azeasy | Azure cloud provisioning for GenAI workloads |
| awseasy | AWS cloud provisioning for GenAI workloads |
| **gcpeasy** | **GCP cloud provisioning for GenAI workloads** |

**Design pattern** across all tools: thin, Pythonic wrappers over provider SDKs, built with
nbdev + fastcore, functional where stateless, small and succinct.

## Authentication

`gcpeasy` uses [Application Default Credentials (ADC)](https://cloud.google.com/docs/authentication/application-default-credentials) via `google.auth.default()`.

Supported credential sources (in order):
1. `GOOGLE_APPLICATION_CREDENTIALS` env var → service account key file
2. `gcloud auth application-default login` user credentials
3. Attached service account (Compute Engine, GKE, Cloud Run, App Engine)
4. Workload Identity Federation (GKE Workload Identity)

No hardcoded credentials anywhere. Use `service_account_file=` for key-based auth or
`impersonate_sa=` for cross-project service account impersonation.

```python
from gcpeasy.core import GCPAuth

# Uses ADC — reads GOOGLE_CLOUD_PROJECT and GOOGLE_CLOUD_REGION from env
auth = GCPAuth()

# Or explicitly:
auth = GCPAuth(project='my-project-id', region='us-central1')

# Service account key file:
auth = GCPAuth(project='my-project-id',
               service_account_file='/path/to/key.json')

# Cross-project impersonation:
auth = GCPAuth(project='my-project-id',
               impersonate_sa='deploy@other-project.iam.gserviceaccount.com')

print(auth)  # GCPAuth(project='my-project-id', region='us-central1')
```

## Compliance Profiles

Compliance requirements are plain dicts, composable as `**kwargs`:

```python
from gcpeasy.core import HIPAA, ISO27001, SOC2
```

| Profile | Key controls |
|---|---|
| `HIPAA` | encryption, TLS 1.2, audit, multi-region, 35-day backup, deletion protection |
| `ISO27001` | encryption, audit, managed SA, least privilege, TLS 1.2 |
| `SOC2` | encryption, audit, MFA required, 7-day backup |

Every `create_*` function accepts `**compliance_opts`, so requirements compose naturally:

```python
from gcpeasy.core import HIPAA
from gcpeasy.data import create_bucket, create_redis
from gcpeasy.network import create_secret

create_bucket(auth, 'phi-data', **HIPAA)
create_redis(auth, 'cache', **HIPAA)
create_secret(auth, 'phi/db-password', 'supersecret', **HIPAA)
```

## One-call GenAI Stack

`GenAIStack` provisions a complete enterprise GenAI infrastructure in a single call:
Service Account → GCS bucket → Firestore → Memorystore Redis → Secret Manager
(plus optional Vector Search and GKE).

```python
from gcpeasy.core import GCPAuth, GenAIStack, HIPAA

auth = GCPAuth(project='my-project-id')
stack = GenAIStack(auth, 'myapp', compliance=HIPAA)
resources = stack.provision()
print(stack.summary())
# {
#   'service_account': 'myapp-sa@my-project-id.iam.gserviceaccount.com',
#   'gcs_bucket': 'myapp-data',
#   'firestore_collection': 'myapp',
#   'memorystore': 'projects/.../instances/myapp-cache',
#   'secret': 'projects/.../secrets/myapp-api-key',
# }
```

## Module Reference

| Module | Key functions |
|---|---|
| `gcpeasy.core` | `GCPAuth`, `HIPAA/ISO27001/SOC2`, `find_resources`, `GenAIStack` |
| `gcpeasy.ai` | `generate_content`, `list_models`, `create_vector_search_index`, `create_search_app`, `search_query` |
| `gcpeasy.data` | `create_bucket`, `signed_url`, `create_postgres`, `create_redis`, `create_topic`, `create_subscription` |
| `gcpeasy.compute` | `create_instance`, `create_gke_cluster`, `create_artifact_registry`, `deploy_cloudrun`, `create_binary_auth_policy` |
| `gcpeasy.network` | `create_vpc`, `add_subnet`, `create_firewall_rule`, `create_secret`, `create_service_account`, `bind_iam_role`, `list_sa_keys`, `rotate_sa_key`, `create_kms_key`, `enable_audit_logs`, `create_armor_policy`, `create_managed_cert`, `create_https_lb` |


## Vertex AI — Generative Models

```python
from gcpeasy.ai import generate_content, list_models

# List available model IDs
print(list_models(auth))

# Generate text with Gemini 1.5 Pro (default)
response = generate_content(auth, 'Explain vector databases in one paragraph.')
print(response)

# Use a different model
response = generate_content(auth, 'Hello!', model='gemini-1.5-flash')
```

## Vertex AI Vector Search

```python
from gcpeasy.ai import create_vector_search_index, create_vector_search_endpoint

# Create a Vector Search index (768-dim, text-embedding-004 compatible)
idx = create_vector_search_index(auth, 'my-kb-index', dimensions=768)
print(idx['name'])

# Deploy to an endpoint for ANN queries
ep = create_vector_search_endpoint(auth, 'my-kb-endpoint')
print(ep['name'])
```

## Google Cloud Storage

```python
from gcpeasy.data import create_bucket, bucket_url, signed_url

# Create a bucket with uniform access + versioning (always on)
bucket = create_bucket(auth, 'my-app-data')
print(bucket['url'])  # gs://my-app-data

# GCS object URL
print(bucket_url('my-app-data', 'docs/readme.md'))
# gs://my-app-data/docs/readme.md

# Signed URL (1 hour)
url = signed_url(auth, 'my-app-data', 'private/file.pdf', hours=2)
```

## Firestore, Cloud SQL, Memorystore, Pub/Sub


```python
from gcpeasy.data import (
    create_collection, firestore_conn,
    create_postgres, postgres_conn,
    create_redis, redis_conn,
    create_topic, create_subscription,
)

# Firestore collection (created on first write)
coll = create_collection(auth, 'events')

# Cloud SQL PostgreSQL (SSL always on)
db = create_postgres(auth, 'myapp-db', **HIPAA)  # HIPAA: 35 backups, deletion protection
conn_str = postgres_conn(auth, 'myapp-db')  # → 'project:region:myapp-db'

# Memorystore Redis (auto STANDARD_HA with HIPAA profile)
cache = create_redis(auth, 'myapp-cache', **HIPAA)

# Pub/Sub
topic = create_topic(auth, 'events', kms_key_name=kms_key)  # optional CMEK
sub   = create_subscription(auth, 'events', 'events-worker', dead_letter_topic='events-dlq')
```

## Compute Engine, GKE, Artifact Registry, Cloud Run


```python
from gcpeasy.compute import (
    create_instance, instance_ip,
    create_gke_cluster, gke_kubeconfig,
    create_artifact_registry, registry_url,
    deploy_cloudrun, create_binary_auth_policy,
)

# Shielded VM + OS Login (IAM-controlled SSH) on a named VPC
vm = create_instance(auth, 'worker', network='prod-vpc', subnet='prod-subnet')

# GKE Autopilot — Workload Identity + Binary Authorization enforcement
cluster = create_gke_cluster(auth, 'myapp-gke', binary_authorization=True)

# GKE Standard — private nodes (no public IPs)
cluster = create_gke_cluster(auth, 'myapp-gke', autopilot=False, private_nodes=True)

# Cloud Run — internal load balancer ingress by default
svc = deploy_cloudrun(auth, 'api', image='gcr.io/myproject/api:latest',
                      service_account=sa_email, env={'ENV': 'prod'})
print(svc['url'])

# Binary Authorization policy — require attestation from named attestors
create_binary_auth_policy(auth, require_attestors=['projects/my-project/attestors/prod-attestor'])

# Artifact Registry
registry = create_artifact_registry(auth, 'myapp-images')
print(registry_url(auth, 'myapp-images'))
```

## VPC, Secret Manager, IAM, KMS, Audit Logs, Cloud Armor, Load Balancer


```python
from gcpeasy.network import (
    create_vpc, add_subnet, create_firewall_rule,
    create_secret, get_secret,
    create_service_account, bind_iam_role, sa_email,
    list_sa_keys, rotate_sa_key,
    create_kms_key, enable_audit_logs,
    create_armor_policy, create_managed_cert, create_https_lb,
)

# VPC + subnet with VPC Flow Logs enabled (default)
vpc    = create_vpc(auth, 'prod-vpc')
subnet = add_subnet(auth, 'prod-vpc', 'prod-subnet', cidr='10.1.0.0/24')

# Firewall — source_ranges must be explicit (no implicit open-world default)
create_firewall_rule(auth, 'allow-https', 'prod-vpc', ports=['443'],
                     source_ranges=['10.1.0.0/24'])

# Cloud KMS — 90-day auto-rotation key
kms_key = create_kms_key(auth, 'myapp-ring', 'data-key')

# Secret Manager with CMEK + rotation schedule
create_secret(auth, 'myapp/db-password', 'hunter2',
              kms_key_name=kms_key, rotation_period='7776000s')

# Enable Cloud Audit Logs for all services (SOC 2 CC7.1)
enable_audit_logs(auth)

# Service account key rotation
print(list_sa_keys(auth, 'myapp-sa'))  # shows age_days per key
new_key = rotate_sa_key(auth, 'myapp-sa')  # creates new, deletes keys >90 days

# Cloud Armor WAF policy (OWASP Top 10 + rate limit)
armor = create_armor_policy(auth, 'prod-waf')

# HTTPS LB with managed SSL cert + Cloud Armor
cert = create_managed_cert(auth, 'myapp-cert', domains=['myapp.example.com'])
lb   = create_https_lb(auth, 'prod-lb', backend_service=backend_svc,
                        armor_policy=armor['self_link'], ssl_cert=cert['self_link'])
print(lb['ip'])
```

## Security Defaults

| Control | Implementation | Compliance |
|---|---|---|
| No hardcoded credentials | ADC only; `service_account_file` if needed | All |
| Encryption at rest | GCS, Firestore, Cloud SQL, Memorystore — on by default | HIPAA §164.312, CC6.7 |
| CMEK | `kms_key_name` on bucket/postgres/redis/instance/secret | HIPAA, ISO 27001 |
| KMS auto-rotation | 90-day default via `create_kms_key` | NIST, ISO 27001 |
| Encryption in transit | Memorystore `transit_encryption=True`, Cloud SQL `requireSsl=True` | CC6.7 |
| Uniform bucket access | GCS uniform bucket-level access always enabled | CC6.7 |
| Shielded VM | Secure boot + vTPM + integrity monitoring by default | CC6.6 |
| OS Login | `os_login=True` default on GCE — IAM-controlled SSH, no project SSH keys | CC6.1 |
| Workload Identity | GKE Autopilot default; pod SA → Google SA mapping | CC6.1 |
| Private GKE nodes | `private_nodes=True` default (Standard mode) — no public IPs | CC6.6 |
| Binary Authorization | `binary_authorization=True` on GKE enforces image signing | CC6.7 |
| VPC Flow Logs | `enable_flow_logs=True` default on `add_subnet` | CC6.6, CC7.1 |
| Cloud Audit Logs | `enable_audit_logs()` — DATA_READ/WRITE/ADMIN_READ for allServices | CC7.1, CC7.2 |
| Cloud Armor WAF | `create_armor_policy()` — OWASP Top 10 + rate limit (10k req/min) | CC6.6 |
| Least privilege | `create_service_account()` + `bind_iam_role()` for minimal grants | CC6.3 |
| SA key rotation | `rotate_sa_key()` — creates new, deletes keys older than 90 days | CC6.2 |
| Secret management | Secret Manager with CMEK + rotation schedule | CC6.7 |
| Data residency | `region` param controls GCP region for all resources | HIPAA, GDPR |
| Backup retention | Cloud SQL: `backup_retention` (automated backups) + PITR (max 7d) | HIPAA §164.312(c) |
| Deletion protection | Cloud SQL: `deletion_protection=True` with HIPAA | HIPAA |
| Vulnerability scanning | Artifact Registry: Container Analysis always enabled | CC7.2 |
| No public bucket access | GCS uniform access blocks legacy ACLs | CC6.7 |
| Private Google Access | Subnets: `private_google_access=True` by default | CC6.6 |
| Cloud Run internal ingress | `INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER` by default | CC6.6 |
| Firewall no implicit default | `source_ranges` must be explicit — no open-world default | CC6.6 |

