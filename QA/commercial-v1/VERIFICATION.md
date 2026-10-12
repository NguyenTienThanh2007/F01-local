# Commercial-v1 acceptance — 2026-10-07

This continuation started from the specified GitHub branch HEAD `8d4aa6051ef74d42d7b4f71736abc61fdef04cfa`. The implementation was committed incrementally and pushed to `codex/f01-commercial-v1`; main remains `449b0588e072cda102144c0c629d776049b4f2d2`. Machine-readable provenance, exact image identity, artifact/release IDs, report timestamps and harness digests are in this directory. This records actual local checks, not an inferred GitHub Actions result.

| Required gate | Observed result |
| --- | --- |
| Backend PostgreSQL regression | 334 passed; four opt-in tests skipped in the default suite and run separately below |
| Strict mypy | Passed across 102 source/test/migration/script files |
| Frontend tests | 61 passed |
| Generated client | 2 passed; OpenAPI/TypeScript drift passed |
| Typecheck / production build | Both passed |
| Browser E2E | Planning/homepage 14, Phase 1 6, signed-in Phase 2A 4, UX0 commands 5, commercial Docker journey 1 passed |
| Browser quality | Four widths 375/768/1280/1440; WCAG A/AA scans, keyboard/focus, reduced motion and 200% reflow passed |
| Exact-image Docker acceptance | 3 passed: containment/resources, signed-in build/repair/change/last-good journey, exact-source production package/root health |
| Live deployment/provider | 1 passed: real Vercel staged package, observed public health, v2 redeploy, previous-package restore, return to v2, history and disposable-project cleanup |
| Public browser | Fresh credential-free browser opened the actual v2 public app, verified its exact marker, hydrated the priority filter and checked zero cookies/page errors |
| Backup/restore | Actual PostgreSQL custom dump/restore retained populated source/release history, exact package bytes/digests and the current migration revision |
| Dedicated Reliability Pass | Cancellation/deadline races, duplicate/unknown responses, stale/foreign context, explicit failure retry, observation recovery, immutable history, routing compensation, global lease capacity and project-before-operation locking passed |

The isolated Docker image is `sha256:c20b9d0f8e0691a9813f14a3fa89abbb50b135fac8fb274fbfee614fa10c9c11`, derived from the exact Phase 2B base `sha256:bf55945a66450b4d747196aed159eba926ca377b66e41400da70c0a54e3363c0`. It was accepted on the local Linux arm64 Docker daemon. Image creation, skipped tests and controlled provider results were never treated as live runtime evidence. Other hosts/images must run acceptance again before enabling execution.

The commercial browser journey uses real Docker builds, packaging and the isolated gateway with synthetic signed-in RSA OIDC and controlled model/deployment responses. The separate live Vercel suite uses real Docker, real Vercel and a real public browser probe. Model generation/planning responses remain explicitly controlled; no live OpenAI or production identity-provider acceptance is claimed. The Vercel test project was removed afterward, so its recorded URL is historical acceptance evidence rather than an ongoing customer site.

## Reproductions and corrections

- Production packaging failed against the copied read-only scaffold and the preview dependency check's original configuration comparison. The separate production helper verifies the immutable scaffold before applying its approved writable configuration. Real Docker package/root-health regression then passed. No existing preview helper or frozen 2B migration was changed.
- An unconfirmed release receipt became unreachable while the server already showed an active operation. Recovery is now visible in that state; the signed-in response-loss/reload browser test confirms the same key/body produces one release.
- A cancellation or deadline crossing during successful public health could still commit production. Both races were reproduced as failing PostgreSQL regressions, then fixed with a fresh authorization/cancel/deadline check under the pointer-commit lock. Compensation leaves the last-good pointer intact.
- Failed commands previously could only converge to their failed record. Reviewed retry creates a new bounded attempt while preserving immutable failure history; unknown dispatches instead resume observations with the original identity. Definite provider rejections and ambiguous response loss have separate tested handling.
- Release publication and cancellation needed one lock order. Publication now takes project before operation; a real PostgreSQL barrier test proves cancellation can acquire the operation while the worker awaits the project. Global lease tests bound concurrent workers.
- Production cleanup could retain a failed container forever. Failed cleanup retains the recorded identity and terminal preparation cleanup is retried; successful/failed preparation evidence remains immutable.
- Real intent depended on whether the executor was currently enabled. Creation now saves real intent in real mode even when runtime support is unavailable, with no invented run/version. Its API regression passed.
- The browser test harness inherited local real-execution configuration. It now explicitly disables real/release execution outside the opt-in commercial fixture. Full Phase 1 browser regression passed afterward.
- The readiness regression restored a hardcoded old Alembic version, contaminating later tests. The real backup/restore test reproduced the wrong revision; readiness now restores the observed original revision and verifies readiness again. The complete suite passed afterward.
- Provider URL validation conservatively rejected distinct Vercel factory/app tenants. The authoritative Public Suffix List confirms the tenant boundary; validation still rejects the exact factory host and all non-provider/unsafe URLs, with regression coverage.

The first browser failures were also isolated to test scheduling: manual worker ticks ran before command confirmation, and interaction ran before preview hydration. Confirmation/load waits now exercise the real workflow without relaxing application validation or iframe isolation.

One existing backend warning concerns Starlette's deprecated httpx TestClient integration. It is not a failing check. CI gates and the runtime/reconciliation runbook are committed in this branch. No merge was performed.
