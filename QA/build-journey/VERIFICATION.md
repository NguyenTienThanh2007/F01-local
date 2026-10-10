# F01 observed Build / Project Journey acceptance

The implementation is committed on `codex/f01-commercial-v1`. Main is unchanged and PR #1 remains open and unmerged. **Public-launch readiness is not declared:** fresh Vercel authentication and production OIDC/topology acceptance remain unresolved.

## Implementation

- An accepted real build immediately shows F01's factory activity indicator and a saved-state timeline: Understanding → Generating code → Building → Verifying → Preparing preview → Ready.
- Every confirmed step uses current-candidate command evidence, scoped real Build Trace events, or atomic verified-publication guarantees. No percentage or ETA exists. Saved files alone cannot confirm a build, verification, preview publication or deployment.
- The existing owner-scoped, repeatable-read BuildDetail endpoint adds `current_candidate_evidence`, `progress_updated_at` and `progress_sequence`. Old immutable evidence remains present. No migration, worker dispatch, provider, cancellation, publication or sandbox behavior changes.
- Current-build reads refresh while the authoritative run is active, and on saved event sequence changes. A fresh server acknowledgement is displayed before the next snapshot arrives; a reload reconstructs from server records. Receipts keep original keys and frozen command bodies.
- At 45 seconds without a saved step, a recent worker heartbeat produces a visible waiting state. A check-in older than the existing 30-second worker lease boundary produces a status-check warning. Lost reads/access produce a separate connection warning. These observations pause animation; they never declare a worker dead or fabricate progress.
- Cancellation requests remain pending until a terminal server result. Failed attempts offer a saved-context retry; uncertain commands retain their original receipt. Status checks only read data.
- The first pending preview surface is replaced by the build screen. A prior verified preview remains available in a disclosure during updates. A confirmed new atomic publication opens Preview and closes the build screen automatically.
- Every workspace route includes Create → Plan → Build → Preview → Deploy → Live, Step X of 6 and a next action. Build expands on other workspace pages. Update progress is separate from the last confirmed live release. Only a successful current release pointer confirms Live. Failed replacement releases keep an attention journey without discarding that pointer.
- Technical lineage, digests and evidence remain under Details. Motion stops in waiting/stalled/terminal states and respects reduced motion. Compact mobile rails use two rows instead of unreadably small labels.

## Acceptance completed

| Check | Result |
| --- | --- |
| Full backend / disposable PostgreSQL regression | 343 passed, 5 opt-in checks skipped in this run |
| Frontend regression | 90 passed |
| Strict mypy | Passed; 107 files after adding the real-worker acceptance harness |
| Generated-client tests | 2 passed |
| OpenAPI / generated-client drift | Passed |
| Typecheck / production build | Passed |
| First-time/account/lost-response browser recovery | 7 passed |
| Planning frontend browser | 14 passed |
| Authenticated planning/session browser | 4 passed |
| Persisted workspace/keyboard/offline/200% reflow browser | 6 passed |
| Full real-Docker commercial browser journey | 1 passed; controlled source/identity/publisher |
| Exact-image Docker containment/journey/production package | 3 passed |
| Build-state rendering/browser regression | 1 passed; 18 states, 54 desktop/mobile/720×500 captures and axe scans, saved-contract fixtures |
| Actual OpenAI plan/source/Docker preview | 1 passed; exact source/version/input-Brain identifiers saved; development identity; no public publish |
| Actual manual review and scoped shutdown cleanup | Passed; one recorded Docker runtime removed and absence confirmed |

The additional real-worker intermediate/failure/process-loss browser acceptance passed: 13 states and 26 desktop/mobile captures with axe scans. Results are in `real-states.json` and actual screenshots in `actual-worker/`. It uses real persisted PostgreSQL and Docker, controlled source responses, and an actually terminated owned worker. It is not a real OpenAI or public-provider claim.

Before/after screenshots for Homepage, Projects, Create, Planning, Build, Preview and Deploy are in `../ux-system-v2/gallery.html` and its `before/` / `after/` folders. The final commercial audit covers 27 states, 52 passing WCAG axe scans, widths 320/375/720/768/1280/1440, reduced motion and 200% equivalent reflow. Two transient Projects loading captures did not run axe. The current build-state suite supplements these with explicit queued, generation, build, verification, repair, failure, source rejection, retry, cancellation request/confirmation, reload, interrupted-read, stale-worker and preserved-Live cases. Technical logs/IDs remain in Details.

## Dedicated Reliability Pass: reproduced fixes

Each issue was reproduced before fixing, regression-tested, and checked with adjacent functionality.

- Repair/read/trace races could reuse the previous candidate's completed checks. Fence the read by saved event sequence and candidate identity; reset checks on generation and worker recovery. Old immutable evidence remains available. See `logs/stale-repro.log`, `race-repro.log`, `recovery-repro.log` and passing frontend regression.
- New generated/check events could be hidden behind an older generation-pending response. Prefer newer scoped observations without inventing checks. Context resolution now precedes generation explicitly.
- A confirmed cancellation or newly accepted build could be replaced by an older snapshot. Retain the authoritative command result until a same-run read catches up; terminal observations use idle/error states. See `logs/ack-repro.log`.
- Interrupted event streaming could incorrectly block a fresh successful current-build read. Current saved reads remain authoritative; read failures and expired/revoked access still stop activity and preserve last data. Regression covers each combination.
- A failed replacement release disappeared behind the last successful Live pointer. Keep the separate deployment attention journey while preserving that pointer. See `logs/live-preservation-repro.log`.
- Retry's disabled-to-enabled button colors briefly fell below WCAG contrast (4.48:1). The actual axe failure was captured; foreground/background now change without color interpolation, while borders retain motion. Browser regression asserts the transition rule and rescans every state.
- A real model returned an unchanged repair. Source validation correctly rejected it, but the worker returned generic `EXECUTION_FAILED`. Preserve validation and report `SOURCE_PROPOSAL_REJECTED`; clarify meaningful repair and strict typing in the source policy. Valid initial/repair rejection regressions verify no publication or lost preview. The subsequent bounded actual-model build passed. See `logs/source-rejection-repro.log` and `live-model.json`.
- A quiet event stream waited for its 15-second heartbeat before confirming connection. After ownership and authorization checks, flush a comment immediately. This carries no build event, progress, percentage or success. An actual browser failure and PostgreSQL timing regression reproduce it; replay/expiry/foreign-owner and the full 6-test legacy browser suite pass. See `logs/stream-repro.log`.
- Active demonstrations could enter the real-build panel. Preserve explicit simulation provenance; an actual browser scenario switches modes and verifies no real-build activity/panel appears.
- Confirmed failed-candidate deletion left a stale job container identity and temporarily rejected retry as `CLEANUP_PENDING`. Clear the identity only after confirmed deletion, retaining it on failures/crashes. The PostgreSQL reproduction, full regression and actual-worker retry/cancel/recovery browser check pass; see `logs/cleanup-repro.log`.
- Manual review shutdown retained a disposable preview container. Remove only database-recorded runtimes with matching accepted image/project/run/role labels; reject non-disposable databases and foreign labels. Five regressions pass. Actual shutdown removed the owned running preview, then Docker inspection confirmed no runtime remained for that project. The two older exited F01 test containers were verified and removed; unrelated containers were untouched.

The earlier product pass also fixed cross-account lost-create replay, first-brief loss through sign-in/reload, and owned-browser teardown. Their regressions were rerun on this interface; details are in `../ux-system-v2/VERIFICATION.md`.

## Full-system coverage and limits

The pass covers frontend/backend API contracts, authentication/session isolation, database transactions and backup restoration, planning/approval, source generation/validation, Docker containment, build/repair, isolated preview, explicit static-package publication, controlled Vercel protocol, modification/redeployment/history, recovery, concurrency/idempotency, keyboard navigation, responsiveness and accessibility. The matrix is in `FULL_SYSTEM_RELIABILITY.md`.

The five default skips are the three explicit Docker checks and two live-provider checks. Docker and live model ran separately and passed. **Real Vercel acceptance failed at target setup with `RELEASE_PROVIDER_AUTHENTICATION`; public health, redeploy and restoration were not reached.** Earlier Vercel results under `QA/commercial-v1` are historical, not a successful new recheck. Credentials must be refreshed privately before retrying. Production OIDC and production hosting/operations topology remain unverified. Generated apps are browser-state/static-export scope; server-function releases are rejected. Model output can still fail bounded verification or integrity checks; such failures remain explicit and preserve last-good versions. No claim of 100% bug-free software is made.

The remaining warning is Starlette's existing TestClient/httpx deprecation. WCAG audits of the F01 shell exclude generated iframes; the legacy curated sample frames have their own accessibility scans. Production-provider and application-specific user acceptance are separate checks.

Automatic approval review was temporarily unavailable due to an account usage limit. Work continued locally as instructed, then approved Git/Docker/browser operations resumed after reset. No bypass occurred. The temporary block is resolved; the implementation and evidence are pushed only to the existing branch.

## Open for final review

From this repository:

```sh
pnpm build
pnpm open:commercial --production --no-open
```

Open the exact URL printed by the launcher. Earlier review URLs (54821 and 64789) are stopped. Use its test sign-in and follow Create → Plan → Approve → Build → Preview → Publish → Modify → Rebuild → Preview → Redeploy → Versions. This disposable environment uses actual accepted Docker and controlled identity/source/publishing providers, not a public Vercel deployment. Ctrl+C performs scoped runtime cleanup. `scripts/test-m5.py --build-states` runs the opt-in real-worker observation/recovery acceptance. Never merge main automatically.
