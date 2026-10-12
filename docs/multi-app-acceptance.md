# Generalized multi-app acceptance

TaskPilot proved one task-board app end to end. This kit checks whether F01 can build
**different classes** of browser applications through its normal create → plan →
approve → trusted Docker build/repair → isolated preview path, using real model
output that nobody edits by hand.

## Scenarios

`QA/multi-app/scenarios.json` is the single catalog for the Python live runner and the
browser checker:

| Scenario | Class | What the browser checks exercise |
| --- | --- | --- |
| `analytics-dashboard` | data dashboard | visible "Sample data" label, ≥4 numeric KPIs, labelled SVG revenue trend, top-products table, Date range and Region filters that really change KPIs/chart |
| `storefront` | e-commerce | "Sample catalog" label, ≥6 priced products, search → "No products" → Clear filters, category filter, details dialog with Escape/focus return, add to cart, accurate subtotal, remove, cart survives reload |
| `social-profile` | social | "Sample profile" label, name heading, Follow toggle with aria-pressed and follower count, empty post rejected, new post first, Like toggle and count, post/like survive reload |

Each brief ends with a short **interface contract**: the exact accessible names the
checker uses (for example `Search products` or `Cart (2)`). The contract tells the
model what is tested; it does not supply source, layout, styling or a template. A
regression test asserts every name the checker relies on appears in its brief.

Every scenario also runs the existing four-width visual audit and axe WCAG A/AA scan,
and fails on uncaught exceptions, console errors, failed responses or **any request
outside the preview origin**. Builds and previews have no network access, so remote
images/fonts/APIs are a real defect, not a cosmetic one.

## Running it (spends money)

Prerequisites: an OpenAI key in `apps/api/.env`, a passing exact-image Docker
acceptance report in `.runtime/` (see [COMMERCIAL_V1.md](../COMMERCIAL_V1.md)), the
worker Docker socket, and Chromium for Playwright. Check without spending:

```sh
apps/api/.venv/bin/python scripts/test-multi-app-live.py --max-usd 1.50 --dry-run
```

Then run all three scenarios under one shared ceiling:

```sh
apps/api/.venv/bin/python scripts/test-multi-app-live.py --max-usd 1.50
# compare a stronger supported model with the same scenarios and its own ceiling
apps/api/.venv/bin/python scripts/test-multi-app-live.py --model gpt-4.1 --max-usd 4.00
```

`--max-usd` is required and is the explicit spending authorization (hard maximum
$5.00, 40 calls). Before each request the guard reserves the worst case from request
size and `max_output_tokens` at standard prices (gpt-4.1-mini $0.40/$1.60, gpt-4.1
$2.00/$8.00 per million input/output tokens). A completed response settles to its
observed usage; an unknown outcome keeps its full reservation. Unpriced models fail
before dispatch. Reaching the ceiling stops the run and is reported as `budget_limit`.

Each scenario gets a fresh disposable PostgreSQL database; its containers are removed
afterwards. Evidence lands in `.runtime/multi-app/<timestamp>-<model>/`:
`summary.md`/`summary.json`, the shared `usage.json` journal, and per scenario
`model-report.json` plus `browser/acceptance.json` and screenshots. Failures are
categorized by first failed stage: `planning:*`, `build:<error code>`,
`browser:functional|visual|accessibility|runtime` or `budget_limit`.

To re-check an already running preview without any model call:

```sh
F01_GENERATED_PREVIEW_URL=<private local preview URL> F01_ACCEPTANCE_SCENARIO=storefront \
  pnpm --filter @f01/web audit:generated-app
```

## What it does and does not prove

`pnpm --filter @f01/web test:generated-apps:e2e` (in CI) runs the checker against
small **hand-written harness fixtures**: one conforming page per scenario plus broken
variants (unlabelled sample data, inert filter, inert add-to-cart, cart lost on
reload, remote image, like without state) and nested product markup. Those prove the checker catches real
defects. They are not generated applications and are never evidence of model quality.

Only a live run produces generation evidence. Passing checks still do not certify
premium design: review the screenshots. One run per scenario is a sample, not a
reliability rate; repeat runs before drawing conclusions about a model.
