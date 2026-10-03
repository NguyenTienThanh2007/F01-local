# F01 — Product specification

Status: Phase 1 M6 and Phase 2A implemented and verified; Phase 2B foundation only, execution blocked; Phase 2C unimplemented.  
Revision: 0.13 · 2026-10-02  
Scope: Phase 1, Phase 2A and inactive Phase 2B source/policy foundations. F01 is a temporary internal codename, not a final brand.

## 1. Product intent

A person describes an app, web product, SaaS, dashboard, internal tool, or browser game. The long-term platform plans, builds, verifies, fixes, previews, and deploys it, then keeps it hosted and manageable in the same workspace. Users return to modify and maintain that existing product through natural language. Teams can create, review, manage, and evolve the same software together.

The product direction is a **full software lifecycle platform**: “Create, run, manage and evolve your software in one place.” “An operating system for software” expresses that product ambition. Its durable asset is the existing codebase and accumulated project knowledge. The primary interface is a persistent software control center with a preview, operational controls, and evidence of progress.

Core lifecycle: **Idea → Plan → Build → Verify → Preview → Deploy → Run → Manage → Modify → Version → Monitor → Improve.** Requirements, architecture, and controlled repair remain part of planning and verification. This lifecycle can repeat for an existing product; it does not replace Phase 1 lifecycle enums or the simulated run protocol.

The differentiated experience is: “Describe what you want. The platform builds it, runs it, remembers it, and keeps evolving it.” Eventually users can also describe a business outcome, and the system can determine an intervention, measure results, and test improvements. Outcome-driven, self-evolving software remains the furthest evolution of the platform, as defined in section 13.

Two product experiences anchor this identity:

- **Project Brain:** structured, persistent project knowledge with provenance and revision history.
- **Build Trace:** an ordered, intelligible record of what happened, what failed, and what was resolved.

Project Pulse expresses the current operating state throughout the product. These three experiences must remain recognizable without the wordmark.

The eventual product family includes web apps, SaaS, dashboards, internal tools, and simple browser games. Mobile applications and advanced games follow after dependable web execution. Phase 1 establishes their shared project model; it does not implement generation for these categories.

| Long-term pillar | Product responsibility |
| --- | --- |
| Project Brain | Remember requirements, architecture, codebase context, decisions, preferences, changes, and known problems |
| Build Trace | Show what the system did, why, and the evidence behind its results |
| Autonomous verification | Build, test, inspect, and repair within bounded attempts |
| Managed software lifecycle | Preview, deploy, run, version, roll back safely, and monitor |
| Natural language maintenance | Modify the existing software without requiring manual source editing |
| Team collaboration | Share context and ownership; review changes and control production releases |
| Outcome-driven evolution | Improve software against measurable user or business outcomes |

## 2. Source-of-truth responsibilities

| Document | Owns |
| --- | --- |
| `PRODUCT_SPEC.md` | Product behavior, scope, user journeys, acceptance criteria, terminology |
| `ARCHITECTURE.md` | System boundaries, domain/schema, routes, contracts, consistency, security |
| `DESIGN_SYSTEM.md` | Visual tokens, components, interactions, accessibility, state presentation |
| `ROADMAP.md` | Implementation order, milestone gates, validation, deferred work |

The founder's explicit requirements take priority. Resolve document conflicts before implementation; do not silently choose whichever document is convenient. Accepted changes update the relevant documents and their revision notes together.

### Delivery layers

| Layer | Actual status and scope |
| --- | --- |
| Current implementation | Product shell and stateless draft planning: `/projects/new` → server-only `/api/v1/plan` → FastAPI `/v1/plan`. All six plan sections render; validation, loading, cancellation, retry, and credential-boundary checks exist. M2 implements the PostgreSQL domain and ownership-scoped project API. M3 persists projects. M4 provides the saved workspace, immutable Brain inspection, original brief/request history, context-bound change recording, Activity/Versions reads and isolated synthetic preview foundations. M5 adds the persisted fixture runner, replayable Build Trace, simulation commands and atomic Brain/version/internal-deployment records. Standalone planning still holds an unsaved draft; no application is built. |
| Completed Phase 1 | Existing M0–M6 plan: complete the shell, then single-owner persistent projects, Brain, workspace, fixture previews, simulated Trace/version history, and polish. M2 persistence is implemented. Dashboard saving is implemented in M3; workspace rendering is M4 and persistent simulation is now implemented in M5. M6 completes the quality, accessibility, consistency and acceptance pass. |
| Phase 2 | 2A is implemented: verified identity, secure sessions and persisted context-aware planning proposals. 2B: real source generation → isolated sandbox → build → test → bounded automatic repair → real preview. 2C: real deployment → public URL → release versions → modify the existing app → redeploy. 2B/2C are planned scopes, not implemented capabilities. |
| Long-term platform | Real generation/execution, managed hosting, operational controls, teams, visual editing, monitoring, and outcome improvements. The A–K direction in `ROADMAP.md` is not implementation authorization. |

The founder authorized M2 through M6, one milestone at a time. Creation atomically saves the project, original request, immutable initial Brain, queued demonstration run and first event. Initial Brain remains a deterministic scaffold with user/template provenance. M3 dashboard, creation and metadata journeys, M4 workspace/Brain/request views and preview isolation, and the standalone real draft planner are preserved. With the M5 runner enabled, the server progresses versioned fixtures and publishes a curated sample on success. Failed updates retain the current successful preview and Brain. Cancellation returns to Live · Demo when a version exists, otherwise Idle. Active runs still block new requests and archiving. Saving a change records immutable intent only; the optional “Record and simulate” action starts a separate idempotent demonstration command. Arbitrary requested changes may leave the bundled preview unchanged. Historical inspection never changes current pointers. M6 verifies the final Phase 1 journeys and improves focus, connection recovery, inspection clarity and responsive quality. Phase 2A extends identity and planning only; Phase 2B and later capabilities remain unimplemented.

## 3. Phase 1 boundaries

The Phase 1 target is a polished, persistent product foundation. Project records, user requests, Brain revisions, build events, and version metadata will be real database records. The workspace lifecycle continues to use deterministic demonstrations. As an explicitly requested extension, `POST /v1/plan` now makes a real OpenAI call to produce a validated draft plan; it does not create or modify a project or run.

| Included | Phase 1 behavior |
| --- | --- |
| Authentication-ready shell | Identity boundary, route protection hooks, account area, clearly labeled development identity |
| Projects dashboard | Persisted projects, search, status filter, archive filter, recent activity, empty/loading/error states |
| Create-project flow | Natural-language brief, optional title, examples, validation, duplicate-submit protection |
| Project workspace | Preview-first layout, persistent navigation, utility inspector, request history |
| Project Brain | Readable brief, requirements, plan, architecture, schema, decisions, history, provenance |
| Build Trace | Persisted event stream, reconnect/replay, phase groups, timestamps, failure and resolution relationships |
| Status system | Shared lifecycle vocabulary and Project Pulse mapping |
| Preview | Interactive, bundled sample application; fixture selection and viewport controls |
| Requests and changes | Persist requests against a Brain revision and version; optionally start another demonstration run |
| Versions and activity | Inspect simulated version metadata; select older demo previews; activity from the same event source |
| Project settings | Rename and archive/unarchive; read-only environment and deployment capability information |
| Engineering foundation | PostgreSQL migrations, typed contracts, modular UI, environment validation, ownership checks |

Included extension: a backend-only, development-token-protected planning endpoint connected to the create-project form through a server-only frontend route. It accepts a software product idea and returns a project title, summary, target users, core features, recommended stack, and ordered implementation milestones. The form presents validation, pending/cancel, success, error/retry, and structured plan review states. Provider and internal development credentials never enter browser code. The result is a draft proposal held in page memory; M3 offers a separate title/original-brief save journey using M2 persistence. Reloading or leaving the page discards it. Submission does not start a build or advance the simulated workspace lifecycle.

Explicitly outside Phase 1: other LLM workflows, autonomous source generation, executing user code, Docker project sandboxes, Redis workers, real bug fixing, generated authentication, provisioning databases for generated apps, external deployments, custom domains, public preview links, source downloads, file editing, real rollback, billing, invitations, collaboration, mobile generation, and advanced games.

The planning endpoint requires an OpenAI API key in backend environment configuration. The shell and health endpoint work without it. No provider key is accepted from the frontend or request body. A small provider-independent planning contract allows future Claude/Gemini adapters. Files, logs, and deployment panels remain honest capability placeholders or labeled fixture examples.

An authentication-ready shell is not a production identity system. Phase 1 development identity is limited to local or explicitly private development environments. Public multi-user operation requires a real identity provider and the launch gates in `ROADMAP.md`.

### Phase 2 progression

Phase 2 follows the Phase 1 acceptance gate. The current completed checkpoint is Phase 2A; Phase 1 acceptance remains complete. The three stages below introduce real capabilities separately, preserving the workspace, original brief, immutable Brain revisions, request context and existing history.

| Stage | User-visible result | Completion evidence |
| --- | --- | --- |
| 2A — Production identity + context-aware real planning | A signed-in owner creates or reopens a project and reviews a real model-produced plan grounded in its original brief, current Brain, requests and selected version. Change plans identify scope, assumptions and acceptance criteria. | Verified identity and ownership/session isolation; validated, persisted planning proposals with provider/provenance and pinned context; stale-plan review and failure/retry behavior. A plan remains proposed work. |
| 2B — Real code generation and preview | An accepted plan produces actual project source, runs build/tests in an isolated sandbox, repairs observed failures within limits and opens the generated app in a real preview. | Source/artifact lineage, actual commands/results and sanitized logs, bounded repair evidence, containment/cancellation/restart checks and a working preview tied to the verified artifact. No fixture can stand in for this preview. |
| 2C — Real deployment and continued modification | The owner publishes a verified app to a public URL, inspects release versions, requests a change to that existing app and redeploys the verified update. | Observed release/health and public URL, immutable deployment/version history, context-bound incremental changes and preservation of the last working release on failure. |

2A plans from authorized stored context. If generated source does not exist yet, it must say so; it cannot invent file summaries or execution evidence. Saving/reviewing a plan never changes the original brief, claims implementation or creates a successful build/deployment. Provider errors and stale bases preserve user intent.

2B distinguishes preview startup from production release. Generated source, dependency scripts and application servers execute outside the factory control plane. Trace reports observed results; repairs respond to actual failures and stop at their attempt/time/resource budgets. Failure preserves the last verified preview. Preview access remains isolated from factory sessions and credentials.

2C modifies the pinned existing source through the same plan → patch → isolated verification → preview pipeline before promotion. It preserves unrelated behavior and recorded history, rechecks stale bases, and promotes the reviewed artifact. Failed updates do not replace the working public release. Source rollback does not imply reversal of data migrations or external effects.

Teams, billing, connectors, visual editing, advanced operational controls and the outcome engine retain their later roadmap gates. Identity, model, sandbox and deployment provider choices require implementation decisions; this plan does not select them.

## 4. Initial audience and primary job

Start with a founder or small-business operator who can explain a workflow but needs help turning it into maintainable software. The first useful demonstration is a small real-estate CRM. Avoid trying to satisfy every software category with an identical preview.

Primary job: “Turn my request into a project I can understand, inspect, and return to.”

Secondary job: “Record a change in the context of the existing project and show its relationship to prior work.”

## 5. Primary journey

1. Open `/projects` in a clearly identified development workspace. Existing projects come from the API; the first empty state offers one primary create action.
2. Open `/projects/new`. Enter an optional title and a brief, for example: “Build a CRM for a small real estate agency with authentication, leads, pipeline, notes and analytics.”
3. The page explains: “Demo mode. Your brief and project history are saved. Planning, builds, and previews use sample scenarios.” The primary action is **Create demo project**.
4. Submission atomically creates the project, original request, initial Brain revision, queued demonstration run, and initial trace event. Navigate to `/projects/{projectId}` only after the server confirms creation.
5. The workspace presents the title, Pulse, lifecycle, original brief, draft structured plan, sample preview, and current Trace. Progress is controlled by the server.
6. Simulate Understanding → Planning → Building → Verifying → Deploying → Live. Each execution panel displays **Simulation**; the final project status reads **Live · Demo**.
7. Inspect Brain, activity, and version 1. Reload or open another tab: the project and event ordering remain consistent.
8. Submit a change request. Save its original text and the exact Brain/version context. The user can start a demonstration update; existing history and the original brief remain intact.
9. Return from the dashboard and continue the same project. No successful navigation or page refresh recreates it.

The interface must not claim that an arbitrary prompt produced a functioning application. A supported CRM example uses a curated scenario. Other briefs receive a generic, clearly labeled draft scaffold and sample preview. Requirements explicitly entered by the user are distinguished from template assumptions. Unsupported changes are recorded faithfully; the preview states that the sample has not implemented that change.

## 6. Workspace information architecture

| Region | Role | Content |
| --- | --- | --- |
| Global rail | Move between projects and account | Project switcher, Projects, account/development identity |
| Project header | Establish location and state | Editable title, Pulse, lifecycle, Simulation label, active run, selected version |
| Project navigation | Inspect a stable project | Preview, Brief, Brain, Activity, Versions, Settings |
| Main canvas | Inspect the product or its specification | Dominant preview on the root route; structured content on other routes |
| Utility inspector | Inspect work without losing place | Build Trace, Run details, Files, Logs, Deployment |
| Request drawer | Record intent and inspect prior requests | Initial brief, dated change requests, compact composer, run linkage |

The request drawer is secondary and collapsible. It is not a permanent conversation column. Trace and request history preserve their scroll position and selection while navigating within a project. Inspector open state and viewport preference may be local UI preferences; domain records must not live in localStorage.

On small screens, show one main surface at a time. Navigation becomes a sheet and the inspector becomes a full-height drawer. Preview, Trace, and request history remain reachable; they do not compress into three unusable columns.

## 7. Project Brain

Project Brain is a typed, versioned project dossier. Every project retains:

- Original user brief, unchanged, with its author and creation time.
- Product requirements with stable IDs, source references, assumptions, and acceptance criteria.
- Ordered plan and architecture rationale.
- Intended generated-project stack, kept separate from the factory's own stack.
- Proposed generated-project database entities and relationships.
- Features and their requested, planned, or simulated status.
- Design decisions and rationale.
- Change requests and links to their outcomes.
- Previous bugs and fixes, represented by structured issue/resolution events.
- Version and deployment records with execution mode.
- Relevant constraints, open questions, and other explicit context.

Store immutable Brain revisions. The current revision is a pointer, not an editable history blob. User requests and events are durable canonical records; Brain history references them rather than copying a growing transcript into every revision.

Display provenance such as **User requested**, **Template assumption**, and **Simulated outcome**. “User requested” describes the source of a requirement, not proof that it has been implemented. Derived issue and deployment summaries remain available even when a failed run produces no new Brain revision.

A change is tied to a base Brain revision and optional base version. If the base is stale, keep the unsent text and ask the user to review the current project before resubmitting. Future generation must consume this context and produce a patch to the existing project, with traceable decisions. Phase 1 establishes that contract; it does not perform source patches.

## 8. Build Trace and activity

Trace is an append-only project event timeline ordered by a server-assigned project sequence. Wall-clock timestamps aid reading but never determine event order. The same records power Activity; do not maintain separate competing histories.

Each visible event has a timestamp, concise action/result, phase, severity, run reference, and Simulation label where appropriate. Expandable details expose safe structured evidence. A failure can link to its resolution using a stable issue ID.

Example fixture narrative, entirely simulated:

| Time | Trace entry | Phase |
| --- | --- | --- |
| 12:41 | Brief recorded | Understanding |
| 12:43 | Sample architecture attached | Planning |
| 12:47 | Authentication interface milestone completed | Building |
| 12:51 | Sample verification failed: callback route mismatch | Verifying |
| 12:52 | Sample callback repair recorded | Building |
| 12:54 | Sample verification passed | Verifying |
| 12:56 | Demo preview available | Deploying |

Times above illustrate the format; fixture duration is short and does not imply real work. Do not generate invented logs, test counts, commits, deployment URLs, or code evidence. Mock failures and fixes are marked as examples.

Activity defaults to meaningful milestones and user actions. Trace defaults to the current run with access to earlier runs. A user reading older events sees a “Jump to latest” action; new events do not steal their scroll position.

## 9. Lifecycle and operational state

| Domain lifecycle | Interface label | Pulse | Meaning |
| --- | --- | --- | --- |
| `idle` | Idle | Idle | No run is active and no completed demo version is current |
| `understanding` | Understanding | Thinking | Recording the request and its existing context |
| `planning` | Planning | Thinking | Preparing a sample structured plan |
| `building` | Building | Building | Demonstrating implementation milestones |
| `verifying` | Verifying | Verifying | Demonstrating verification outcomes |
| `deploying` | Deploying | Shipping | Preparing the internal fixture preview |
| `live` | Live · Demo | Live | A completed simulated version has a preview |
| `error` | Needs attention | Error | Latest run failed; recovery action is available |

Run outcome is a separate field: `queued`, `running`, `succeeded`, `failed`, or `canceled`. A queued run shows “Queued” beside a static Thinking Pulse. Cancellation returns the project to Live if a completed version exists, otherwise Idle. Archive is an independent visibility setting, not a lifecycle state.

An update can fail while the prior version remains available. The header reports the update failure; the preview reports which successful version it still shows. Selecting an older version changes only the inspected preview. It does not reset the Brain or simulate a rollback.

## 10. Product quality requirements

- Every user action has a pending, successful, and failed result. Errors preserve inputs and offer a relevant recovery action.
- First load uses layout-matched skeletons. Refreshes retain existing content with a restrained stale/reconnecting indicator.
- Keyboard navigation, readable focus states, semantic landmarks, accessible labels, and reduced-motion behavior are required.
- Status is communicated through text and shape as well as color. A timer is never presented as a verified percentage of real work.
- Demo leads and analytics use synthetic data. CRM login fixtures cannot create real accounts.
- Preview is isolated from the factory interface, with no access to identity tokens or factory navigation.
- Project ownership is enforced in API operations and event streams, even in seeded development tests.
- User-entered text is rendered as text, not executable HTML. No request can cause shell execution or an arbitrary iframe URL.
- The factory UI remains recognizable through typography, a structured rail and canvas, restrained terracotta accent, Trace time gutter, and Pulse.

## 11. Phase 1 completion criteria

Phase 1 is complete when a project can be created, persisted, reopened, inspected, updated through recorded requests, and archived; a server-driven demo run can complete, fail, recover, or be canceled; and Trace replay, Brain history, version selection, and sample preview all remain coherent after reload and process restart.

The example CRM must make its saved brief, scaffold assumptions, synthetic preview, and simulated execution distinguishable at a glance. The product must handle empty data, long titles, validation failures, unavailable API, lost connection, stale changes, and missing/unauthorized projects without losing user input or leaking another user's records.

No generated app has actually been built, verified, fixed, or deployed at this completion point. A commercial public launch requires the later gates in `ROADMAP.md`.

## 12. Proposals to review

The review should approve or revise: F01 as a temporary codename; a warm paper/ink visual system with terracotta accent; single-owner projects in Phase 1; a separate FastAPI service owning all domain writes; bundled CRM and generic demo previews; and immutable Brain revisions with one shared event timeline.

Final brand, production identity provider, long-term model/provider choices, deployment provider, and commercial pricing remain undecided. OpenAI is the first planning adapter; the domain remains provider-independent.

## 13. Long-term direction — outcome-driven, self-evolving software

This section defines future product direction only. Phase 1 scope, M1–M6 milestones, simulated lifecycle, current domain models, and the standalone planning endpoint remain unchanged. Outcome analysis, production telemetry, experiments, and autonomous improvements are not implemented or added to Phase 1.

### Outcome briefs

The user describes a desired result rather than needing to prescribe a feature. The system clarifies the audience, current workflow, constraints, available data, and what success means before proposing software. These examples are hypotheses and proposed metric definitions, not promises or observed results:

| User outcome | Possible success metric | Possible software or workflow |
| --- | --- | --- |
| “I want to increase customer retention.” | Share of an eligible customer cohort retained after a defined period | Customer health dashboard, follow-up workflow, renewal reminders |
| “I want to reduce missed appointments.” | Missed appointments divided by eligible scheduled appointments during a defined window | Confirmation and reminder workflow, accessible rescheduling |
| “I want to improve sales conversion.” | Qualified leads becoming customers within a defined window | Lead prioritization, follow-up tasks, pipeline visibility |

### Improvement loop

1. **Understand the outcome:** preserve the original intent and clarify constraints and affected users.
2. **Define success:** agree on measurable metrics, baseline, target, evaluation window, and guardrails.
3. **Determine the intervention:** propose software, workflows, or features and explain the hypothesis connecting them to the outcome.
4. **Build and deploy:** translate the approved hypothesis into requirements and use the existing architecture, implementation, verification, repair, and release pipeline.
5. **Observe real results:** collect consented usage and business outcome data associated with the deployed version.
6. **Find opportunities:** identify evidence-supported problems or opportunities, including uncertainty and alternative explanations.
7. **Propose or generate changes:** produce bounded changes to the existing project using its Brain, requirements, and version history.
8. **Measure effects:** evaluate the candidate against predefined metrics and guardrails, using a control or staged rollout when appropriate.
9. **Retain or withdraw:** keep successful changes, stop or roll back unsuccessful ones when safe, and record the decision before beginning another cycle.

Build success and deployment success do not establish outcome success. Usage is often a proxy for the business outcome; correlation alone does not demonstrate causation. Insufficient or unreliable evidence produces an inconclusive result, not automatic promotion.

### Persistent context and evidence

**Project Brain** continues to own the original brief, requirements, architecture, design decisions, bugs, fixes, and deployment context. Future additive context can reference outcome objectives, versioned metric definitions, hypotheses, experiments, and decisions. Preserve the distinction between requested goals, proposed explanations, and observed results. Changes retain the Brain revision and software version they were based on; a new objective does not erase previous intent or regenerate the project.

**Build Trace** remains the evidence timeline for the software lifecycle. Future entries can reference an approved hypothesis, candidate build, release, observation window, evaluation, adoption, or rollback. Operational events and outcome observations have different meanings: raw analytics belong in the Metrics layer, while Brain and Trace hold summaries and evidence references. Never present simulated data or an estimated gain as an observed business improvement. Project Pulse continues to express operating state; outcome evaluation does not change the Phase 1 status vocabulary.

### Measurement, experiments, and autonomy

Every future success metric needs a versioned definition, source, eligible population or cohort, denominator where applicable, time window, baseline, target, and data-quality requirements. Measurements must reference relevant releases and account for changes in instrumentation. Collection needs tenant isolation, appropriate consent, and retention controls. Missing data, delayed outcomes, and changes outside the software must be visible in the evaluation.

An experiment connects an objective and hypothesis to a candidate version, rollout population, measurement window, and decision record. Define success and stop rules before rollout, with guardrails for harms such as increased cancellations or degraded reliability. Use controlled comparisons where feasible and make limitations explicit otherwise. Do not label a weak comparison as proven causation.

Autonomous improvement is a later capability operating within an owner's explicitly authorized policy: permitted changes, environments, rollout limits, resource budgets, and escalation rules. Models may propose hypotheses and changes; measured evidence and defined evaluation rules govern adoption. Human review remains available and is required where the approved policy reserves material production or data changes for review.

Retained changes become part of the version history. Withdrawal uses the release/version architecture and a validated rollback or remediation strategy. A code rollback cannot undo every database migration or external action; when restoration is unsafe, stop the rollout or disable the feature and propose a safe corrective change. Preserve evidence from unsuccessful experiments so later cycles do not repeat unsupported decisions.

## 14. Long-term project control center and managed lifecycle

All capabilities in this section are future-facing. Existing Phase 1 navigation in section 6 remains the foundation; these sections are not new routes or panels to implement now. The request composer remains a secondary tool inside a structured software workspace.

### Workspace sections

| Section | Future responsibility |
| --- | --- |
| Overview | Current project and release status, production URL, latest deployment, application health, and recent activity |
| Preview | Running application preview, responsive device views, candidate version selection, and later element selection/visual editing |
| Changes | Natural language requests, change plans, implementation progress, Build Trace, review decisions, and change history |
| Versions | Significant modification snapshots with author/change ownership, changed files, description, build results, deployment links, and safe rollback eligibility |
| Deployments | Preview and production releases, status/history, and promotion of an approved preview artifact to production |
| Runtime | Health, logs, errors, authorized restart/redeploy actions, and later monitoring integrations |
| Database | Connection state, schema overview, migration evidence, safe permissioned data tools, and later table/data views |
| Environment | Variable names and metadata, write-only secret creation/replacement, and separate preview/production configuration; stored secret values are never shown again |
| Domains | Generated domain/subdomain, binding status, and later ownership-verified custom domains |
| Project Brain | Requirements, architecture, stack, schema, design decisions, version-linked file summaries, prior changes, known problems, deployment context, and scoped user/project preferences |
| Settings | Project name, permissions, membership, archive, later policy-governed deletion, and collaborators |

Brain and Trace remain shared canonical project knowledge. File summaries reference the source version they describe. Personal preferences retain their author and scope; they do not silently overwrite team-wide requirements or decisions. Secrets are never Brain content.

### Natural language modification

For “Add recurring subscriptions,” the future system:

1. Loads the current shared Project Brain and requester's authorized project context.
2. Inspects the existing repository and its current source version.
3. Identifies affected systems and files, including schema, runtime, and integration implications.
4. Creates a change plan with requirements, acceptance criteria, assumptions, and expected effects.
5. Creates a working branch/candidate version tied to the base source version and Brain revision.
6. Patches only the necessary code and preserves unrelated project behavior.
7. Runs type checks, build, tests, and appropriate inspection in an isolated execution environment.
8. Repairs failures within controlled attempt, time, and resource budgets; escalates when those limits are reached.
9. Deploys an isolated preview with verification evidence.
10. Shows the changed files, behavior, migration/configuration needs, and Build Trace.
11. Collects the required review and approval before production promotion; a new patch or relevant configuration change invalidates approval of the older candidate.
12. Records the change, actors, review/release decisions, and resulting context in history and immutable Brain revisions.

The system must never regenerate the whole application unnecessarily. A significant modification creates a traceable candidate version even if its build fails; it cannot replace the last working release merely by existing. Future source/candidate version states remain distinct from build attempts and deployments. Phase 1 still creates successful simulated versions only.

Preview and production are separate environments. Production promotion uses the approved, verified artifact and explicit environment configuration. Rolling back selects a previously verified release compatible with current data and dependencies. It does not rewrite history or imply that irreversible migrations, subscription charges, or other external actions have been undone.

### Managed hosting and maintenance

Each future project connects its source repository, isolated build environment, preview environment, production environment, database/storage, logs, and version/deployment history inside one product. Hosting can use replaceable infrastructure adapters; the workspace remains the user's management surface. Generated applications run separately from the factory control plane and other projects/users. Platform infrastructure and model credentials are never injected into generated applications.

Future operational controls report observed health and logs, distinguish an unsuccessful update from the previous working release, and require appropriate permissions for restart, redeploy, migration, environment changes, and rollback. Monitoring can open a maintenance request with evidence; repairs use the same verified change pipeline and release policy.

### Visual editing — future

A user selects a button, heading, sidebar, card, or form in the running preview and requests “Make this smaller,” “Move this to the right,” or “Turn this into a two-column layout.” Version-linked inspection metadata resolves the rendered element to its source component. The selection becomes a scoped change request, then a patch, verification, and a new preview.

Selections are context, not permission to edit an arbitrary file. Ambiguous or stale mappings require clarification or reselection. Visual changes use the same review, version, and release flow as text requests. Comments can reference these element anchors where a reliable mapping exists. No element inspection bridge, selection UI, or source editing is implemented now.

## 15. Team collaboration — future core capability

Projects eventually belong to shared organization/team workspaces. Multiple people can create, review, manage, and evolve the same product with one Project Brain, Build Trace, version history, and release history. Phase 1 remains single-owner: no invitations, memberships, comments, reviews, seat billing, or role UI are added now.

### Membership and permission defaults

Future invitations are sent to email addresses and accepted through verified identity. Membership is a durable authorization record; email alone is not an identity or access grant. Roles apply at explicit workspace/project scopes and are enforced server-side for every action.

| Role | Proposed default responsibility |
| --- | --- |
| Owner | Manage ownership, workspace/project policy, members, billing, and production permissions; approve and release where permitted |
| Admin | Manage permitted project operations and members; approve/release under the workspace's deployment policy; no automatic ownership transfer |
| Builder | Request and implement changes, inspect affected files/evidence, generate previews, and participate in discussions; no production promotion by default |
| Reviewer | Inspect preview, changed files, Brain, and Trace; comment; approve or request changes; approval does not itself grant deployment permission |
| Viewer | Read permitted project context, previews, and history; no changes, approvals, or operational mutations by default |

Production deployment, rollback, database mutations, secret replacement, and environment operations have explicit capabilities beyond ordinary project viewing. No role may retrieve a stored secret value through the workspace. Role inheritance and exceptions require a defined policy; being able to create a preview does not imply permission to deploy it.

### Shared review workflow

A Builder requests “Add subscription billing.” The system creates the plan, patches the existing application, verifies it, and deploys a preview. A Reviewer inspects that preview, changed files, and Build Trace, then chooses **Approve** or **Request changes**. Approval binds to the exact candidate and its verification/configuration evidence. An authorized production releaser promotes the approved artifact; an approval is not a deployment command.

Activity attributes who requested, authored, reviewed, approved, deployed, and rolled back each change, distinguishing humans from system actions. Comments and mentions are scoped to accessible projects, changes, versions, or preview elements. Anchors include the preview/source version; an outdated anchor is shown as outdated instead of silently moved to unrelated content.

Concurrent requests preserve their own source/Brain bases. Conflicts are reviewed or rebased and reverified; one person's work cannot overwrite another's context or approved candidate. Removing a member revokes future actions and pending privileges without erasing historical attribution. Audit logs record membership, permission, approval, deployment, and sensitive operational actions. Future team billing/seats attach to the organization/workspace and remain separate from deployment authorization.

Default production changes require human review under project policy. Phase K may eventually permit bounded improvements under an explicitly preauthorized policy, with its own gates; it cannot silently bypass the team review model or impersonate a reviewer.

## Revision notes

- 0.11: Completed M6 and Phase 1 acceptance. Corrected capability copy, keyboard/focus behavior, transport recovery visibility, historical loading/selection and Trace readability. Preserved simulation-only execution, ownership, immutable context, preview isolation and the planned Phase 2 scopes.
- 0.10: Clarified the planned 2A identity/context-aware planning, 2B real generation/isolated verification/repair/preview, and 2C public deployment/versioned ongoing modification sequence. Real preview belongs to 2B; production release belongs to 2C. Current implementation remains M5, with M6 pending.
- 0.9: Completed M5 only: persistent versioned fixture progression, atomic publication, ordered simulated Trace, SSE replay/polling/gap recovery, run inspection/retry/cancel and preserved successful previews. No real generation, tests, fixes, commits or external deployment; M6 remains pending.
- 0.8: Implemented M4 only: preview-first saved workspace, immutable Brain/provenance, original brief and context-bound requests, Activity/Versions/utility foundations and isolated synthetic fixtures. Active-run/archive/stale-context constraints remain enforced. M5–M6 remain pending.

- 0.7: M3 connects the redesigned dashboard and create journey to M2 persistence, retains standalone draft planning, and adds only minimal saved-record/settings navigation. Domain contracts and future milestone scope are unchanged.

- 0.6: Implemented the authorized M2 backend persistence milestone with immutable Brain/history, ownership, idempotent creation, settings ETags, consistent reads, migrations, and a generated server-only client. M3–M6 scope, the design system, and long-term direction are unchanged.

- 0.5: Aligned the long-term vision around a full software lifecycle control center, managed hosting, natural language maintenance, visual editing, and future team collaboration. Preserved the current implementation, Phase 1 scope, M0–M6 milestones, and outcome-driven direction.

- 0.4: Connected the founder-authorized frontend draft planning flow to the existing endpoint through a credential-safe server route. Project persistence and M2–M6 remain deferred; the outcome-driven direction is unchanged.

- 0.3: Added outcome-driven, self-evolving software as the long-term direction, including measurement, experiments, and the improvement loop. Phase 1 scope, implementation plan, and runtime contracts are unchanged.

- 0.2: Authorized standalone real planning endpoint added to Phase 1. It returns a validated proposal without project persistence, frontend integration, execution, or deployment.

- 0.1: Initial proposal based on the founder's brief. Workspace inspection found no application code, Git repository, or applicable `AGENTS.md`. Only planning documents are authorized for this turn.

## 14. Phase 2A implemented product boundary

Sign-in uses a configured OpenID Connect provider; the browser holds opaque HttpOnly sessions. Account shows the verified owner and expiry, and sign-out revokes that session. Stable internal user/project/history IDs remain canonical. A verified operator-only link can attach an existing development owner to an issuer/subject before first sign-in; matching email never transfers ownership. Missing, expired or revoked sessions return no project data. Foreign owners receive 404. Development identity remains an explicit local/test compatibility mode and cannot run in production. No teams or shared workspace permissions are implemented.

Project navigation includes Planning. Original-brief and recorded change planning consume current immutable Brain/version context and bounded relevant requirements/history with provenance. The OpenAI adapter returns a validated structured proposal; it does not execute tools. Proposals and their pinned context are immutable records separate from Brain revisions. Marking a proposal reviewed records acknowledgement only. New requests never overwrite the original brief. Existing source is explicitly unavailable. Current Simulation state, successful preview and Brain/version pointers are unaffected by planning.

A planning attempt reserves a request and conservative token allowance before dispatch. One attempt may be pending per owner. Minute/day limits, context/output limits and deadlines apply; failed, canceled and uncertain requests retain their reservation. Actual provider token fields are nullable and contain only reported counts. Input/key receipts survive uncertain responses; replay does not call the model again. Publication and review reject stale context. Cancellation discards a late result. Lost in-process work expires as abandoned and requires a deliberate new attempt, with no automatic provider retry.

Verification uses a controlled RSA-signed identity provider and the actual OpenAI adapter with controlled transport responses. No live identity account or paid model call was configured or verified. Provider provisioning, public operations, session refresh and commercial readiness remain separate work. Generated application execution/deployment is not yet implemented.

Revision 0.12: implemented Phase 2A only; preserved Phase 1 Simulation, immutable history and preview isolation.

Revision 0.13: authorized Phase 2B; added inactive source proposal/patch, artifact-value, bounded provider and Docker prerequisite/policy contracts. The environment has no container daemon and rejects namespace isolation. These foundations create no persisted application source or real execution evidence. No real build, repair, preview or worker is available; Phase 2B acceptance remains pending. Phase 2A remains the latest completed stage. See [Phase 2B foundation](PHASE2B_FOUNDATION.md).

## Phase 2B execution checkpoint

The foundation-only descriptions above are historical. The remaining execution implementation now uses additive migration 0003, persisted immutable candidates and evidence, fenced leased workers, bounded provider/repair budgets, atomic real version/Brain/preview publication and a separate cookie-host preview gateway. Source/worker/Docker wire types remain outside domain provider contracts. Simulation records remain distinguishable. The supported recipe is browser-focused Next.js/React/TypeScript; no application database, external integrations or production release is provisioned. Available application checks pass, but Docker provisioning/containment/execution and interactive browser acceptance remain unverified here. Real execution is disabled until a passing acceptance report matches the exact image ID. See [PHASE2B_IMPLEMENTATION.md](PHASE2B_IMPLEMENTATION.md). Phase 2C and later capabilities have not begun.
