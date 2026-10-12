# Editorial Pro implementation and acceptance

Reviewed 2026-10-09 on the existing `codex/f01-commercial-v1` branch. Baseline `2fe82d3`; implementation `d3ad86e`. This directory archives the completed design pass. Later targeted stabilization fixes and fresh results are recorded in ../stabilization/VERIFICATION.md. PR #1 stays open and unmerged. Main remains `449b0588e072cda102144c0c629d776049b4f2d2`.

## Delivered behavior

F01 now uses warm paper, charcoal and terracotta in Light, and differentiated charcoal surfaces with a soft coral accent in Dark. IBM Plex typography, the factory mark, Project Journey, Project Brain, Build Trace and all existing routes remain recognizable. The real homepage composer carries a brief into the existing protected creation pipeline. Naming is optional. Saved projects use owner-checked actual preview descriptors with honest loading/fallback covers. The workspace puts actual saved direction and a change composer beside the large isolated application preview; small screens collapse the conversation panel. Changes go through the existing plan/review/build/release pipeline.

A native, keyboard-accessible sun/moon appearance control offers Light, Dark and System throughout navigation and Account. New users default to Light even on a dark device. Preferences persist in browser localStorage, reload, follow OS changes only in System, and synchronize across tabs. The render-blocking same-origin bootstrap sets colors and streamed native selectors before React hydration without adding inline-script CSP permissions. Reduced motion disables movement. Generated applications retain their own theme; no iframe DOM, CSS or media preference is changed by F01's selection.

Appearance is browser-local. The existing profile API supports display name but has no theme field, so no account API/schema/migration or authentication infrastructure was changed. Account labels this limitation. Blocked browser storage supports the in-page theme but cannot persist it across reload.

## Results at the captured implementation

| Check | Result | Evidence |
|---|---|---|
| Backend/PostgreSQL regression | 363 passed, 5 opt-in skips | logs/backend.log |
| Strict mypy | 108 files, no issues | logs/mypy.log |
| Frontend unit/contract tests | 102 passed | logs/frontend.log |
| Generated client | 2 passed; drift current | logs/client.log, logs/openapi.log |
| Typecheck and production build | passed | logs/typecheck.log, logs/production-build.log |
| Planning browser | 14 passed | logs/planning.log |
| Creation/receipt/owner recovery browser | 7 passed | logs/creation.log |
| Existing workspace browser | 9 passed, including 8 scenarios | logs/workspace.log |
| Full real commercial browser journey | passed | logs/commercial.log, reports/commercial.json |
| Controlled OIDC authentication browser | passed | logs/authentication.log, reports/authentication.json |
| Both-theme build/recovery presentation | 18 states, 144 checks | logs/build-states.log, reports/build-states.json |
| Actual persisted worker/process-loss browser | 13 states, 26 desktop/mobile captures | logs/real-worker.log, reports/real-worker.json |
| Pre-hydration colors and selector | 3 preferences; first 8 body frames each correct with React blocked | logs/bootstrap.log, reports/theme-bootstrap.json |
| Docker containment, build/repair/preview, production packaging | all 3 passed on exact trusted image | logs/docker.log, reports/docker.json |

The product audit covers 30 actual states in Light/Dark at 1440px and 375px, with additional 320/720/768/1280px reflow checks: 116 passing WCAG 2 A/AA and 2.1 A/AA axe checkpoints; four deliberately held transient-loading captures skipped axe. Authentication adds 72 passing checks at desktop/mobile/tablet/720×500. Build/recovery presentation adds 144 at 1440/1140/375/720×500. Together these are 332 recorded both-theme checks. Actual worker states add 26 Light checks, for 358 recorded state audits. Extra historical-preview checks and workspace keyboard/opaque-origin checks are separate. 720×500 is a 200%-equivalent desktop CSS reflow test, not a physical browser zoom or device test.

Fresh Docker image: `sha256:c20b9d0f8e0691a9813f14a3fa89abbb50b135fac8fb274fbfee614fa10c9c11`. Containment includes no host mounts/secrets, resource enforcement and cleanup. Actual execution/repair, preview interactions, failed-update preservation and exact-source root-path production packaging passed. The full browser journey confirms create → plan → approve → build → verified isolated preview → reviewed publishing → modify → rebuild → preview update → redeploy → immutable history. OIDC, AI transport and publishing in this browser harness are controlled fixtures; public provider success is not inferred.

GitHub Actions now runs the pre-hydration browser check, both-theme build/recovery/accessibility and both-theme OIDC/session recovery, with pinned axe-core 4.11.1, alongside existing backend/client/frontend/types/build/planning/creation checks. Exact final-commit Actions links are reported on PR #1 after the evidence push.

## Reproduced fixes and regression evidence

- Light footer contrast: the inherited opacity blended muted text below AA. Full product axe reproduced it. Opaque semantic text fixes it; both-theme route scans pass.
- Transient Dark navigation contrast: an inherited background transition lagged the newly applied foreground (observed ratio 2.9). Semantic colors now switch together; subtle transform/border/shadow motion remains. The build suite asserts no foreground/background interpolation and scans both themes immediately after switching.
- Wrong initial theme selector: blocking React showed Dark colors with a Light selector. The scoped bootstrap synchronizes streamed appearance controls before paint and disconnects its parser observer at DOMContentLoaded. Unit and dedicated browser checks verify both colors and selector across the first eight observed body frames.
- Owned change reload: a delayed session left the change editor briefly editable before restoring its saved context. The editor and commands wait for owner-bound restoration. A browser regression holds the session response, proves editing is disabled, releases it, and checks the exact text. Sign-in retains only the recognized internal planning `change=1` flag; invalid/duplicate/external returns are rejected by unit tests.
- Journey alignment at 1140px: an inherited 460px maximum crowded the six stages. The rail now fills its panel; the build audit asserts panel coverage at four widths in both themes.
- Preview covers: initial iframe loading produced a blank cover and the fixed scaled width left a gap. An honest monogram/loading layer stays until the actual iframe load event; the isolated frame fills the card. The commercial browser waits for real content and the load marker, and checks sandbox and keyboard exclusion.

Two browser harness races were corrected without extending deadlines: creation reload assertions now await the restored text; cover assertions await the actual iframe load event. The old minimal rendering proposal fixture also lacked the required `content` field consumed by the new conversation panel; it now supplies the full existing proposal shape. Actual backend responses already contained that field.

A diagnostic real-worker run launched alongside two other Docker build suites exceeded its 90-second stage-observation deadline while the saved worker remained running in typecheck/build. Fresh Docker acceptance passed; rerunning the exact worker suite after other acceptance workloads finished passed every state, including actual owned-worker termination and no blind provider replay, with unchanged deadlines/assertions. This establishes the normal acceptance flow, not production capacity under concurrent container compilation.

## Remaining gates and limits

- Actual configured Auth0/Google login, delivered magic links, production session/cookie/origin behavior and SMTP delivery remain unverified. The controlled RSA issuer verifies protocol, signup/method routing, ownership, verification denial, expiry, logout and recovery. Required private configuration and live tests are in ../premium-auth/AUTHENTICATION.md.
- Fresh real Vercel public-health, redeploy and restore acceptance was not run. The preceding real-provider attempt failed with `RELEASE_PROVIDER_AUTHENTICATION`; the controlled publishing fixture does not resolve that gate.
- At capture time, live OpenAI planning/source acceptance was not run. Later real-provider stabilization evidence is recorded separately in ../stabilization/VERIFICATION.md; these design captures use controlled provider responses.
- Backend's five skips are three explicit Docker tests (freshly passed separately) and two opt-in live provider tests (not run). The backend log records existing Starlette deprecation and Pydantic alias warnings; unrelated dependency changes were not introduced to silence them.
- Chromium was tested. Physical devices, Safari/Firefox, a human screen-reader audit, timed five-second usability research, production topology/operations/load qualification, and application-specific generated content remain separate acceptance. Axe excludes generated iframes; actual controlled preview interaction/isolation is tested separately.
- The legacy M4 launcher is Linux-specific and unavailable on this Mac. The existing nine browser checks passed unchanged using the shared portable disposable PostgreSQL helper; run-workspace-regression.py records the reproducible adapter. A direct invocation without its required test environment was rejected before testing product behavior.

No claim of 100% bug-free software or public-launch readiness is made.

## Open and test

From the repository root:

```sh
pnpm build
pnpm open:commercial --production --auth-methods --no-open
```

Open the printed localhost URL. Continue with Google or Email routes to a clearly labeled controlled test issuer; choose owner A. Create a brief, review/approve the plan, build, try the preview, publish the reviewed package, then modify/rebuild/redeploy. Try Light/Dark/System from navigation and Account; reload and open another tab. This review environment uses a disposable database and accepted real Docker, but controlled identity/AI/publishing, and sends no real authentication email. Ctrl+C performs its scoped cleanup. Do not use these test settings as production configuration.

For automated theme checks after a production build:

```sh
pnpm --filter @f01/web test:theme:e2e
M5_AXE_SCRIPT="$PWD/apps/web/node_modules/axe-core/axe.min.js" F01_EDITORIAL_AUDIT=1 pnpm --filter @f01/web test:build-experience:e2e
F01_EDITORIAL_AUDIT=1 F01_VISUAL_AUDIT=1 M5_AXE_SCRIPT="$PWD/apps/web/node_modules/axe-core/axe.min.js" apps/api/.venv/bin/python scripts/test-m5.py --commercial
```

See SCREENSHOTS.md/gallery.html for actual before/after captures and reports/ for state-by-state evidence.
