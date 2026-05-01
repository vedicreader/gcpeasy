# gcpeasy — GCP Cloud Provider for GenAI

## Why this exists

`gcpeasy` is the GCP member of the `vedicreader` tool ecosystem:

| Tool | Purpose |
|---|---|
| dockeasy | Docker/Compose config generation |
| cfeasy | Cloudflare DNS + Zero Trust tunnels |
| vpseasy | Hetzner VPS provisioning + deployment |
| gheasy | GitHub automation |
| azeasy | Azure cloud provisioning for GenAI workloads |
| awseasy | AWS cloud provisioning for GenAI workloads |
| **gcpeasy** | **GCP cloud provisioning for GenAI workloads** |

The pattern across all tools: thin, Pythonic wrappers over provider SDKs, built with nbdev + fastcore, functional where stateless, small and succinct.

---

## Design decisions

### Raw google-cloud-* SDKs (not Deployment Manager / Terraform)

`gcpeasy` is a **Python library / building block**, not a standalone IaC CLI.

- All sibling tools (vpseasy, cfeasy, azeasy, awseasy) wrap provider SDKs directly — no IaC runtime
- Deployment Manager/Pulumi add heavy CLI + state-backend dependencies that don't fit the library model
- Terraform/Pulumi users can call `gcpeasy` functions _inside_ their programs
- Mitigation: every `create_*` function uses **create-or-return** semantics (idempotent), not blind POST

### Functional style + thin classes

Matching azeasy/awseasy:

- **Standalone functions** for stateless ops (`create_bucket`, `generate_content`, …)
- **Thin classes** only when a client connection is reused (`GCPAuth`, `GenAIStack`)
- No unnecessary ceremony, each module < 150 lines

### Compliance as dict profiles

```python
HIPAA   = dict(encryption=True, tls_min='1.2', audit=True, multi_region=True,
               backup_retention=35, deletion_protection=True,
               labels={'compliance': 'hipaa'})
ISO27001 = dict(encryption=True, audit=True, managed_sa=True,
                least_privilege=True, tls_min='1.2',
                labels={'compliance': 'iso27001'})
SOC2    = dict(encryption=True, audit=True, mfa_required=True,
               backup_retention=7, labels={'compliance': 'soc2'})
```

Every `create_*` function accepts `**compliance_opts`, so compliance requirements compose naturally:

```python
create_bucket(auth, 'phi-data', **HIPAA)
create_redis(auth, 'cache', **ISO27001)
```

### Authentication — Application Default Credentials

Supports the full GCP credential chain:

1. `GOOGLE_APPLICATION_CREDENTIALS` env var (service account key JSON)
2. `gcloud auth application-default login` (user credentials)
3. Attached service account (Compute Engine metadata server)
4. GKE Workload Identity / Pod identity
5. Cloud Run / App Engine built-in identity

No hardcoded credentials anywhere. Optional `service_account_file=` for key-based auth.
Optional `impersonate_sa=` for cross-project service account impersonation.

---

## AWS/Azure → GCP service mapping

| azeasy (Azure) | awseasy (AWS) | gcpeasy (GCP) |
|---|---|---|
| `DefaultAzureCredential` | `boto3.Session` | `google.auth.default()` ADC |
| `AZURE_SUBSCRIPTION_ID` | `AWS_DEFAULT_REGION` | `GOOGLE_CLOUD_PROJECT` + `GOOGLE_CLOUD_REGION` |
| Resource Group | AWS Resource Groups | Labels / Cloud Asset Inventory |
| Azure OpenAI | Amazon Bedrock | Vertex AI `GenerativeModel` (Gemini) |
| AI Search | OpenSearch | Vertex AI Search |
| Blob Storage | S3 | Google Cloud Storage |
| Cosmos DB | DynamoDB | Firestore |
| PostgreSQL Flexible | RDS PostgreSQL | Cloud SQL PostgreSQL |
| Redis Cache | ElastiCache | Memorystore Redis |
| VM | EC2 | Compute Engine |
| AKS | EKS | Google Kubernetes Engine (GKE) |
| ACR | ECR | Artifact Registry |
| VNet / NSG | VPC / SGs | VPC / Firewall Rules |
| Key Vault | Secrets Manager | Secret Manager |
| Managed Identity | IAM Role | Service Account + IAM |
| Private Endpoint | VPC Endpoint | Private Service Connect |
| Front Door + WAF | CloudFront + WAF | Cloud CDN + Cloud Armor |
| App Gateway WAF v2 | ALB + WAF v2 | Cloud Load Balancing + Cloud Armor |

**Key GCP-specific differences vs. awseasy:**
- Vertex AI is serverless (no `create_openai()` step) — use `generate_content()` directly
- GKE Autopilot is preferred over Standard (no node pool management)
- Firestore replaces DynamoDB (document model, not key-value)
- Service Accounts replace IAM Roles as the principal concept
- Labels (not tags) for resource grouping

---

## Project structure

```
gcpeasy/
├── nbs/
│   ├── index.ipynb        # README source (nbdev → README.md)
│   ├── 00_core.ipynb      # GCPAuth, compliance profiles, labels, GenAIStack
│   ├── 01_ai.ipynb        # Vertex AI Gemini, Vector Search, Vertex AI Search
│   ├── 02_data.ipynb      # GCS, Firestore, Cloud SQL PostgreSQL, Memorystore
│   ├── 03_compute.ipynb   # Compute Engine, GKE, Artifact Registry
│   ├── 04_network.ipynb   # VPC/Firewall, Secret Manager, Service Accounts,
│   │                      #   Private Service Connect, Cloud CDN, Cloud LB
│   ├── nbdev.yml
│   └── _quarto.yml
├── gcpeasy/
│   ├── __init__.py
│   ├── core.py
│   ├── ai.py
│   ├── data.py
│   ├── compute.py
│   └── network.py
├── pyproject.toml
├── MANIFEST.in
└── PLAN.md
```

Notebooks are the source of truth; `.py` files are generated via `nbdev_export`.

---

## Module breakdown

### `00_core.ipynb` → `core.py`

```python
__all__ = ['HIPAA', 'ISO27001', 'SOC2', 'GCPAuth',
           'label_resources', 'list_labeled_resources', 'GenAIStack']
```

### `01_ai.ipynb` → `ai.py`

```python
__all__ = ['list_models', 'generate_content',
           'create_vector_search_index', 'create_vector_search_endpoint',
           'create_search_app', 'search_query']
```

### `02_data.ipynb` → `data.py`

```python
__all__ = ['create_bucket', 'bucket_url', 'signed_url', 'bucket_conn',
           'create_collection', 'firestore_conn',
           'create_postgres', 'postgres_conn',
           'create_redis', 'redis_conn']
```

### `03_compute.ipynb` → `compute.py`

```python
__all__ = ['create_instance', 'instance_ip', 'start_instance', 'stop_instance',
           'delete_instance', 'create_gke_cluster', 'gke_kubeconfig', 'scale_gke',
           'create_artifact_registry', 'registry_url', 'attach_registry_to_gke']
```

### `04_network.ipynb` → `network.py`

```python
__all__ = ['create_vpc', 'add_subnet', 'create_firewall_rule',
           'create_secret', 'get_secret', 'update_secret', 'secret_name',
           'create_service_account', 'bind_iam_role', 'sa_email',
           'create_private_service_connect',
           'create_cdn_backend', 'create_https_lb']
```

---

## Compliance coverage

| Control | How applied |
|---|---|
| Encryption at rest | GCS (Google-managed), Cloud SQL, Firestore, Redis — on by default |
| Encryption in transit | Memorystore `transit_encryption=True`, Cloud SQL `requireSsl=True` |
| Uniform bucket access | GCS uniform bucket-level access always enabled |
| Shielded VM | Secure boot + vTPM + integrity monitoring by default on GCE |
| Workload Identity | GKE Autopilot default; pod SA → Google SA mapping |
| Least privilege | `create_service_account()` + `bind_iam_role()` for minimal grants |
| Secret management | Secret Manager; `get_secret()` returns string only |
| Data residency | `region` param controls GCP region |
| Backup retention | Cloud SQL: `backup_retention` from compliance profile |
| Deletion protection | Cloud SQL: `deletion_protection=True` when HIPAA |
| Vulnerability scanning | Artifact Registry: Container Analysis always enabled |
| Audit logging | Cloud Audit Logs via `audit=True` compliance flag |
| No public bucket access | GCS uniform bucket-level access blocks legacy ACLs |
| Private Google Access | Subnets: `private_google_access=True` by default |

---

## Implementation status

- [x] Bootstrap — `pyproject.toml`, `MANIFEST.in`, `nbs/` structure
- [x] `00_core.ipynb` — `GCPAuth`, compliance profiles, labels, `GenAIStack` skeleton
- [x] `01_ai.ipynb` — Vertex AI `generate_content`, Vector Search, Vertex AI Search
- [x] `02_data.ipynb` — GCS, Firestore, Cloud SQL PostgreSQL, Memorystore Redis
- [x] `03_compute.ipynb` — Compute Engine, GKE, Artifact Registry
- [x] `04_network.ipynb` — VPC/Firewall, Secret Manager, Service Accounts, PSC, CDN, LB
- [x] Wire `GenAIStack.provision()`
- [x] `nbs/index.ipynb` — README + usage examples
- [x] `nbdev_export` — generate all `.py` files
- [x] `README.md` + `PLAN.md`
- [x] **Secure GenAI Webapps gap remediation** (google/skills audit):
  - [x] Migrate `generate_content` to `google-genai` SDK (deprecated `vertexai` removed)
  - [x] Add `safety_settings` parameter to `generate_content()`
  - [x] Update model IDs to current Agent Platform models (default `gemini-2.5-flash`)
  - [x] `deploy_cloudrun()` + `cloudrun_url()` — primary GenAI webapp serving pattern
  - [x] `create_armor_policy()` — Cloud Armor WAF/DDoS protection
  - [x] `create_managed_cert()` — Google-managed SSL; wired into `create_https_lb()`
  - [x] `enable_iap()` — Zero Trust identity layer for web apps
  - [x] `get_oidc_token()` — service-to-service OIDC token helper
  - [x] `enable_data_access_audit()` — wire `audit=True` compliance flag to actual audit log config
  - [x] `create_vpc_sc_perimeter()` — VPC Service Controls for GenAI data exfiltration prevention
  - [x] Add `google-genai`, `google-cloud-run`, `google-cloud-access-context-manager` deps
- [x] **Production-readiness pass for `vr-deploy gcp-vm` / `vr-deploy gcp-cloudrun`** (see `CHANGELOG.md`):
  - [x] Phase 1 — `create_instance` external IP/SSH/startup; safe firewall defaults; real Gemini default; `enable_apis`; `preflight`; `vm_install_docker` / `wait_for_ssh` / `vm_run_compose`; CLI; pytest + CI
  - [x] Phase 2 — `create_backend_service` + `reserve_global_ip` + Armor on backend; HTTP→HTTPS redirect; Cloud Run cpu/memory/port/secrets/ingress + additive IAM; `build_image_cloudbuild` / `push_image`; `cloud_dns_record` / `cloudrun_domain_mapping` / `wait_managed_cert_active`
  - [x] Phase 3 — Postgres wait + Secret Manager-backed master password + `create_database`/`create_db_user`; `create_collection` no-op; Vector Search `wait=False`; redis/secret label reconcile; uniform bucket access at create time
  - [x] Phase 4 — IAM v3 etag w/ retry; `get_or_create_oauth_brand` + IAP `patch` w/ field-mask; `list_labeled_resources` empty-query fix; OS Login / `block-project-ssh-keys` defaults; audit defaults curated list; `delete_*` for every resource + `GenAIStack.destroy()`
  - [x] Phase 5 — `_wait` progress logger; error translation; `CHANGELOG.md`

### Source-of-truth note

`nbs/*.ipynb` were originally the source of truth; however the `.py` files
have been hand-edited extensively (notably during the Secure GenAI gap
remediation and the production-readiness pass).  The canonical source is
now the `.py` files in `gcpeasy/`.  A future change may either restore
parity with the notebooks or remove the legacy `# AUTOGENERATED! DO NOT
EDIT!` headers.
---

## Future work

### Short-term

- [ ] **`GenAIStack.provision(gke=True)`** — full GKE Autopilot cluster provisioning
- [ ] **`GenAIStack.provision(cloud_sql=True)`** — Cloud SQL in the stack flow
- [x] **Cloud Armor policy creation** — `create_armor_policy(auth, name, rules)` ✓
- [x] **Managed SSL certs** — `create_managed_cert(auth, name, domains)` ✓
- [ ] **VPC Service Controls** — perimeter creation for HIPAA data isolation ✓ (`create_vpc_sc_perimeter`)
- [x] **Cloud Run** — `deploy_cloudrun(auth, name, image, ...)` for serverless containers ✓
- [ ] **Pub/Sub** — `create_topic()` / `create_subscription()` for event-driven GenAI
- [ ] **BigQuery** — `create_dataset()` / `create_table()` for analytics layer

### Medium-term

- [ ] **Cloud Functions** — `deploy_function(auth, name, source, ...)` wrapper
- [ ] **Vertex AI RAG Engine** — `create_rag_corpus()` (managed alternative to Vector Search)
- [ ] **AlloyDB** — `create_alloydb()` as pgvector-native alternative to Cloud SQL
- [ ] **Cloud Spanner** — globally distributed OLTP for multi-region HIPAA workloads
- [ ] **Data catalog / tagging** — Cloud DLP + Data Catalog integration
- [ ] **Monitoring / alerting** — Cloud Monitoring alerting policies + uptime checks

### Long-term

- [ ] **`gcpeasy` CLI** — thin CLI wrapping the library for quick provisioning
- [ ] **Terraform export** — `stack.to_terraform()` for teams wanting IaC output
- [ ] **Cost estimation** — `stack.estimate_cost()` using Cloud Billing API
- [ ] **Multi-project** — cross-project resource provisioning with Shared VPC support

---

## Verification checklist

- [ ] `python -c "from gcpeasy import *"` succeeds
- [ ] `python -c "from gcpeasy.core import HIPAA; print(HIPAA)"` prints profile
- [ ] With ADC: `GCPAuth()` resolves `project` + `region`
- [ ] `create_bucket(auth, 'test-bucket')` creates uniform-access, versioned bucket
- [ ] `create_secret(auth, 'test/key', 'val')` stores in Secret Manager
- [ ] `generate_content(auth, 'Hello')` returns Gemini response
- [ ] `GenAIStack(auth, 'myapp').provision()` provisions full stack
- [ ] `create_vpc(auth, 'test-vpc')` creates custom-mode VPC
