# Real OpenAI TaskPilot acceptance — 2026-10-10

Continued the existing `codex/f01-commercial-v1` implementation from the fetched remote `42299f05cb11ac1ac6183b3b59c753917900c8ce`. Main remains `449b0588e072cda102144c0c629d776049b4f2d2`; PR #1 remains open and unmerged. The pre-existing `apps/web/next-env.d.ts` development paths are preserved and excluded from commits.

## Actual environment and provenance

The acceptance used the existing Next.js frontend, FastAPI application, standalone leased build worker, preview gateway, and a new **persistent, owned local PostgreSQL database**. Existing project databases were not reset. Authentication uses the approved private development credential, not a synthetic OIDC provider and not verified Google login. The real OpenAI Responses endpoint was called with `gpt-4.1-mini`; neither planning nor source generation was substituted with controlled responses.

TaskPilot was created through F01's user-facing Product brief composer using the founder's exact prompt. Planning, approval, build, the repair request, and the exact due-date instruction were also submitted through the real interface. OpenAI supplied every generated application source edit; no TaskPilot source was handwritten or replaced with the controlled “Verified dashboard”. Source exports are read-only copies of validated immutable database artifacts under `.runtime/taskpilot/source-v1`, `source-v2`, and `source-v3` on the founder's machine.

Project: `d8147000-9d86-42f0-8deb-4a1e174f57f1` (renamed TaskPilot through Project settings).

| Version | Version ID | Source digest | Result |
| --- | --- | --- | --- |
| 1 | 74356dd0-99d9-4614-acb9-f78436bbe1b6 | ed50e5673a69bc2005635121b3faa2b910db19297440041f94f66ea393ab5a1f | Actual generated source; Docker checks passed, browser acceptance failed |
| 2 | 39b7b4e9-359d-4539-b7bd-aa60efd2b4b7 | f1495206e6fd0f79dc9825cbcfb3c1e3c648646209c5720f0f8bb5c3aab5e8f5 | Incremental OpenAI repair; functional browser acceptance passed |
| 3 | a9218b77-7987-46da-adfe-c35e9ba7e4b6 | 3cca01e90d573ef2e789110f2b925f06440f3aa788e39a538524aa857470b232 | Exact due-date modification; data-compatible browser acceptance passed |

Each source digest is linked to its exact approved plan, request, Brain revision, run and parent digest. Versions 1 and 2 remain in immutable history. All three real runs succeeded after materialization, dependency verification, strict TypeScript, Next production build and runtime verification. There were **zero automatic compiler-repair attempts** in these three runs. The browser compatibility repair was an explicit, reviewed AI modification, recorded as version 2.

The sandbox image is exactly `sha256:bf55945a66450b4d747196aed159eba926ca377b66e41400da70c0a54e3363c0`. Dependencies come from the trusted immutable offline scaffold; its install phase verifies/links those pinned dependencies. This is not a fresh network npm install. Actual command evidence is in [build-evidence.json](reports/build-evidence.json), and Build Trace retains generation, generated candidates, checks, publication and preview-ready events.

## Confirmed failures, root causes, fixes and retests

1. **Real planning excluded real execution.** The first real OpenAI response included Phase 1 simulation scope and excluded actual source/build work. The bounded context still said no source could exist in Phase 2A and did not provide current runtime capabilities. The fix adds current capability/scaffold scope while preserving historical template provenance, and removes the unconditional “No source exists yet” instruction. The first proposal remains immutable. A new real plan, initial/change persistence regressions, full backend and strict types passed.
2. **Native localStorage was unavailable in every original preview.** Chromium reproduced `SecurityError` under the existing opaque-origin CSP, including a standalone tab. A disabled-by-default, development/test-only browser preview now uses a fixed per-project `f01-<project-UUID>.localhost` origin; versions of one project share browser storage. It requires real execution, localhost gateway and a separate 127.0.0.1 factory. The original embedded URL and `sandbox="allow-scripts"` are unchanged. Native responses cannot be framed (`frame-ancestors 'none'`); capability, exact project host, expiry, bounded Docker forwarding, no factory credentials, no forms, no dialogs, no workers and restricted connections remain enforced. Invalid project hosts, capabilities, expiry, unsafe environments and frontend URL substitution have regression coverage. Actual v2→v3 browser storage compatibility passed.
3. **Generated TaskPilot controls and styling did not match the trusted runtime.** Actual Chromium failed add/update: the sandbox blocks submission before React `onSubmit`. Native confirm dialogs are also blocked. The generated page depended on Tailwind classes although the immutable scaffold has no Tailwind compiler; the browser reported zero stylesheets. Source instructions now deliver the actual CSS/browser/storage constraints on every source request. Through F01 we requested an incremental OpenAI repair using plain CSS, explicit button actions, inline confirmation and guarded storage. The resulting version passed create/edit/delete/cancel, priorities, status movement, search/filter, validation and reload tests. Protections were retained; no package/scaffold changes were made to accommodate model output.

The first version's failed browser evidence is deliberately retained. A workspace test attempted before its required disposable database configuration was rejected by the harness; rerunning with the existing portable setup passed. One real-frame smoke test acted on server-rendered controls before JavaScript loaded; waiting for the generated frame's load and observing validation before interaction resolved that test timing issue. No backend behavior or timeout was changed for either harness issue.

## Acceptance results

| Check | Result |
| --- | --- |
| Full PostgreSQL backend regression | 374 passed, 5 explicit opt-in skips; 2 existing dependency warnings |
| Strict mypy (`src/f01 tests migrations scripts`) | Passed, 112 files |
| Frontend regression | 103 passed |
| Generated-client tests | 2 passed |
| OpenAPI/client drift | Passed |
| Typecheck | Passed for client and web |
| F01 production build | Passed |
| Existing planning browser regression | 14 passed |
| Existing workspace browser regression | 9 passed, separate disposable database |
| Exact-image real Docker containment and build/repair/preview acceptance | 2 passed; controlled source used only in this separate regression |
| Actual generated TaskPilot version 2 browser acceptance | 10 functional checks passed |
| Actual generated TaskPilot version 3 browser acceptance | 10 functional checks passed, including old-record preservation and due dates |
| Actual F01 workspace / opaque iframe | Generated TaskPilot interaction, fixed shared host, unchanged sandbox and hydration passed |
| Actual application console | No console errors or page errors in successful native/embedded acceptance |
| Responsive application | Desktop 1440px, tablet 768px, mobile 390px; no horizontal overflow. Mobile create/edit/refresh passed |

Version 3 tested adding due dates to a pre-existing record without changing its ID, title, description, priority or status; creating an overdue task; clearing/restoring its overdue styling by moving to Done and back; deleting with inline confirmation/cancellation; search/status/priority filtering; keyboard focus; and persistence after refresh. The same persistent Chromium profile was used across versions. The founder's separate in-app-browser task also survived navigating from v2 to v3.

These generated-app checks were performed against the real gateway and running Docker application, without route interception or fixture-generated source. Existing regression suites still use their documented controlled cases and are reported separately.

## Measured OpenAI usage and budget

Four real planning requests (including the first rejected-for-scope proposal) and three source requests: **7 calls**, all HTTP 200. OpenAI reported **38,156 input tokens**, **19,498 output tokens**, and **0 cached input tokens**. At the official standard `gpt-4.1-mini` rates of $0.40/M input and $1.60/M output, the estimated uncached cost is **$0.0464592**. This is measured token usage with a price estimate, not a verified invoice. [Official model pricing](https://developers.openai.com/api/docs/models/gpt-4.1-mini).

A private acceptance-only HTTP guard reserves cost under a cross-process file lock **before** calling the real endpoint. It limits the model, output, request count and cumulative cost, and never generates a response. The unchanged dollar cap is **$0.50**; conservative reservations totaled **$0.1369028**. The initial six-call ceiling was raised to eight for the observed compatibility repair; the cost cap never changed. The database token allowance was raised from 200,000 to 250,000 conservative reserved tokens for the larger existing-source context. No budget was reset or prior usage discarded. The guard remains active on the running API and worker; seven of eight calls have been used. [Usage journal](reports/provider-usage.json).

## Manual review and operational limits

The real local frontend remains at `http://127.0.0.1:57469`; the project workspace is `/projects/d8147000-9d86-42f0-8deb-4a1e174f57f1`. The native application uses `http://f01-d81470009d8642f08deb4a1e174f57f1.localhost:57470` plus its version/capability path. Both founder-facing tabs are kept open. Exact capability URLs are provided privately in the final response and `.runtime/taskpilot/state.json`, not committed here.

Use **Open application** in the workspace for persistent browser data. F01's embedded frame intentionally uses temporary, opaque-origin state; its reload does not restore native-tab tasks. Storage is per browser/profile and project origin, not shared across devices. Keep Docker Desktop and the local services running. V3 expires **2026-10-11 10:14:23 Asia/Ho_Chi_Minh** under the existing preview lifetime/cleanup policy. PostgreSQL data and source artifacts remain persistent after service shutdown; the private database password, API key, development credential, usage guard and browser profile remain under ignored `.runtime/taskpilot`, outside Git.

No production publishing occurred. Real Google/email/OIDC delivery and live Vercel deployment remain external gates from the existing commercial-v1 audit; none is claimed verified by this development-identity run. Five opt-in backend tests were skipped by the ordinary suite; the two applicable Docker tests were run separately. Production packaging/provider publication were not required or rerun for this local preview task. Safari/Firefox, physical devices, generated-app screen-reader acceptance and exhaustive accessibility are not certified.

TaskPilot moves tasks with arrow controls; drag-and-drop is not implemented. Its generated overdue indicator currently uses red styling and UTC day comparison; an explicit accessible overdue label and local-midnight/timezone boundary coverage remain refinements. The generated storage effects briefly write initial empty state before restoring loaded records; normal refresh/version-compatibility passed, but crash/interruption during that narrow hydration window and concurrent-tab conflicts are not certified. Generated visual quality remains subject to founder review. Docker command verification alone does not prove functional app acceptance; version 1 demonstrates that limit.

This is a working **local TaskPilot acceptance**, not a public-launch readiness or bug-free declaration. No critical local acceptance blocker remains.

## Screenshots

All captures show actual generated TaskPilot or its real F01 workspace, not a model mockup or the controlled dashboard.

- [Initial failed application, desktop](screenshots/taskpilot-v1-desktop.png) / [mobile](screenshots/taskpilot-v1-mobile.png)
- [AI repair, desktop](screenshots/taskpilot-v2-desktop.png) / [tablet](screenshots/taskpilot-v2-tablet.png) / [mobile](screenshots/taskpilot-v2-mobile.png)
- [Due-date version, desktop](screenshots/taskpilot-v3-desktop.png) / [tablet](screenshots/taskpilot-v3-tablet.png) / [mobile](screenshots/taskpilot-v3-mobile.png)
- [Real F01 workspace](screenshots/f01-workspace-build.png)

Raw scoped results are under `reports/`; reusable frontend/backend check outputs are under `logs/`. Preview capabilities are redacted in committed browser reports. Application code remains immutable database data with local read-only exports rather than handwritten F01 source changes.
