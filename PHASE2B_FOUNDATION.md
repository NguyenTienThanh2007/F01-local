# Phase 2B foundation — blocked before real execution

Phase 2B is **not complete or stable**. Phase 2A remains the latest completed stage. Phase 2C has not begun. This checkpoint adds independent, inactive contracts without exposing a misleading real-build action or running generated code on the factory host.

## Implemented foundation

| Area | Implemented | Not implemented |
| --- | --- | --- |
| Source boundary | Provider-independent strict frozen DTOs; typed Brain/approved-plan JSON validation; bounded requirements/design/history/repair context; same-project source context | Authorized persisted context assembly for a real run; live source-provider call |
| Patches | Exact base digest and prior-file hashes; minimal edit merge; untouched content preserved; required entrypoints protected; no-op/conflicting input rejected | Persisted candidates; review/build command integration |
| Artifact values | Deterministic sorted manifest/digest with request/Brain/plan/project/base-version lineage; exact UTF-8 content; deterministic in-memory tar; safe archive inspection | Artifact storage, source downloads, source/version tables and atomic publication |
| Provider adapter | One bounded strict Responses request; no tools/redirects/automatic retries; deadline/response/output caps; sanitized errors; nullable actual reported token usage | Ledger reservation/metering for generation/repair; operational repair orchestration |
| Sandbox boundary | Application-owned argv/deadlines; proposed bounded Docker policy; read-only daemon/image prerequisite probe; execution always disabled | Container creation, materialization, build/typecheck/tests, timeout/cancel cleanup or verified containment |
| Existing product | Phase 1 simulations and completed Phase 2A behavior preserved | Real Build Trace, worker/jobs/recovery, real Brain provenance/publication or real preview |

Generated editable files are limited to app/components/lib/styles/public text sources and explicit tests/*.test.mjs files. Absolute paths, traversal, backslashes, Windows/UNC paths, hidden files, reserved names, unsafe components, unsupported extensions and protected package/lock files are rejected. Each file is at most 64 KiB UTF-8, each proposal at most 32 edits, and each snapshot at most 128 files/512 KiB. Context is at most 128 KiB total; existing snapshots too large for that bound require a future relevant-file selection strategy rather than silent truncation. Proposals cannot alter manifests, scripts, dependencies, build configuration or factory credentials. The archive inspector rejects links, devices, PAX overrides, duplicate/case-colliding names, oversized/truncated content and missing entrypoints; it never extracts to the host.

The provider adapter is not connected to endpoints, background tasks, configuration switches or UI. Its context DTO is not an authorization grant or persisted plan approval. The future orchestrator must authorize the owner and compare current request/Brain/version/plan/source bases inside its transaction before calling or publishing. Secret checks reject the configured provider credential and explicitly supplied forbidden values; they are not a universal secret detector. No raw response transcript becomes Brain state.

The proposed sandbox uses a pinned image ID, UID/GID 10000, read-only root, capabilities dropped, no-new-privileges, private namespaces, network none, no host mounts/devices/ports, fresh explicitly selected environment, 2 CPUs, 2 GiB memory with no extra swap, 128 PIDs, and bounded 1 GiB workspace/128 MiB temporary tmpfs. The policy is configurable only within smaller bounded values. Install argv is offline, frozen and ignores package scripts; typecheck/build use fixed trusted-image tool paths and tests use explicit validated paths. There is **no image, trusted scaffold/dependency catalog or executor provisioned**, so none of these commands has executed against generated source. A policy specification and mocked Engine tests do not prove resource enforcement or sandbox-breakout resistance.

## Observed environment blocker

The current workspace has no Docker/Podman/runc executable, no Docker/Podman socket and no configured remote executor. Effective Linux capabilities are zero. User/mount namespace creation fails with Operation not permitted; bubblewrap cannot create the isolated network namespace. A trusted runtime download probe timed out. Executing generated code directly on the host would violate ARCHITECTURE.md and the Phase 2B request.

A read-only prerequisite command is included. Run it from apps/api against an operator-provisioned private worker Docker socket and exact installed image ID:

```sh
uv run --locked python scripts/check_sandbox.py --socket /var/run/docker.sock --image-id sha256:YOUR_64_HEX_IMAGE_ID
```

The image ID above is a placeholder, not a provided image. The probe validates the ID, checks Linux/cgroup-v2/seccomp/resource prerequisites and image metadata. It does not pull or start an image, read application secrets, or run generated source. Exit 0 means prerequisites_present, **not execution readiness**; execution_enabled remains false. In this workspace the probe returns SANDBOX_SOCKET_UNAVAILABLE with exit 1.

## Required work before Phase 2B acceptance

In a Docker-capable execution environment, provision and pin a trusted Next/React/TypeScript scaffold/image and dependency lock/store; implement and demonstrate actual containment, resource/time limits, safe evidence handling, cancellation and cleanup. Add additive persisted source/candidate/evidence/job/preview identities, durable leased orchestration with bounded concurrency and recovery, stale input checks, deduplication and atomic publication. Integrate generation and bounded issue-to-patch repair with the Phase 2A usage ledger. Preserve old Simulation records and current successful pointers on failed updates.

Implement the isolated preview runtime/origin and lifecycle without exposing factory cookies, credentials, control-plane/metadata access or other projects. Integrate real workspace states, real evidence Trace, source/version inspection and immutable generated/verified Brain provenance. Then run the requested real sign-in → generation → controlled failure → bounded repair → successful preview → reload → change patch → failed update preservation journey, plus containment/worker/preview tests and responsive acceptance. None of that journey is represented by the contract tests below.

## Verification for this partial checkpoint

Available checks passed: full PostgreSQL-backed backend suite **265 tests**, including **96 new source/provider/sandbox-policy contract tests**; strict mypy **68 files**; full frontend **48 tests**; generated-client **2 tests**; OpenAPI/client drift; pnpm typecheck; pnpm build. Migration drift reported no upgrade operations. The final backend run has one existing Starlette/httpx test-client deprecation warning.

The signed-in Phase 2A browser regression passed **3 scenarios / 4 tests including parent**, with responsive/WCAG scans at 375/768/1280/1440 pixels. Phase 1 acceptance passed **5 scenarios / 6 tests including parent**, covering the persisted lifecycle, long content, keyboard/focus, 200% reflow, reduced motion, reconnect/history recovery and ownership denial. No project test/runtime processes remained after cleanup. These exercise the factory and Phase 2A, never generated-application execution. Real sandbox lifecycle, build/test/repair, durable-job recovery, real artifact/version publication and preview isolation acceptance remain **not run / not implemented**. The checkpoint QA report includes the exact source inventory and selected screenshots.

No public production URL, production deployment, billing, teams, connectors, mobile generation, visual editing or outcome engine is added. This checkpoint is not ready for Phase 2C.
