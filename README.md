# F01 — local project handoff

Commercial-v1 continues the existing branch and implements create → plan/review → trusted Docker build/repair → isolated preview → verified static production package → explicit Vercel deploy/public URL → pinned-source modify/rebuild/preview/redeploy → versions and release history. See [COMMERCIAL_V1.md](COMMERCIAL_V1.md) for the supported profile, runtime setup, recovery and acceptance evidence. Phase 2B protections remain in place. Release support is disabled until exact-image acceptance and private worker configuration are supplied.

The remaining handoff notes below record Phase 1–2B setup and historical checkpoints. Commercial-v1 release instructions and current status are in the document above.

Phase 1 M0–M6, Phase 2A and **Phase 2B are complete**. The verified `f9c2a69` completion includes passing exact-image Docker containment and signed-in build/repair/change/failure acceptance, 289 backend tests passed/2 skipped, and frontend typecheck/build passing. The accepted image and evidence provenance are in [PHASE2B_IMPLEMENTATION.md](PHASE2B_IMPLEMENTATION.md). Real execution remains disabled by default until runtime configuration supplies the installed accepted image and matching report; acceptance is complete. PHASE2B_FOUNDATION.md is historical. [PHASE2C_IMPLEMENTATION.md](PHASE2C_IMPLEMENTATION.md) preserves the original release proposal; its implemented continuation is [COMMERCIAL_V1.md](COMMERCIAL_V1.md).
The ZIP includes the source, dependency lockfiles, environment templates and the
four planning documents. Secrets, installed dependencies and generated builds are
excluded. Dependencies are installed on your Mac, so no Linux virtual environment
or native binaries need to be reused.

## What currently works

- `/`: editorial product entry with a real planning composer, selectable starters,
  Project Pulse and a clearly labeled lifecycle demonstration.
- Redesigned projects workspace, deliberate empty state and starter artifacts.
- Dominant brief composer and document-style structured plans at `/projects/new`.
- Connected OIDC sign-in/account/sign-out with revocable server sessions; explicit local development compatibility.
- Project Pulse state showcase at `/development/design-system`.
- Responsive navigation, loading/error foundations and shared UI primitives.
- FastAPI liveness endpoint at `/v1/health/live` and validated configuration.
- `POST /v1/plan`: a real OpenAI planning adapter behind a provider-independent
  contract, with strict request/response validation and sanitized errors.
- `/projects/new`: submit a brief and review all six structured plan sections,
  with validation, loading, cancel, success, error and retry states.
- `POST /api/v1/plan`: a fixed server-side frontend gateway. The browser receives
  neither the development token nor the backend OpenAI key.
- Reviewed persisted plans drive real source generation and durable leased builds
  in the accepted isolated Docker image, with dependency/typecheck/build/test
  evidence, bounded repairs, source metadata and verified isolated preview.

M3 now connects `/projects` and `/projects/new` to the real M2 APIs through the generated TypeScript client on the server. Create a demo project from an optional title and original brief, reopen it after reload, search/filter it and manage title/archive metadata. `/projects/{id}` is the persisted preview-first workspace with Brief, Brain, Activity, Versions and Settings subroutes, shared header/Pulse and a collapsible inspector/request drawer. The optional **Explore a draft plan** tool preserves the existing real planning behavior and keeps draft results in page memory.

Creation retries retain the same key and submitted input until confirmation. Tab session storage contains only an unresolved command receipt, never a project inventory; after confirmation it is removed. There is no localStorage project database.

Simulation mode retains the deterministic Phase 1 runner and labeled fixture records. Configured real mode saves project intent, then requires a reviewed current plan and a separate real build command. Successful verification atomically publishes source/version/Brain/preview; failed updates and cancellations preserve the prior successful preview. Active runs block conflicting requests/archiving; Run details exposes supported cancel/retry. Real Trace uses persisted command/repair evidence; historical Simulation Trace remains labeled. Phase 1, Phase 2A and Phase 2B are complete. Production deployment, connectors, billing, teams and later capabilities remain deferred.

## 1. Install prerequisites

Install **Node.js 24** using the [official Node.js download page](https://nodejs.org/en/download).
Then install the version of pnpm specified by this project:

```sh
npm install --global pnpm@11.25.0
```

Install [uv](https://docs.astral.sh/uv/getting-started/installation/).
If you already use Homebrew:

```sh
brew install uv
```

The backend commands below select Python 3.12; uv can download that interpreter if
it is missing. Internet access is needed for the initial dependency installation.
These commands work with Apple Silicon and Intel Macs; native dependencies are
selected during installation. Verification for this handoff was performed on
Linux, not macOS.

## 2. Unzip and install

Extract `F01-Phase2A.zip`. It contains one folder named `F01-local`.
In Terminal, enter that folder; adjust the path if you extracted elsewhere:

```sh
cd ~/Downloads/F01-local
pnpm install --frozen-lockfile
cd apps/api
uv sync --locked --python 3.12
uv run --locked python ../../scripts/setup-local.py
```

To update an earlier download in `~/Downloads/F01-local`, stop the servers and
merge the archive's files into that folder. For the exact ZIP name above:

```sh
unzip -o ~/Downloads/F01-Phase2A.zip -d ~/Downloads
```

The archive contains no `.env` files, so it preserves your existing secrets.
Then run `pnpm install --frozen-lockfile` from the project root and restart the
frontend. Run `uv sync --locked` in `apps/api`, configure PostgreSQL, apply
migrations below, and restart the backend.

The setup script creates a project-root `.env` with a random development token,
and `apps/api/.env` containing only `OPENAI_API_KEY=`. Existing files are preserved,
and values are never printed. If you bring your own root `.env`, ensure it includes
`DATABASE_URL` with the `postgresql+psycopg://` scheme and a `DEV_API_TOKEN` of at
least 32 characters. The root template lists the other configuration names.

PostgreSQL is required for persistence. Liveness and development standalone draft planning work independently; OIDC sessions and all project planning require PostgreSQL.
On your Mac, install/start PostgreSQL and create a database (adapt for an existing
installation):

```sh
brew install postgresql@16
brew services start postgresql@16
$(brew --prefix postgresql@16)/bin/createdb f01
```

Set `DATABASE_URL` privately in your root `.env` to your local connection URL,
for example `postgresql+psycopg://localhost/f01`. From `apps/api`:

```sh
uv run --locked alembic upgrade head
uv run --locked alembic check
```

Startup never applies migrations automatically. `/v1/health/ready` checks database
access and migration compatibility.

## 3. Start the backend

From `F01-local/apps/api` in the same Terminal window:

```sh
uv run --locked uvicorn f01.main:app --reload --host 127.0.0.1 --port 8000
```

Check [http://127.0.0.1:8000/v1/health/live](http://127.0.0.1:8000/v1/health/live).
It should return `{"status":"alive"}`. API documentation is at
[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

## 4. Start the frontend

Open a second Terminal window:

```sh
cd ~/Downloads/F01-local
pnpm dev
```

Open [http://127.0.0.1:3000](http://127.0.0.1:3000) for the redesigned entry surface.
Its **Create plan** action uses the same real planning integration as `/projects/new`.
Stop either server with Control-C in its Terminal window.

Next.js loads the shared project-root `.env` through a web-only allowlist:
`APP_ENV`, `AUTH_MODE`, `EXECUTION_MODE`, `API_INTERNAL_URL`, `DEV_API_TOKEN`, `AUTH_GATEWAY_TOKEN`, and
`NEXT_PUBLIC_APP_URL`. It never reads `apps/api/.env`. Existing process or
`apps/web/.env*` values take precedence. Keep `API_INTERNAL_URL` pointing to the
backend origin (normally `http://127.0.0.1:8000`) and use the same private
`DEV_API_TOKEN` as the backend. Do not put either credential in a `NEXT_PUBLIC_`
variable. Restart the frontend after changing shared configuration.

Open [http://127.0.0.1:3000/projects/new](http://127.0.0.1:3000/projects/new),
use **Create demo project** to save an original brief and queue a Simulation.
For optional real planning, select **Explore a draft plan**, then **Create plan**.
With a configured planning provider, it returns title, summary, target users,
features, stack and milestones. This planning action saves no project and starts no build. Retry is manual and makes another provider request.
Cancel stops waiting for the result but cannot guarantee cancellation of an
already-started provider request or charge.

## 5. Configure OpenAI planning locally

An OpenAI key is optional for the shell and health endpoint, and required for
`POST /v1/plan`. No OpenAI request happens automatically when the server starts.

The exact key file, with the default extraction location above, is:

```text
~/Downloads/F01-local/apps/api/.env
```

From the project root, open it with your preferred code editor, or with TextEdit:

```sh
open -e apps/api/.env
```

Keep it as plain text with the exact filename `.env`. Paste the key privately
after `OPENAI_API_KEY=` and save. Never put it in frontend files, a `NEXT_PUBLIC_`
variable, or chat. `.env` files are ignored by git; `.env.example` templates are
included with blank secret values. Your local edits affect your Mac's copy only.

Backend settings load the project-root `.env` first, then `apps/api/.env`, using
paths resolved from the backend source location. Process environment variables
take precedence. Settings are cached in the process: stop and restart the backend
after changing environment files. Do not rely on source reload to reload `.env`.

The model defaults to `gpt-4.1-mini`. Optional backend environment settings are
`OPENAI_MODEL`, `PLANNING_PROVIDER=openai`, and `PLANNING_TIMEOUT_SECONDS=30`.
Model overrides must support Responses and strict structured output. The blank
backend template intentionally still contains only `OPENAI_API_KEY=`.

### Call `POST /v1/plan`

Input:

```json
{"idea":"Build a CRM for a small real estate agency with leads, notes and analytics."}
```

The idea is trimmed and validated as 1–10000 characters. Extra request fields are
rejected. The result has `project_title`, `product_summary`, `target_users`,
`core_features`, `recommended_stack` and `implementation_milestones`. Feature
objects have `name`/`description`; stack has `frontend`/`backend`/`database`/
`rationale`; milestones have `title`/`deliverables` and are ordered by array position.

The endpoint requires `Authorization: Bearer <DEV_API_TOKEN>`, using the private
development token created in the project-root `.env`. This is a different
credential from your OpenAI key. The frontend supplies the development token
server-side; you never enter either credential into the project form. Use the
Terminal command below for direct authenticated API testing.

Alternatively, with the backend running, execute this from `apps/api` to load the
development token privately and call the endpoint without printing credentials:

```sh
uv run --locked python - <<'PY'
import httpx
from f01.config import get_settings

settings = get_settings()
response = httpx.post(
    "http://127.0.0.1:8000/v1/plan",
    headers={"Authorization": "Bearer " + settings.dev_api_token.get_secret_value()},
    json={"idea": "Build a CRM for a small real estate agency with leads and notes."},
    timeout=settings.planning_timeout_seconds + 10,
    trust_env=False,
)
print(response.status_code)
print(response.json())
PY
```

Only the HTTP status and validated plan/sanitized API error are displayed. A plan
is a proposal: the endpoint does not save projects, modify Brain state, build,
or deploy. The frontend displays this response through its server gateway.
Each valid submission makes one provider request
with no automatic retries, a total deadline, a 3000-output-token cap and `store=false`.

| Status | Error code | Meaning |
| --- | --- | --- |
| 401 | `AUTHENTICATION_REQUIRED` | Missing/invalid identity or session |
| 422 | `VALIDATION_ERROR` | Invalid idea or request body |
| 503 | `PROVIDER_NOT_CONFIGURED` | Missing/empty backend OpenAI key |
| 502 | `PROVIDER_AUTHENTICATION_FAILED` | Provider rejected credentials or permissions |
| 503 | `PROVIDER_QUOTA_EXCEEDED` | Credits or spending/usage allowance exhausted |
| 429 | `PROVIDER_RATE_LIMITED` | Temporary provider rate limit |
| 504 | `PROVIDER_TIMEOUT` | Provider deadline or transport timeout |
| 503 | `PROVIDER_UNAVAILABLE` | Network/server failure |
| 502 | `PROVIDER_INVALID_RESPONSE` | Malformed or schema-invalid plan |
| 502 | `PROVIDER_INCOMPLETE_RESPONSE` | Incomplete model output |
| 422 | `PROVIDER_REFUSED` | Provider declined the idea |
| 502 | `PROVIDER_ERROR` | Other provider failure |
| 500 | `INTERNAL_ERROR` | Unexpected adapter failure |

Error responses use `{"error":{"code":"…","message":"…","request_id":"…","details":{}}}`.
Raw provider messages, exception messages and validation inputs are not echoed.
No application code logs credentials, request headers or provider response bodies.

Provider code is in `apps/api/src/f01/providers`; provider-independent plan models
are in `domain/planning.py`. A future Claude or Gemini adapter implements
`PlanningProvider.create_plan(idea) -> ProjectPlan` and is wired in the factory.
No OpenAI SDK types appear in the endpoint or domain models.

## 6. Verification commands

Final M6 verification passed 43 frontend tests, the full 130-test backend suite,
strict mypy across 46 files, OpenAPI/generated-client drift checks, two client
transport tests, typecheck and the production-style web build. The final Phase 1
quality suite passed five scenarios (six tests including parent), alongside
eight M5, eight M4, one M3 and thirteen planning/homepage browser scenarios.

Checks cover all persisted journeys, long content, WCAG A/AA scans, actual
keyboard/focus interaction, 375/768/1280/1440px and compact-rail layouts, reduced
motion and 200% reflow (720×500 CSS pixels at DPR 2 for a 1440×1000 equivalent
view). PostgreSQL checks cover migration round trips, rollback, ownership,
idempotency, replay and actual backend-lifespan restart recovery. These are
factory implementation tests, not generated-application execution evidence.
No live model was called. Linux was verified; macOS was not executed.

From the project root:

```sh
pnpm typecheck
pnpm test:web
pnpm api:check
pnpm test:client
pnpm build
```

For browser tests, install the test browser once, then run the suite after a build:

```sh
pnpm --filter @f01/web exec playwright install chromium
pnpm test:e2e
```

The test harness starts and stops its own local frontend and controlled backend
on temporary ports. It does not use or change your environment files. A
`PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` override is supported for environments with
an existing Chromium binary.

From `apps/api`:

```sh
# Set TEST_DATABASE_URL privately to a disposable f01_test_* database first.
uv run --locked pytest
uv run --locked mypy src/f01 tests migrations scripts
```

`pnpm build` validates a production-style compilation for local use. APP_ENV=production requires the OIDC adapter; development identity is rejected. A successful build is not a public-launch or operations gate. This scaffold is intended to run on your Mac.

## M2 persistence and core API

The nine domain tables are `users`, `projects`, `project_requests`,
`brain_revisions`, `build_runs`, `build_events`, `project_versions`,
`deployment_records`, and `idempotency_keys`. Alembic owns schema changes.

In explicit development mode project routes use the private development bearer token and backend `DEV_AUTH_SUBJECT`. In OIDC mode they require a verified provider API token and revocable server session; caller identity headers are ignored.
Foreign-owned resources return 404. The development adapter is local compatibility only; see Phase 2A setup below for verified identity.

| Endpoint | Behavior |
| --- | --- |
| `GET /v1/session` | Resolved identity and capabilities |
| `POST /v1/projects` | `{brief, title?}` with required `Idempotency-Key`; atomic creation, 201 and Location |
| `GET /v1/projects` | Owner-scoped listing, title/status/archive filters and pagination |
| `GET /v1/projects/{id}` | Metadata and ETag |
| `PATCH /v1/projects/{id}` | Rename/archive/unarchive; required `If-Match` |
| `GET /v1/projects/{id}/workspace` | Consistent snapshot and sequence watermark |
| `GET /v1/projects/{id}/requests` | Immutable request history |
| `GET /v1/projects/{id}/brain` | Current or selected `?revision=` with canonical context |
| `GET /v1/projects/{id}/brain/revisions` | Immutable revision history |

Creation commits the project, original request, typed initial Brain, queued
simulation run, first event and saved idempotency response together. The Brain is
a deterministic scaffold with provenance; creation makes no model call. Same
key/input replays the result for 24 hours; changed input returns 409.

Database constraints protect immutable history, frozen run inputs, valid run
transitions, same-project references, active-run uniqueness and archive exclusion.
Missing metadata `If-Match` returns 428; stale values return 412. A real metadata
change increments the ETag once; no-op updates preserve it. Updates are atomic.

At the M2 checkpoint, new runs stayed queued; M5 now advances them through
deterministic simulation. Archive rejects active runs (409); archive and
unarchive work for projects without active runs. M5 adds cancellation and
simulated version/deployment publication. The existing frontend planner stays
stateless; the separate M3 creation journey saves projects.

The generated client transport is server-only. Browser code may import schema
types only; private tokens remain outside browser code. From the root:

```sh
pnpm api:generate
pnpm api:check
pnpm test:client
```

Persistence tests require `TEST_DATABASE_URL` using `postgresql+psycopg://` and a
disposable database named `f01_test_*`. They never fall back to `DATABASE_URL`.
The fixture runs upgrade/downgrade/upgrade and schema drift checks, and clears all
domain tables between tests. Never point this variable at a database to preserve.

## Planning documents

- `PRODUCT_SPEC.md`: product scope and lifecycle.
- `ARCHITECTURE.md`: proposed domain, database, route and API contracts.
- `ROADMAP.md`: milestone implementation plan and acceptance criteria.
- `DESIGN_SYSTEM.md`: typography, colors, geometry, motion and state language.

The intended stack remains Next.js/React/TypeScript/Tailwind, FastAPI/Python and
PostgreSQL. Future model integration must remain provider-agnostic. Execution,
Docker sandboxing and deployment are deferred as described in the roadmap.

## M3 API-connected verification

The real API/PostgreSQL browser journey passed create → lost response → reload/retry → reopen → rename → archive/unarchive, search/status/archive filtering, stale ETag review, validation/input preservation and unavailable-service retry. It verifies one saved project after duplicate recovery. The disposable test fixture ends its queued run directly before archive; no application runner or cancellation endpoint is used. All three M3 surfaces passed 375/768/1280/1440px overflow and WCAG A/AA scans. Backend/generated-client sources were unchanged by M3; M4 extends them as described below.

The workspace harness command is `apps/api/.venv/bin/python scripts/test-m3.py`. It provisions a disposable PostgreSQL 16 database using workspace-provided binaries, migrates it and launches the existing API. For another local environment, run the API against a fresh migrated PostgreSQL database named `f01_test_*`, with a synthetic development token, then set `M3_API_URL`, `M3_TEST_DATABASE_URL` (SQLAlchemy psycopg URL) and `M3_TEST_TOKEN` when running `pnpm --filter @f01/web test:projects:e2e`. This test expects an empty dedicated database and modifies only its own created run fixture. Install Playwright Chromium if it is unavailable. The checks invoke no live model.


## M4 workspace and verification

`/projects/{id}` reads the persisted M2 workspace snapshot. Brief preserves the original user text; Brain renders every typed section, immutable revisions, sources and canonical request/outcome references. Activity uses ordered persisted events; Versions uses persisted simulated metadata only, with inspection that cannot change the current Brain/version or roll back. Settings retains M3 rename/archive behavior. Panel, request draft/scroll and viewport state survive project subroute navigation and responsive drawer changes.

Eligible change requests require 20–10,000 characters, the current Brain ID and the current version ID (null only without a completed version). A stable frozen command key survives uncertain save/reload/retry. Explicit Brain/version conflicts preserve the draft and require a current-context review. Saving adds only an immutable request and attributed activity; original brief, Brain and runs are unchanged. At M4, new projects remained queued. M5 now progresses those runs; change recording and archiving still require the active run to end. An optional demonstration starts through a separate command after a request is saved.

Projects without completed versions display **Preview pending** without an iframe. `/development/previews` lets you inspect independent synthetic CRM/generic fixtures. Preview HTML bypasses factory layouts/hydration; classic scripts and CSS are bundled and work in the pinned Next.js runtime under opaque-origin sandboxing. The frame permits scripts only; CSP prohibits connections/forms, restricts framing to the factory and blocks other content. Samples use no cookies/storage/API access and cannot read factory identity or navigate its top frame. Files, Logs, Deployment and Runtime explain unavailable capabilities without fabricated output.

M4 passed typecheck, production build, 36 frontend tests, 105 relevant backend tests (`tests/persistence tests/test_plan.py`) with clean PostgreSQL migration round trips/schema checks, strict mypy across 40 files, generated-contract drift checks and 2 client transport tests. The real PostgreSQL/FastAPI M4 browser suite passed 8 scenarios (9 including parent); M3 create/reload/recovery/settings and 13 planning/homepage browser regressions (14 including parent) passed. Six workspace surfaces passed 375/768/1280/1440px overflow and WCAG A/AA scans. Checks validate this factory implementation, not a generated application. No live model call was made.

Workspace-provisioned browser harness:

```sh
apps/api/.venv/bin/python scripts/test-m4.py
```

On another machine, run an API against an empty migrated disposable PostgreSQL database named `f01_test_*`, then set `M4_API_URL`, `M4_TEST_DATABASE_URL`, `M4_TEST_TOKEN` and, optionally, `M4_AXE_SCRIPT`, and run:

```sh
pnpm --filter @f01/web test:workspace:e2e
```

The browser fixture helper mutates only that disposable test database to exercise ended runs, historical/unsupported Brain revisions and persisted fixture versions. It is not an application runner.

See `M4_IMPLEMENTATION.md` for that checkpoint’s changed-file inventory and limitations. M4 added no runner or run commands. M5 extends its workspace as described below; real code generation, sandbox/worker infrastructure, live hosting and external deployment remain deferred.


## M5 simulation and recovery

The runner defaults to enabled. It is a lightweight due-step loop in one always-running local/private FastAPI process; it is not a production worker or request-only serverless runner. No Docker/Redis or new dependency/migration is required. `SIMULATION_TICK_MS` defaults to 1000 and permits 100–10000ms. `SIMULATION_RUNNER_ENABLED=false` pauses dispatch for controlled tests. Restart resumes persisted cursors, including queued M4 records. Missing scenario versions terminate with an honest error.

Normal creation selects CRM or generic version-1 fixtures. `SIMULATION_CHANGE_SCENARIO=auto` is the default. For development/test demonstrations only, set it to `terminal-failure` or `recoverable-verification`, then restart the backend. These affect new change runs; retry selects a deterministic success fixture. Failure selection is never a browser/API body field and is rejected in private-preview configuration. Optional `DEV_TOKEN_EXPIRES_AT` must be an explicit timezone-aware timestamp; otherwise leave it unset.

Use Requests to record intent alone, or select **Run an optional demonstration after saving**. Saving and starting have separate stable keys. A saved request remains available when start fails. Unknown run responses retain their exact command/context in tab session storage for 24-hour recovery. Stale bases require reviewed new intent; retry never rebases silently. The original brief is immutable. The bundled sample can remain unchanged despite successful simulation.

Trace groups ordered phases and linked fixture issues/repairs. Follow can be paused by scrolling or its button; Jump to latest resumes it. SSE preserves project sequence and replay cursors, polls at three-second intervals when unavailable, and reconnects with bounded backoff. Version and attempt inspection do not change current pointers. Failed/canceled updates keep the successful iframe and its M4 `allow-scripts`-only isolation. Deployment shows internal simulation records; files, terminal logs and application runtime remain unavailable.

M5 verification: 130 backend tests, 43 frontend tests, strict mypy (46 files), typecheck/build, OpenAPI/client drift and two client transport tests. Eight M5 browser scenarios (nine tests including parent) exercised the full success/failure/retry journey, lost-response reload, repair links, sequence gaps, duplicates, polling/reconnect, cancellation, stale drafts, historical selection, follow/scroll, isolation and 375/768/1280/1440px layouts. M3/M4 and planning/homepage browser regressions also passed. These are factory tests with disposable PostgreSQL/synthetic credentials, not generated-application execution evidence.

Provisioned workspace browser harness: `apps/api/.venv/bin/python scripts/test-m5.py` after `pnpm build`. On another machine, provide a disposable migrated `f01_test_*` PostgreSQL database, run the API with the development/test fixture configuration above, and set `M5_API_URL`, `M5_TEST_DATABASE_URL`, `M5_TEST_TOKEN`, then run `pnpm --filter @f01/web test:simulation:e2e`. Existing M3/M4 harnesses explicitly pause simulation for their original foundation regressions.

See `M5_IMPLEMENTATION.md` for the exact change inventory and verification results. No commit or deployment was made; the source tree has no Git metadata.


## Historical final Phase 1 acceptance — M6

Phase 1 now supports persisted create/reopen/search/filter/rename/archive,
immutable original briefs and Brain revisions with provenance, context-bound
requests, server-owned deterministic simulations, ordered Build Trace and
Activity, retry/cancel/restart recovery, SSE replay/reconnect/polling, successful
simulated versions/internal deployment records, and isolated synthetic previews.
Failures retain the last successful Brain/version/preview. Historical inspection
does not change current pointers. Optional standalone real planning is still a
separate unsaved draft and needs a configured backend provider key.

Local/private scope: one development owner and an always-running FastAPI
process backed by PostgreSQL. Development identity is not production auth.
APP_ENV=production with that adapter is rejected; a production-style web build
does not authorize public operation. Simulation events never prove source
generation, application builds/tests/fixes, commits or external deployment.
At that Phase 1 checkpoint, generated application execution/deployment, source
files and application runtime were unavailable. Phase 2B subsequently completed
real execution, source metadata and verified isolated preview; unrestricted
terminal logs and external release controls remain unavailable. No billing,
teams, connectors, visual editing or outcome automation exists. Phase 2A and
Phase 2B are complete; Phase 2C is documentation/planning only.

In the provisioned workspace, after pnpm build, run the final acceptance and
regressions from the project root:

```sh
apps/api/.venv/bin/python scripts/test-m5.py --phase1
apps/api/.venv/bin/python scripts/test-m5.py
apps/api/.venv/bin/python scripts/test-m4.py
apps/api/.venv/bin/python scripts/test-m3.py
pnpm test:e2e
```

These scripts use disposable PostgreSQL 16 binaries supplied by that workspace;
those binaries are not shipped in the ZIP. On another machine, start an API
against a fresh migrated disposable f01_test_* database for each suite. For
the M6/M5 journeys, use APP_ENV=test, EXECUTION_MODE=simulated, an explicit
synthetic development token, SIMULATION_RUNNER_ENABLED=true,
SIMULATION_TICK_MS=800 and SIMULATION_CHANGE_SCENARIO=terminal-failure. Set
M5_API_URL, M5_TEST_DATABASE_URL and M5_TEST_TOKEN, then run:

```sh
pnpm --filter @f01/web test:phase1:e2e
pnpm --filter @f01/web test:simulation:e2e
```

Use each suite's documented M3/M4 variables and pause its runner for their
original foundation regressions. Install Playwright Chromium first. Set
M5_AXE_SCRIPT (and M3_AXE_SCRIPT/M4_AXE_SCRIPT) to an installed axe-core
axe.min.js for the accessibility scans; the provisioned harness supplies this.
Run full backend pytest with TEST_DATABASE_URL pointing only at disposable
f01_test_* storage: the fixture clears domain tables and runs migration round
trips. Migrations for a database to preserve use alembic upgrade head and
alembic check as documented in setup; startup never migrates it automatically.

If the event service disconnects, keep working from the labeled last loaded
context and use Retry connection. Polling/replay recovers saved sequence.
Stale request or metadata conflicts require review and preserve the draft.
A queued/running simulation blocks archive; the settings view links to Run
details. Stop/restart the API to resume its committed run cursor. For an expired
development token, correct the private server configuration and restart; the
Phase 1 sign-in placeholder cannot renew a production session.

See M6_IMPLEMENTATION.md for exact fixes, acceptance evidence, local timing
measurements and the changed-file inventory. Phase 1 acceptance is complete;
that historical implementation stopped before Phase 2. Phase 2A is the new checkpoint below.

## Phase 2A setup and current boundary

Use a configured OpenID Connect provider that issues **RS256 JWT API access tokens** for the configured API audience, supports authorization code + PKCE S256, and supplies ID tokens and JWKS. Providers returning opaque access tokens or different algorithms need another verified adapter; they are not accepted here. No particular vendor account was provisioned. Register the exact callback URL `/api/auth/callback` on the factory origin, configure the API audience, and restrict allowed callback origins in the provider. No browser client secret or trusted user-ID header is used.

After installing dependencies, apply the additive migration from apps/api:

```sh
uv run --locked alembic upgrade head
uv run --locked alembic check
```

The root configuration is read by FastAPI but Next.js loads only its web allowlist. Set these privately in the root environment for both servers:

```dotenv
AUTH_MODE=oidc
AUTH_GATEWAY_TOKEN=<private random value of at least 32 characters>
API_INTERNAL_URL=http://127.0.0.1:8000
NEXT_PUBLIC_APP_URL=http://127.0.0.1:3000
EXECUTION_MODE=simulated
```

Set these only in backend configuration (`apps/api/.env` or backend process environment):

```dotenv
SESSION_ENCRYPTION_KEY=<valid Fernet key>
OIDC_ISSUER=<exact issuer>
OIDC_AUTHORIZATION_URL=<fixed authorization endpoint>
OIDC_TOKEN_URL=<fixed token endpoint>
OIDC_JWKS_URL=<fixed JWKS endpoint>
OIDC_CLIENT_ID=<registered client>
OIDC_CLIENT_SECRET=<server client secret if required by provider>
OIDC_API_AUDIENCE=<registered API audience>
OIDC_REDIRECT_URI=http://127.0.0.1:3000/api/auth/callback
OPENAI_API_KEY=<backend planning credential>
```

Use HTTPS URLs and Secure cookies outside local/test loopback. APP_ENV=production permits only OIDC; its factory origin and identity endpoints must use HTTPS. Keep the backend private behind the fixed gateway. Production hosting/operations are not provisioned by this checkpoint. Never set provider, session, gateway or database secrets in NEXT_PUBLIC_* variables. Keep the encryption key stable across restarts so saved sessions remain readable. Key rotation and backup/retention procedures are not implemented.

To generate secrets without printing them, run the following **from apps/api**. It exclusively creates a private fragment and never overwrites an existing file. Copy its values privately to the respective root/backend configuration above, then remove the fragment when no longer needed. It is not automatically loaded.

```sh
uv run --locked python - <<'PY'
import os, secrets
from cryptography.fernet import Fernet
fd = os.open('.identity-secrets.env', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, 'w') as output:
    output.write('AUTH_GATEWAY_TOKEN=' + secrets.token_urlsafe(32) + '\n')
    output.write('SESSION_ENCRYPTION_KEY=' + Fernet.generate_key().decode() + '\n')
print('Private secret fragment created. Values were not displayed.')
PY
```

Restart both servers using the start commands above. Open `/sign-in`, sign in with the configured provider, then create/reopen projects. Account shows session expiry and sign-out. Default absolute TTL is 3600 seconds and idle TTL 900 seconds, additionally capped by provider token expiry. Session refresh is not implemented; expired sessions require sign-in. Sign-out revokes this factory session and leaves upstream provider SSO unchanged.

### Preserve an existing development owner

Before first OIDC sign-in for the intended provider subject, record the stable development user UUID from GET /v1/session using the existing private development session. Stop the servers, migrate and configure OIDC. Obtain an unexpired API access token for that owner through the provider's verified flow, save it in a private owner-readable file, and run from apps/api:

```sh
uv run --locked python scripts/link_identity.py \
  --user-id <existing-user-uuid> \
  --access-token-file <private-access-token-file>
```

This verifies signature/issuer/audience/expiry before linking. It preserves every project/history ID and does not change owner UUIDs. Delete the temporary token file afterward. A subject already linked to another internal user is rejected; email never links or adopts projects. New unlinked subjects receive new stable users. No team/workspace sharing is available.

### Context planning and limits

Project → Planning offers Plan from original brief and Record request and plan. Change intent is saved separately against current Brain/version context. Every model call is proposed work, not execution. Proposals retain immutable content, provider/model, source manifest and context hash. Mark proposal reviewed records acknowledgement only. Context changes invalidate publication/review; reload and review current context before making a new plan. No Brain revision, simulated run, version, source, preview or deployment is changed by a planning proposal.

Default controls:

| Setting | Default |
| --- | --- |
| PLANNING_REQUESTS_PER_MINUTE | 5 |
| PLANNING_REQUESTS_PER_DAY | 30 |
| PLANNING_DAILY_TOKEN_BUDGET | 200000 reserved tokens, UTC reset |
| PLANNING_CONTEXT_BYTES | 24000 UTF-8 bytes |
| PLANNING_INPUT_TOKENS | 28000 conservative input allowance |
| PLANNING_OUTPUT_TOKENS | 3000 |
| PLANNING_TIMEOUT_SECONDS | 30 |

The Phase 2A checkpoint assembled bounded Brain summary/plan, requirements, stack/architecture/constraints/decisions/questions, recent request history and the then-current simulated version; source was unavailable at that checkpoint. Phase 2B adds persisted source manifests and exact source/version/Brain bases to real execution context. Excerpt provenance and truncation remain explicit. All project-aware calls and authenticated OIDC draft calls reserve durable usage before dispatch; one pending attempt is allowed per owner. Failures/cancellations/unknown outcomes retain reservations. Reported provider usage is nullable. These values are usage-control foundations, not billing, credits or generated-application test counts. Development DB-free draft limits are process-local and reset on restart.

Project planning returns a persisted pending attempt, then polls its status. An uncertain response retains a frozen input/key receipt in tab session storage; resolve it to avoid duplicate provider dispatch. Cancel prevents publication of a late result but cannot guarantee stopping provider work or cost. Restart does not resend planning calls: a lost pending task becomes abandoned after its persisted deadline. Retry is a deliberate new attempt after reviewing context. No uncontrolled automatic retries occur.

### Phase 2A verification

169 full backend tests, 48 frontend tests, strict mypy across 58 files, two client transport tests, OpenAPI/client drift, typecheck and production build passed. The signed-in browser suite passed three scenarios (four tests including parent) with a controlled cryptographic OIDC issuer and actual OpenAI adapter using controlled responses. Phase 1 acceptance (six tests), M5 (nine), M4 (nine), M3 (one) and planning/homepage (fourteen) browser regressions passed. Responsive/WCAG scans at 375/768/1280/1440 and Phase 1 keyboard/200% reflow/reduced-motion checks passed. One upstream Starlette/httpx test-client deprecation warning remains.

Use the frontend/backend test commands above. In the provisioned workspace, after pnpm build:

```sh
apps/api/.venv/bin/python scripts/test-m5.py --phase2a
```

That harness creates disposable PostgreSQL, a test-only RSA OIDC provider and controlled model transport, and stops its processes afterward. The test fixture refuses non-test or non-disposable database configuration. Workspace PostgreSQL/Chromium binaries are not shipped in the ZIP. No live provider login or paid model call was configured or verified in this handoff. Configure and validate your intended provider before relying on it operationally.

Historical Phase 2A handoff: that milestone added identity/planning only; its foundation-era absence of execution was superseded by completed Phase 2B. See PHASE2A_IMPLEMENTATION.md and the historical PHASE2B_FOUNDATION.md. Simulation compatibility remains labeled; current real execution/preview is recorded below.

## Phase 2B completed; Phase 2C proposed only

Real source generation, immutable candidates/evidence, fenced jobs, trusted dependency verification/typecheck/build/tests, bounded repair, verified preview and gateway isolation passed Docker acceptance. Failed updates retain the prior successful version. The matching exact-image report remains required for operational enablement. Production deployment is not implemented; its bounded proposal is in [PHASE2C_IMPLEMENTATION.md](PHASE2C_IMPLEMENTATION.md). Never run generated code on the factory host.
