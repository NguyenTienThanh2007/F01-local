# Dedicated Full-System Reliability Pass

This pass follows the premium UI/authentication implementation. Full final counts, reproductions, limitations and review instructions are in `VERIFICATION.md`; exact product provenance is in `source.json`.

| System boundary | Acceptance / limit |
| --- | --- |
| Frontend/navigation | Production browser journeys, all major routes and 30 visual states; central preview, current stage, next action and one primary workspace action. |
| Authentication/authorization | Signed controlled OIDC, PKCE/state/nonce/browser binding, verified email, expiry/revocation, return recovery, provider error redaction, CSRF and owner-denial regression. Actual Auth0/Google/email delivery remains unverified. |
| Account | Strict owner-scoped GET/PATCH, stable issuer/subject identity, verified-email updates without auto-linking, profile reload and duplicate save. Cross-connection provider identity linking is not implemented or inferred from equal email. |
| Database/API contracts | 355 full backend regressions with disposable PostgreSQL; immutable constraints, locking/fencing, concurrency and backup/restore tests; generated client/OpenAPI drift and strict mypy pass. No migrations changed. |
| Create/planning/approval | Persisted first brief and owner-bound recovery receipt; stale context, explicit approval, quotas, failed model/planning, cancellation, duplicate and lost-response cases. First-time copy no longer implies a live version. |
| AI generation | Existing bounded source contract and validators preserved; malformed/unsafe/stale/unchanged responses remain rejected. Fresh source provider is controlled; preceding real OpenAI acceptance is historical. |
| Docker/build/repair | Three accepted exact-image checks with real containment, repair, isolated preview and packaging; no host mounts/factory secrets, read-only/resource/security policy and immutable lineage retained. |
| Observed execution | 18 contract-fixture states and 13 real persisted worker/Docker states; current-candidate checks, saved sequence, pending/confirmed/failed distinctions and stopped animation for quiet/stale workers. No fake percentages or timelines. |
| Interruption/recovery | Actual owned worker termination, reload during generation, stalled refresh, explicit recovery without blind source replay, failed/canceled build and last-good preview. Existing lease/capacity/fencing and bounded cleanup regressions pass. |
| Preview | Successful current-candidate publication opens isolated verified Preview; historical inspection and capability expiry/reload remain guarded. Replacement failures preserve last-good preview. |
| Deployment/Vercel | Real package bytes/source/version/Brain/target/digest binding; explicit review, unknown-response recovery, staging/health/promotion/reconciliation/compensation and restore regressions use the controlled publisher. Fresh real Vercel remains unverified following previous credential failure. |
| Modification/history | Version 1 → pinned natural-language modification → approved update → real Docker version 2 → preview → controlled redeploy; previous live version preserved until confirmed promotion and immutable history remains navigable. |
| Browser failure/concurrency | Offline/read failures, expired sessions, stale observations, duplicate clicks, uncertain mutation receipts, concurrent backend commands and safe retries are exercised by full regression/browser suites. |
| Local review tooling | Reproduced premature database shutdown and repeated INT/TERM teardown abort; PostgreSQL session isolation and shutdown guards now preserve bounded scoped cleanup. Actual repeated Ctrl+C exits successfully. No global Docker prune or unrelated process shutdown. |
| Responsive/accessibility | Desktop, phone, tablet, 320px and 200%-equivalent reflow; reduced motion, skip link, focus/navigation, readable state text; 174 passing targeted axe checkpoints across product/auth/build-state/actual-worker suites. Two transient Projects loading captures did not run axe. Chrome/axe is not full assistive-technology or device certification. |

The auth/profile and tooling fixes are additive. Existing Project Brain, Build Trace, source/version/Brain binding, immutable evidence, idempotency, sandbox isolation, separate preview origin, reviewed release target and last-good-live guarantees were not weakened. Controlled providers never count as production-provider success.

Public-launch gates: actual configured Auth0 Google/magic-link acceptance and email delivery; valid Vercel target/public-health/redeploy/restore; deployed production topology and operations acceptance. Application-specific accessibility and human usability review remain separate. The user is the final reviewer; PR #1 stays open and unmerged.
