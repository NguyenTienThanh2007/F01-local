# Dedicated Full-System Reliability Pass

This pass follows the UX/Build/Journey implementation. It is not public-launch approval or a claim of bug-free software. Exact results and remaining dependencies are in `VERIFICATION.md`, JSON reports and `logs/`.

| Area | Evidence / practical limit |
| --- | --- |
| Frontend / routes / navigation | Full production-browser commercial journey; 27 visual states; every major route; desktop/mobile/tablet/320px/200% reflow; 52 passing WCAG scans and two transient loading captures without axe |
| Build-state presentation | 18 state fixtures, 54 passing browser/axe captures; separate real persisted worker/Docker-state acceptance; motion stops for missing observations, failure and cancellation |
| Backend / contracts / database | Full disposable PostgreSQL regression; generated OpenAPI/client drift; strict mypy; real metadata and package-byte backup restore in the regression |
| Authentication | Signed cryptographic controlled OIDC, HttpOnly credentials, logout, expired/revoked sessions and cross-owner denial; production identity provider remains unverified |
| Create / recover | Initiating-account-bound lost-response receipt; first brief through sign-in/reload; duplicate-click and exact-key recovery browser cases |
| Planning / approve | Context-bound proposed work, stale state, explicit review, provider failure, cancellation, quotas and lost-response recovery; 14 planning / 4 contextual-auth / 7 creation browser checks |
| AI generation | Actual bounded OpenAI plan/source/Docker build; exact source/run/version/Brain references recorded; unsafe, malformed, stale or unchanged proposals remain rejected; no-op repair now has an owned actionable error |
| Docker execution | Accepted exact image, no host mounts/factory secrets, read-only containment/resource/security policy, real build/repair and production-package acceptance |
| Build / repair / workers | Global lease capacity and fencing, duplicate requests, bounded repair, source rejection, deadline/session revocation, provider uncertainty without blind replay, cancellation/cleanup and interrupted worker recovery |
| Preview | Current-candidate evidence, atomic source/Brain/version publication, isolated capability origin, expiry, reload and last-good preservation; successful publication opens Preview automatically |
| Deployment / Vercel | Real package bytes/digests, reviewed target/configuration/version/Brain binding, staging/public-health/promotion/reconciliation/compensation verified with the controlled provider; fresh real Vercel authentication fails, so its public/redeploy/restore stages are unverified |
| Modify / redeploy / history | Real Docker version 1 → source-pinned change → version 2 preview → reviewed package → controlled redeployment; immutable historical inspection and last-good release preservation |
| Failures / recovery | Read/trace races, interruption/offline, reload, unknown command outcome, stale worker, failed provider, cancellation, duplicate click, concurrent requests and restored backup state; scoped test runtimes are removed only after image/project/run/role verification |
| Accessibility / product quality | Keyboard focus containment/return, skip link, mobile navigation, 200% reflow, reduced motion, state text beyond color, actual transient contrast fix, meaningful waiting/error/source rejection states |

The actual quiet-stream failure was reproduced in the browser and PostgreSQL: no new events meant the connection waited for the 15-second heartbeat. The fixed authenticated comment frame confirms transport only; event sequence, application activity, evidence and completion remain untouched. Foreign ownership and expired authorization still fail before any connection comment.

The real-worker failure exercise also exposed a stale cleanup identity after confirmed Docker deletion. Clear that identity only after deletion succeeds; leave it intact on cleanup failure/crash. Regression verifies retry, cleanup recovery, fencing and the unchanged last-good version. Additional worker-state evidence is in `real-states.json` (13 actual states, 26 desktop/mobile captures, passing axe scans).

Known production gates: refresh private Vercel credentials and rerun target/staging/public-health/redeploy/restore; configure/accept production OIDC and production deployment/operations topology. The supported release contract remains browser state with static export. Generated-application-specific user acceptance and accessibility remain separate from factory-shell audits. The default regression's five opt-in skips are run separately: three Docker checks and the two live-provider checks. A passed controlled publisher never counts as real Vercel success.

No migration, source-integrity validator, idempotency/freshness boundary, factory-secret restriction, sandbox containment or deployed-version guarantee was relaxed. PR #1 stays open; never merge main automatically.
