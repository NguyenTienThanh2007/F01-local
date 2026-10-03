# F01 — Implementation roadmap

Status: Phase 1 M0–M6 and Phase 2A complete; remaining Phase 2B execution path implemented with application checks passing, Docker/browser acceptance pending. Phase 2C has not begun.
Revision: 0.14 · 2026-10-03
Related: [Product specification](PRODUCT_SPEC.md), [Architecture](ARCHITECTURE.md), [Design system](DESIGN_SYSTEM.md).

## 1. Current checkpoint

Phase 2B now includes a trusted runtime recipe, Docker adapter, leased jobs, source/evidence persistence, bounded repairs, atomic source/version/Brain publication, isolated preview gateway and honest workspace integration. Available checks pass: 289 backend tests (2 Docker tests skipped), strict mypy, 52 frontend tests, generated-client drift/transport, typecheck, factory production build and Phase 2A migration preservation. Real execution remains disabled until a passing Docker acceptance report matches the exact provisioned image. This Work environment has no Docker executable/socket; actual containment, the real Docker journey, interactive browser acceptance and live provider verification remain pending. Phase 2A remains the latest accepted stage. See [PHASE2B_IMPLEMENTATION.md](PHASE2B_IMPLEMENTATION.md).

M0 planning documents, the M1 shell, M2 persistence, the M3 projects journey, M4 workspace foundations, M5 persistent simulations and M6 quality/acceptance are implemented. The dashboard now reads saved projects through the generated M2 client. Creation persists title/brief with a stable recovery key; project metadata can be renamed or archived/unarchived when the active-run invariant permits it. The redesigned interface and standalone draft planner are preserved. Phase 1 is complete; Phase 2A identity and contextual planning are implemented. Simulation history remains available alongside the new gated real-run path. Production deployment remains unavailable. The implementation continues repository commit `167c023`.

The founder authorized M3 after M2 and the homepage identity passes, then M4, M5 and M6 separately. The standalone OpenAI planning extension remains separate from deterministic initial Brain creation. An unresolved create command retains its exact key/input in tab session storage until confirmed; this is no project database. M4 adds context-bound request recording and event/version reads through the generated client. Backend ownership, frozen persistence schema/migration, project creation, metadata ETags and explicit local development authentication remain compatible; verified OIDC is the production identity boundary.

At the Phase 1 checkpoint the endpoint was stateless and protected by the development token. Phase 2A preserves its input/output contract and adds authenticated sessions and server usage accounting. It does not advance the simulated lifecycle, create projects, write Brain revisions or trigger code execution. The frontend holds a draft only in page memory. Its server route loads the shared development token privately, restricts same-origin JSON submissions to the fixed backend planning endpoint, validates the response, and returns static sanitized errors. Backend provider credentials stay backend-only. Frontend checks include strict TypeScript, proxy/configuration tests, a production build, browser submission/loading/validation/error/retry/cancel tests, responsive inspection, and a browser-bundle credential check. Backend code is unchanged by the frontend milestone. Report a real provider success only if a live call actually succeeds. F01 remains an internal codename.

| Delivery layer | Checkpoint |
| --- | --- |
| Current implementation/workstream | Phase 2B execution and acceptance harness implemented; 289 backend tests passed with 2 Docker tests skipped, strict mypy across 71 files, 52 frontend tests, 2 client transport tests, typecheck, factory build, drift and migration checks passed. Real execution stays gated; Docker and browser acceptance remain unverified. Earlier milestone counts below are historical. |
| Near-term plan | Provision the exact trusted image and complete Docker containment, real execution and browser acceptance for Phase 2B. Phase 1 and Phase 2A retain their accepted status. Stop before Phase 2C. |
| Long-term architecture | A–K below describes future product capabilities and dependencies; it adds no implementation work, schema, routes, hosting, team access, or execution now. |

## 2. Operating rule for every implementation milestone

1. Read the relevant source-of-truth sections and inspect existing code, configuration, migrations, and applicable repository instructions.
2. Implement only the milestone's scope, using the established contracts and tokens.
3. Type-check strict TypeScript and the touched Python boundaries; regenerate/check the client when API schemas change.
4. Build the web application and validate API startup/imports/configuration. If schema changes, apply migrations to a clean PostgreSQL test database and verify upgrade behavior from the prior milestone.
5. Run meaningful domain, integration, interaction, and end-to-end tests appropriate to the changes. Inspect actual UI states for visual work.
6. Fix failures and rerun the affected checks. Expand checks when a failure, new change, or unresolved concern warrants it.
7. Summarize the exact files/behavior changed, checks and results, limitations, and any document revisions.
8. Continue to the next milestone only after this one is stable. A stable milestone may expose explicitly labeled future capabilities; it cannot pretend unfinished behavior works.

After the initial plan is approved, routine reversible implementation can progress milestone by milestone without asking for repeated permission. A material scope/design change is documented and raised before dependent work. Deployment or public launch is a separate later task.

## 3. Phase 1 milestones

### M0 — Product and system plan

Deliverables: `PRODUCT_SPEC.md`, `ARCHITECTURE.md`, `ROADMAP.md`, `DESIGN_SYSTEM.md`.

Acceptance: all requested Phase 1 capabilities are mapped; excluded capabilities are explicit; statuses, models, routes, contracts, and tokens agree across documents. Present the plan and stop before implementation.

Validation: document consistency, internal links, schema/endpoint coverage, proposed color contrast. There is no application to type-check, build, or test at M0.

### M1 — Repository, design tokens, and authentication-ready shell

Inspect: approved design system, runtime availability, repository instructions, dependency compatibility, and any new code added since M0.

Implement: proposed web/API workspace setup, strict TypeScript, Python config skeleton, lockfiles, non-secret `.env.example`, semantic tokens, typography, essential accessible UI primitives, responsive rail/header/navigation, Pulse states, loading/error/not-found boundaries, and server-only identity interface. The development entry is explicitly labeled; real sign-in remains unconnected.

Acceptance: shell works at desktop and phone widths; keyboard focus and drawers are correct; the design remains recognizable without the codename; no fake sign-in form or undocumented colors. Production startup rejects development identity configuration. Placeholder pages explicitly describe their current state.

Checks: TypeScript/Python configuration checks, web build, API startup/config guard, and focused keyboard/interaction tests for complex primitives. Manually inspect 375px, 768px, and 1440px widths and reduced motion. Verify proposed font licensing before bundling.

### M2 — PostgreSQL domain, persistence, and core API

Status: implemented and verified. Delivery includes session/capabilities, readiness, core project create/read/list/PATCH, request history, Brain/current-selected revision reads, revision history, workspace snapshots, and a generated server-only TypeScript transport. Creation commits the initial records and replay response together. Unknown Brain schemas have an explicit safe error. Archive/unarchive is available for projects without active runs; cancellation remains M5. No M3 UI or M4/M5 commands were added.

Inspect: M1 scaffolding, API boundary, environment validation, and database access patterns.

Implement: Alembic migrations for the nine proposed tables; ownership resolution; validated Brain schema; transaction services; project create/read/list/settings; initial request/revision creation; workspace snapshot; request/Brain reads; standardized errors; metadata ETags; idempotent create commands; OpenAPI-derived TypeScript client. Define state-transition functions and active-run invariants. Actual fixture ticking remains M5.

Acceptance: a created project and its initial records persist through API restart; duplicate creation cannot create two projects; foreign-owned IDs return not found; project-scoped references cannot point into another project; archived/active-run constraints hold. Queued simulation is explicitly pending until the runner is added in M5.

Checks: clean migration plus upgrade path; PostgreSQL integration tests for atomic creation/rollback, ownership, active-run uniqueness, idempotency concurrency, ETags, and consistent snapshot sequence; schema/client generation drift check. Web type-check/build must remain clean.

### M3 — Projects dashboard and creation journey

Status: implemented and verified. Real API-backed dashboard, optional title/original brief creation, stable idempotency recovery (including reload), URL filters/pagination, rename and archive/unarchive controls, ETag conflict review and all loading/error/empty states. At M3 completion, `/projects/{id}` was only a saved metadata/settings record; M4 now extends it into the workspace described below. New M2 projects have queued active runs and cannot be archived until those runs end; no M5 cancellation or simulation was added. The test journey ends its disposable run fixture directly before testing archive/unarchive. Checks: 30 frontend tests, strict typecheck, production build, 13 planning/homepage regression scenarios, real PostgreSQL/API browser journey and twelve responsive/accessibility surfaces. Backend/generated client unchanged; no backend test rerun was required.

Inspect: M2 API/client, session capability flags, shell, form primitives, and loading/error handling.

Implement: real project listing, title/brief form, example briefs, search/status/archive filters, navigation after confirmed save, rename/archive/unarchive controls, and inline pending/error/retry states. Creation shows the demo boundary before submission and uses a stable idempotency key until its outcome is known.

Acceptance: create, reload, find, rename, archive, and reopen the same persisted project. Long briefs and titles remain readable. Failed submissions retain text; a lost response can be retried safely. No localStorage project database or hardcoded dashboard inventory.

Checks: form and filter interaction tests; one API-connected create/reload/settings journey; input-preservation and duplicate-submit cases; visual review of empty, loading, populated, and unavailable-API states; type-check/build/API tests affected by changes.

### M4 — Workspace, Project Brain, request history, and preview foundation

Status: implemented and verified. Shared persisted preview-first project layout and subroutes; immutable Brain sections/revision selection/provenance; original brief and request history; idempotent context-bound change recording without execution or Brain changes; ordered Activity and read-only Versions foundations; persistent inspector/request/viewport UI state; truthful capability placeholders. Independent HTML fixtures work under `allow-scripts` only with restrictive CSP. Projects without completed versions show preview pending; synthetic samples stay in a labeled development showcase. Checks: typecheck/build, 36 frontend tests, 105 relevant backend tests (persistence and planning), mypy across 40 files, OpenAPI/client drift and 2 transport tests, 8 M4 browser scenarios (9 including parent), the M3 persistence journey and 13 planning/homepage regressions (14 including parent). Six project surfaces passed four responsive widths and WCAG A/AA scans. Active-run and stale-context guards remain enforced; fixture state changes are disposable test setup only. Stopped before M5.

Inspect: project layout, snapshot/client data flow, Brain schema, shared navigation, and current routes.

Implement: preview-first workspace, project header, persistent navigation, collapsible utility/request areas, original brief and Brain pages, provenance and revision selection, immutable request recording with base context, activity/versions foundations, capability placeholders, and bundled synthetic CRM/generic preview frames. Before M5 completion, a project without a successful version explains that its preview is pending; fixtures can be inspected in a labeled development-only component showcase.

Acceptance: the workspace operates as a development environment; requests are secondary. Original brief survives changes. Stale requests retain their text and require review of current context. Panel state is stable across project subroutes. Sample previews cannot access factory identity or navigate the top frame. Missing source files/logs/deployment capabilities are explained plainly.

Checks: request history and stale-context integration tests; Brain revision rendering and unknown-schema handling; keyboard/focus tests; iframe CSP/sandbox test against the pinned Next.js runtime; responsive inspection and type-check/build. If preview assets fail in an opaque-origin iframe, resolve isolation before continuing; do not relax the sandbox silently.

### M5 — Persistent simulation, Build Trace, versions, and recovery

Status: implemented and verified. Versioned deterministic scenarios, lifespan due-step loop, persisted cursor/events, atomic Brain/version/internal-deployment publication, run start/history/details/cancel/retry, SSE replay and polling fallback, sequence-gap recovery, phase-grouped Trace and issue/repair links. Optional saved-change simulations, command recovery, historical inspection and prior-success preview preservation are integrated. No real source, tests, fixes, commits or external deployment. All requested transaction/recovery/stream/browser checks passed; stopped before M6.

Inspect: transition services, run constraints, transaction locking order, snapshot high-water sequence, Trace reducer, and preview descriptors.

Implement: versioned fixture scenarios; server-owned due-step loop; run start/cancel/retry endpoints; persisted ordered events; SSE replay and polling fallback; Trace phase groups and issue/repair links; terminal version/Brain/deployment publication; version inspection; current-version preview. Connect the saved change flow to optional demonstration runs with honest support/unchanged-preview disclosure.

Acceptance: normal success, recoverable sample failure, terminal failure, retry, and cancel are demonstrable. Restart resumes from persisted state; refresh or a second tab agrees with the first. Duplicate ticks/replayed events do not duplicate outcomes. Failure preserves the prior successful preview; selecting history does not change current Brain. No event asserts real code execution, test evidence, commit, fix, or external deployment.

Checks: controlled-clock scenario tests; PostgreSQL atomic publication and duplicate-step tests; restart/replay and sequence-gap recovery; success/cancel race; stale retry/input conflict; unauthorized/expired stream; unknown scenario version; polling fallback; one end-to-end create→success→change→failed update→retry journey. Type-check/build and inspect Trace follow/scroll behavior.

### M6 — Product quality, accessibility, and foundation acceptance

Status: implemented and verified. Final persisted lifecycle/metadata journey, all workspace surfaces with long content, responsive/accessibility scans, modal/skip-link keyboard review, 200% reflow, reduced motion, offline/manual reconnect, historical selection and ownership denial passed. M3–M5/planning regressions, full frontend/backend suites, mypy, contract drift, typecheck/build and persisted restart recovery passed. No Phase 2 implementation was added. See M6_IMPLEMENTATION.md for evidence and exact changes.

Inspect: complete journeys, unresolved issues from M1–M5, token consistency, environment guard behavior, and acceptance criteria in all documents.

Implement: fix observed usability/layout/consistency issues; improve meaningful loading states; eliminate inaccessible controls, hidden overflow, duplicated styles, noisy animation, and misleading demo claims. Document local setup, environment configuration, test commands, migration procedure, and known Phase 1 limits in the relevant source-of-truth sections or a small implementation README when implementation is authorized.

Acceptance: all Phase 1 journeys below pass with actual persisted records. UI remains usable at 200% zoom and reduced motion. Build Trace, Brain, and version metadata agree. No unresolved critical persistence, ownership, accessibility, or input-loss defect. No public commercial release is implied.

Checks: final integrated test suite and production web build; backend type/startup/migration checks; automated accessibility scan plus manual keyboard and focus review; responsive visual inspection at 375px, 768px, 1280px, and 1440px. Measure load/stream behavior on a documented local/private baseline and fix obvious regressions; do not claim an unmeasured performance SLA.

## 4. Final Phase 1 acceptance matrix

| Scenario | Required result |
| --- | --- |
| Create CRM project | Saved original brief, scaffold provenance, queued run, workspace URL |
| Simulated success | Ordered phases/events, immutable output Brain revision, version 1, Live · Demo preview |
| Generic brief | Brief preserved; generic scaffold/sample explicitly identified |
| Reload / second tab | Same project, current state, and ordered history; no recreated records |
| Backend restart during build | Resume committed cursor; no lost/duplicated outcome |
| Connection loss | Existing content retained; replay or polling catches up without order corruption |
| Lost create response / duplicate submit | Original project returned for same key/input |
| Recoverable sample failure | Failure and linked repair remain visible; completion is still labeled simulated |
| Terminal update failure | Needs attention; previous successful preview remains available |
| Retry | New linked attempt; old attempt retained; frozen context revalidated |
| Cancel racing with success | Exactly one committed terminal result; no post-cancel version |
| Change request | Original brief untouched; saved request linked to base Brain/version |
| Unsupported change | Saved text preserved; sample preview explicitly unchanged |
| Stale change | Conflict explained; draft retained for review/resubmit |
| Older version selection | Historical preview inspected; current project pointers unchanged |
| Archive / unarchive | Dashboard visibility changes; project history retained |
| Unauthorized project/stream | No data returned; foreign project indistinguishable from missing |
| Keyboard / zoom / mobile | Controls reachable, focus restored, layout usable, statuses readable |
| Production + development identity | Both applications reject unsafe configuration |

Use deterministic scenarios and synthetic data. Do not test cosmetic wrappers simply to increase test counts. Do not create unnecessary tests for the planning Markdown itself.

## 5. Phase 2A checkpoint and subsequent stages

| Phase | Objective | Gate before proceeding |
| --- | --- | --- |
| 2A: Production identity + context-aware real planning | Verified owner/session integration; real project/change plans assembled from authorized Brain/request/version context; provider-independent planning | Ownership/session/CSRF checks; immutable validated proposals and provenance; stale-context review; bounded usage/time; distinction between proposed and completed work |
| 2B: Real code generation → isolated sandbox → build → test → automatic repair → real preview | Actual source/artifact versions; durable execution orchestration; observed verification and bounded repairs; running generated-app preview | Execution containment, resource/network/secrets limits; cancellation/restart/deduplication; artifact and evidence provenance; real preview isolation; supported-stack acceptance journey |
| 2C: Real deployment → public URL → versions → modify existing app → redeploy | Promote a verified artifact to production; release history; context-bound incremental changes to existing source through the 2B pipeline | Actual release/health evidence; deployment credential isolation; stale-base checks; last working release preserved; migration/recovery and owner release policy |
| 3: Commercial SaaS | Billing/quotas, future team seats, support/operations, backups, deletion/retention, organization/workspace tenancy | Restore and incident drills; usage controls; multi-user authorization; product reliability; clearly defined support and data obligations |
| Later categories | SaaS workflows, dashboards, internal tools, simple browser games; mobile/advanced games later | Reliable web lifecycle first; category-specific validation and deployment strategy |

OpenAI, Claude, Gemini, or another provider can be connected behind the same domain-oriented model contract. There is no requirement to implement every provider immediately, and no provider should own stored project state or the lifecycle protocol. Generated-project deployment may use Vercel or another suitable provider; this decision is deferred.

### Phase 2 stage gates

The implementation order is 2A → 2B → 2C after Phase 1 acceptance. M6 completed that acceptance gate; Phase 2A is now implemented and verified. Phase 2B implementation is present but its Docker/browser acceptance gate is pending. Each stage needs its own bounded implementation plan and verification before the next begins.

**2A:** Replace the private development principal with verified production identity/session handling. Preserve stable project/history identifiers through an explicitly verified ownership migration. Keep authorization server-owned and test cross-user project, request, Brain, version and stream access. Assemble context from the original brief, current Brain, relevant immutable requests and selected version; include source summaries only when actual source exists. Persist validated planning proposals with provider/provenance and exact Brain/version bases. Review/publication must recheck those bases; provider failure, cancellation or conflict preserves the draft and original brief. Retain the standalone /v1/plan integration while introducing project-aware planning separately. Complete a signed-in create/reopen → real plan → context-aware change plan journey, session expiry/revocation, stale-plan, provider-error and budget tests. No generation or execution belongs to 2A.

**2B:** Begin with one explicitly supported web application stack and define its real build/test recipe. Generate actual source from the accepted plan, preserve immutable source/candidate/artifact lineage and execute only in a scoped sandbox. Durable orchestration must handle restart, deduplication, retry and cancellation; the queue/worker technology is an implementation decision, not a requirement to use Redis. Validate isolation and CPU/memory/disk/process/network/secret limits before executing generated code. Record actual commands, exit status, sanitized logs and verification outcomes. Repair observed failures within bounded attempts/time/resources and stop honestly when exhausted. Publish a real running preview from the verified artifact; failure retains the prior verified preview. Complete plan → source → isolated build/test → deliberate failure → repair → working preview, plus containment, cleanup, restart/cancel and exhausted-repair tests. Production deployment remains 2C.

**2C:** Use a release adapter to deploy the reviewed immutable artifact and record the observed public URL, release version and health. Separate production and preview data/configuration and keep release credentials out of generated code/build workers. Bind release decisions to source, evidence and relevant configuration; recheck permissions and current base before promotion. A change request plans and patches the existing pinned app through the 2B pipeline, preserving unrelated behavior and original history. Complete deploy → working public URL → request change → verified preview → redeploy → inspect old release, including failed update, stale-base, deployment failure, duplicate command and safe recovery tests. Define migration compatibility and recovery explicitly; code rollback alone cannot undo data or external effects.

Simulation history remains labeled and inspectable throughout these stages. Real runs gain their own observed execution provenance; they never relabel old fixture events as real evidence. Teams, connectors, billing, visual editing and outcome automation remain later work. Production identity in 2A is not the commercial SaaS launch gate.

### Long-term platform capability stages A–K

The product evolves toward “Create, run, manage and evolve your software in one place”: Idea → Plan → Build → Verify → Preview → Deploy → Run → Manage → Modify → Version → Monitor → Improve. Letters identify future capability stages, not replacements for M0–M6 or the existing 2A–2C implementation ordering. Some foundations already overlap with Phase 1; completion of the simulated foundation does not establish real execution, hosting, or collaboration.

| Stage | Future deliverable | Existing roadmap relationship and gate |
| --- | --- | --- |
| Phase A — AI planning | Validated product plans through the provider abstraction; later context-aware change planning | The current endpoint/frontend extension supplies the first draft-planning slice. Further planning uses 2A identity, context, and usage-budget gates. |
| Phase B — Persistent projects | Durable requests, stable project identity for future teams, immutable Brain revisions, Trace, and history | Existing M2–M6 remain single-owner and simulated. Preserve stable project/user IDs and centralized authorization seams; team tables and Brain persistence are not added by this task. |
| Phase C — Code generation | Repository/source artifacts and bounded patches to an existing version | Extends 2B after persistent context. Validate paths and diffs; do not execute generated code or install its dependencies before Phase D isolation is established. |
| Phase D — Isolated build/test/fix | Per-build sandbox, resource/network limits, durable jobs, verification evidence, bounded automatic repairs | Implements 2B execution gates. Demonstrate containment, cancellation/restart, cleanup, credential isolation, and controlled retry behavior before real user-code execution. |
| Phase E — Live preview | Running generated application, responsive views, candidate-specific preview environment | Completes 2B after D; fixture previews do not satisfy this stage. Validate access/isolation, evidence, and preview data/environment separation before 2C promotion. |
| Phase F — Deployment and versions | Managed preview/production releases, immutable source/artifact lineage, significant-change versions, promotion and safe rollback | Extends 2C; require verification, an approval/release policy, migration recovery, separated credentials, and basic health/log visibility. Initial approval can be single-owner; team approvals follow G. |
| Phase G — Project management/control center | Overview, Changes, Versions, Deployments, Brain and Settings around the existing product; organization/team workspaces, invitations, memberships, scoped roles, discussions and review workflows | Requires production identity, a tested owner-to-workspace migration, centralized action authorization, actor attribution, stale-review invalidation, deployment permissions, and tenant-isolation tests. Shared Brain/Trace are canonical, not copied per member. |
| Phase H — Runtime/logs/environment/database controls | Health/log/error inspection; authorized restart/redeploy; preview/production configuration and write-only secrets; schema/migration/safe data tools; domain management | Builds on F/G release and authorization boundaries. Require log redaction, environment isolation, backups/recovery, scoped operational capabilities, audited mutations, and domain ownership verification. |
| Phase I — Visual editing | Version-aware element selection mapped to source, scoped natural language edits, and element-anchored comments | Requires reliable preview inspection metadata/channel, permission checks, stale/ambiguous selection handling, and reuse of verification/review/new-preview flow. No direct production DOM mutation. |
| Phase J — Monitoring and maintenance | Production telemetry, incident evidence, maintenance proposals, and reviewed repairs to existing software | Extends existing natural language modification; requires trustworthy monitoring, alert/action budgets, incident auditability, and safe release/recovery. Basic production health must already exist in F. |
| Phase K — Outcome-driven autonomous improvement | Outcome Engine, Metrics layer, experiments, and a bounded improvement loop | Requires J's reliable observations and established verification, approvals, rollback, and tenant boundaries; detailed O1–O4 gates below govern progression. |

This update implements no additional stage functionality. Each future stage needs a concrete implementation proposal and its gate checks. The control center's sections are logical future capabilities, not new Phase 1 routes. Team billing/seats follow the commercial gate after identity, membership, and usage attribution are dependable; adding a seat never grants production release permissions by itself.

### Future outcome-driven product track

O1–O4 below detail Phase K. Measurement foundations may be prepared alongside H/J, but autonomous outcome improvement requires the full safety and evidence gates. Production promotion continues to honor the team's review/release policy, including any explicitly authorized bounded autonomy policy.

The long-term direction is outcome-driven, self-evolving software: outcome → success metrics → intervention → build and release → observation → improvement hypothesis → experiment → retain or withdraw. Software briefs remain supported. See [the product specification](PRODUCT_SPEC.md#13-long-term-direction--outcome-driven-self-evolving-software) for the full loop and evidence requirements.

The following track follows dependable real execution, release, and ongoing modification. It is not a new Phase 1 milestone or a calendar commitment. Existing M0–M6 deliverables, acceptance criteria, order, and the current planning extension remain unchanged.

| Future stage | Objective | Gate before proceeding |
| --- | --- | --- |
| O1: Outcome and Metrics foundation | Capture outcome briefs and agreed success definitions; establish baselines, versioned instrumentation, and release-linked observations | Production identity and tenant isolation; data collection permissions; reliable real usage/outcome data; defined cohorts, windows, and data-quality checks |
| O2: Guided improvements | Outcome Engine proposes evidence-linked hypotheses and converts approved interventions into requirements for the existing project | Dependable 2C modification/release pipeline; preserved Brain/version lineage; uncertainty visible; authorized reviewers approve changes under the project/team release policy before production rollout |
| O3: Experiments and decisions | Limited rollouts or controlled comparisons; predefined evaluation and stop rules; durable adopt, reject, or inconclusive decisions | Sufficient evidence for the chosen method; guardrails and monitoring; tested feature-disable/rollback strategy; migration and external-action constraints understood |
| O4: Autonomous improvement loop | Observe, propose, build, verify, release, evaluate, and retain or withdraw within an approved policy | Proven measurement and recovery; bounded scope, budgets, and rollout; cancellation/kill switch; escalation and human-review rules; complete decision/evidence history |

Commercial readiness gates still apply before public operation. Each outcome stage requires its own implementation proposal and validation; no outcome telemetry, experiment UI, workers, schema migrations, or autonomous behavior is authorized by this document update.

### Architecture extension points

Keep the modular FastAPI application and domain-owned PostgreSQL records as the foundation. The current architecture already proposes immutable Brain revisions, project ownership, ordered events, version/deployment records, and replaceable model, execution, and deployment boundaries. Extend those boundaries when the future track is authorized; do not add empty modules or infrastructure now.

| Future component | Responsibility | Existing boundary to preserve and extend later |
| --- | --- | --- |
| Outcome Engine | Clarify objectives, propose metric definitions, identify opportunities, and create typed intervention hypotheses | A separate application/domain capability feeds approved requirements into planning. Model adapters remain provider-independent; stored goals and decisions belong to the application. The current `PlanningProvider`, `ProjectPlan`, and `POST /v1/plan` contracts stay unchanged; introduce outcome-specific contracts only when implemented. |
| Metrics layer | Own versioned definitions, baselines, observations, cohorts, and reproducible evaluations | Link measurements to project and release/version identifiers under the ownership boundary. Keep raw measurement ingestion separate from Build Trace; Brain and Trace reference evidence summaries. Start with justified storage choices, adding specialized analytics infrastructure only when volume and queries require it. |
| Experiment system | Connect objectives and hypotheses to candidate versions, rollout assignment, evaluation windows, guardrails, and decisions | Extend version/deployment lineage and immutable decision history. Model experiment states separately from build states. Promotion and withdrawal use verified release adapters and their migration/recovery constraints. |
| Improvement orchestrator | Coordinate the bounded observation-to-change loop and enforce its approved policy | Reuse the planned build/test/repair/deploy pipeline and eventual durable job boundary. Preserve revision/version conflict checks, idempotency, cancellation, restart recovery, budgets, and verification gates. No model provider owns workflow state or bypasses release checks. |

Future domain concepts may include outcome objectives, metric definitions, observations, hypotheses, experiments, and evaluation decisions. These are conceptual extension points, not additions to today's nine-table Phase 1 schema or API routes. Their records should reference existing project, Brain revision, candidate/base version, and deployment identities rather than duplicate project state.

Evaluation must remain reproducible from defined rules and observed data. Model-generated explanations can support review but cannot substitute for measurements. The loop evaluates business outcomes separately from software verification; a technically valid change may still be rejected. Rollback cannot be assumed to reverse irreversible data changes or external actions, so experiment rollout depends on a safe recovery strategy.

## 6. Major risks and how this plan addresses them

| Risk | Foundation response |
| --- | --- |
| Impressive demo mistaken for working automation | Capability flags, panel-level Simulation labels, fixture-only descriptors, no fabricated evidence |
| Future edits regenerate the project | Immutable original request, stable requirement IDs, revision/version bases, preserved requests and decisions |
| Progress disappears after reload | Database-owned run cursor and append-only replayable events |
| Failed update removes usable preview | Separate current run outcome and current successful version |
| UI becomes a chatbot | Preview-first canvas and structured Brain/Trace; collapsible request drawer |
| Framework/provider lock-in | Domain owned by FastAPI/PostgreSQL; generated DTO client; small execution/model boundaries |
| Foundation grows into premature infrastructure | Single-owner scope, one backend process, no real workers/sandboxes/deployments in Phase 1 |
| Development shell becomes an accidental public SaaS | Startup guard and explicit private/local boundary; real identity is a later launch gate |

## Revision notes

- 0.11: Completed M6 only and closed Phase 1 acceptance. Recorded the integrated journeys, accessibility/zoom/motion/focus checks, regression results and honest local/private limitations. Phase 2A–2C remain planned; no real generation or production identity/execution/deployment began.
- 0.10: Defined the planned 2A/2B/2C scopes and evidence gates. Real generated-app preview completes 2B; public deployment and incremental redeployment follow in 2C. Orchestration technology remains a later choice. M5 remains the completed checkpoint and M6 remains pending.
- 0.9: Completed M5 only, with persisted simulation/publication and workspace recovery. Existing persistence, creation, M4 views, planning and preview isolation preserved. M6 and all future capabilities remain deferred.
- 0.8: Completed M4 only. Added workspace, immutable Brain/request inspection, context-bound recording, Activity/Versions reads and isolated synthetic fixture foundations. M5–M6 and all future capabilities remain deferred.

- 0.7: Completed M3 only. Added real persisted frontend project management and safe command recovery; recorded the active-run archive constraint. M4–M6 and all future capabilities remain deferred.

- 0.6: Completed the founder-authorized M2 persistence/API/client milestone and recorded its checks. Existing milestone deliverables and A–K direction are unchanged; implementation stops before M3.

- 0.5: Added the full software lifecycle A–K capability map and future collaboration/control-center gates. Current code, the frontend planning workstream, Phase 1 schema, and all M0–M6 milestone text remain unchanged.

- 0.4: Recorded the authorized frontend draft planning milestone and its validation boundary. The existing M0–M6 persistence/workspace/simulation implementation plan and future outcome track retain their order and scope.

- 0.3: Added the future outcome-driven track and extension points for an Outcome Engine, Metrics layer, Experiment system, and improvement orchestrator. Current Phase 1 milestones, runtime, schema, and API contracts remain unchanged.

- 0.2: Recorded the actual M1 scaffold and founder-authorized standalone planning extension. Later milestones remain pending; stop after endpoint verification.

- 0.1: M0 review checkpoint and M1–M6 implementation plan. Later phases describe direction only. No milestone beyond planning has begun.

## Phase 2A completion gate — 2026-10-02

Implemented configurable verified OIDC identity, opaque revocable sessions and explicit stable-ID linking; owner authorization applies to projects, Brain, requests, versions, proposals and streams. Sign-in/account/sign-out are connected. Additive migration preserves Phase 1 records. Project Planning saves validated original/change proposals from bounded current Brain/version/requirements/history context, with immutable provenance and stale publication/review rejection. Conservative persisted request/token reservations, deadlines, cancellation and idempotent response recovery bound planning. No automatic provider retries or restart redispatch occur.

The controlled signed-in create → plan → reopen → context-aware change-plan journey passed with a cryptographic test issuer and actual OpenAI adapter using controlled responses. Provider failure/cancel/lost-response and second-owner denial passed. Full backend/frontend suites, strict mypy, client drift, typecheck/build and Phase 1 browser regressions are recorded in PHASE2A_IMPLEMENTATION.md. No live identity account or model invocation was configured or verified.

At that historical Phase 2A checkpoint, execution had not begun. The separately authorized Phase 2B work below now implements source lineage, sandbox, worker and preview boundaries; its Docker/browser acceptance remains pending.

## Phase 2B execution checkpoint

Implemented the remaining execution path and Docker acceptance harness. Source/repair calls use the existing bounded provider contract and usage ledger; successful recipe verification commits version/Brain/preview pointers atomically. Recovery preserves immutable evidence and last-good previews. Actual Docker containment and end-to-end execution are not verified in this Work environment. Complete the local commands and remaining gates in PHASE2B_IMPLEMENTATION.md before changing this status to complete. Phase 2C, billing, teams, connectors, visual editing, Growth Engine and Outcome Engine remain outside this change.
