# Generated interface quality

F01 sends the reusable `providers/interface_quality.py` policy to both real context
planning and every source-generation dispatch. It describes product-specific visual
direction, compact controls, primary-content composition, CSS tokens, responsive
behavior, semantic/keyboard access, honest empty/error states, and data-compatible
storage hydration. It does not prescribe a brand, universal sidebar, color palette,
or identical application template. Source protocol/scaffold/security constraints
remain authoritative; diagnostic repair retains unrelated design and functionality.

The TaskPilot v3 sizing regression came from `flex: 1 1 150px` on shared input/select
classes inside vertical flex parents. Flex basis measures the main axis, so the same
rule used for filter widths became form-control height. The policy specifically
directs width distribution to row/grid wrappers and compact sizing to controls.
Provider transport regressions verify this guidance reaches actual request payloads.

## Browser evidence alongside functional acceptance

After a real build has published an isolated local **browser** preview, run:

```sh
# Set the exact private preview URL in your environment; keep capabilities out of Git.
# Optional selector identifies the actual primary working content for this product.
F01_PRIMARY_CONTENT_SELECTOR='[aria-label="Task board"]' \
F01_EDITOR_ACTION='New Task' \
F01_VISUAL_OUTPUT=.runtime/generated-visual \
pnpm --filter @f01/web audit:generated-visual
```

`F01_GENERATED_PREVIEW_URL` must be set privately first. The CLI accepts local browser
previews only, makes no model calls, rewrites no source, and changes no application
records. Four fixed desktop/tablet/mobile/narrow-reflow viewports produce bounded
viewport screenshots, measured geometry/typography and automated WCAG A/AA scans.
Each accessibility scan has a 10-second deadline. The compact-app profile checks
page overflow, ordinary control heights up to 72px, control font sizes at least 14px,
and primary-content placement when an explicit selector is provided. This profile
is appropriate for dashboards/data-entry apps; content-specific exceptions require
review rather than quietly relaxing limits. A missing requested primary selector
fails the measurement instead of inventing layout success.

Reports distinguish deterministic results, axe violations/incomplete checks and
human-review observations. Smaller touch targets, tall textareas and landmark
structure are surfaced for review. Screenshots require human assessment of density,
alignment, hierarchy, aesthetics and product suitability. Passing measurements does
not certify a premium interface, exhaustive accessibility or functional behavior.
An optional `F01_EDITOR_ACTION` opens the named primary button, requires a visible
semantic dialog within five seconds and audits desktop/mobile editor geometry and
contrast. An inert action is recorded as failure with a real screenshot. It changes
no form fields or task records. Run the existing product-specific functional tests, including modal interactions,
empty/error states and persistence, separately. Inspect those states with the same
audit helper as needed; the CLI examines initial state and the configured editor,
not every application interaction/state.

`pnpm --filter @f01/web test:generated-visual:e2e` verifies the measurement harness
against a minimal faithful flex-basis failure and a compact responsive fixture,
including a deliberately overflowing layout. CI runs these harness regressions
after installing Chromium. Those fixtures are **not** generated-app acceptance;
real-provider acceptance reports must identify the real source/version, Docker
evidence, actual preview screenshots, measured API usage and saved-data lineage.

Visual QA is an explicit acceptance tool, not fabricated execution evidence or a
replacement for the trusted build verifier. It does not change sandbox policy,
release availability, publication, source/version/Brain lineage or last-good state.
