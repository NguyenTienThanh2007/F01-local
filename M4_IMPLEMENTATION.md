# M4 — persisted workspace and preview foundation

Status: implemented and verified; stopped before M5. Date: 2026-10-02.

## Result

`/projects/[projectId]` now reads the real persisted workspace snapshot and presents a preview-first canvas. Its shared layout retains the project title, lifecycle/Pulse, simulation/queued/selected-version labels, project navigation, inspector selection, request draft/history scroll and viewport state across project subroutes and responsive changes. Settings retains M3 rename/archive behavior. Original brief, Brain, Activity, Versions and Settings have distinct navigable surfaces with loading/error/retry states; unavailable/missing/foreign resources have safe outcomes.

Brain renders every schema-v1 section with stable entry IDs, proposed/requested/simulated status, source labels/references, immutable revision metadata and revision pagination/selection. Current canonical requests, issues, versions and deployments remain separate from the selected revision’s frozen history references. Historical inspection never moves current pointers. User-entered HTML-like text remains text; unsupported schemas produce an explicit safe error without rewriting content.

Original brief/history retain author, time, request ID and frozen Brain/version context. Eligible new requests save only immutable intent and an attributed `request.recorded` event. The server reserves/replays an identity-and-route-scoped 24-hour idempotency receipt, locks current project context, and rejects archived projects, active runs and stale Brain/version bases. Failures roll back atomically. Browser retries retain the exact submitted text, bases and key, including across reload; uncertain outcomes lock the command. Definite stale conflicts preserve text and require explicit current-context review. Saving never edits the original request or Brain, generates a revision/version, or starts a run.

Added four backend boundaries: `POST /v1/projects/{id}/requests`, `GET /v1/projects/{id}/events`, `GET /v1/projects/{id}/versions`, and `GET /v1/projects/{id}/versions/{versionId}`. Events read canonical server-sequence history; versions expose persisted metadata/descriptors. Fixed same-origin server-only gateways use the regenerated OpenAPI client for these and the existing workspace/Brain/request reads. No arbitrary proxy path/URL, identity header forwarding, browser credential, stream or run command was added. The M2 tables, frozen migration, original creation service, ownership/configuration boundary, metadata ETags and existing planning integration are preserved.

No completed version means **Preview pending**, with no project iframe. Separate `/development/previews` showcases independent CRM and generic synthetic examples. Allowlisted `/demo-preview` handlers return complete HTML outside factory React layouts/hydration, with bundled CSS/classic-script assets. Both response CSP and iframe restrict sandbox to `allow-scripts`; same-origin, top navigation, popups and download grants are absent. Connections/forms, frames, objects and base changes are prohibited; only the factory can frame these responses. The fixtures have no factory API/storage/cookie access and receive no raw brief HTML or arbitrary URL. Browser checks verified assets and interactions work under this boundary. Stored fixture version descriptors can be inspected without changing current Brain/version or implying rollback.

Build Trace is a non-executing foundation linking to Activity; Run details show saved attempt/context only. Files, Logs, Deployment and Runtime explain their unavailable capabilities without invented files, logs, progress, test evidence or deployment URLs. Typography, color tokens, global rail, editorial layout and Project Pulse remain consistent with the redesigned frontend. No dependency was added.

## Verification completed

| Check | Result |
| --- | --- |
| `pnpm typecheck` | Passed, generated client and frontend |
| `pnpm test:web` | 36 passed |
| `pnpm build` | Passed on pinned Next.js 16.3.8 |
| PostgreSQL/backend: `tests/persistence tests/test_plan.py` | 105 passed; clean migration upgrade/downgrade/upgrade and ORM drift checked by fixture |
| strict mypy: `src/f01 tests migrations scripts` | Passed across 40 files |
| `pnpm api:check` | OpenAPI and generated TypeScript current |
| `pnpm test:client` | 2 transport tests passed |
| real PostgreSQL/FastAPI M4 browser journey | 8 scenarios passed (9 tests including parent) |
| M3 persisted project regression journey | Passed; settings assertions updated for the M4 Settings subroute |
| planning/homepage browser regressions | 13 scenarios passed (14 tests including parent) |
| responsive/accessibility | Preview, Brief, Brain, Activity, Versions, Settings at 375/768/1280/1440px: no page overflow; tested WCAG A/AA axe scans clear |
| browser preview restrictions | Parent DOM, storage, cookies, factory requests, forms, top navigation and popups blocked; both sample assets/interactions worked |
| browser persistence/context | Same-key lost-response recovery/reload, preserved drafts, stale Brain and version review, immutable revision/historical-version inspection, mobile focus and resize persistence passed |

Factory verification uses synthetic credentials, controlled planning responses and disposable real PostgreSQL storage. No live model call occurred; these tests do not assert generated-app builds/tests/fixes/deployment. Verification ran on Linux; macOS was not executed.

## Deliberate limits

M4 adds no M5 runner, scheduled progression, run start/cancel/retry commands, SSE/polling execution or Build Trace reducer. New M2 projects still queue active runs, so the architecture blocks new changes and archiving until those runs end. Disposable test setup ends runs/inserts historical or fixture output records solely to verify eligible paths; there is no corresponding product simulation command.

No real generation/build/fix, Docker/Redis, live preview hosting/deployment, production identity, billing, teams, connectors, visual editing or outcome engine was implemented. Domain records remain server-owned; tab session storage contains only unresolved command receipts. The source tree has no Git metadata; no commit or deployment was made.

## Exact source changes relative to the M3 handoff

### Modified existing files

- `ARCHITECTURE.md`
- `PRODUCT_SPEC.md`
- `README.md`
- `ROADMAP.md`
- `apps/api/src/f01/api/errors.py`
- `apps/api/src/f01/api/v1/projects.py`
- `apps/api/src/f01/application/projects.py`
- `apps/api/src/f01/domain/projects.py`
- `apps/web/package.json`
- `apps/web/src/app/(product)/projects/[projectId]/page.tsx`
- `apps/web/src/app/layout.tsx`
- `apps/web/src/components/ui/sheet.tsx`
- `apps/web/src/lib/projects/contracts.ts`
- `apps/web/src/lib/projects/server.ts`
- `apps/web/tests/projects.e2e.test.mjs`
- `packages/api-client/openapi.json`
- `packages/api-client/src/schema.ts`
- `packages/api-client/tests/contracts.ts`

### Added files

- `apps/api/tests/browser_fixture.py`
- `apps/api/tests/persistence/test_m4.py`
- `apps/web/src/app/(preview)/demo-preview/[fixtureId]/route.ts`
- `apps/web/src/app/(preview)/demo-preview/assets/[asset]/route.ts`
- `apps/web/src/app/(product)/development/previews/page.tsx`
- `apps/web/src/app/(product)/projects/[projectId]/activity/page.tsx`
- `apps/web/src/app/(product)/projects/[projectId]/brain/page.tsx`
- `apps/web/src/app/(product)/projects/[projectId]/brief/page.tsx`
- `apps/web/src/app/(product)/projects/[projectId]/error.tsx`
- `apps/web/src/app/(product)/projects/[projectId]/layout.tsx`
- `apps/web/src/app/(product)/projects/[projectId]/loading.tsx`
- `apps/web/src/app/(product)/projects/[projectId]/settings/page.tsx`
- `apps/web/src/app/(product)/projects/[projectId]/versions/page.tsx`
- `apps/web/src/app/api/v1/projects/[projectId]/brain/revisions/route.ts`
- `apps/web/src/app/api/v1/projects/[projectId]/brain/route.ts`
- `apps/web/src/app/api/v1/projects/[projectId]/events/route.ts`
- `apps/web/src/app/api/v1/projects/[projectId]/requests/route.ts`
- `apps/web/src/app/api/v1/projects/[projectId]/versions/[versionId]/route.ts`
- `apps/web/src/app/api/v1/projects/[projectId]/versions/route.ts`
- `apps/web/src/app/api/v1/projects/[projectId]/workspace/route.ts`
- `apps/web/src/features/workspace/preview.tsx`
- `apps/web/src/features/workspace/requests.tsx`
- `apps/web/src/features/workspace/views.tsx`
- `apps/web/src/features/workspace/workspace.tsx`
- `apps/web/src/fixtures/previews/fixtures.ts`
- `apps/web/src/lib/workspace/contracts.ts`
- `apps/web/src/lib/workspace/server.ts`
- `apps/web/src/styles/workspace.css`
- `apps/web/tests/workspace.e2e.test.mjs`
- `apps/web/tests/workspace.test.mjs`
- `scripts/test-m4.py`
- `M4_IMPLEMENTATION.md`

### Removed unused M3 component

- `apps/web/src/features/projects/project-record.tsx`

