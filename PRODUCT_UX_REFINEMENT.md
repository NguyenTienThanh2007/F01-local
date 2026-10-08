# F01 product UX / visual refinement

This pass continues commercial-v1 on the existing branch. It preserves the paper, ink and terracotta identity, IBM Plex typography, Project Pulse, routes, workspace sections, Project Brain and Build Trace. It changes frontend presentation and guidance; API contracts, release workers, sandbox configuration and immutable evidence remain intact.

## Product changes

- A consistent workspace inset, stronger document titles, clearer paragraph rhythm and restrained ruled panels.
- An aligned project register with readable filters, useful empty states and a separate starting-point shelf.
- A creation composer with a title field, original brief, clear save action and a concise lifecycle guide.
- A review document that takes precedence once a proposal exists. Another planning direction remains available through a disclosure.
- Numbered Build and Production panels. A reviewed build takes precedence over publishing controls; a live current version leads to planning the next update. Publishing that same version again remains available through a disclosure.
- Preview isolation and historical read-only inspection remain visible. Source, package, Brain and version references remain accessible in Details.
- Active mobile tabs scroll into view. Sheets retain focus trapping, Escape and focus restoration. Reduced motion produces static states.

The shared refinements live in `apps/web/src/styles/refinement.css`, loaded after the established surface styles.

## Findings and regression checks

| Reproduction | Root cause | Correction and check |
| --- | --- | --- |
| Hover working dashboard search/filter controls | Old decorative dashboard CSS used a disabled cursor | Correct editing/select affordances; the real-project browser audit checks usable cursor states and opens saved projects |
| Inspect the real Brain after two builds at 375px | Long verification digests in decision headings did not wrap | Document-wide word wrapping; the audit scans the actual post-rebuild Brain at four widths |
| Inspect Versions after deployment | A historical build summary mentioning no deployment was promoted to the current heading | Show version titles and retain the original summary in lineage Details; browser check rejects that misleading heading |
| Open later workspace sections directly on mobile or resize the window | The active tab could remain outside the horizontal navigation viewport | Align the current tab on navigation and resize; every mobile workspace capture checks visibility |
| Review the next plan while an earlier version is live | Build and production could both appear primary | Build readiness sets presentation priority; the reviewed-rebuild audit checks a single visible primary action |
| Follow Trace at 720×500 equivalent 200% reflow | Larger inspector chrome allowed a second scroll container to clip the last event | Follow within both the timeline and its inspector; retain the existing last-event visibility assertion |
| Type a change after reopening Planning, then refresh context | Derived disclosure state could override the user's open editor | Explicit disclosure state with the latest shown proposal tracked separately; signed-in recovery checks visibility and retained input after refresh |
| Inspect the dashboard connection error | Adjacent inline actions had no spacing and creation competed with recovery | Add an action gap, prioritize Retry and exercise recovery back to saved projects |

Homepage, sign-in, dashboard, Brain and the deployment inspector also had historical Simulation-only language. The updated copy distinguishes saved versions, observed execution and production release history. The homepage sample remains explicitly illustrative; creating a draft or saving a brief still starts no build.

## Verification

Final results and screenshots are recorded in [QA/product-refinement/VERIFICATION.md](QA/product-refinement/VERIFICATION.md). The opt-in route audit runs within the commercial browser harness:

```sh
F01_VISUAL_AUDIT=1 pnpm test:commercial
```

The harness uses disposable storage, controlled identity/model/deployment fixtures and the accepted local Docker image. It runs actual builds, production packaging and isolated previews. This visual pass does not claim a new live-provider deployment; earlier live Vercel acceptance remains in `QA/commercial-v1`.
