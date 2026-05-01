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

| Module | AWS equivalent | Key functions |
|---|---|---|
| `gcpeasy.core` | `awseasy.core` | `GCPAuth`, `HIPAA/ISO27001/SOC2`, `GenAIStack` |
| `gcpeasy.ai` | `awseasy.ai` | `generate_content`, `create_vector_search_index`, `create_search_app` |
| `gcpeasy.data` | `awseasy.data` | `create_bucket`, `create_collection`, `create_postgres`, `create_redis` |
| `gcpeasy.compute` | `awseasy.compute` | `create_instance`, `create_gke_cluster`, `create_artifact_registry` |
| `gcpeasy.network` | `awseasy.network` | `create_vpc`, `create_secret`, `create_service_account`, `create_https_lb` |

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

## Firestore, Cloud SQL, Memorystore

```python
from gcpeasy.data import (
    create_collection, firestore_conn,
    create_postgres, postgres_conn,
    create_redis, redis_conn,
)

# Firestore collection (created on first write)
coll = create_collection(auth, 'user-sessions')

# Cloud SQL PostgreSQL
pg = create_postgres(auth, 'app-db', tier='db-g1-small')
conn_str = postgres_conn(auth, 'app-db')  # for cloud-sql-python-connector

# Memorystore Redis with TLS
redis = create_redis(auth, 'app-cache', transit_encryption=True)
uri = redis_conn(auth, 'app-cache')  # redis://host:port
```

## Compute Engine, GKE, Artifact Registry

```python
from gcpeasy.compute import (
    create_instance, instance_ip,
    create_gke_cluster, gke_kubeconfig,
    create_artifact_registry, registry_url,
)

# Shielded VM (secure boot + vTPM + integrity monitoring on by default)
vm = create_instance(auth, 'ml-worker', machine_type='n2-standard-4')
print(instance_ip(auth, 'ml-worker'))

# GKE Autopilot cluster with Workload Identity
cluster = create_gke_cluster(auth, 'prod-cluster', autopilot=True)
kubeconfig = gke_kubeconfig(auth, 'prod-cluster')

# Artifact Registry Docker repo
repo = create_artifact_registry(auth, 'app-images')
print(registry_url(auth, 'app-images'))
# us-central1-docker.pkg.dev/my-project-id/app-images
```

## VPC, Secret Manager, IAM, Load Balancer

```python
from gcpeasy.network import (
    create_vpc, add_subnet, create_firewall_rule,
    create_secret, get_secret,
    create_service_account, bind_iam_role, sa_email,
    create_https_lb,
)

# Custom-mode VPC
vpc = create_vpc(auth, 'app-vpc')
subnet = add_subnet(auth, 'app-vpc', 'app-subnet', cidr='10.10.0.0/24')
create_firewall_rule(auth, 'allow-https', 'app-vpc',
                     protocol='tcp', ports=['443'])

# Secret Manager
create_secret(auth, 'app/db-password', 'my-secure-password')
password = get_secret(auth, 'app/db-password')  # never logged

# Service Account + IAM binding
sa = create_service_account(auth, 'app-backend',
                            display_name='Backend Service Account')
bind_iam_role(auth, sa['email'], 'roles/secretmanager.secretAccessor')
print(sa_email(auth, 'app-backend'))

# HTTPS Load Balancer with Cloud Armor
lb = create_https_lb(auth, 'app-lb',
                     backend_service='global/backendServices/app-backend')
```

## Security Defaults

| Control | Implementation |
|---|---|
| No hardcoded credentials | ADC only; `service_account_file` if needed |
| Encryption at rest | GCS (Google-managed), Firestore, Cloud SQL, Redis — all on by default |
| Encryption in transit | Memorystore TLS, Cloud SQL `requireSsl=True` |
| Uniform bucket access | GCS uniform bucket-level access always enabled |
| Shielded VM | Secure boot + vTPM + integrity monitoring by default |
| Workload Identity | GKE — node SA → pod SA mapping; no key files in pods |
| Least privilege | Service Accounts + minimal IAM role bindings |
| Secret management | Secret Manager; `get_secret()` returns string, never logged |
| Idempotent operations | All `create_*` use create-or-return semantics |
| Compliance profiles | HIPAA / ISO27001 / SOC2 as composable `**kwargs` |
| Audit logging | `enable_data_access_audit()` wired into `GenAIStack` when `audit=True` |
| Cloud Armor / WAF | `create_armor_policy()` + `create_https_lb(armor_policy=...)` |
| Managed SSL certs | `create_managed_cert()` → zero certificate management toil |
| Zero Trust (IAP) | `enable_iap()` — verify identity before requests reach the app |
| OIDC tokens | `get_oidc_token()` for secure service-to-service calls |
| Data exfiltration | `create_vpc_sc_perimeter()` restricts GenAI service-plane API calls |
| Cloud Run defaults | `deploy_cloudrun(allow_unauthenticated=False)` — authenticated by default |

## Secure GenAI Webapp Pattern

The recommended stack for a production GenAI webapp on GCP:

```
Internet → Cloud Armor (WAF/DDoS) → HTTPS LB (Managed SSL) → IAP → Cloud Run → Vertex AI
                                                                         ↓
                                                               Secret Manager / GCS / Firestore
```

```python
from gcpeasy.core import GCPAuth, GenAIStack, HIPAA
from gcpeasy.network import (
    create_armor_policy, create_managed_cert,
    create_https_lb, enable_iap, get_secret,
)
from gcpeasy.compute import deploy_cloudrun

auth = GCPAuth(project='my-project')

# 1. Provision the data + AI infrastructure (audit logging auto-enabled via HIPAA)
stack = GenAIStack(auth, 'myapp', compliance=HIPAA)
resources = stack.provision()

# 2. Deploy the GenAI webapp on Cloud Run (authenticated only, custom SA)
service = deploy_cloudrun(
    auth, 'myapp-api',
    image='us-central1-docker.pkg.dev/my-project/myapp/api:latest',
    service_account=resources['service_account'],
    env_vars={'PROJECT_ID': auth.project},
    allow_unauthenticated=False,   # enforced by default
)

# 3. Cloud Armor: block SQLi / XSS + rate-limit
armor = create_armor_policy(auth, 'myapp-armor', rules=[
    {'priority': 1000, 'action': 'deny(403)',
     'match': {'expr': {'expression': 'evaluatePreconfiguredExpr("sqli-stable")'}},
     'description': 'Block SQLi'},
    {'priority': 2147483647, 'action': 'allow',
     'match': {'versionedExpr': 'SRC_IPS_V1', 'config': {'srcIpRanges': ['*']}},
     'description': 'default allow'},
])

# 4. Managed SSL cert + HTTPS LB
cert = create_managed_cert(auth, 'myapp-cert', domains=['api.myapp.example.com'])
lb = create_https_lb(
    auth, 'myapp-lb',
    backend_service='global/backendServices/myapp-backend',
    armor_policy=armor['self_link'],
    ssl_certificates=[cert['self_link']],
)

# 5. Enable IAP (zero-trust: only authorized users reach Cloud Run)
iap_secret = get_secret(auth, 'myapp/iap-client-secret')
enable_iap(auth, 'myapp-backend',
           iap_client_id='YOUR_OAUTH_CLIENT_ID',
           iap_client_secret=iap_secret)

print(stack.summary())
```

## Environment Variables

| Variable | Purpose |
|---|---|
| `GOOGLE_CLOUD_PROJECT` | GCP project ID (required) |
| `GOOGLE_CLOUD_REGION` | Default region (default: `us-central1`) |
| `GOOGLE_CLOUD_LOCATION` | Gemini API location (default: `global` for automatic routing) |
| `GOOGLE_GENAI_USE_VERTEXAI` | Set to `true` to use Agent Platform (Vertex AI) |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to service account key JSON |
| `GCLOUD_PROJECT` | Alias for `GOOGLE_CLOUD_PROJECT` |

