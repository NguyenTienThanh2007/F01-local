# F01 — Frontend design milestone

Completed on 2026-10-01. Frontend presentation only. Stopped after the redesign.

## Audit and hierarchy

The initial homepage redirected to a dashboard, scaffold notices occupied primary
space, and brief/result surfaces had weak hierarchy. The redesign uses an
interface-first entry, a dominant brief composer, numbered plan documents, a
functional three-stroke Pulse, and a deliberate empty workspace. IBM Plex, paper,
ink, terracotta, subtle borders and restrained radii remain the visual foundation.

## Pages and components

| Surface | Change |
| --- | --- |
| `/` | Editorial outcome headline, real composer, labeled workspace/Trace sample, selectable CRM/booking/game directions, availability-labeled Create → Run → Manage → Evolve |
| `/projects` | Control-center hierarchy, intentional empty register, disabled/explained inventory tools, starter artifacts and real preset navigation |
| `/projects/new` | Dominant brief, planning guide, preset selection and structured plan document |
| Shared shell | Home/start navigation, refined rail typography and accessible contrast |
| Loading/error boundaries | Workspace-shaped skeleton and clear recovery surface |
| Development showcase | All seven Pulse presentation states plus existing lifecycle aliases |

New: `first-time/product-entry.tsx`, `first-time/lifecycle-demo.tsx`,
`project-planning/project-starters.tsx`, and the product layout stylesheet
`styles/experience.css`. Reworked: `ProjectPlanningForm`, `PlanView`,
`ProjectPulse`, `ProductShell`, the button loading signal, and route presentations.

The existing submit/validation/timeout/cancel/retry/error machinery is retained.
The homepage uses the same form and `/api/v1/plan` server integration. Briefs and
plans still live only in page memory. Preset IDs are the only new query values;
arbitrary user briefs are never placed in URLs or persisted by this milestone.

## Verified boundary

Backend source/configuration/tests/migrations/lockfile, API contracts, frontend
planning server route and transport, authentication module and persistence were
compared with a protected baseline and remain unchanged. No backend test rerun or
migration was required. No production authentication, saved-project UI connection,
new deployment, runtime, billing, team, visual-editing or outcome functionality
was added. Product/architecture/roadmap documents remain unchanged;
`DESIGN_SYSTEM.md` and README describe the visual update.

## Validation

- `pnpm typecheck`: passed.
- `pnpm test:web`: 24 tests passed.
- `pnpm build`: passed.
- `pnpm test:e2e`: 11 browser scenarios passed (12 reported including parent).
- Browser coverage includes real frontend HTTP routing to a controlled backend,
  all six plan sections, input validation/preservation, cancellation, retry,
  HTML-safe output, credential absence from browser code, starter selection and
  navigation, bounded demo/Pause/Play/Replay, reduced motion, and mobile dialog
  keyboard focus restoration.
- Homepage, dashboard and create page: screenshots reviewed at 375, 768, 1280 and
  1440 pixels; no horizontal overflow. The successful plan was also captured at
  all four widths. Visible focus and readable status labels remain.
- Temporary axe-core WCAG A/AA scans: zero reported violations across 12 route/width
  combinations and the desktop plan result after the rail contrast fix.
- Create page at 200% CSS zoom: no horizontal overflow.

Browser tests use controlled responses and synthetic credentials. No live OpenAI
call was made. Accessibility scans cover the tested surfaces and are not a claim
of complete certification. Temporary audit dependencies are excluded from source.

## Deliberate demonstrations and limits

The homepage sample interfaces, counts, names, timestamps and five Trace events are
illustrations labeled as a visual demonstration. They are not saved projects,
generated applications, builds, logs, versions or deployments. Timers update only
presentation, play once and stop; they never call an API. Reduced motion starts the
sequence static. Project Brain, release controls and natural-language evolution
are presented as product direction. Dashboard search/filter remain disabled until
inventory is connected; no fictional project data is shown as actual inventory.

## Run locally

Follow README for the existing local configuration. Merge the archive into your
local `F01-local`, preserving environment files, run `pnpm install --frozen-lockfile`,
and restart the frontend. This milestone needs no database migration or backend
configuration change. Visit `/`, `/projects`, and `/projects/new`.
