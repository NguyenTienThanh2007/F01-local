# Premium product / authentication acceptance

2026-10-08. Continued the remote `codex/f01-commercial-v1` branch from `c5ce0f4`; no restart, new branch, main edit, migration rewrite or merge. Product source provenance is in `source.json`. This report supersedes earlier counts while retaining their historical evidence.

## Delivered

F01 keeps its paper/ink/terracotta identity with a stronger typographic homepage, useful illustrative examples, a quiet workspace rail, clearer project rows, focused brief creation, human-readable plan review, observed build activity, central verified Preview, explicit publishing and separate update/history views. Describe → Plan → Build → Preview → Deploy → Live remains persistent, with the current step and recommended action. Brain, Trace, lineage and provider details remain available through disclosure and existing routes.

Authentication retains the secure OIDC infrastructure and adds Google/email connection handoffs, dedicated signup, safe return after interrupted sign-in, verified email, revocable sessions, logout/recovery and a persistent owner-scoped account profile. External credentials and hosted provider setup are required before actual Google or magic-link login can be accepted. See `AUTHENTICATION.md`.

## Final checks

| Check | Result / evidence |
| --- | --- |
| Full backend + disposable PostgreSQL regression | **355 passed, 5 skipped**; `logs/backend-final.log` |
| Strict mypy | **107 files passed**; `logs/mypy-final.log` |
| Frontend regression | **96 passed**; `logs/frontend-final.log` |
| Generated-client tests | **2 passed**; `logs/client-final.log` |
| OpenAPI/generated-client drift | Passed; `logs/contracts-final.log` |
| Typecheck / production build | Passed; `logs/typecheck-final.log`, `build-final.log` |
| Planning browser | **14 passed**; `logs/planning-browser-final.log` |
| First-brief/account/lost-response recovery browser | **7 passed**; `logs/creation-recovery-final.log` |
| Contextual planning / session browser | **4 passed**; `logs/context-session-final.log` |
| Persisted workspace / keyboard / offline / reflow browser | **6 passed**; `logs/workspace-recovery-final.log` |
| Full commercial Docker browser journey | **1 passed**; `logs/commercial-browser-final.log`, `reports/commercial.json` |
| Authentication integration browser | **1 passed**, 9 states / 36 WCAG checkpoints; `authentication/result.json` |
| Build observation browser | **1 passed**, 18 contract-fixture states / 54 axe checkpoints; `build-observations.json` |
| Actual persisted worker/Docker/process-loss browser | **1 passed**, 13 states / 26 axe checkpoints; `actual-worker.json`, selected screenshots |
| Exact-image Docker containment / build-repair-preview / production packaging | **3 passed**; `logs/docker-final.log`, `reports/docker.json` |
| Disposable cleanup process regressions | **8 passed**, including actual INT/TERM and PostgreSQL process-group interruption; `logs/cleanup-final.log` |
| Actual repeated Ctrl+C manual shutdown | Passed; scoped cleanup confirmed, exit 0, **zero containers in this review**; `logs/manual-shutdown-final.log` |

The production commercial browser journey verifies explicit approval, accepted build, isolated working preview, reviewed package/publication, lost-response idempotent release recovery, source-pinned modification, version-2 preview, last-live preservation until redeploy, history and historical preview. Identity, AI responses and publishing are controlled; Docker and persistence are real. No controlled public receipt counts as live Vercel acceptance.

The actual-worker browser test records queued, generating, generation reload, building, verifying, preview preparation, succeeded, repairing, failed, canceled, quiet generation, real worker termination/stalled reload and explicit recovery without model replay or replacing the last-good preview.

The visual audit covers **30 product states**, 60 desktop/mobile measurements, 58 passing WCAG scans and two transient loading captures without axe. Additional reflow checks cover 320/720/768/1280px. Auth covers 1440/375/768/720px. The 720×500 case is a 200%-equivalent reflow check, not a claim of physical-device or browser-zoom certification. Keyboard, mobile navigation/current-tab visibility, reduced motion and one primary workspace action were checked. Automated factory scans exclude generated iframes; application-specific accessibility remains separate.

All major pages were visually inspected in browser captures; interactive in-app review additionally covered configured sign-in, account, empty projects, creation, saved workspace, pending planning and plan review. Before/after captures are in `SCREENSHOTS.md` and `gallery.html`. Signup is new; the previous sign-in entry is its baseline. Modify comparison uses explicitly captioned different update stages.

## Reproduced fixes

| Failure | Root cause / fix / regression |
| --- | --- |
| Later verified login left the account email empty | Existing-user resolution only saved email on creation. Update verified email on the same issuer/subject, never merge by email. Persisted regression reproduced None vs verified email, preserves display name and separate owner. `logs/profile-repro.log`; full backend passes. |
| Create overflowed at 768px | Legacy two-column companion grid survived inside a narrow new composition. Reset the companion layout/minimum width. Actual browser failure in `logs/after-browser-initial.log`; all six layout widths pass in final audit. |
| First-time planning implied an existing live release | Unconditional update copy appeared before a version existed. Render first-plan guidance and qualify any live release for updates. Actual in-app reproduction; commercial browser regression asserts no live-release implication before the first plan. |
| Repeated interrupt aborted teardown | SIGINT could interrupt subprocess wait; pnpm's second interrupt becomes SIGTERM. Enter bounded cleanup on the first INT/TERM and ignore repeats only during cleanup. Actual failed shutdown and failing SIGTERM process regression; final process tests and actual double-Ctrl+C pass. |
| Ctrl+C stopped the database before runtime cleanup | PostgreSQL inherited the terminal process group. Launch the disposable database in its own session while retaining explicit bounded teardown. Real group-signal regression failed with connection refused, then passed; actual shutdown confirms cleanup. `logs/database-interrupt-repro.log`, `manual-shutdown-recheck.log`, `terminate-cleanup-repro.log`. |

Initial failed test attempts are retained in `logs/`. The first browser command lacked a bundled Chromium installation; subsequent runs used installed Google Chrome. A Node native-TypeScript syntax incompatibility was corrected without changing auth policy. Strict test annotations were corrected before passing mypy. The wrapper `pnpm api:check` encountered restricted uv-cache access; direct installed-venv OpenAPI check plus generated-client check passed. These tooling attempts are not reported as application success.

## Remaining gates and known limits

- **Live authentication not run:** configure the Auth0 tenant, production Google OAuth connection, hosted Classic magic-link flow, production SMTP/sender, HTTPS callbacks and secret/session/gateway environment. The same-browser magic-link limitation and separate subjects across sign-in methods are documented in `AUTHENTICATION.md`.
- **Fresh live Vercel not run in this pass:** the preceding actual acceptance failed at target setup with `RELEASE_PROVIDER_AUTHENTICATION` (`../build-journey/live-vercel.json`). Refreshed private credentials have not been confirmed. Real public-health/redeploy/restore remain gated.
- **Fresh live AI not run in this pass:** source behavior here uses controlled model responses. The preceding actual OpenAI plan/source/Docker preview passed; it is historical evidence in `../build-journey/live-model.json`, not a fresh premium-pass result.
- Default regression skips are three opt-in Docker checks and two live-provider checks. The three Docker checks ran separately and passed. Two fresh live-provider checks remain skipped.
- Production hosting, HTTPS/private networking, operations, email delivery and configured-tenant acceptance remain unverified. Server-function apps remain outside the supported browser-state/static-export release contract.
- Existing Starlette TestClient/httpx deprecation remains. No new dark-mode preference was added; the supported light theme was refined. Safari, real mobile devices, manual assistive-technology certification and generated-app-specific usability are not verified by Chrome/axe acceptance.
- No known unresolved critical/high implementation defect was found in the covered paths after these fixes. This is neither a 100%-bug-free claim nor public-launch approval. Provider and production gates must pass first.

## Open the updated interface

From the repository, with Docker Desktop available and the exact-image acceptance report present:

```sh
pnpm build
pnpm open:commercial --production --auth-methods --no-open
```

Open the exact fresh URL printed by the launcher. Sign in as **test owner A** through either controlled method. Create → Plan → Approve → Build → Preview → Publish → Modify → Rebuild → Preview → Redeploy → Versions; also review `/account`, `/sign-in` and `/sign-up`. This disposable environment uses the production frontend build, real Docker and synthetic identity/source/publishing providers. It does not use the existing production database or send authentication emails. Ctrl+C performs scoped cleanup; confirm the printed cleanup result. Old review URLs from this pass are stopped. Do not merge main.
