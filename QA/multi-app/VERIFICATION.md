# Multi-app acceptance kit — 12 October 2026

Continued from remote `codex/f01-commercial-v1` HEAD `c3d6df7` (CI green on that commit)
in a cloud Linux x86_64 container, on branch `claude/focused-wozniak-qvr5qb`. Main
(`449b058`) and PR #1 are unchanged. Nothing was reset, rewritten or force-pushed.

## What this pass changed

1. **Generation guidance (RISK addressed).** Source instructions and planning runtime
   capabilities did not say that builds and previews have no network. That is a
   deterministic platform constraint: sandbox containers run `NetworkMode: none`, the
   scaffold `next.config.mjs` configures no remote image hosts, and the preview CSP
   allows only same-origin and `data:` resources. Storefront and social briefs invite
   remote photos, Google fonts and remote `next/image`; those cannot load or build.
   The guidance now says so and directs CSS/inline SVG/initials. It also requires
   requested demonstration data to be deterministic and visibly labelled as sample
   content. Provider-payload and planning-context regressions assert both.
   This is a policy change; its effect on real model output is **not yet measured**.
2. **Multi-app acceptance kit** — see [docs/multi-app-acceptance.md](../../docs/multi-app-acceptance.md):
   scenario catalog (dashboard, storefront, social profile), generic contract-driven
   browser checker, labelled harness fixtures, per-model budget guard with a shared
   journal, scenario support in the existing live model test (real gateway on
   loopback + browser checks), failure categories, and the
   `scripts/test-multi-app-live.py` orchestrator. CI runs the harness regressions.

## Evidence in this environment

| Check | Result |
| --- | --- |
| Backend pytest (fresh disposable PostgreSQL) | 402 passed, 5 opt-in skips; 3 tooling tests fail only because `initdb` refuses root here — rerun unprivileged: 16/16 passed |
| Strict mypy | 118 source files, no issues |
| Frontend unit / client / contract drift | 105 / 2 passed; OpenAPI and TypeScript contracts current |
| Typecheck / production build | Passed / passed (baseline) |
| Planning browser e2e, theme, conversation recovery, build experience | 14, 1, 1, 1 passed (baseline, Chromium 1194 aliased for Playwright 1.58.2) |
| Generated visual harness | 5 passed |
| **New** multi-app checker harness | 10 passed: 3 conforming fixtures pass all checks; 6 broken variants fail exactly the intended checks; nested product markup is counted once |
| **New** backend tests (budget guard, catalog contract, failure classification, run summary, loopback gateway) | 21 added, all passing (included in the 402) |
| UX0 and auth signed-in browser suites | **Not run locally** — need root `initdb` or an unprivileged pnpm install; left to CI |

## External blockers (honest status)

- **Real OpenAI:** no API key in this environment and no spending authorization. No
  provider call was made; $0 spent. The dry run reports `PROVIDER_NOT_CONFIGURED`.
- **Real Docker:** a daemon could be started and the trusted `next-web-v1` image
  built from a scratch recipe copy (CA bind-mounted for build steps only), but
  F01's prerequisite probe correctly refused it: this host uses **cgroup v1**, and
  generated code requires cgroup v2 limits (`SANDBOX_POLICY_UNSUPPORTED`). The policy
  was not relaxed. No Docker acceptance, generated build or preview was produced here.
- **Vercel, production OIDC/Google/email:** not exercised.

No generated application exists from this pass. The harness fixtures are hand-written
test pages and are not evidence of F01's generation quality.

## Next step for the founder

On the Mac with the accepted image and key, run
`scripts/test-multi-app-live.py --max-usd 1.50 --dry-run`, then without `--dry-run`.
Review `summary.md` and the screenshots, then decide on prompt fixes per failure
category, and only afterwards whether to compare `--model gpt-4.1`.
