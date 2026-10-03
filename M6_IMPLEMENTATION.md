# M6 — final Phase 1 quality and acceptance

Status: implemented and verified; Phase 1 complete. Date: 2026-10-02.
Implementation stopped before Phase 2.

## Scope and result

M6 completes the quality pass over the persisted M2–M5 product. It preserves
the redesigned visual identity, original brief, immutable Brain revisions,
context-bound requests, server-owned Simulation runner, ordered events,
successful-version pointers and isolated synthetic previews. The existing
standalone `/v1/plan` integration remains a real, unsaved draft-planning tool.

No backend/domain behavior, database schema or migration, generated API
contract, dependency lockfile, preview HTML/assets or isolation policy changed.
Phase 2A/2B/2C descriptions remain future plans. No real generated-application
source, execution, hosting or deployment was implemented.

## Issues found and fixed

| Observed issue | Final behavior |
| --- | --- |
| Homepage availability still treated implemented project capabilities as future work | Planning and saved projects are available; Brain is available; version/deployment records are labeled Simulation; real generation, runtime/logs and hosting remain planned |
| Compact navigation hid link text and therefore accessible names | Start, Projects and account links retain explicit accessible names; short desktop rails scroll vertically |
| Native modal Shift+Tab could move focus outside the document | Modal keyboard traversal wraps through visible, enabled controls; Escape closes through React and restores the opener; desktop inspector remains nonmodal |
| Sheet cleanup could close the dialog before its focus-restoration branch | Open/close and unmount handling are separate; connected opener focus is restored |
| Changing a selected resource could briefly display the previous record under a new selection | Resource reads are keyed by requested path; a new selection has a loading state and no old record; same-record refresh retains loaded content |
| Historical/current version and run context needed clearer labels | Header, preview, version list and run details distinguish current versus historical inspection; off-page selected Brain/run options remain selectable |
| Preview reload reused the previous frame's loaded flag | Loading status is tied to fixture path and reload identity |
| Connection problems were visible only inside the inspector | Workspace-wide connecting, polling, offline and expired/unavailable-access messages; explicit Retry connection; last loaded context remains visible |
| Manual transport retry could discard already recovered Trace history | Contiguous cached history survives retry, backfills from its saved cursor, and ignores late commits from disposed subscriptions |
| Trace references and issue/repair relationships were difficult to inspect | Per-event type/run/request/UTC/cursor disclosure; reciprocal issue/repair links focus the referenced event and pause follow |
| Trace explanatory copy consumed too much of a short viewport | Compact phase index and collapsed Simulation/time disclosure leave room for ordered events; followed final event remains within the inspector viewport |
| Saved sequence and Pulse both announced frequent changes | Pulse has a polite atomic status; sequence is readable without a duplicate live announcement |
| UI label “Shipping” differed from the specified phase | Pulse and workspace use Deploying consistently |
| Rapid repeated metadata actions could submit twice | A synchronous busy guard permits one title/archive command; browser double-submit check observes one PATCH |
| New external metadata could appear to silently replace a settings draft | Explicit latest-context review preserves the draft and blocks stale submission |
| Active-run archive action offered an invalid operation | Archive is disabled with a reason and a link to inspect/cancel the run |
| Repeated CSS overrides obscured final inspector behavior | Workspace stylesheet is formatted; duplicate rules and overridden height caps are consolidated; pagination/metadata wrap |

No fake terminal output, source files, commits, application test counts or
external deployment URLs were added. Simulation labeling remains visible in
Pulse, Trace, run/version/deployment records and preview explanations.

## Final verification

All commands below completed successfully against the final implementation.
Browser counts distinguish child scenarios from their enclosing parent test.

| Check | Result |
| --- | --- |
| Full backend pytest | 130 passed on disposable PostgreSQL 16 |
| PostgreSQL migration/schema checks | Upgrade → downgrade → upgrade; no new upgrade operations detected |
| Strict mypy: `src/f01 tests migrations scripts` | Passed across 46 files |
| OpenAPI/client drift: `pnpm api:check` | Backend OpenAPI and generated TypeScript schema current |
| Client transport: `pnpm test:client` | 2 passed |
| Full frontend: `pnpm test:web` | 43 passed |
| `pnpm typecheck` | Passed |
| `pnpm build` | Passed on pinned Next.js 16.3.8 |
| M6 final quality/acceptance | 5 scenarios passed; 6 tests including parent |
| M5 simulation regression | 8 scenarios passed; 9 tests including parent |
| M4 workspace regression | 8 scenarios passed; 9 tests including parent |
| M3 persistence/metadata regression | 1 journey passed |
| Planning/homepage regression | 13 scenarios passed; 14 tests including parent |
| Accessibility | Tested WCAG 2 A/AA and 2.1 A/AA axe scans clear on factory surfaces and separately inside both opaque-origin sample frames |
| Responsive, focus, motion, reflow | Four required widths, compact rail, actual keyboard/focus interactions, reduced motion and 200% equivalent reflow passed |
| Browser runtime | No uncaught page errors in the final M6 acceptance suite |

The backend emitted two non-failing framework warnings: Starlette TestClient's
httpx deprecation and Pydantic's field-alias warning. No dependency upgrade or
API contract change was made for those warnings.

These results test the factory implementation. They are not evidence that a
generated application was built, tested, repaired or deployed. Credentials and
project content were synthetic; storage was disposable; no live model was
called. Linux was verified; macOS was not executed.

## Required journey evidence

| Step | Verified result |
| --- | --- |
| 1. Create project | Browser submits title/brief and opens the saved project ID |
| 2. Reload and find project | Reload and dashboard reopen retain the same project and original brief |
| 3. Simulated success | Server runner publishes version 1 and Live · Demo |
| 4. Build Trace | Unique ascending project sequences, phase groups and inspectable event references |
| 5. Brain revision | Immutable revision 2 rendered; M4 regression checks typed sections, provenance and historical/unsupported revisions |
| 6. Version | Successful version is marked CURRENT with its saved context |
| 7. Change request | Recorded independently of original brief, with Brain/version bases and optional Simulation |
| 8. Failed update | Deterministic update fails and reports Needs attention |
| 9. Prior preview retained | Original successful Brain/version pointers and preview remain available |
| 10. Retry and succeed | Linked retry publishes version 2 and Brain revision 3 |
| 11. Historical inspection | Version 1 can be inspected; current pointers remain version 2/revision 3; return-to-current link works |
| 12. Cancel run | Cancel publishes one terminal result, preserves successful version 2 and returns Pulse to Live · Demo |
| 13. Rename | Two synchronous clicks produce one PATCH and one reviewed title |
| 14. Archive/unarchive | Archived filter finds the same project; unarchive restores it to the normal dashboard; active-run restriction is explained |
| 15. Reconnect/replay/polling | M6 offline/manual retry preserves visible content; M5 regression verifies missing/terminated streams, replay, gap backfill and deduplication |
| 16. Unauthorized access | Nine foreign-project read/stream paths return the same no-data 404 as missing IDs; unauthenticated access is 401; browser reveals no foreign title |

The full backend suite also verifies controlled-clock fixtures, due-time guards,
duplicate/concurrent steps, terminal publication rollback, success/cancel races,
stale input/retry conflicts, scoped idempotency, unknown scenario versions,
stream authorization/expiry and replay cursor validation. Actual FastAPI
lifespan restart recovery resumes the committed cursor. Browser recovery tests
cover unknown command responses, reload, multi-tab updates and polling without
advancing runs.

## Accessibility and visual review

Six workspace routes with a 100-character unbroken title and 10,000-character
brief were checked at 375, 768, 1280 and 1440 CSS pixels. Trace and run details
were scanned at each width; screenshot review checked their layout. An 1100px
compact rail retains link names. Home, dashboard, creation, account, design
showcase and fixture showcase were scanned, as were both isolated sample DOMs.
No horizontal page overflow or executable brief markup was observed. The
existing color tokens were preserved; scanned color-contrast checks passed.

Keyboard review uses actual Tab/Shift+Tab/Enter/Escape events and inspects focus:
the skip link focuses main content; mobile navigation and inspector restore
their opener; modal traversal remains contained. Issue/repair links focus their
target, pause follow and support returning to the latest event. Long content,
pagination and inspector controls remain reachable by scrolling.

Reduced-motion mode contains no running animation, including after choosing
Play demo. The 200% check uses a 1440×1000 physical-equivalent view represented
by 720×500 CSS pixels at DPR 2. It verifies reflow, control reachability, no
overflow and the followed final Trace event within the 500px viewport. Native
browser-chrome zoom was not available in this headless runtime; this is an
explicit equivalent-reflow check, not a claim of native zoom interaction.
Automated scans and this keyboard/visual review are not an accessibility
certification or a cross-browser/screen-reader audit.

## Local reliability baseline

`apps/web/test-results/m6/local-baseline.json` records measured create-to-workspace
and explicit-reconnect timings from the final acceptance run. The baseline is
a production-style Next.js frontend, FastAPI, disposable PostgreSQL 16 and
headless Chromium on loopback, with an 800ms Simulation tick and no live model.

| Final local observation | Time |
| --- | --- |
| Create submission → saved workspace | 446ms |
| Explicit reconnect → saved event connection | 139ms |

It is a single local observation, not a performance SLA, internet latency
benchmark or production load test.

## Phase 1 capabilities and deliberate limits

Phase 1 provides one persisted development owner's projects, dashboard filters,
recoverable creation, rename/archive management, immutable briefs/Brain history,
provenance, saved change intent, project-sequence Activity/Trace, deterministic
Simulation attempts, atomic simulated version/Brain/deployment records,
retry/cancel/restart recovery and read-only historical previews. A failed or
canceled update keeps the last successful preview. The optional standalone
planner returns a validated real proposal without saving or executing it.

Generated application execution/deployment is not yet implemented. Samples are
bundled curated fixtures and may remain unchanged after a successful
Simulation; arbitrary requested changes are recorded intent. Files, terminal
logs, application runtime and external release controls remain honest
unavailable surfaces. Deployment records have an internal fixture target and
no external URL. No real source generation, application build/test/fix, commit,
public hosting, real deployment or public-launch claim exists.

Operation is local/private with a development identity and an always-running
FastAPI process. This is not production authentication or a production worker;
the production environment rejects the development adapter. If the API stops,
Simulation waits and resumes from persistence after restart. An expired
development token requires private configuration correction/restart; the
sign-in placeholder does not renew a production session. No Docker sandbox,
Redis, billing, teams, connectors, visual editing or outcome engine was added.

The Phase 1 acceptance gate is complete. Phase 2A requires its own bounded
implementation and verification for production identity and context-aware
planning; 2B/2C require separate real execution/deployment evidence. No Phase 2
implementation began during M6.

## Setup, commands and checkpoint

`README.md` documents local dependencies, private environment setup, database
migration/readiness commands, frontend/backend start commands, complete tests
and portable browser-suite configuration. The provisioned M6 harness is
`apps/api/.venv/bin/python scripts/test-m5.py --phase1`; the web suite is
`pnpm --filter @f01/web test:phase1:e2e`. Each persistence browser suite requires
fresh disposable `f01_test_*` storage. Optional axe source must be supplied for
portable accessibility runs; the provisioned harness supplied it here.

`F01-M6.zip` contains the source under `F01-local`, this report and selected
final M6 screenshots/baseline. Secrets, installed dependencies, build/runtime
caches, databases and earlier ZIPs are excluded. M5 remains a separate
checkpoint. The source has no Git metadata; no commit or deployment was made.

## Exact source changes relative to F01-M5.zip

The planning documents retain the already approved Phase 2A–2C direction and
now record M6/Phase 1 completion. Those future descriptions add no runtime code.

### Modified existing files (25)

- `ARCHITECTURE.md`
- `DESIGN_SYSTEM.md`
- `PRODUCT_SPEC.md`
- `README.md`
- `ROADMAP.md`
- `apps/web/package.json`
- `apps/web/src/components/shell/product-shell.tsx`
- `apps/web/src/components/ui/sheet.tsx`
- `apps/web/src/features/first-time/platform-index.tsx`
- `apps/web/src/features/first-time/product-entry.tsx`
- `apps/web/src/features/projects/project-dashboard.tsx`
- `apps/web/src/features/projects/project-settings.tsx`
- `apps/web/src/features/workspace/feed.ts`
- `apps/web/src/features/workspace/preview.tsx`
- `apps/web/src/features/workspace/trace.tsx`
- `apps/web/src/features/workspace/views.tsx`
- `apps/web/src/features/workspace/workspace.tsx`
- `apps/web/src/lib/projects/contracts.ts`
- `apps/web/src/styles/globals.css`
- `apps/web/src/styles/workspace.css`
- `apps/web/tests/planning.e2e.test.mjs`
- `apps/web/tests/projects.e2e.test.mjs`
- `apps/web/tests/simulation.e2e.test.mjs`
- `apps/web/tests/workspace.e2e.test.mjs`
- `scripts/test-m5.py`

### Added files (3)

- `M6_IMPLEMENTATION.md`
- `apps/web/src/components/ui/dialog-focus.ts`
- `apps/web/tests/phase1.e2e.test.mjs`

No source files were removed. Backend, migrations, dependency lockfiles,
generated contracts and preview isolation are unchanged from M5.
