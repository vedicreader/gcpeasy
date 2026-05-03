# Changelog

All notable changes to `gcpeasy` are documented here.  This project follows
[Keep a Changelog](https://keepachangelog.com/) and uses semantic versioning.

## [Unreleased] — production-readiness pass

This release closes the gaps identified in the gap-analysis between
`gcpeasy` and the downstream `vr-deploy` integration.

### Added

* **CLI** (`gcpeasy ...`) wrapping the library:
  `preflight`, `enable-apis`, `vm create | deploy`, `run deploy`,
  `stack provision | destroy`.
* **Project bootstrap**: `core.enable_apis(auth, [...])` and
  `core.preflight(auth)` — fail fast with concrete remediation when ADC,
  billing, or required APIs are missing.  `GenAIStack.provision()` now
  enables required APIs by default.
* **VM bootstrap helpers**: `compute.vm_install_docker`,
  `compute.wait_for_ssh`, `compute.vm_run_compose` to mirror the Hetzner
  `htz_deploy` flow.
* **Cloud Build / image push**: `compute.build_image_cloudbuild` (tar
  source → upload to staging bucket → submit Cloud Build job → return
  digest) and `compute.push_image` for local Docker auth setup.
* **Cloud Run extras**: `compute.deploy_cloudrun` now accepts
  `cpu`, `memory`, `port`, `timeout_sec`, `secrets={env: secret-ref}`,
  `ingress`, and chooses a sensible `ingress` default based on
  `allow_unauthenticated`.  `compute.cloudrun_domain_mapping` and
  `compute.delete_cloudrun` added.
* **Load balancer plumbing**: `network.reserve_global_ip`,
  `network.create_health_check`, `network.create_backend_service`
  (with Cloud Armor attached **here** — where it actually applies),
  HTTP→HTTPS redirect (port 80) when `create_https_lb(http_redirect=True)`.
* **Cloud DNS**: `network.create_dns_zone`, `network.cloud_dns_record`.
* **IAP**: `network.get_or_create_oauth_brand`,
  `network.wait_managed_cert_active`.
* **Cloud SQL**: `data.create_database`, `data.create_db_user`.
  `create_postgres` now waits for the LRO and stores generated passwords
  in Secret Manager.
* **Teardown** (B4 of the plan): `delete_*` for instance, secret, bucket,
  redis, postgres, service-account, firewall, vpc, subnet,
  artifact-registry, cloudrun.  `GenAIStack.destroy()` reverses
  `provision()` in dependency order.
* **Test suite + CI**: `pytest` unit tests (38 tests) for the high-risk
  areas — IAM read-modify-write, Cloud Run IAM merge, firewall safe
  defaults, audit-config defaults, instance NIC wiring, signed-URL
  validation, CLI parsing.  GitHub Actions workflow added.
* **Constants**: `IAP_SSH_RANGE` (`35.235.240.0/20`), `REQUIRED_APIS`,
  `GENAI_APIS`, `DEFAULT_AUDIT_SERVICES`.

### Changed (security defaults)

* **`create_firewall_rule`** no longer defaults to `0.0.0.0/0` for ingress.
  It now requires explicit `source_ranges`, or `iap_ssh=True` (uses
  `35.235.240.0/20`), or `allow_public=True`.  *Breaking* if you relied on
  the implicit open-world default.
* **`create_instance`** assigns an external IP by default (one-to-one
  NAT), enables OS Login, blocks project-wide SSH keys, and accepts
  `ssh_keys=`, `startup_script=`, `service_account=`, `tags=`,
  `network=`, `subnetwork=`.  `instance_ip` falls back to the internal IP.
* **`enable_data_access_audit`** no longer defaults to `allServices`
  (which produces large Cloud Logging bills).  Default target is now a
  curated list (`aiplatform`, `storage`, `secretmanager`, `bigquery`).
  Pass `all_services=True` (or use a HIPAA profile, which sets
  `audit_all_services=True`) for the legacy behavior.
* **`deploy_cloudrun`** uses an additive IAM update for
  `allow_unauthenticated=True` (no longer overwrites all bindings),
  defaults `ingress` based on whether public access is allowed, and sets
  CPU/memory/port/timeout via the API instead of relying on Cloud Run
  defaults.
* **`bind_iam_role`** uses IAM policy v3 with etag round-tripping; retries
  on 409 ABORTED.
* **`enable_iap`** uses a precise field-mask `patch` rather than mutating
  the entire backend body.
* **`create_bucket`** sets uniform bucket-level access on the local
  `Bucket` object *before* creation, eliminating the brief window during
  which legacy ACLs applied.
* **`signed_url`** rejects expiry > 7 days (GCP signing v4 hard limit)
  and ≤ 0; uses v4 signing.
* **`generate_content`** default model is now `gemini-2.5-flash` (was
  `gemini-3-flash-preview`, which does not exist).  `list_models` makes a
  live SDK call with a curated fallback list.

### Fixed

* `create_https_lb` — Cloud Armor was attached to the global forwarding
  rule, where GCP silently ignores it.  Armor is now attached to the
  backend service via `create_backend_service(armor_policy=...)`.
  `create_https_lb`'s own `armor_policy` parameter is a no-op kept for
  backward compatibility (a warning is emitted).
* `create_postgres` — was fire-and-forget (`insert()` without
  `op.result()`), causing a race for any subsequent operation; now waits.
  Auto-generated passwords are stored in Secret Manager so they aren't
  lost when the caller doesn't capture the return value.
* `create_collection` — no longer pollutes Firestore with an `__init__`
  document; is now a pure-metadata no-op (Firestore collections are
  created on first real write, by API design).
* `create_vector_search_index` — accepts `wait=False` so the caller is
  not blocked for ~30 minutes on Vertex Vector Search index creation.
* `list_labeled_resources` — used to send `query=''` (which the Cloud
  Asset API rejects); now omits the field for unfiltered searches.

### Documentation

* `PLAN.md` and `README.md` updated with the new functions, CLI, and
  notebook-vs-`.py` source-of-truth note.
* This `CHANGELOG.md` added.

### Notes

* `nbs/*.ipynb` are kept as historical artifacts.  The canonical source
  is now the `.py` files; the legacy `# AUTOGENERATED!` headers were
  misleading because the `.py` files have been hand-edited extensively.
  A future change may either re-establish notebook parity or remove the
  legacy headers.
