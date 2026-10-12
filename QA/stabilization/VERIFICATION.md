# F01 incremental full-system stabilization

Audit date: 2026-10-09. Continued from remote `d3ad86e7e738d17a943721f70b6316768e94ad39` on `codex/f01-commercial-v1`. The existing Editorial Pro implementation and pending Conversation Recovery work were retained. No architecture rewrite, database migration, route replacement, new authentication infrastructure or frontend redesign was introduced. Main remains `449b0588e072cda102144c0c629d776049b4f2d2`; PR #1 stays open and unmerged.

The production fixes are confined to the existing workspace conversation component. Backend production code, provider adapters, Docker policy, source publication, releases and data schemas are unchanged. Existing generated `apps/web/next-env.d.ts` dev-path differences were preserved locally and excluded from commits. Prior design screenshots and their original source provenance are archived in [../editorial-pro](../editorial-pro/VERIFICATION.md), rather than discarded or presented as new stabilization work.

## Confirmed bugs and fixes

| Failure reproduced | Root cause | Targeted fix | Regression evidence |
|---|---|---|---|
| Workspace change editor accepted typing while `/session` was delayed | Editing was not gated on confirmed owner-bound draft restoration; a late restoration could overwrite typing | Lock editing until session owner matches the project and that owner's saved draft has restored | Before failure in logs/conversation-before.log; new browser test holds the response, checks disabled editing, then releases and restores the exact draft |
| Partial, unsubmitted change disappeared after reload | Draft persisted only at the review handoff | Persist text as it is edited, with the original project/owner/Brain/version context | Browser reload restores the unsent partial text and asserts its exact saved lineage |
| Historical preview allowed staging a new change | Conversation composer did not honor the historical version route | Disable editor/review and guard form submission on historical views; expose return to current version | Valid saved text plus programmatic form submission cannot stage a draft or issue any API write; full commercial history regression asserts read-only controls |
| Saved long briefs could not be scrolled with the keyboard | Existing compact request paragraph has `max-height:180px; overflow:auto` without a focus target | Give the reading area a named region and keyboard focus; retain current presentation | Existing Phase 1 axe check reproduced `.user-message > p` / `scrollable-region-focusable`; added actual Arrow-key scrolling, focus visibility and axe in Light/Dark at 1440/375px |

Exact product files: `apps/web/src/features/workspace/conversation.tsx` and the small inherited error-color correction in `apps/web/src/styles/editorial.css`. Regression and CI files: `apps/web/tests/conversation-recovery.e2e.test.mjs`, `apps/web/tests/commercial.e2e.test.mjs`, `apps/web/package.json`, `.github/workflows/commercial-regression.yml`. Owner mismatch, archived projects, active builds, session errors and stale captured context remain guarded; typing/review does not start a build or publish anything.

The live acceptance harness was also bounded before network dispatch, with four provider calls and a conservative $0.50 reservation ceiling. `apps/api/tests/live_budget.py` and `test_live_acceptance_budget.py` verify that an unpriced model, invalid output budget, oversized input and fifth request never reach the transport. `tests/live/test_model_acceptance.py` accepts a disposable realistic brief and records observed calls, actual repair and lineage. These are test-only changes, not production pricing or provider retry changes. Rates are from [OpenAI's official gpt-4.1-mini model page](https://developers.openai.com/api/docs/models/gpt-4.1-mini); request bytes conservatively reserve input tokens and the report is not an invoice.

## Verification

See [checks.json](checks.json), logs/ and reports/ for results and provenance. The backend's five default skips are three explicit Docker tests and two opt-in providers; Docker and OpenAI were run separately. Vercel remains blocked by credentials. Existing Starlette/Pydantic dependency warnings were retained, not hidden.

| Check | Result |
|---|---|
| Full PostgreSQL backend regression | 368 passed, 5 opt-in skips, 2 existing warnings |
| Strict mypy | 110 files, no issues |
| Frontend regression / generated client | 102 / 2 passed; contract drift current |
| Typecheck / production build | passed |
| Planning / creation recovery / existing workspace browser | 14 / 7 / 9 passed |
| Owned draft, historical read-only and long-brief keyboard regression | passed with default Chromium; four both-theme desktop/mobile axe and actual scrolling checks |
| Preserved Phase 1, Phase 2A and simulation browsers | 6 / 4 / 9 passed |
| Pre-hydration theme | Light/Dark/System: first eight observed body frames correct with React blocked |
| Both-theme build-state presentation | 18 contract-fixture states, 144 passing state/width/axe checks |
| Controlled RSA OIDC browser | 72 passing both-theme accessibility checks; signup/method routing, ownership, verification denial, profile, expiry, logout and recovery |
| Full commercial browser lifecycle | passed: real persisted DB and Docker; controlled identity/model/publishing |
| Actual worker interruption browser | 13 persisted states, 26 desktop/mobile captures; actual owned worker killed; quiet/stall reload stops activity animation; uncertainty fails safely without provider replay |
| Real Docker | all three containment, build/repair/preview and exact-source production-package checks passed |
| Real OpenAI | realistic agency task tracker: actual planning, generation, one repair, verified real Docker preview and exact source/Brain/version lineage passed |
| Real Vercel / Google / email delivery | unverified; configuration gates below |

Product/browser audit: 30 states × two themes × two widths, 120 measurements, 116 passing axe checkpoints plus four deliberately held loading captures excluded from axe. Authentication adds 72 and build-state presentation 144, giving 332 both-theme checkpoints; actual worker adds 26 Light checkpoints. The new long-brief regression adds four both-theme checks. Additional 320/720/768/1280 reflow, focus-trap restoration, mobile navigation, opaque-origin preview interaction and reduced-motion checks are separate. 720×500 tests 200%-equivalent CSS reflow, not physical browser zoom.

The full commercial journey uses actual protected commands, saved state and trusted Docker through create → plan → approve → build → verify/repair → preview → prepare/publish → modify → rebuild → preview update → redeploy → immutable history. Its public provider is controlled: passing that suite is not proof of actual Vercel deployment. The live OpenAI scenario is an accessible browser-only agency task tracker with seeded tasks, creation, priorities, status, filtering/search and deletion requested. Its verified artifact demonstrates real model/build/repair/preview execution; application-specific functional completeness is not independently certified by that model test.

Trusted image: `sha256:c20b9d0f8e0691a9813f14a3fa89abbb50b135fac8fb274fbfee614fa10c9c11`. Tests preserve no host mounts, no factory secrets, bounded containers, isolated preview origins and last-good preview/live state. No user-owned database or provider project was deleted. Disposable test databases and recorded test containers were scoped and cleaned.

## Browser tooling recovery

The requested default Playwright test failed before application execution because Chromium headless shell build 1208 was missing. Official full and headless-only installers both completed their downloads and stalled during ZIP extraction. The owned complete official archive passed CRC and relative-path checks (17 entries), SHA256 `8510b9b1575538aa6a092ed16d981738b2ebf52c5e41ea4c54a7ce16756cdcf5`. Scoped native extraction restored the expected cache, and the binary identified itself as Google Chrome for Testing 145.0.7632.6. The default conversation/browser checks then passed without an executable override. No repository dependency/assertion/deadline was changed to mask that failure. The precise cause of the SDK extractor stall is not established.

Standalone planning/theme/build-state/conversation checks use that installed default Chromium. Existing `scripts/test-m5.py` selects this Mac's Google Chrome 154.0.8037.98 for its suites; it is not falsely reported as the downloaded binary. The legacy Linux-specific M4 launcher was not rewritten: the unchanged nine workspace browser tests use the portable disposable-DB adapter archived with prior evidence.

## Remaining production gates and limits

- Vercel: the existing private CLI credential returns HTTP 403 on a read-only project listing. No provider project mutation was attempted in this pass. Privately refresh Vercel CLI sign-in or supply `F01_VERCEL_TOKEN` (and team configuration where required), then rerun `scripts/test-commercial-live.py --socket /var/run/docker.sock --use-cli-login` after Docker acceptance. Actual public health, redeploy and restoration are not verified.
- Identity: an actual OIDC issuer and Google/email connections are absent. Configure the supported provider privately using [../premium-auth/AUTHENTICATION.md](../premium-auth/AUTHENTICATION.md), then verify actual Google sign-in, delivered single-use email links and production callback/cookie/session/origin behavior. Controlled RSA OIDC success does not prove email delivery or production login.
- Real OpenAI is verified for one bounded disposable scenario, including one actual repair. It does not certify all generated applications or production capacity. Functional generated-app requirements and nontrivial production applications require their own acceptance.
- Safari/Firefox, physical devices, a human screen-reader review, timed user research, production load/concurrent Docker compilation, production infrastructure/backup operations and live-provider outage handling remain unverified dependencies. PostgreSQL constraints, concurrency, immutable source/history, additive migrations and populated dump/restore passed locally in the regression suite.
- No remaining critical/high implementation failure was observed in the completed tested flows. That is a bounded audit result, not a claim of bug-free software or public-launch readiness. Live authentication and Vercel remain launch gates.

## Review and reproduce

Use `pnpm open:commercial --production --auth-methods --no-open` and open the printed localhost URL. This launcher uses a disposable PostgreSQL database, accepted real Docker, and clearly labeled controlled identity/model/publishing; it sends no real authentication email and proves no real Vercel publication. Ctrl+C performs scoped cleanup. Existing persisted user data is untouched.

Fresh local evidence is recorded here; the final exact-commit GitHub Actions result is linked in [PR #1](https://github.com/NguyenTienThanh2007/F01-local/pull/1). Only the existing working branch is pushed; main is unchanged and no merge is performed.
