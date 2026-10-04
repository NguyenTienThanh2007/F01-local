# Phase 2C implementation plan — proposal only

Status: Phase 1 M0–M6, Phase 2A and Phase 2B complete. Phase 2C implementation has **not started**. This document proposes seven bounded milestones; it authorizes no code, migration, provider resource, credential setup or deployment.
Revision: 0.1 · 2026-10-04
Related: [Product](PRODUCT_SPEC.md), [Architecture](ARCHITECTURE.md), [Roadmap](ROADMAP.md), [Phase 2B completion](PHASE2B_IMPLEMENTATION.md), [Design system](DESIGN_SYSTEM.md).

## 1. Starting point and objective

Phase 2B is complete at `f9c2a69`, with trusted sandbox image `sha256:bf55945a66450b4d747196aed159eba926ca377b66e41400da70c0a54e3363c0`, passing Docker containment and end-to-end execution journey, 289 backend tests passed with 2 skipped, and passing frontend typecheck/build. The acceptance report records `live_provider` and `browser_journey` as `not_run`. Phase 2C implementation must build from this completed repository state. No production deployment acceptance result is inferred from a mocked deployment provider.

Phase 2C completes this journey:

verified source/version and evidence → verified production artifact → owner-authorized release → observed public URL and health → immutable release history → request against existing pinned source → existing 2B plan/patch/build/test/repair/preview → reviewed production redeploy → inspect old release → preserve the previous working release on failure.

Keep the browser-focused Next.js/React/TypeScript stack and single-owner model. Proposed first acceptance app has local UI state and bundled assets, no generated database, uploads, outbound service integration or irreversible external writes. Public hosting is a Phase 2C acceptance deployment, not Phase 3 commercial launch. Every milestone below depends on the preceding gate; implementation requires a separate founder instruction.

### The artifact handoff

Phase 2B persists immutable source candidates and verification evidence. Its verified build output lives in a bounded preview container and is associated with a capability-specific Next `basePath`. That container's image ID is not a digest of the generated app, and its temporary output is not a durable production package.

2C must create a **production artifact from the exact saved source**, using an application-owned packaging recipe inside the trusted sandbox. It must not generate source again or rebuild on the factory host. Production uses its own root path/configuration; a preview build cannot be relabeled production. If packaging changes configuration or output, run the applicable typecheck/build/tests and production-runtime checks again, bind the resulting evidence to that artifact, and show it in the owner's release review. No silent provider rebuild is allowed after artifact approval. If `f9c2a69` already adds an export format, inspect and reuse it; do not replace working 2B implementation.

The packaging manifest must bind project, source version/candidate/digest, parent digest, Brain revision, request/plan, recipe version, dependency lock digest, exact sandbox image, target OS/architecture, output manifest/digest, verification evidence IDs/digests, production configuration revision/hash and compatibility declaration. The production package can differ from the preview package; both retain the same source lineage and distinct evidence.

## 2. Provider decision — recommendation, not selection

**Recommend evaluating Vercel first, using an uploaded prebuilt production package, staged with domain assignment disabled, then explicit promotion after health checks.** This is a proposed fit for the existing Next.js stack and provider-generated public URLs. Approval depends on the 2C.0 artifact/credential/isolation gates. No account, plan, resource or default adapter has been selected.

Official docs were reviewed on 2026-10-04. Provider capabilities below are documented facts; the F01 adapter design and recommendation are our proposed interpretation. Recheck versions, permissions and account limits during 2C.0; do not rely on an undocumented idempotency guarantee.

| Option | Deployment model and minimum operations | Credentials and public URL | Tradeoffs, rollback and reconciliation | Local-test strategy |
| --- | --- | --- | --- | --- |
| **Vercel staged prebuilt — recommended evaluation** | Produce a validated Build Output API package; upload/deploy it without a remote source build; observe deployment; health-check staged production output; explicitly promote; inspect/restore previous deployment. Use documented REST operations where they cover the requirement and a pinned trusted CLI for the remaining prebuilt/staging/promotion operations. | Release service alone holds a scoped Vercel token plus target account/project IDs. One provider project per F01 project, separate from factory hosting; production configuration is independently pinned. Store the returned unique deployment URL and observed production alias, normally under `vercel.app`; no custom domain needed. | Good Next/CDN fit and staged promotion. A Preview-to-Production promotion can rebuild; require a **staged production** package instead. A 2B `.next` tree is not Vercel output. Native functions require compatible Linux/architecture packaging. No assumed create idempotency: correlate persisted F01 operation IDs with provider metadata, then reconcile. Keep old deployment/output for restore; provider retention is not the only artifact archive. | Real Docker package/production-path checks; controlled adapter HTTP/CLI transports and crash tests; finally an explicitly approved disposable provider project proving prebuilt upload, staged health, public alias, update and restoration. `vercel dev` or mocks do not prove public release. |
| **Render prebuilt OCI — fallback candidate** | Package the verified app as an OCI runtime image and push it by registry digest; create/get an image-backed web service; trigger/get/cancel deploy; observe HTTP health; inspect/roll back old deploy. | Private release-service Render token, separate registry upload credentials, and provider-side read-only image-pull credential if needed. Returned `onrender.com` service URL; no custom domain. These credentials are absent from image layers and app environment. | Fits ordinary Next server output and exact OCI digest. Adds registry/runtime packaging and service cost. A normal service deploy switches routing after provider health, so it needs a proven manual staging/promotion strategy or separately staged service before adoption; PostgreSQL pointer checks alone cannot stop provider routing. Digest-pinned rollback needs retained images and compatible config; disks are not rolled back. | Run the exact OCI image and trusted health probe locally; controlled Render/registry transports; then a disposable live image-backed service and failed-update/rollback test. |
| **Fly Machines/OCI — more control, larger first scope** | Push an OCI digest; create/get/start/stop/destroy Machines with bounded app configuration; observe health; explicitly coordinate staging/routing and restore prior image/config. | App-scoped deploy token for normal operations; separate provisioning authority if app/network creation requires it; registry credential stays outside generated runtime. Observe the app's `fly.dev` URL and machine/image identity. | Flexible container runtime, but F01 owns more rollout, routing and recovery. Fly apps in one organization share private networking by default: per-project isolation must be explicitly designed and demonstrated. Do not place untrusted generated apps on the factory's private network. Not the minimum first adapter unless container control is required. | Same OCI/local runtime tests; controlled Machines transports; disposable live app with isolation, stage/switch/failure and cleanup tests. No claim that Machines API automatically gives atomic blue/green promotion. |

References supporting the table: [Vercel Build Output API](https://vercel.com/docs/build-output-api), [prebuilt and staged CLI deployment](https://vercel.com/docs/cli/deploying-from-cli), [promotion behavior](https://vercel.com/docs/deployments/promoting-a-deployment), [generated URLs](https://vercel.com/docs/deployments/generated-urls), [create deployment REST API](https://vercel.com/docs/rest-api/deployments/create-a-new-deployment), [Render images](https://render.com/docs/deploying-an-image), [Render health](https://render.com/docs/health-checks), [Render rollback](https://render.com/docs/rollbacks), [Fly Machines operations](https://fly.io/docs/machines/guides-examples/managing-machines-with-the-api/), [Fly private networking](https://fly.io/docs/networking/private-networking/).

### Conditions before adopting Vercel

- Decide whether the first release profile is a static export of eligible browser apps or the full Next Build Output/function profile. Static export is simpler but cannot silently narrow already supported apps: reject incompatible apps clearly. Full Next packaging requires proving a pinned, offline, credential-free builder and native/runtime compatibility. No arbitrary model-authored build, routing or infrastructure settings are accepted.
- Provider discovery/linking and any `vercel pull` equivalent happen in trusted release administration. Official CLI guidance downloads settings/environment variables before local build; sanitize an allowlisted, nonsecret configuration snapshot before sandbox injection. Never copy downloaded token/environment files into source or give the sandbox a Vercel token. If credential-free/network-disabled packaging cannot be demonstrated, this adapter fails the gate; ask for a provider/profile decision, rather than weakening isolation.
- Use production-target prebuilt staging with automatic domain assignment disabled, including the **first** deployment. Confirm project defaults and observed alias behavior in the live spike. Never promote the 2B preview or use a path that silently rebuilds with different environment variables.
- Use a separate provider project for each generated application and separate factory hosting resources. Provider account identity, least available credential scope, region/runtime limits, plan and a cost ceiling need founder approval. Vercel Hobby is restricted to personal noncommercial use; do not assume it covers F01 commercial hosting. See [Hobby policy](https://vercel.com/docs/plans/hobby). This is provider provisioning, not F01 billing or team functionality.
- Decide how old releases remain reproducible: durable package storage is mandatory; live old URLs depend on provider retention/protection. Proposed minimum retains the current and previous live deployment plus immutable records/packages for accepted releases during Phase 2C acceptance. Define later cleanup explicitly rather than promising permanent running instances.

## 3. Common release architecture and invariants

### Boundaries

FastAPI remains authoritative for authorization, frozen release intent and production pointers. A separate trusted release worker consumes persisted operations and calls a small provider-independent `ReleaseAdapter`. The source-generation provider and 2B build worker cannot invoke it. Next.js uses fixed generated-client routes and receives sanitized IDs/status/URL/health only. Provider SDK/wire types stay in adapters.

Proposed domain operations are `prepare_or_locate_target`, `upload_artifact`, `stage_release`, `observe_release`, `observe_routing`, `promote`, `cancel_if_supported`, and `restore_previous`. Inputs are application-owned target/operation/artifact/configuration values, never model shell commands or arbitrary URLs. Implement only one approved provider; keep this interface small, not a plugin framework or Connector Ecosystem.

The release worker can upload bounded opaque artifact bytes but cannot execute generated code. Packaging remains in 2B isolation. Registry/provider credentials stay in the release service or provider-side pull configuration, never in Brain, source, artifact layers, sandbox, generated runtime, browser or Trace. Initial production runtime receives no factory credentials and no generated-app secrets. Allowlisting public configuration does not allow arbitrary `NEXT_PUBLIC_*` secret exposure.

Production is a distinct public hosting boundary, not the local Docker gateway exposed to the internet. It has separate cookie hosts, target/configuration and any data resources; it cannot access preview storage, factory databases, container sockets, metadata endpoints or other projects' private resources. A provider project label alone is not proof of isolation. Demonstrate the chosen provider profile; reject unsupported networking/configuration instead of claiming the Docker `network=none` policy transfers to cloud hosting unchanged. Prefer static output for the first acceptance if approved; no outbound server integrations are authorized.

### Proposed additive persistence

Names below are tentative. Implement in a new `0004_phase2c` migration after inspecting the completed 2B schema; never rewrite frozen migrations or relabel Phase 1 deployments.

| Record | Frozen identity or controlled state |
| --- | --- |
| `production_targets` | Scoped project/provider account/resource binding, target host allowlist, current production release pointer and monotonic generation; serialized release-operation lease. Separate from the 2B current version/preview pointer. |
| `release_configurations` | Immutable environment=`production` configuration revision/hash, public allowlist, runtime/profile/region/health policy, secret revision references (empty in initial scope), compatibility declaration. No secret values. |
| `artifact_preparations` | Frozen packaging command/intent and owner/session/source/configuration bases, with fenced lease/deadline, bounded attempts, cancellation, persisted sandbox cleanup identity and eventual artifact/failure reference. Packaging can run before a release exists. Reuse 2B lease/cleanup helpers without inventing a generation run or changing its frozen inputs. |
| `release_artifacts` | Immutable source/version/candidate/Brain/request lineage, source/dependency/recipe/image/platform/configuration digests, validated file manifest, durable object/OCI reference, output digest, evidence manifest and packaging outcome. Only passed packaging becomes eligible. |
| `production_releases` | Immutable logical release ID, owner approval/initiator, command ID and canonical intent hash, target/artifact/configuration/evidence bindings, expected current Brain/source version/production release/generation, previous release ID and policy version. Outcome is derived from observations/operations, not rewriting history. |
| `release_operations` | Persisted stage/action UUID, payload hash, provider correlation ID, external resource IDs, bounded attempts/deadline, lease epoch/token, state and safe error. Unique `(release_id, action, ordinal)` provides stable dispatch/recovery identities. |
| `release_observations` | Append-only sanitized provider, URL/routing and health observations with operation/release identity, timestamps, observed artifact marker and compatibility/recovery decisions. No unrestricted logs/responses. |

Use scoped composite foreign keys for every project/target/source/version/evidence reference, unique command/intent identities, immutable input triggers and a target-scoped single active operation constraint. Immutable release headers can have many deployments/operations; do not inherit `deployment_records`' Phase 1 one-simulation-per-run uniqueness. Production pointers reference only an observed successful release of that same target/project.

Create the immutable artifact only after packaging passes; a 202 response identifies its durable preparation until then. Failed/canceled preparations retain bounded evidence and cleanup identity, never an eligible artifact. The trusted runtime marker uses the preassigned artifact identity and source/configuration digests; the final output digest is verified separately, avoiding a self-referential package hash.

### Execution, promotion and reconciliation

| Step | Required behavior |
| --- | --- |
| Reserve | In a short owner/project/target transaction, validate session, ownership, archive state, exact current source/version/Brain, artifact/evidence/configuration and expected production generation; persist immutable owner-approved intent, stable operations and replay receipt. No provider call while holding a DB transaction. |
| Stage | Claim a fenced operation, recheck authorization/bases/configuration, dispatch upload/stage outside PostgreSQL, persist bounded observation in a separate transaction. Staging must not redirect current production traffic. |
| Verify | Check provider readiness **and** application-owned HTTPS health at the returned allowlisted staged host. Require bounded bodies/time/redirects and the expected artifact/version marker plus representative app/asset behavior. Provider `READY` alone is insufficient. Never probe user/model-supplied destinations, loopback/private/metadata addresses or a factory origin. |
| Promote | Recheck owner/session, exact bases/configuration/evidence and target generation immediately before dispatch. Serialize promotions/config changes and relevant project writes through the release operation guard; do not hold DB locks across network calls. Persist the cutover operation before calling the provider. |
| Observe and commit | Reconcile provider target/alias and check public URL health/marker. Under locks, recheck operation fence and bases; atomically append release outcome, set only `production_targets.current_release_id`, advance its generation and append canonical Trace/provenance. A preview/source pointer is never updated by deployment. |
| Compensate | On failed public health or invalidated authorization/base after external cutover, preserve the last successful DB production pointer and restore the prior provider target if possible. A bounded service recovery authority may restore the already approved prior binding even if the initiating session ended; it cannot promote a new candidate. Re-observe routing/health before reporting restoration. |

External routing and PostgreSQL cannot commit atomically. A lost response may mean the provider succeeded. Record `outcome_unknown`/`reconciling`, query the known resource/operation metadata and compare artifact/configuration before any replay. Stop new promotion while ambiguity exists. Never report a failed deployment as current; never imply DB rollback reverses traffic. If compensation is unavailable, display actual routing as degraded/unknown while preserving the last successful logical release, and require recovery rather than claim the old URL is healthy. The provider's before-switch health gate and recovery must be demonstrated before enabling releases.

Stable command IDs and intent deduplication survive the existing 24-hour HTTP receipt window. Canonical intent hashes exclude transport keys/command nonces but include the exact artifact/configuration/bases/target generation. Repeated keys or different keys for the same frozen logical intent return the same release. Explicit retry resumes a reconcilable stage with the same operation identity; creating a new logical release is a distinct reviewed command. Native provider idempotency can be used only when documented/tested. If no reliable correlation can establish whether create succeeded, do not blindly repeat create. Discover and quarantine duplicate physical resources; they never become duplicate logical releases or receive production routing.

Bound provider polling/retries by persisted deadlines, attempt count and concurrency. Retry safe reads, throttled requests and a write only if idempotency/reconciliation establishes safety. Do not automatically retry authorization, invalid artifact/config, stale-base or application-health failures. Cancellation before dispatch prevents effects; after dispatch it is `cancel_pending` until observed cancellation/compensation. Leases fence DB state but cannot cancel an in-flight external request; restart must observe it before taking another action.

### Migration compatibility and recovery

Factory migration: additive upgrade from completed 2B with existing real/simulated history retained; previous API/worker compatibility and feature-disable behavior tested. Old code must not read/write production state incorrectly. Once production records exist, downgrade refuses destructive loss; rollback application code within a documented compatible schema or use an explicit forward migration. Back up and test restoring the factory metadata/artifact manifest before release acceptance.

Generated app data: initial `migration_mode=none`, `data_schema=none`, `external_effects=none`; no database/storage provisioning or arbitrary pre/post-deploy command. Reject a release requiring those capabilities. Preview browser state is not copied to production. Future data migrations require a separate approved extension with expand/contract compatibility, backups, restore verification, safe schema windows and forward recovery. Rolling code back never claims to undo a database migration, external payment, sent message or other irreversible effect.

## 4. Small implementation milestones

Backend module paths below are relative to `apps/api/src/f01/`; migrations are under `apps/api/migrations/versions/`. New module names are proposals. Set numeric artifact, concurrency, polling, dispatch, health and compensation budgets in 2C.0; persist deadlines and test their boundaries before enabling operations.

### 2C.0 — Release architecture and provider decision

| Item | Plan |
| --- | --- |
| Scope | Reconcile actual `f9c2a69`; approve one provider, artifact profile/storage, public URL and staging/restore model, cost ceiling and owner promotion policy. Prove package portability and absence of release credentials in the builder. |
| Likely files/modules | This document and source-of-truth docs; future trusted packaging recipe under `sandbox/`, future acceptance fixture/spec under `apps/api/tests/releases/`. An authorized spike may use disposable resources only. |
| Database/schema | None in the decision milestone. Specify manifest/schema and migration compatibility before 2C.1. |
| API contracts | Draft provider-independent artifact/release DTOs and adapter method semantics only. No empty public endpoints. |
| Security | Exact toolchain/image and bounded build policy; sanitized production config; separate provider project/cookie/network boundary; release token outside every source/build/runtime path. |
| Idempotency/reconciliation | Demonstrate correlation after create/promotion response loss and ability to query actual routing; define what an unknown outcome does. Reject a provider/profile that needs unsafe blind retry. |
| Acceptance | Founder records the decisions; a separately authorized spike proves exact package, no silent rebuild, staged first deployment, public health/marker, previous-target restore and isolation. |
| Tests | Artifact manifest/path/link/size validation design; actual sandbox packaging/health and provider staging/restore spike. Review fixture failure cases before implementing shared code. |
| Exclusions | Production product rollout, domain UI, infrastructure provisioning for customer databases, multiple provider adapters, billing/teams/connectors. A recommendation alone does not pass this gate. |

### 2C.1 — Deployment domain and persistence

| Item | Plan |
| --- | --- |
| Scope | Implement frozen artifacts/configurations/release intents, target pointer, append-only observations and durable operation leases. Keep new release state separate from 2B run/preview and simulated deployment records. |
| Likely files/modules | `domain/releases.py`, `application/releases.py`, `db/models.py`, `db/` queries, new migration, `tests/persistence/test_releases.py`; reuse existing ownership/idempotency helpers. Names are proposed. |
| Database/schema | Add the seven scoped records in section 3, their uniqueness/FKs/input immutability, target generation and active-operation guard. No team schema or edits to 0001–0003. |
| API contracts | Define `ReleaseArtifact`, `ProductionTarget`, `ReleaseDetail`, `ReleaseOperation` and immutable `PromoteRelease` input. Provider wire types excluded; public responses contain no storage credentials. |
| Security | Owner and same-project lineage/FK checks; historical simulated versions cannot qualify; only passed exact production packaging/evidence can bind a release. |
| Idempotency/reconciliation | Stable command/intent/action identities; atomic receipt + release intent; leased recovery state persists uncertain dispatch. Exactly one logical release per frozen intent. |
| Acceptance | Upgrade a populated 2B DB without changing IDs/current previews; independent production pointer; duplicate reservations converge; failed/stale/incomplete evidence cannot create a current production release. |
| Tests | Real PostgreSQL migration/rollback guards, immutable history, cross-project references, duplicate/concurrent reservation, lease fencing, expected-generation CAS and preservation of real/simulated rows. |
| Exclusions | Live provider calls, deployment buttons, shipping unverified packages, widening generated-app schema/data scope. |

### 2C.2 — Verified artifact packaging and release adapter

| Item | Plan |
| --- | --- |
| Scope | Export/package exact saved source in an isolated production-profile build, validate/store digest-bound output, implement only the approved adapter's upload/stage/observe/cancel/restore primitives and recovery correlation. No traffic promotion enabled yet. |
| Likely files/modules | `execution/` packaging/export helpers, trusted `sandbox/` profile, `application/release_artifacts.py`, private artifact storage adapter, `release/adapter.py`, `release/<approved_provider>.py`, `config.py`, release worker and tests. Reuse working 2B verification. |
| Database/schema | Populate artifact preparations/artifacts/configurations/operations/observations from 2C.1. Add provider-specific optional indexes only if justified; provider schemas stay outside domain JSON. |
| API contracts | Proposed owned `POST /v1/projects/{id}/release-artifacts` with verified version/configuration and frozen bases + stable command/idempotency key; GET preparation status and artifact list/detail. Returns 202 persisted preparation, never an invented passed artifact. |
| Security | Bounded output export rejecting symlink/archive/path/size escapes; no generated code on host/CLI uploader. Durable bytes verified before upload. Credential references outside sandbox; production root path and no preview capability in output. New builder image requires its own containment checks. |
| Idempotency/reconciliation | Content-addressed artifact identity and verified upload reuse; persisted stage ID before network call; query after lost response; no model re-generation, provider remote rebuild or duplicate logical artifact. |
| Acceptance | Local isolated runtime serves exact production package/marker/assets; package persists after preview/container expiry. Controlled adapter reaches staged/ready/failed/unknown states without changing either current pointer. |
| Tests | Real Docker install/typecheck/build/tests/production-path checks; manifest tampering, artifact corruption/oversize, credential echo, platform mismatch; controlled provider auth/429/timeout/malformed response/response-loss/restart. |
| Exclusions | Production cutover, arbitrary shell/package/deploy hooks, app secrets/database, new source provider, multiple adapters. |

### 2C.3 — Promotion command and public health verification

| Item | Plan |
| --- | --- |
| Scope | Implement explicit single-owner release approval/command, bounded release worker, stage/health/promote/public-health/commit and compensation workflow from section 3. |
| Likely files/modules | `application/releases.py`, `release/worker.py`, owned `api/v1/releases.py`, safe error mapping, identity/access helpers, generated OpenAPI/client; existing project/planning/execution write services where promotion guards coordinate base changes; targeted persistence/provider tests. |
| Database/schema | Store immutable approval on release intent; stage/cutover/restore operations and append-only health/alias observations; update only target production pointer/generation on confirmed success. |
| API contracts | Proposed `POST /v1/projects/{id}/releases`: `{command_id, artifact_id, configuration_id, expected_brain_revision_id, expected_version_id, expected_production_release_id, expected_target_generation}` + `Idempotency-Key` → 202 `ReleaseDetail`. Owned GET list/detail, POST cancel, POST explicit retry/resume. Reject arbitrary URL/provider/commands. Safe conflicts include stale source/Brain/production/config, release in progress, unverified artifact and reconciliation required. |
| Security | Verified owner/session and current bases at reservation and before promotion; deny archived/foreign targets. Same-origin/CSRF BFF writes; allowlisted HTTPS health hosts with SSRF defenses, bounded evidence; operator recovery can only restore a prior approved binding. |
| Idempotency/reconciliation | Stable intent/action IDs across HTTP replay and worker restart. Before replaying an unknown write observe provider deployment/routing. Duplicate command never makes a second logical release; serialized cutover cannot overwrite a newer generation. |
| Acceptance | Approved live acceptance deployment reaches observed public URL/health/marker. Stale/expired/revoked commands do not dispatch promotion; failure preserves prior production and preview. Lost successful response is reconciled once. |
| Tests | Same-owner and foreign-owner API tests; CSRF/session expiry/revocation; source/config/base races, success/cancel/restart races, SSRF and forged provider URL, pre/post-cutover failure, DB-unavailable-after-promotion and bounded compensation. |
| Exclusions | Automatic production promotion after a build, independent reviewers/team policy, custom domains, rolling experiments, unrestricted logs or advanced runtime operations. |

### 2C.4 — Deployment and version UI

| Item | Plan |
| --- | --- |
| Scope | Add one compact production release view/inspector and version-linked release history using existing layout/tokens. Owner explicitly reviews exact artifact/config/evidence before Deploy; current preview and production are labeled separately. |
| Likely files/modules | Existing `apps/web/src/features/workspace/{workspace,views,trace}.tsx`, a focused release component, fixed `/api/v1/projects/.../releases` gateway, server/client contracts, receipt recovery, frontend/browser tests. A dedicated Deployments route is optional, not a new control-center redesign. |
| Database/schema | None beyond 2C.1–2C.3. UI never owns domain state in localStorage. |
| API contracts | Generated owned artifact/release list/detail/command routes; extend workspace/session capability projections only when backend release functionality is operational. Old Simulation deployment reads stay labeled. |
| Security | Server-only provider/identity secrets; reject arbitrary upstreams; public URL comes from validated observed provider record. Open production separately; do not weaken preview iframe sandbox or pass factory cookies/tokens. |
| Idempotency/reconciliation | Frozen per-command receipts retain exact artifact/config/bases/key across reload; resolve uncertainty by rereading the same operation. Show Reconciling rather than falsely successful/failed. |
| Acceptance | Owner sees pending/staged/checking/promoting/success/failure/recovery honestly, observed public URL, exact source version, last health time and previous release. Historical inspection changes no pointer. Input/focus survive failure/reload. |
| Tests | Frontend contracts/receipts, unknown/stale responses, duplicate submissions, reload/polling; signed-in browser journey, keyboard/focus, responsive 375/768/1280/1440, accessibility and explicit public-origin isolation. |
| Exclusions | New visual identity, full Runtime/Database/Environment/Domains management, fake rollback buttons, team review/comments and billing. |

### 2C.5 — Incremental modification through 2B and redeploy

| Item | Plan |
| --- | --- |
| Scope | Connect release history to existing request → reviewed change plan → pinned source patch → 2B build/test/repair/verified preview → production artifact → explicit new release. Preserve untouched files and previous release throughout. |
| Likely files/modules | Existing `application/{planning,execution,projects}.py`, release use cases/lineage, workspace change/versions/release UI, existing 2B plus new release acceptance harness. Reuse source compare-and-apply and worker. |
| Database/schema | New requests/candidates/versions use existing 2B records. Release points to the new artifact and previous production release; no source pointer reset, history rewrite or parallel branch model. |
| API contracts | Reuse current request/planning/build endpoints and frozen Brain/version inputs, then 2C artifact/release endpoints. Include production release/base identity in the release review context. |
| Security | Load authorized actual saved source and Brain; never accept a client source path/digest as proof. Updated candidate/config invalidates earlier release approval. No whole-app regeneration or external effects. |
| Idempotency/reconciliation | Separate stable keys for request, planning, build, packaging and release; recovery follows saved IDs without silently resubmitting model or provider work. Recheck source/production bases before each promotion. |
| Acceptance | Release v1 → ask for bounded change → patch v1 preserving unrelated source → verify v2 preview → explicitly redeploy v2 → inspect v1. Failed build/repair/package/deploy leaves v1 (or latest successful production) usable. |
| Tests | Real Docker change/repair/unrelated-file preservation, release/base/config staleness, production marker vs preview marker, reload throughout, artifact expiry-independent history, failed update at each stage. |
| Exclusions | Visual edits, Git connectors, branch/rebase UI, database migration, unrelated integrations. If preview/source head is ahead of production, show both; require owner review of the current 2B head or reject stale context. Do not silently patch the older production base or overwrite current preview to match it. |

### 2C.6 — Failure, reconciliation and recovery acceptance

| Item | Plan |
| --- | --- |
| Scope | Close full cross-runtime/live-provider acceptance, outage/crash/restart/duplicate/cancel/recovery and artifact/metadata restore checks. Record exact release/runtime/provider identities and remaining operational limits. |
| Likely files/modules | `apps/api/tests/releases/`, PostgreSQL persistence tests, release/Docker/browser harness under `scripts/`, documentation/runbook and targeted fixes in the existing milestone modules. |
| Database/schema | Verify additive upgrade with real 2B and historical simulation records; test refusal of destructive downgrade after release history and compatible application recovery. No unrelated schema expansion. |
| API contracts | Finalize safe error/status/replay/reconciliation semantics and client drift; no new broad operational API. |
| Security | Prove release-credential isolation, private/metadata/other-project denial, public cookie separation and foreign-owner rejection; ensure failure evidence is bounded and sanitized. |
| Idempotency/reconciliation | Crash before/after every external dispatch and DB commit; simulate provider success with lost response, inconsistent observation, late worker, rate limits and revoked credentials. Bound polling and restore; ambiguous writes block promotion. |
| Acceptance | Signed-in v1 public release/health → reload → patch existing source → verified v2 preview → redeploy/public health → inspect v1 → failed update retaining v2. Duplicate commands produce one logical release. Restart reconciles the actual public target. Demonstrate restoration to the previous retained package/config without claiming data reversal. No provider mocks stand in for the final observed public URL. |
| Tests | Full backend pytest and strict mypy, frontend tests/typecheck/build, OpenAPI/client drift, populated-2B migration and backup/restore, actual Docker packaging/isolation, controlled provider fault suite and approved disposable live provider/browser acceptance. Save machine-readable results with IDs/digests and clean only disposable resources. |
| Exclusions | Phase 3 commercial launch, billing, teams, connectors, custom domains, visual editing, Outcome Engine and Growth Engine; advanced monitoring and generalized customer data rollback. |

## 5. Founder decisions before implementation

| Decision | Recommendation | Approval needed |
| --- | --- | --- |
| Provider | Evaluate Vercel staged prebuilt first; Render OCI is fallback; Fly only if extra container control is necessary | Choose one after the 2C.0 feasibility gate; no silent default or fallback |
| Production artifact/profile | Durable digest-bound package from unchanged 2B source and separately verified production config; static-first only if the supported app scope is explicitly accepted, otherwise prove full Next output | Approve static vs full Next, target architecture, trusted packaging tooling and artifact storage |
| Provider resources/budget | Platform-owned release account with separate generated-app targets and minimum authority; founder-authorized disposable live test | Approve account/credential scope, region, plan, resource/concurrency ceiling and test spend; credentials supplied via trusted configuration only |
| Public URL/retention | Provider-generated production alias plus unique deployment URL; no custom domains. Immutable record/package retention, current + previous live target during acceptance | Approve stable-URL expectations, provider protection settings, package retention/storage quota and old-URL lifetime |
| Release policy | Explicit owner review/Deploy for every exact artifact/config; no automatic promotion; stale or changed context invalidates approval | Approve single-owner policy and bounded service compensation to restore the previous approved release |
| State/migration scope | Stateless first app; reject generated DB migrations/external irreversible actions; additive factory migration with compatible recovery | Confirm this scope and recovery limits; any data-backed extension needs its own approved design |

These decisions are unresolved, not blockers to writing this plan. Stop after documentation. No Phase 2C implementation, provider provisioning or push is performed by this task.
