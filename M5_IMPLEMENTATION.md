# M5 — persistent simulation runner and Build Trace

Status: implemented and verified; stopped before M6. Date: 2026-10-02.

## Runner behavior

The FastAPI lifespan owns a due-step loop over persisted queued/running attempts. Version-1 immutable fixture definitions cover CRM success, generic success, recoverable verification and terminal update failure. Each step uses the saved scenario/version, input request, Brain/version bases and cursor; reads never advance runs. Short PostgreSQL transactions lock the project before its run, recheck due time/status/context, append deduplicated events with monotonically increasing project sequence and persist cursor, heartbeat and next due time. A restart resumes those records, including queued M4 attempts. Missing scenario versions or invalid persisted contexts publish explicit failure events.

Project creation schedules its initial simulation. Start accepts only a saved request and expected Brain revision; fixture selection is server-owned. Retry creates a new linked attempt with unchanged original inputs and chooses a deterministic success fixture. Cancel terminates eligible queued/running attempts. Project ownership, archive/active-run rules and stale Brain/version checks apply. Start/retry have scoped 24-hour idempotency receipts; cancellation is inherently idempotent. The shared lock order ensures cancel and success produce exactly one terminal result.

No new tables, migrations, dependencies, Docker, Redis or worker service were added. The local/private always-running API process must remain running for due steps to progress; this is not a production worker or request-only serverless execution system.

## Build Trace and workspace

Project Pulse reflects authoritative run status and phase. The utility inspector now shows Understanding, Planning, Building, Verifying, Deploying, and Live / Needs attention. Events stay in project-sequence order and consecutive phase groups; a repair can return to Building and then Verifying without reordering history. Recorded fixture issues link to their corresponding repairs by stable issue identifiers.

Trace follows the latest event while enabled. Scrolling away or Pause stops follow; unread events accumulate and Jump to latest resumes it. The bounded inspector scroller responds to viewport size changes. Run details include attempt, scenario/version, timings, cursor, immutable input context, retry relationship and errors, plus valid retry/cancel controls. Historic run selection is inspection only.

M4 Requests can save intent alone or start an optional demonstration after saving through a separate command. A failed start preserves the saved request. Frozen unresolved run commands and their keys survive reload in tab session storage; a lost response is resolved with the same command. Definite stale conflicts preserve the draft/request and require reviewed current-context intent, rather than silently rebasing. Original brief and prior Brain revisions remain immutable.

## SSE, polling and replay

The backend streams persisted events with SSE event IDs equal to project sequence. Replay honors a validated Last-Event-ID ahead of the query cursor. Fixed same-origin frontend gateways forward unbuffered bytes without exposing private credentials or accepting arbitrary proxy destinations.

The frontend initializes from the consistent workspace watermark, fills prior history, deduplicates replay and holds later events until sequence gaps are backfilled. Missing EventSource or interrupted streaming enables three-second polling; bounded reconnect backoff restores SSE using the recovered contiguous cursor. Polling and streams read persisted state only. Transport health is separate from project lifecycle. Expired/revoked credentials close the stream and stop recovery with a session message. Authentication, ownership, malformed/future cursor and expired-session paths were tested.

## Atomic publication, versions and recovery

Success publishes the terminal events, successful attempt, immutable Brain revision, numbered version, internal-fixture simulated deployment and current Brain/version pointers in one PostgreSQL transaction. The output Brain preserves stable existing entries and original-request linkage, adds saved change intent with requested/provenance labels, and freezes canonical history references. It does not assert that arbitrary requested changes were implemented.

Failure publishes Needs attention and its recorded error without creating a version, Brain revision or deployment, or changing the last successful pointers. Cancellation likewise creates no successful output. Duplicate/concurrent final steps cannot publish twice. Injected transaction failure rolls back the whole publication, and a new runner resumes from the saved cursor.

Versions and historical Brain/run details are read-only inspections. Historical preview selection uses the stored allowlisted fixture descriptor without changing the project’s current version. Failed or canceled updates retain the last successful preview. Synthetic CRM/generic samples can remain visually unchanged despite successful simulation.

## Honest simulation and preserved foundations

Fixture execution, events, issues, repairs, versions and deployment records are explicitly Simulation. The deployment has an internal fixture target and no external deployment URL. Files, terminal logs and application runtime remain honest unavailable placeholders. The implementation produces no real source files, builds, application tests/fixes, commits, hosted preview or external deployment, and contains no fabricated terminal output or execution test counts.

M2 persistence and frozen migration, M3 dashboard/creation/settings, M4 Brain/request/history/navigation, existing /v1/plan integration, and the redesigned visual identity are preserved. Preview HTML/assets and allow-scripts-only opaque-origin sandbox/CSP are unchanged. Browser isolation checks cover parent access, credentials/storage, factory connections and navigation. No M6 or later capability was implemented.

## Verification completed

| Check | Result |
| --- | --- |
| pnpm typecheck | Passed |
| pnpm test:web | 43 passed |
| pnpm build | Passed on pinned Next.js 16.3.8 |
| Backend: tests/persistence tests/test_plan.py tests/test_config.py tests/test_lifecycle.py | 130 passed on disposable PostgreSQL 16; clean upgrade/downgrade/upgrade and schema drift checks |
| Strict mypy: src/f01 tests migrations scripts | Passed across 46 files |
| pnpm api:check | OpenAPI and generated TypeScript client current |
| pnpm test:client | 2 passed |
| M5 PostgreSQL/API/production browser suite | 8 scenarios passed (9 tests including parent) |
| M4 workspace browser regression | 8 scenarios passed (9 tests including parent) |
| M3 persisted project browser regression | 1 journey passed |
| Planning/homepage production browser regression | 13 scenarios passed (14 tests including parent) |
| Responsive/accessibility | Trace/run details at 375, 768, 1280, 1440px; no page overflow; tested WCAG A/AA axe scans clear |
| Trace and preview inspection | Follow/pause/unread/jump, followed event within viewport, issue → repair links, isolation and historical selection passed |

Controlled-clock backend cases verify all four fixtures, due-time enforcement, duplicate/concurrent progression, atomic rollback/publication, cursor restart, replay, five success/cancel races, canceled queued/running attempts, stale retry/input conflicts, idempotency, ownership, unknown scenario versions, stream expiry/replay/cursor validation, read-only polling and actual lifespan restart recovery.

The M5 browser journey creates a project → simulated success → saves a change → simulated failed update → retries through a lost-response/reload → simulated success. Additional scenarios verify historical pointers, repair relationships, sequence gaps/duplicates, unavailable and terminated streams, polling/reconnect, active cancellation, stale draft review, multi-tab/reload consistency, follow behavior and responsive isolation. M3/M4 harnesses pause the runner to retain their original checkpoint expectations.

These are tests of the factory implementation using synthetic credentials and disposable PostgreSQL. No live model call or generated-application execution occurred. Linux was verified; macOS was not executed.

## Configuration and running

The runner defaults to enabled. SIMULATION_TICK_MS defaults to 1000 and accepts 100–10000ms; SIMULATION_RUNNER_ENABLED=false pauses dispatch. SIMULATION_CHANGE_SCENARIO=auto selects normal fixtures. Development/test-only terminal-failure and recoverable-verification settings select change-run demonstrations; they are rejected in private-preview configuration and are not public API fields. Retry uses a deterministic success fixture. Optional DEV_TOKEN_EXPIRES_AT must be an explicit timezone-aware timestamp or remain unset.

Start/cancel/retry routes are POST /v1/projects/{id}/runs, POST /v1/projects/{id}/runs/{runId}/cancel and POST /v1/projects/{id}/runs/{runId}/retry. Run list/details, simulated deployment records and GET /v1/projects/{id}/events/stream supply inspector data. Existing event polling now permits an optional owned run filter.

After pnpm build, the provisioned workspace harness is apps/api/.venv/bin/python scripts/test-m5.py. On another machine, supply an empty migrated disposable f01_test_* database and development/test API with the documented simulation configuration, then set M5_API_URL, M5_TEST_DATABASE_URL and M5_TEST_TOKEN and run pnpm --filter @f01/web test:simulation:e2e. The README contains setup, backend test and other regression commands.

## Handoff

F01-M5.zip contains the source under F01-local, this report and selected M5 responsive screenshots. It excludes installed dependencies, build/runtime caches, local secrets, databases and earlier ZIP checkpoints. M4 remains a separate checkpoint. No commit or deployment was made; the source tree has no Git metadata.

## Exact source changes relative to F01-M4.zip


### Modified existing files (29)

- `.env.example`
- `ARCHITECTURE.md`
- `PRODUCT_SPEC.md`
- `README.md`
- `ROADMAP.md`
- `apps/api/src/f01/api/dependencies.py`
- `apps/api/src/f01/api/errors.py`
- `apps/api/src/f01/api/v1/projects.py`
- `apps/api/src/f01/application/projects.py`
- `apps/api/src/f01/config.py`
- `apps/api/src/f01/domain/brain.py`
- `apps/api/src/f01/domain/projects.py`
- `apps/api/src/f01/main.py`
- `apps/api/tests/browser_fixture.py`
- `apps/api/tests/conftest.py`
- `apps/web/package.json`
- `apps/web/src/features/projects/project-creation.tsx`
- `apps/web/src/features/projects/project-dashboard.tsx`
- `apps/web/src/features/workspace/requests.tsx`
- `apps/web/src/features/workspace/views.tsx`
- `apps/web/src/features/workspace/workspace.tsx`
- `apps/web/src/lib/projects/contracts.ts`
- `apps/web/src/lib/workspace/contracts.ts`
- `apps/web/src/lib/workspace/server.ts`
- `apps/web/src/styles/workspace.css`
- `packages/api-client/openapi.json`
- `packages/api-client/src/schema.ts`
- `scripts/test-m3.py`
- `scripts/test-m4.py`

### Added files (22)

- `M5_IMPLEMENTATION.md`
- `apps/api/src/f01/api/stream.py`
- `apps/api/src/f01/application/runs.py`
- `apps/api/src/f01/execution/__init__.py`
- `apps/api/src/f01/execution/runner.py`
- `apps/api/src/f01/execution/scenarios.py`
- `apps/api/tests/persistence/test_m5.py`
- `apps/web/src/app/api/v1/projects/[projectId]/deployments/route.ts`
- `apps/web/src/app/api/v1/projects/[projectId]/events/stream/route.ts`
- `apps/web/src/app/api/v1/projects/[projectId]/runs/[runId]/cancel/route.ts`
- `apps/web/src/app/api/v1/projects/[projectId]/runs/[runId]/retry/route.ts`
- `apps/web/src/app/api/v1/projects/[projectId]/runs/[runId]/route.ts`
- `apps/web/src/app/api/v1/projects/[projectId]/runs/route.ts`
- `apps/web/src/features/workspace/feed.ts`
- `apps/web/src/features/workspace/run-commands.ts`
- `apps/web/src/features/workspace/trace.tsx`
- `apps/web/src/lib/workspace/run-command.ts`
- `apps/web/src/lib/workspace/run-server.ts`
- `apps/web/src/lib/workspace/trace.ts`
- `apps/web/tests/simulation.e2e.test.mjs`
- `apps/web/tests/simulation.test.mjs`
- `scripts/test-m5.py`

No source files were removed. Dependency lockfiles and the frozen M2 database migration are unchanged.
