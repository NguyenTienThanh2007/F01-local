# F01 UX v2 and Full-System Reliability Pass

The visible product pass was committed and pushed to the existing branch in `0b8b437`, `0408573` and `efa8f1e`. It preserves routes, Project Brain, Build Trace, saved workspaces, immutable source/version lineage, trusted Docker execution and release guarantees. Main was not edited or merged.

The homepage, dashboard, creation composer, readable planning/review, workspace composition, preview/publishing handoff, versions and recovery states were inspected as actual pages. First-time and returning-user flows use a clear primary action and progressive disclosure for technical metadata.

## Actual before/after captures

`gallery.html` compares Homepage, Projects, Create, Planning, Build, Preview and Deploy at desktop 1440px and mobile 375px. Before images come from authoritative starting commit `3227ef5947da4b03b38d673dac98d67074ceb832`. After images now come from the final production-browser pass at `ffb7aa7`; source attribution is in `after/source.json`.

**The after images have been refreshed from the final Build/Journey production-browser run at ffb7aa7.** Current acceptance is in `../build-journey/VERIFICATION.md`.

The actual commercial browser pass covered 27 states and 54 desktop/mobile measurements with no overflow. It ran 52 passing axe WCAG scans; the two transient Projects loading captures did not run axe. It also checked widths 320, 720, 768 and 1280, including 720×500 200% reflow and reduced motion. See `browser-audit.json`.

## Completed checks before the Build/Journey v3 changes

| Check | Actual result |
| --- | --- |
| Full backend / disposable PostgreSQL regression | 335 passed, 5 opt-in tests skipped in this run |
| Strict mypy | Passed, 103 files |
| Frontend | 65 passed |
| Generated client / contract drift / typecheck / production build | Passed; 2 client tests |
| Planning browser | 14 passed |
| Creation/account recovery browser | 7 passed |
| Phase 1 persisted/recovery/accessibility/reflow browser | 6 passed |
| Phase 2A authenticated planning browser | 4 passed |
| Commercial browser with real accepted Docker | 1 passed; controlled model, identity and deployment provider |
| Exact-image Docker containment / journey / production package | 3 passed |
| Real OpenAI planning, source generation, repair and Docker preview | 1 passed; development test identity; one actual repair |
| Fresh Vercel live-provider acceptance | Failed at setup: `RELEASE_PROVIDER_AUTHENTICATION`; public health, redeploy, restoration not reached |

The five opt-in skips are three Docker checks and two live-provider checks; separate runs are shown above. Earlier historical Vercel success in `QA/commercial-v1` is not represented as a successful new recheck. Neither production OIDC nor public-launch readiness is claimed.

## Reproduced reliability fixes

- Lost project creation response followed by switching accounts: the earlier regression created data in the wrong account. Bind the unresolved command to its initiating account; compare the verified session before dispatch and assert expected owner on the server. The original account safely recovers the same command exactly once. Browser, gateway and backend regressions pass.
- First brief disappearing on sign-in/reload: reproduced manually in the actual browser. Preserve a scoped unsent draft, bind it after verified sign-in, isolate other owners, and clear it only after confirmed save. Reload/sign-in and blocked-storage regressions pass.
- Browser-test teardown held open by detached diagnostic pipes: scenario assertions had completed but teardown remained blocked. Release only the owned browser process's inherited pipes after its main process has exited; use bounded owned-server shutdown. A process-level regression and complete browser reruns pass.

The full backend pass includes owner/session isolation, stale-context rejection, API constraints, planning deadlines, concurrent/duplicate commands, worker fencing/crashes, bounded repair, cancellation/cleanup recovery, provider uncertainty without blind replay, source security, immutable evidence, release observation recovery, failed-public-health compensation, last-good-live preservation, reviewed retry and database/package backup restoration. Tests use disposable data. These remain required reruns after the new additive build-detail fields.

## Remaining known issues / unverified dependencies

Private Vercel credentials need refreshing. Production OIDC and production topology need acceptance. The temporary automatic-review block is resolved. New Build/Journey browser/screenshots, PostgreSQL metadata, strict checks and Docker reruns now pass and are committed on the existing branch. Scoped manual-harness cleanup was fixed and verified against an actual runtime. See the current build/journey report for final results. The only emitted test warning is Starlette's existing TestClient/httpx deprecation. No claim of bug-free software or public-launch readiness is made.

Use `../build-journey/VERIFICATION.md` for current blockers, local results and the command to open the updated interface. PR #1 stays open and unmerged.
