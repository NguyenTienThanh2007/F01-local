# Commercial v1 continuation — core stabilization checkpoint

Historical checkpoint/proposal. The commercial-v1 implementation, selected Vercel/static profile and final runtime evidence are documented in [COMMERCIAL_V1.md](COMMERCIAL_V1.md). The earlier status and blockers below are preserved as historical records, not the current continuation status.
Date: 2026-10-05. Starting GitHub main: `449b0588e072cda102144c0c629d776049b4f2d2`.
Branch: `codex/f01-commercial-v1`. Main was fetched and independently verified through GitHub before editing. No old patch or chat implementation was applied.

**Milestone 1 is not fully accepted: command/browser stabilization is implemented, but a fresh real-Docker build/repair/preview run is blocked in this execution environment. Commercial v1 is unfinished.** Deployment implementation has not begun and no commercial review PR has been opened.

## Repository audit before changes

The README, product specification, architecture, roadmap, Phase 2B foundation/completion and Phase 2C plan were inspected against their implementation. `UX0_IMPLEMENTATION.md` was absent from starting main.

| Area | State on starting main |
| --- | --- |
| Phase 1 M0–M6 | Implemented: persistent projects, immutable requests/Brain/history, simulated lifecycle, ownership, ETags, idempotency, SSE/polling and workspace UI |
| Phase 2A | Implemented: cryptographically verified OIDC, revocable opaque sessions/CSRF, contextual planning, immutable proposal/review provenance, bounded usage ledger |
| Phase 2B | Implemented: immutable source candidates/evidence, pinned source patches, fenced leased jobs, trusted Docker verification/repair, atomic Brain/version/preview publication, isolated gateway, last-good preservation |
| Recorded Phase 2B acceptance | Main records passing containment and signed-in Docker/API/gateway journey at `f9c2a69`, exact image `sha256:bf55945a66450b4d747196aed159eba926ca377b66e41400da70c0a54e3363c0`. Its report records live provider and comprehensive browser journey as `not_run`; that historical evidence is not a fresh run on this branch |
| UX0 | Not committed. Real-mode creation and Build transport defects were reproduced in new signed-in browser tests |
| Incremental changes | Existing Brain/source/version-aware plan → bounded patch → isolated verification/repair → immutable version/preview pipeline is implemented. Production redeployment is absent |
| Phase 2C | Design only. No selected provider, portable production package, release tables/worker/adapter/promotion API or public URL. Historical `deployment_records` remain simulation-only |
| Commercial hardening | Auth/configuration guards, readiness/migrations, client drift and regression suites already exist. No `.github` CI configuration on starting main. Live identity/provider/deployment acceptance and full operational runbooks remain unfinished |

## Milestone plan and gates

| Order | Incremental scope | Current status |
| --- | --- | --- |
| 1. Core stabilization | Reproduce/fix create → plan → review → build commands/recovery; verify real trusted-Docker build/repair/preview and last-good behavior | Frontend/command fixes implemented; real Docker acceptance blocked |
| 2. UX refinement | Refine the existing routes, state-specific primary actions, technical detail disclosure, F01 identity, responsive/accessibility acceptance | Only copy/action fixes necessary for core correctness are included. Full milestone not started |
| 3. Deployment | Follow existing 2C.0–2C.6 design: prove one provider/package/staging/restore profile; additive release persistence, isolated packaging/credentials, explicit promotion, health, reconciliation and history | Not started; depends on milestone 1 and 2. Existing provider recommendation remains unselected |
| 4. Modify/redeploy | Extend existing incremental source pipeline with verified production artifacts and explicit new releases; retain old preview/live/history on failure | Existing source pipeline preserved; release integration not started |
| 5. Commercial hardening | Production identity/configuration, logs/secrets, migrations/restore, CI/client drift, runbooks and full browser/Docker/provider acceptance | Not completed. Existing protections retained |

No billing, collaboration, connectors, visual editor, custom domains, marketplace, Growth/Outcome Engine or native mobile scope is included.

## Reproduced defects and fixes

1. A real project was committed successfully, but creation rejected `execution_mode=real` and displayed service unavailable. The UI now validates the actual saved-project contract and owned project path for both modes. An unresolved save retains its exact receipt/input/key; navigation happens only after confirmation.
2. Build sent a JSON string without its JSON content type. The strict BFF rejected it with 422. The shared browser transport now supplies the JSON header for string bodies and a bounded 25-second request deadline. The gateway/backend validation remains unchanged.
3. Build could issue duplicate clicks, show no useful pending state, discard an uncertain 409 receipt, or convert a successful command into an error when browser storage failed. A synchronous command guard, safe receipt storage, server-confirmed run response and explicit queued/pending/recovery states address these cases. Unknown outcomes retain the exact key; expired or undated legacy receipts cannot redispatch blindly.
4. Planning storage exceptions could prevent planning or overwrite a successful result. Storage failure now leaves the mounted receipt in memory. A known persisted attempt is recovered by GET, without another planning POST. Unconfirmed expired commands remain visible and cannot silently become new attempts.
5. Fresh real projects were labeled Simulation and described a demonstration preview. Session capabilities and persisted run/version mode now inform the core copy. Review provides a next-step link; build stages/evidence remain available under Details. Queued builds explain that their state is saved and awaiting the worker. Unavailable real execution is explained without enabling it.
6. Invalid preview expiry could pass the frontend URL check. Preview validation now rejects malformed/expired timestamps, unsafe paths, factory cookie hosts, credentials/query/fragment and nonlocal HTTP. The iframe retains `allow-scripts` only and `no-referrer`; expiry triggers a new availability check.

Two older browser suites still expected pre-2B wording (`Latest simulated update…`, `Saved demonstration timeline`). Their selectors now match the already-existing current wording while retaining the lifecycle/history/last-good assertions.

## Architecture and compatibility

No production backend service, database model, frozen migration, API schema, generated client, source-provider contract, sandbox recipe, worker policy or preview gateway was replaced or changed. StartBuild still accepts only the proposal ID; the backend authorizes and freezes its exact current request/Brain/source/version context under the existing transaction rules. Generated code never executes on the host or in the control plane.

The new browser fixture reuses the test RSA OIDC issuer and controlled planning provider. It injects real-mode command reservation into a guarded disposable test app, just as the existing persistence tests do. It starts no execution worker, Docker container or generated application. It cannot create a runtime acceptance report and must not be configured as a production adapter.

Browser storage contains unresolved command receipts only. When storage is blocked, memory recovery works while mounted; reload recovery cannot be promised in that browser environment. Source/versions/evidence remain server-owned. Existing previews have a finite TTL; no permanent public URL or automatic preview restoration is claimed.

## Validation

Initial signed-in tests against unchanged main reproduced both root defects: creation saved but failed navigation; Build reserved zero runs. The backend baseline passed 289 tests with 2 opt-in Docker skips, and the frontend baseline passed 52 tests.

| Check | Result on this checkpoint |
| --- | --- |
| Backend/PostgreSQL regression | 289 passed, 2 Docker tests skipped; migration downgrade/upgrade/drift checks included |
| Strict mypy | Passed, 81 source files including the new test-only fixture |
| Frontend unit tests | 57 passed |
| Generated client transport | 2 passed |
| OpenAPI and generated TypeScript drift | Passed; generated files unchanged |
| TypeScript and production-style frontend build | Passed |
| UX0 real-mode command browser acceptance | 4 scenarios / 5 tests passed, including the parent; lost create/build response, reload/same-key recovery, duplicate clicks, blocked storage, cancellation, uncertain 409 and expiry rejection |
| Phase 1 browser regression | 5 scenarios / 6 tests passed: persisted lifecycle/history/last-good/metadata, long content, ownership, keyboard, 200% reflow, reduced motion, reconnect and four-width WCAG scans |
| Phase 2A signed-in browser regression | 3 scenarios / 4 tests passed: planning/change context, provider failure/cancel/response loss, sign-out and foreign-owner denial |
| Simulation browser regression | 8 scenarios / 9 tests passed: persisted runs/history/replay/polling/cancellation/last-good and preview isolation |
| Standalone planning/homepage browser regression | 13 scenarios / 14 tests passed, including responsive navigation, safe rendering and browser-bundle secret checks |
| New queued-build visual/accessibility review | Screenshots inspected; 375/768/1280/1440px overflow and WCAG A/AA scans passed with zero violations |
| Docker acceptance | Exit 2: `DOCKER_SOCKET_UNAVAILABLE`; containment/journey `not_run` |
| Live provider/public deployment | Not run; no deployment implementation or public URL |

The existing backend warnings concern Starlette/httpx test-client deprecation and a Pydantic field-alias warning. No dependency upgrades were introduced.

Self-review checked the diff for changes to production backend code, migrations, sandbox/worker/preview policy and generated contracts: none. Terminal real execution events refresh the dependent resources, and the frontend selects only a reviewed plan matching the exact current Brain/version IDs. Technical source/evidence details and historical simulation provenance remain available. `git diff --check` passed.

Repeat command browser acceptance after a production build with `pnpm --filter @f01/web test:ux0:e2e` using the guarded fixture's disposable OIDC/API environment. The existing workspace harness supports `apps/api/.venv/bin/python scripts/test-m5.py --ux0`, with provisioned disposable PostgreSQL 16 tooling; `--phase1` and `--phase2a` retain their existing meanings. `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` and `M5_AXE_SCRIPT` can select installed test tooling.

## Blocker and exact remaining scope

This checkpoint is committed locally on the dedicated branch, but branch publication is also blocked. Git HTTPS push failed because this workspace has no GitHub credentials; the connected GitHub tree-write API returned `403 Resource not accessible by integration`. No branch update, main update, merge or PR succeeded. Resume publication with repository write access, preserving the two logical commits and their exact trees.

The current workspace has no Docker/Podman executable, no standard/Desktop Docker socket, no configured remote executor, zero effective Linux capabilities and `NoNewPrivs=1`. Creating a user namespace fails with Operation not permitted. The committed acceptance runner independently reported `DOCKER_SOCKET_UNAVAILABLE` for the recorded accepted image. Installing a client alone would not provide a trusted daemon or image. Running generated code directly on the host would violate the existing execution boundary.

Continue on this branch in a Docker-capable trusted execution environment with the recorded accepted image and its matching acceptance report, or deliberately provision and accept a reviewed new exact image. Run fresh containment and signed-in build/repair/preview/reload/change/failed-update acceptance before completing milestone 1 or starting deployment.

Then complete the full UX milestone, existing 2C release/package/provider/reconciliation/history design, modification-to-production integration and commercial operational hardening. Provider account/least-privilege credentials, durable artifact storage and observed live-provider acceptance will also be needed; supply secrets through trusted runtime configuration. No existing acceptance or current public production state is inferred from documentation or controlled fixtures.
