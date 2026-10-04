# Phase 2B execution implementation — complete

**Phase 1 M0–M6, Phase 2A and Phase 2B are complete.** The founder's verified completion record identifies `f9c2a69` (Complete Phase 2B trusted execution path), passing Docker containment and end-to-end acceptance, 289 backend regression tests passed with 2 skipped, and passing frontend typecheck/production build. Phase 2C implementation has not started; [PHASE2C_IMPLEMENTATION.md](PHASE2C_IMPLEMENTATION.md) is a proposal only.

The accepted trusted sandbox image is `sha256:bf55945a66450b4d747196aed159eba926ca377b66e41400da70c0a54e3363c0`. It is an exact installed image identity, not a mutable tag, provider deployment ID or portable production artifact digest.

Evidence provenance: Phase 2B completion is recorded at `f9c2a69`. The exact-image Docker acceptance passed containment and the end-to-end journey; the full backend regression passed 289 tests with 2 skipped, and frontend typecheck/build passed. The acceptance report records `live_provider` and `browser_journey` as `not_run`. Earlier Docker-unavailable notes describe the historical implementation session and are not current Phase 2B blockers.

`PHASE2B_FOUNDATION.md` is the historical foundation checkpoint. Its test counts and absent-capability statements describe that earlier commit, not this implementation.

## Implemented behavior

| Area | Implementation | Recorded completion evidence |
| --- | --- | --- |
| Runtime recipe | Exact accepted image above; trusted Next.js/React/TypeScript scaffold and pinned dependency lock/store | Trusted image provisioned; exact-image Docker acceptance passed |
| Isolation adapter | Private worker-owned Docker Engine API, UID/GID 10000, read-only root, network none, private PID/IPC/cgroup/mount/network boundaries, no binds/devices/ports, dropped capabilities, no-new-privileges, bounded memory/swap/CPU/PIDs/tmpfs/time | Docker containment acceptance passed, in addition to policy/transport tests |
| Materialization | Trusted in-container helper copies only scaffold and validated bounded source; no host extraction, model shell, dependency edits or factory environment inheritance | Real Docker materialization, controlled dependency install and dependency/source integrity verification passed |
| Durable jobs | PostgreSQL jobs with a global concurrency lock, fenced expiring leases, stable run identities, atomic command receipts, cancellation, frozen context and actor/session rechecks | PostgreSQL duplicate-worker, cancel, stale, deadline, revoked-session and recovery tests |
| Generation | Authorized persisted Brain, reviewed current plan, request, current source/version and bounded history; existing provider-independent DTOs and OpenAI adapter through provider factory | Real source-generation orchestration passed in the signed-in journey; acceptance uses controlled provider responses, not a claimed paid model invocation |
| Metering | Source and repair reservations share the Phase 2A owner-locked daily/minute ledger; per-run token, attempt and wall-clock budgets; uncertain/failed calls stay charged; actual usage nullable | Budget tests and existing usage suite |
| Verification | Application-owned materialization → offline frozen install with scripts ignored → typecheck → build → explicit generated tests when present → source/dependency/scaffold integrity and runtime health | Real Docker typecheck/build/test and runtime verification passed with persisted evidence |
| Repair | Typecheck/build/test failures supply bounded codes, validated paths and lines; minimal digest/hash-bound patches; max 2 repairs by default, max 3 configurable; no indefinite retry | Observed Docker failure → bounded repair → successful verification passed; exhausted update preserved the last good version |
| Publication | Exact candidate and same-image phase evidence rechecked under owner/session/project locks; immutable version + Brain provenance + scoped preview + current pointers commit together | Atomic publication/rejection and last-good-version tests |
| Preview | Retains the verified build container; Next base path is a scoped random capability. Separate host/process gateway forwards bounded GETs through Docker exec to container loopback, with no generated network or host ports | Verified isolated preview and gateway isolation passed in Docker acceptance |
| Workspace | Real builds from reviewed plans, receipt recovery, cancel/retry, persisted Trace phases, generated file metadata/source inspection, verified iframe descriptors; old simulations remain labeled | Signed-in build/repair/reload/change/failure journey passed; frontend typecheck and production build passed |

The supported recipe is a browser-focused Next.js/React/TypeScript application with local UI state, bundled assets and explicitly generated Node tests. This checkpoint provides no application database, outbound API access, uploads, email, payments or production hosting. The GET-only preview gateway does not support arbitrary API mutations, WebSockets, streaming or service workers. These are explicit supported-stack limits; existing planning recommendations do not provision those resources.

Recipe verification establishes compilation, supplied tests, source integrity and runtime health. It does not automatically certify every natural-language acceptance criterion. User-requested requirements remain requested; model output is never silently marked completed.

## Persistence and recovery

Frozen migrations `0001_phase1` and `0002_phase2a` are unchanged. `0003_phase2b` adds `execution_jobs`, immutable `source_candidates`, immutable `verification_evidence` and `isolated_previews`. Scoped composite foreign keys prevent cross-project job/candidate/evidence/version links. Existing run/event/version checks admit real records alongside simulated records. Deployment records remain simulation-only. The one-active-run constraint remains shared across both modes. Public timestamps serialize in canonical UTC.

Each candidate stores its immutable validated source artifact, lineage, parent digest, file hashes and attempt identity in PostgreSQL. A successful real version refers to that candidate through its isolated preview record and source digest. Build output remains in the verified ephemeral container; this is not a portable production artifact store or a Phase 2C release mechanism.

External container identity is committed before creation. Cleanup success clears that identity; unavailable cleanup leaves it persisted for the recovery sweep. Failed/canceled resources count toward worker capacity until cleanup. A project cannot begin another build while its failed sandbox awaits cleanup. Leases expire after 30 seconds and are renewed during work. Every evidence/candidate write and publication checks the lease token and frozen bases. Stale workers cannot publish.

A restart can reverify already persisted candidate source in a fresh container without repeating a model call; prior evidence remains immutable. An interrupted generation/repair whose provider outcome is unknown fails explicitly and requires an owner retry. Retry requires current reviewed context and creates a linked new run with a stable receipt.

Preview expiry and cleanup are reconciled by the worker. The trusted PID 1 also has a finite lifetime (build budget plus preview TTL), so processes stop even if a worker disappears. If Docker or PostgreSQL is unavailable, teardown cannot be guaranteed immediately: identities are retained, readiness is not falsely asserted, and recovery retries cleanup. Successful publication is reconciled before teardown if the committing caller was interrupted. Run the worker continuously; do not describe recovery as a guarantee during permanent daemon failure.

## Completed local Docker acceptance and repeatability

No image tag or placeholder is accepted as the execution identity. The accepted image is recorded above. For a deliberate future reprovision, choose and review an exact Docker Official Node 24 Debian base digest, then provision:

```sh
python scripts/provision-sandbox.py --base-image node@sha256:REVIEWED_64_HEX_DIGEST
```

That command builds the committed recipe and writes `.runtime/sandbox-image.json` containing the exact resulting `image_id`. The digest above is intentionally a placeholder, not a provided or verified pin. Never substitute a mutable tag for it.

Use a **disposable** PostgreSQL database named `f01_test_*`; acceptance tests migrate, truncate and clean only that explicitly supplied test database:

```sh
python scripts/run-phase2b-acceptance.py \
  --image-id sha256:bf55945a66450b4d747196aed159eba926ca377b66e41400da70c0a54e3363c0 \
  --database-url postgresql+psycopg://USER@127.0.0.1:5432/f01_test_phase2b \
  --socket /var/run/docker.sock
```

Docker Desktop may use `~/.docker/run/docker.sock`; supply its absolute path if needed. The runner requires a real socket and emits `.runtime/phase2b-acceptance-report.json` plus JUnit evidence. Missing socket exits 2 and reports `not_run`, never passed. The containment scenario must pass before the journey can execute generated code.

Containment probes observe non-root execution, dropped capabilities, no-new-privileges, read-only root, absent factory credentials/socket, loopback-only networking, effective cgroup/tmpfs limits, disk exhaustion, PID exhaustion, CPU throttling, memory OOM enforcement, timeout, cancellation and force cleanup.

The passing second scenario runs real RSA-verified OIDC login/session creation and owned HTTP APIs, the actual OpenAI source adapter with **controlled responses**, and real Docker: create → reviewed plan → generation → observed type error → bounded repair → typecheck/build/generated test → health → isolated preview → reload → change request → source patch preserving layout → reverify → exhausted update retaining the earlier Brain/version/preview. Tests clean recorded runtimes even after assertion failures. Evidence scope is the signed-in API/gateway journey and preview isolation; it does not invent a paid model call, a public production URL or a new comprehensive frontend accessibility certification.

The image's Docker containment and journey have passed. On a runtime with that installed image and its matching passing report, configure the backend/worker:

```dotenv
REAL_EXECUTION_ENABLED=true
EXECUTION_MODE=real
SANDBOX_IMAGE_ID=sha256:bf55945a66450b4d747196aed159eba926ca377b66e41400da70c0a54e3363c0
SANDBOX_ACCEPTANCE_REPORT=/absolute/path/F01-local/.runtime/phase2b-acceptance-report.json
SANDBOX_SOCKET=/absolute/path/to/docker.sock
FACTORY_ORIGIN=http://localhost:3000
PREVIEW_ORIGIN=http://127.0.0.1:3031
SIMULATION_RUNNER_ENABLED=false
```

Keep the frontend's `NEXT_PUBLIC_APP_URL` aligned with `FACTORY_ORIGIN`. Different ports on the same hostname are insufficient because cookies are not port-scoped. Local defaults use `localhost` for the factory and `127.0.0.1` for previews. Nonlocal origins require HTTPS and separately provisioned routing/TLS.

The normal Settings constructor refuses real execution without a passing report for the exact image ID. Acceptance tests use explicit test-only configuration to produce that report; that bypass is not a production setup route.

Apply migrations and run separate trusted processes:

```sh
cd apps/api
uv run --locked alembic upgrade head
uv run --locked uvicorn f01.main:app --host 127.0.0.1 --port 8000
# Another terminal, same backend configuration:
uv run --locked python -m f01.execution.worker
# Another terminal, separate preview cookie host:
uv run --locked uvicorn f01.execution.preview_gateway:app --host 127.0.0.1 --port 3031
```

The API process does not open or operate the Docker socket. The worker/gateway require private Docker access; do not expose Engine APIs to the browser or generated code. Docker Desktop/resource provisioning and worker supervision remain operator responsibilities.

## Completion record — supplied local verification at f9c2a69

| Check | Result |
| --- | --- |
| Exact trusted sandbox image | Provisioned; identity recorded above |
| Docker containment acceptance | Passed |
| Docker signed-in generation/build/repair/preview/reload/change/failed-update journey | Passed |
| Dependency integrity and preview gateway isolation | Passed in Docker acceptance |
| Full backend regression | 289 passed, 2 skipped |
| Frontend typecheck | Passed |
| Frontend production build | Passed |

The two skips belong to the ordinary regression invocation; Docker tests passed in the separate opt-in acceptance invocation. Skips are not the evidence for Docker acceptance.

## Historical application checks — earlier implementation session

These checks remain part of the Phase 2B implementation record:

| Check | Result |
| --- | --- |
| Full PostgreSQL 16 backend pytest | 289 passed; 2 explicitly skipped Docker tests; one existing Starlette/httpx deprecation warning |
| Strict mypy | Passed across 71 backend source/test files |
| Frontend tests | 52 passed |
| Generated-client transport tests | 2 passed |
| Frontend and generated-client typecheck | Passed |
| Factory production build | Passed |
| OpenAPI/generated TypeScript drift | Passed |
| Fresh migration, downgrade/upgrade and ORM/schema drift | Passed |
| Upgrade from Phase 2A with existing project/Brain/plan/review records | Passed; identities and workspace retained |
| Docker provisioning/containment/journey in that earlier Work session | Then unavailable; superseded by the passing local completion record above |
| Live paid source provider | Not run |

Phase 2B is closed. Its accepted image/report gate remains an operational safeguard: a different image requires its own containment and journey acceptance. Preview expiry, the supported browser-focused stack and the lack of production release storage remain deliberate limits, not missing Phase 2B acceptance. Phase 2C is documentation/planning only until the founder approves the bounded provider, artifact and release decisions in its implementation plan.
