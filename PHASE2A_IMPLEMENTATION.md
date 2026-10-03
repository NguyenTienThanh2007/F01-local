# Phase 2A implementation checkpoint

Completed 2026-10-02. Phase 1 M0–M6 remains implemented. Phase 2B has not begun.

## Identity architecture

Configured OIDC authorization-code/PKCE integration verifies RS256 JWT signatures, trusted issuer/JWKS, API audience, expiry/issued-at/subject, nonce, azp and optional at_hash. Browser-bound one-use login state and opaque HttpOnly cookies replace development-only identity for OIDC operation. Secure __Host cookies are required for HTTPS; loopback HTTP is local/test only. FastAPI independently verifies the API token, stable issuer/subject mapping and revocable server-side session on domain reads/writes/streams. Next.js forwards credentials only through fixed private endpoints. Browser identity headers never confer ownership.

Sessions retain hashed handles/CSRF/token bindings, encrypted access tokens, absolute/idle expiry and revocation. Sign-in/account/sign-out have actual pending/error/expiry states. Session end while a plan runs prevents publication. Stream checks reauthorize before query, after query and before each event. The explicit development adapter remains compatible in local/private test mode and is forbidden in production.

Six additive tables in frozen migration 0002_phase2a cover identity mapping, login flows, sessions, attempts, proposals and review acknowledgements. The 0001_phase1 migration is byte-identical to M6. An operator CLI verifies a provider token before linking an existing development user's stable UUID. Email is never used to adopt ownership. Scope-bound foreign keys and immutable triggers protect proposal provenance/history. No teams or membership model was added.

## Planning and usage

Project Planning handles original brief and saved change intent. Server context assembly reads the owned current Brain/version, summary/proposed plan, requirements/acceptance, stack/architecture, constraints/questions/decisions and at most five recent requests. UTF-8 excerpts, source labels, selection/truncation and exact bases remain explicit. Credentials stay outside prompts, output and browser bundles. Source availability is false; all execution history remains Simulation.

Strict provider-independent ContextPlan/PlanningResult contracts separate domain intent from OpenAI wire types. Shared planning instructions remain provider-independent. The actual OpenAI adapter uses one bounded strict-schema call with no tools, redirects, automatic retries or stored Responses object, and rejects malformed output, credential echoes, oversized responses and invalid reported usage. Output is rendered as text and never used to invoke tools or execute code.

A project call reserves durable allowance, returns 202 pending, and runs one bounded in-process FastAPI background task. Browser polling reads saved status; immutable successful proposals retain request/Brain/version references, provider/model, context SHA-256/source manifest and separate review state. Review acknowledges a current proposal only. It changes no Brain revision, run, version, preview or lifecycle state.

Per-user PostgreSQL FOR NO KEY UPDATE locking serializes planning transactions without blocking foreign-key key-share checks from existing request writes, including expired replay/cancel contention. It enforces one pending attempt and minute/day request limits. Conservative byte-based input/instruction/schema/overhead/output reservations enforce UTC daily tokens before dispatch. Failed/canceled/unknown attempts remain charged; provider-reported usage stays nullable when absent. This is a usage foundation with no pricing, credits or billing. /v1/plan retains its standalone ProjectPlan contract, using the same durable ledger in OIDC mode; DB-free development draft planning uses a process-local budget.

Frozen input/key receipts persist unknown project planning responses in tab session storage. Replay returns the same attempt without redispatch. Definite rejected commands preserve typed intent and allow a deliberate retry. Stale publication/review rechecks Brain/version, metadata, latest request and request-event sequence. Cancellation/publication share terminal locks; a late result is discarded. On restart, lost pending work is abandoned at its persisted deadline and never automatically resent.

## API additions

- Private BFF POST /v1/auth/start, /callback, /access and /logout.
- GET /v1/session now identifies development/OIDC mode and optional session expiry.
- POST /v1/projects/{id}/planning/attempts requires pinned PlanInput + Idempotency-Key.
- GET /v1/projects/{id}/planning/attempts/{attempt}; POST its /cancel command.
- GET /v1/projects/{id}/planning/proposals; POST /proposals/{proposal}/review.
- GET /v1/planning/usage exposes owner-scoped UTC allowance/reservations.
- AuthenticatedBearer replaces the misleading DevelopmentToken OpenAPI scheme name; the local credential remains compatible. Existing project, simulation and /v1/plan contracts remain available.

Generated OpenAPI/TypeScript contracts and fixed Next.js gateways match these endpoints. README documents local setup, migration/start/test commands, provider configuration, stable-ID linking, limits and deliberate exclusions. Product/architecture/roadmap revision 0.12 records only Phase 2A as newly complete.

## Verification results

| Check | Result |
| --- | --- |
| Full backend pytest with real disposable PostgreSQL 16 | 169 passed |
| Strict mypy: src/f01 tests migrations scripts | 58 files, no issues |
| Frontend unit/contract suite | 48 passed |
| Generated client transport | 2 passed |
| OpenAPI/client drift | Current |
| pnpm typecheck | Passed |
| pnpm build | Passed |
| Build with APP_ENV=production and synthetic OIDC gateway configuration | Passed |
| Phase 2A signed-in browser journey | 3 scenarios / 4 tests passed |
| Phase 1 M6 acceptance | 5 scenarios / 6 tests passed |
| M5 simulation browser regression | 8 scenarios / 9 tests passed |
| M4 workspace browser regression | 8 scenarios / 9 tests passed |
| M3 projects regression | 1 test passed |
| Standalone planning/homepage browser regression | 13 scenarios / 14 tests passed |
| Browser credential/configuration inspection | 65 compiled JS bundles; no private environment-name or synthetic credential hits |

The Phase 2A browser journey uses a test-only cryptographic RSA OIDC issuer and the actual OpenAI adapter with controlled HTTP transport. It covers sign-in → project creation → simulated success → original plan/review → persisted reopen → current-context change plan; provider quota failure; cancel/discard-late-result; lost response/reload/same-key recovery without a second provider call; sign-out; second-owner denial; original owner reopening. Backend checks cover issuer/audience/signature/expiry/nonce/binding, CSRF/revocation, ownership, migrations/scoped immutable proposals, context/UTF-8/provenance, stale publication/review, budgets/concurrent reservations, failure/timeout/response caps, cancellation races, FK-write lock contention and expired replay/cancel ordering, and abandonment/replay.

The Phase 1 regression retains failed-update preview preservation, retry/cancel/restart, ordered Trace, SSE/gap/replay/polling and preview isolation. Responsive overflow and WCAG A/AA axe scans pass at 375/768/1280/1440, alongside Phase 1 keyboard/focus, 200% reflow and reduced-motion checks. Planning screenshots were visually inspected at phone/desktop widths. These are factory implementation tests, never generated-application execution evidence. One upstream Starlette/httpx TestClient deprecation warning remains; no failing or skipped backend tests.

## Deliberate limitations and next gate

No live identity account or paid OpenAI call was configured or verified. Configure and validate a compatible provider before operational use. The adapter supports RS256 JWT API tokens; opaque tokens/other algorithms require another verified adapter. No session refresh, upstream SSO logout, key rotation, multi-provider UI, account deletion/retention jobs, public hosting/operations, billing or team sharing is implemented. Planning work is in-process and restart-abandoned, not a durable execution worker.

Generated application execution/deployment is not yet implemented. Phase 1 remains Simulation: no generated source/file writes, sandbox, real application builds/tests/fixes, fake logs/commits, real preview hosting, external deployment or release URLs. No Redis/Docker, connectors, visual editing or outcome engine was added. Existing curated previews retain opaque-origin allow-scripts isolation.

The identity and proposal boundaries are ready for a separately scoped Phase 2B design. That stage must introduce supported-stack source/artifact lineage, contained execution, actual verification/repair evidence, cancellation/recovery and real preview isolation before running any generated code. No Phase 2B implementation occurred here.

## Exact source inventory against F01-M6.zip

25 added sources (including this report), 43 changed sources, 207 total source/configuration/document files. No source files were deleted. Historical checkpoints are preserved. Generated build/dependency/runtime/database/cache files and all private environment files are excluded from the checkpoint.

### Added

- `PHASE2A_IMPLEMENTATION.md`
- `apps/api/migrations/versions/0002_phase2a.py`
- `apps/api/scripts/link_identity.py`
- `apps/api/src/f01/api/v1/auth.py`
- `apps/api/src/f01/api/v1/context_plans.py`
- `apps/api/src/f01/application/identity.py`
- `apps/api/src/f01/application/planning.py`
- `apps/api/src/f01/application/usage.py`
- `apps/api/src/f01/domain/context_planning.py`
- `apps/api/src/f01/providers/prompts.py`
- `apps/api/tests/persistence/test_phase2a.py`
- `apps/api/tests/phase2a_browser_fixture.py`
- `apps/api/tests/test_context_provider.py`
- `apps/web/src/app/(product)/projects/[projectId]/planning/page.tsx`
- `apps/web/src/app/api/auth/callback/route.ts`
- `apps/web/src/app/api/auth/sign-in/route.ts`
- `apps/web/src/app/api/auth/sign-out/route.ts`
- `apps/web/src/app/api/v1/planning/usage/route.ts`
- `apps/web/src/app/api/v1/projects/[projectId]/planning/[...segments]/route.ts`
- `apps/web/src/features/workspace/planning.tsx`
- `apps/web/src/lib/auth/routes.ts`
- `apps/web/src/lib/auth/session.ts`
- `apps/web/src/lib/workspace/planning-server.ts`
- `apps/web/tests/auth.test.mjs`
- `apps/web/tests/phase2a.e2e.test.mjs`

### Changed

- `.env.example`
- `ARCHITECTURE.md`
- `PRODUCT_SPEC.md`
- `README.md`
- `ROADMAP.md`
- `apps/api/.env.example`
- `apps/api/pyproject.toml`
- `apps/api/src/f01/api/dependencies.py`
- `apps/api/src/f01/api/errors.py`
- `apps/api/src/f01/api/stream.py`
- `apps/api/src/f01/api/v1/plan.py`
- `apps/api/src/f01/api/v1/projects.py`
- `apps/api/src/f01/config.py`
- `apps/api/src/f01/db/models.py`
- `apps/api/src/f01/domain/projects.py`
- `apps/api/src/f01/main.py`
- `apps/api/src/f01/providers/base.py`
- `apps/api/src/f01/providers/factory.py`
- `apps/api/src/f01/providers/openai.py`
- `apps/api/tests/persistence/conftest.py`
- `apps/api/tests/persistence/test_projects.py`
- `apps/api/tests/test_plan.py`
- `apps/api/uv.lock`
- `apps/web/package.json`
- `apps/web/src/app/(auth)/sign-in/page.tsx`
- `apps/web/src/app/(product)/account/page.tsx`
- `apps/web/src/app/(product)/layout.tsx`
- `apps/web/src/app/page.tsx`
- `apps/web/src/components/shell/product-shell.tsx`
- `apps/web/src/features/projects/project-dashboard.tsx`
- `apps/web/src/features/workspace/workspace.tsx`
- `apps/web/src/lib/config/environment.mjs`
- `apps/web/src/lib/config/root-environment.mjs`
- `apps/web/src/lib/planning/server.ts`
- `apps/web/src/lib/projects/contracts.ts`
- `apps/web/src/lib/projects/server.ts`
- `apps/web/src/lib/workspace/run-server.ts`
- `apps/web/src/lib/workspace/server.ts`
- `apps/web/src/styles/workspace.css`
- `packages/api-client/openapi.json`
- `packages/api-client/src/schema.ts`
- `packages/api-client/src/server.ts`
- `scripts/test-m5.py`
