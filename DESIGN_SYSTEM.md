# F01 — Design system

Status: Identity preserved through commercial-v1 and the dedicated product refinement pass. Earlier phase labels below describe the design's progression.
Revision: 0.6 · 2026-10-08
Related: [Product specification](PRODUCT_SPEC.md), [Architecture](ARCHITECTURE.md), [Roadmap](ROADMAP.md), [Product refinement](PRODUCT_UX_REFINEMENT.md).

## 1. Design position

An editorial, disciplined software environment: warm paper, dark ink, precise alignment, and a restrained terracotta signal color. The product should feel maintained by a careful product team. Technical information is legible and useful; AI machinery remains under the hood.

F01 is a temporary text wordmark. Final naming, logo and trademark checks are outside this checkpoint. Recognition comes from the product's structure: a dark project rail, paper workspace, a precise Trace gutter, squared status treatments, and Project Pulse.

Avoid gradients, glass panels, neon, glows, floating blobs, decorative AI diagrams, giant pill cards, generic illustrations, and icon-heavy navigation. Use hierarchy, alignment, typography, and visible state to establish quality. A restrained interface must still have density and useful information.

## 2. Color tokens

Light mode is the Phase 1 product theme. The rail is intentionally dark; this is not a separate dark-mode implementation. Semantic success/warning/error colors are reserved for their meanings and do not become additional brand accents.

| Token | Value | Use |
| --- | --- | --- |
| `color.canvas` | `#F6F4EF` | App background, workspace paper |
| `color.surface` | `#FFFEFA` | Inputs, inspector, raised detail surfaces |
| `color.surface-muted` | `#EEEDE6` | Table headers, inactive controls, skeleton base |
| `color.ink` | `#222722` | Primary text, dark rail background |
| `color.ink-muted` | `#60665F` | Secondary text with sufficient contrast |
| `color.line` | `#DCDDD5` | Structural dividers; not the only control boundary |
| `color.line-strong` | `#848A82` | Input borders, essential graphical boundaries |
| `color.accent` | `#B84026` | Primary action, active marker, focus ring |
| `color.accent-hover` | `#9C341F` | Primary action hover/pressed |
| `color.accent-soft` | `#F9E5DD` | Selected row/background; use accent text |
| `color.on-accent` | `#FFFFFF` | Primary action text |
| `color.rail-line` | `#3C443D` | Dark rail separators |
| `color.rail-muted` | `#B8BEB5` | Rail secondary text |
| `color.success` | `#2D6847` | Live/passed state |
| `color.success-soft` | `#E3EFE7` | Success background |
| `color.warning` | `#8B5B12` | Recoverable attention state |
| `color.warning-soft` | `#F5ECD9` | Warning background |
| `color.error` | `#AC3434` | Failed state, destructive confirmation |
| `color.error-soft` | `#F8E4E3` | Error background |

Implement these as semantic CSS custom properties referenced by Tailwind, not repeated hex classes. Maintain one theme source. Color changes must update contrast verification and this document.

Normal text requires at least 4.5:1 contrast; large text and essential graphical controls require at least 3:1. Subtle line tokens are for nonessential separation. Input borders use the strong token. Muted text is not low-opacity primary text. Focus uses a visible 2px accent outline with a 2px offset; dark rail focus uses a light outline for reliable contrast.

## 3. Typography

Proposed family: **IBM Plex Sans** for product text, **IBM Plex Mono** for timestamps, versions, log metadata, and code. Self-host a small font subset after verifying the font license at implementation. Fallbacks: system sans and system monospace. No remote font service is required.

| Role | Size / line height | Weight | Use |
| --- | --- | --- | --- |
| `type.display` | 36 / 42px | 500 | Dashboard heading only; responsive 28 / 34px |
| `type.title` | 24 / 30px | 500 | Project/route heading |
| `type.section` | 20 / 26px | 500 | Major specification sections |
| `type.body` | 16 / 24px | 400 | Briefs, rationale, readable prose |
| `type.ui` | 14 / 20px | 400–500 | Controls, navigation, list rows |
| `type.dense` | 13 / 18px | 400–500 | Trace and dense utility details |
| `type.meta` | 12 / 16px | 400–500 | Labels and technical metadata |

Use at most regular, medium, and semibold weights. Headings may use slight negative tracking (-0.02em); metadata labels may use +0.04em. Reserve uppercase for short small labels such as SIMULATION or VERSION. Body content stays sentence case. Monospaced tabular numbers keep event times aligned. Avoid microscopic 10px “technical” text.

Brief and Brain prose have a maximum reading measure of about 70 characters. Long IDs truncate visually with an accessible copy action and full value on demand. Titles wrap or truncate according to location; tooltips must not be the only access to the full title.

## 4. Spacing and geometry

| System | Values | Rules |
| --- | --- | --- |
| Spacing | 4, 8, 12, 16, 20, 24, 32, 40, 48, 64px | 4px base; no random 17px/23px gaps |
| Radius | 0px structural, 2px status, 4px controls, 6px panels, 8px dialogs | No fully rounded containers except true avatars |
| Borders | 1px normal; 2px focus | Separate hierarchy through placement and contrast |
| Control heights | 32px compact, 40px default, 44px touch | Small desktop controls retain adequate hit area |
| Shadow 0 | none | Default layout surfaces |
| Shadow 1 | `0 2px 8px rgba(34,39,34,0.08)` | Menus/popovers |
| Shadow 2 | `0 12px 32px rgba(34,39,34,0.12)` | Modal/dialog separation |

Use borders, not shadows, for most hierarchy. Cards appear only when content is an independent entity; lists, plans, Trace, and utility tabs use shared surfaces with row dividers. Dense rows still have consistent padding and enough pointer/keyboard target area.

## 5. Layout and responsive rules

Desktop workspace: 240px global rail, flexible main canvas, 320px inspector. The project header is 64px high and project navigation is 40px. The preview is the largest surface. Typical canvas padding is 24px; utility regions use 16px.

| Width | Layout |
| --- | --- |
| At least 1280px | Full rail + canvas + optional inspector; preview minimum useful width about 480px |
| 1024–1279px | 64px compact rail; inspector opens as a drawer |
| 768–1023px | Rail opens as a sheet; main content remains full width; utility drawer |
| Below 768px | Single surface, stacked header, horizontally scrollable project nav, full-height utility drawer |

The request drawer is closed by default on the preview route. Opening requests replaces the utility inspector or opens a drawer; it does not add a fourth narrow desktop column. Inspector resizing is deferred; a reliable fixed layout comes first. Persist simple panel preferences locally without persisting project domain data there.

Dashboard default is an editorial project list with aligned title, status, last activity, and version columns. A modest synthetic preview thumbnail may accompany a row; avoid a wall of identical large cards. Search and filters sit directly above the list. Empty state presents one action and one example brief.

The homepage is an interface-first entry surface: editorial outcome heading, a real brief composer, selectable project starters and a labeled sample workspace/Trace. The create-project page emphasizes the composer alongside a concise planning guide. Returned plans use numbered document sections. Workspace utility surfaces remain visually calmer than the preview.

## 6. Project Pulse

Pulse is a functional signature: three narrow vertical strokes with differentiated heights and a shared baseline in an 18 × 20px footprint, followed by a plain-language state label. No glow, orbital animation, or audio. It appears in the brief composer, empty workspace, demonstration and state showcase. Future project rows/run summaries reuse the same geometry.

| Pulse state | Static pattern | Optional motion | Domain mapping |
| --- | --- | --- | --- |
| Idle | Three outlined strokes | None | `idle` |
| Thinking | Center stroke filled | Gentle center opacity cycle, 900ms | `understanding`, `planning`; queued is static |
| Building | First two filled, third outlined | Third stroke activates in a short step pattern, 600ms | `building` |
| Verifying | Outer strokes filled, center outlined | Short alternating emphasis, 700ms | `verifying` |
| Shipping | All three filled in accent | One 480ms fill sweep on entry | `deploying` |
| Live | All three filled in success color | None | `live` |
| Error | Interrupted center stroke, outer strokes filled | None | `error` |

Animated emphasis runs for at most 8 seconds after a phase change and settles to the static pattern; the label remains current. Reduced motion uses static patterns immediately. This expresses state, not progress percentage. Trace supplies the evidence.

Pulse geometry is hidden from assistive technology; the accompanying text is the accessible state. Announce phase changes once in a polite live region, not each animation cycle or event. Error text explains the failed run and recovery action. On the rail use accessible light variants while preserving semantic labels.

Presentation states include Idle, Thinking, Building, Verifying, Shipping, Live and Error. Domain aliases Understanding, Planning and Deploying remain supported without changing lifecycle/API enums. Actual successful fixture runs must still disclose demonstration mode; the homepage labels the entire sample and its Trace as a visual demonstration. Never introduce public “CEO Agent,” “Coding Agent,” or “QA Agent” labels.

## 7. Build Trace signature

Trace uses a 52px monospaced time gutter, narrow phase marker, and aligned action text on a single shared surface. Phase headings separate groups with a subtle divider. The active row has a restrained accent marker; completed rows do not glow or turn the entire panel green.

- Visible times use the viewer's local timezone and 24-hour format; show the timezone in panel metadata and UTC in event details.
- Ordering uses server sequence, even if events have identical timestamps.
- Each row offers action/result, severity, mode, and expandable details. Fixture entries carry a small Simulation treatment.
- Failed verification exposes the issue and links to its repair event. A repaired issue retains its original failure row.
- Auto-follow only while the user is at the latest position. Otherwise show “New events” and “Jump to latest.”
- “Reconnecting” is stream health, not a failed project. Keep the last known state and offer Retry.

Activity reuses this visual language and defaults to user actions/milestones. Real builds show persisted bounded command/issue evidence; raw unrestricted logs are not exposed. Simulation entries remain labeled and never stand in for real verification. Unavailable operational panels explain their limits without fabricated terminal output.

## 8. Component and interaction rules

| Component | Required behavior |
| --- | --- |
| Button | Primary, secondary, quiet, destructive; pending preserves width; single-submit guard |
| Input / textarea | Visible label, inline error, helper text, character limit, preserved content after failure |
| Project row | One primary link; secondary menu does not nest a button in a link; keyboard accessible |
| Status badge | Text + shape/color; 2px radius; shared state mapping |
| Tabs | Correct roles/keyboard movement; selected underline or border, not a giant pill |
| Drawer / dialog | Focus trap, escape-to-close, restore focus, labeled title; background inert |
| Inspector | Trace default; stable tab selection; accessible expand/collapse |
| Preview toolbar | Current fixture/version, viewport presets, refresh action, explicit sample indicator |
| Brain section | Heading, structured content, provenance, revision metadata, unresolved questions |
| Version row | Number, request/run, summary, time, Simulation label; inspect action, no fake rollback |
| Request composer | Plain compact textarea; clear save/simulate action; visible base context |
| Placeholder | Explain unavailable capability once; disabled action with reason, no pretend progress |

Use native elements where possible. Add a small accessible headless primitive library only if it materially improves complex focus behavior. Icons come from one small, consistent outline set, at 16px or 20px with a uniform stroke. Icons indicate actions or navigation; do not attach one to every label. Text labels remain the default. Custom Pulse geometry is the sole signature glyph.

Keyboard: Tab follows visual reading order; Escape closes temporary surfaces; Enter activates links/buttons; Cmd/Ctrl+Enter may submit a focused brief/request form when enabled. Display this shortcut as a hint; never intercept it globally. Provide a skip-to-content link.

Archive is reversible. If a run is active, show why archive is unavailable and link to run cancellation. Run cancellation explains that the prior successful preview remains available. Version inspection never implies rollback. Any future destructive action requires explicit consequence copy.

## 9. Motion and feedback

Motion tokens: 100ms hover/press, 160ms control state, 220ms drawer/dialog entry. Use an ease-out curve such as `cubic-bezier(0.2, 0, 0, 1)`. Animate opacity/transform; avoid layout jumps and spring/bounce effects. Pulse is the only specialized motion and follows its limits above.

Reduced-motion preference removes translation, looping emphasis, shimmer, and preview transitions. No animation gates a user action or hides a result. Streaming events appear without shifting existing rows unexpectedly.

Use inline feedback for form/save outcomes. Use a restrained toast only for background success that would otherwise be missed; it must not be the only place an error is explained. Failure messages say what happened and what action can resolve it.

## 10. Loading, empty, and error states

| State | Treatment |
| --- | --- |
| Initial dashboard/workspace load | Layout-matched static skeletons; no fake project records |
| Save/create pending | Inline button spinner and progress verb; inputs preserved |
| Active simulated run | Real persisted lifecycle/Trace; no invented percentage |
| Refresh pending | Existing content remains, small updating label |
| No projects | Short explanation, Create project, one example brief |
| No successful version | Preview frame states “Demo preview will appear when the simulation completes” |
| Unsupported arbitrary brief/change | Preserve request; generic sample or unchanged demo explicitly identified |
| Stream disconnected | Keep content, show Reconnecting/Retry; do not set project to Error |
| API unavailable | Explain retrieval/save failure, retry, retain pending input |
| Stale Brain/version | Preserve draft, show current revision and review action |
| Failed run | Needs attention, failed step, Retry/Cancel as appropriate, prior preview still identified |
| Unknown/missing project | Accessible not-found page with return to Projects |

## 11. Visual acceptance criteria

Before marking a UI milestone stable, inspect the actual application at representative desktop, tablet, and phone widths. Verify long titles, multiline briefs, dense Trace, empty projects, failed runs, unavailable API, and a selected older version.

Check contrast, keyboard path, focus restoration, 200% zoom, reduced motion, and screen-reader labels. No horizontal page overflow; an intentionally scrollable preview or navigation region is labeled. Body text is readable without zooming. Status is never color-only. Look for duplicated spacing, ad hoc colors, and radius drift.

The application should remain identifiable when its temporary wordmark is hidden. The rail/canvas contrast, terracotta active marker, Trace gutter, and Pulse should carry the identity. These decisions precede component implementation and change only through an explicit revision to this document.

## Revision notes

- 0.5: Aligned availability language with completed Phase 2B and the documentation-only 2C proposal. Real versus simulated Trace/preview and separate future production status reuse existing tokens; no UI or visual redesign implemented.

- 0.4: M6 improves compact navigation names, modal focus wrapping/restoration, saved-state connection visibility, current/historical labels and bounded readable Trace layout. Semantic colors and brand identity are unchanged.

- 0.1: Proposed visual foundations, tokens, layout, functional signature, states, and accessibility requirements. No visual components implemented.


## 12. First-time product experience — original redesign checkpoint

The founder authorized a frontend-only redesign after M2. No backend, database,
authentication, persistence or API contract changes accompany this milestone.

- `/`: 48–82px editorial display type on desktop, responsive 34–54px on phones;
  warm paper, dark ink and terracotta. A real composer shares the first work area
  with a clearly labeled sample workspace. The primary action is **Create plan**,
  accurately describing today's result. Create → Run → Manage → Evolve is a
  ruled progression with availability stated per stage.
- `/projects`: a spacious control-center hierarchy, disabled/explained future
  inventory controls, a deliberate empty-register composition, and three project
  starter artifacts. No rows, counts, timestamps or statuses pretend to be saved
  inventory. Starters are real navigation to known brief presets.
- `/projects/new`: dominant intention/brief input, concise planning guide, all
  existing loading/error/cancel/retry/validation states and a numbered project
  plan document. The draft is explicitly unsaved and starts no build.

Reusable patterns are the paper composer, compact selectable starter rows,
numbered document gutters, restrained artifact graphics, three-stroke Pulse, and
ordered Trace time columns. The same semantic tokens remain in `globals.css`;
`experience.css` contains the product-surface layout rules. No imagery, additional
runtime dependency, external font service or generative asset is needed.

The demonstration presents five fixed illustrative events. It plays one bounded
sequence, then stops; Pause, Play and Replay are keyboard accessible. Reduced
motion starts it static and stops an active sequence when the preference changes.
No timer changes real planning state, calls an API, writes project state or
executes work. The example CRM, booking and game surfaces are illustrations.

At 375px, the composer/CTA precede the sample and starters become compact rows.
At 768px, the homepage uses an input-plus-starters composition above the sample.
At 1280/1440px, input and sample share the same work area. Plans use document
sections with a left label gutter on desktop and explicit stacked section labels
on mobile. The rail wordmark uses the light surface token for readable contrast.

Validation includes real-browser interaction regression tests, all three pages
at 375/768/1280/1440px, reduced motion, mobile dialog focus restoration, visible
focus and 200% zoom reflow. Accessibility scans cover WCAG A/AA rules; their scope
is the visible tested surfaces, not a claim of complete accessibility certification.


### Homepage identity pass

The entry uses a continuous registration frame: numbered command and workspace
regions, precise corner marks, and a stepped-gate Pulse symbol shared with the
wordmark. The global navigation exposes Projects, Templates, Connections, Docs,
Account and Start a brief. Mobile navigation uses the existing accessible Sheet.
The composer uses outcome-first language and category starters.

The sample workspace exposes Preview/Blueprint, compact/full viewport, selectable
Trace evidence and bounded playback. Every sample is labeled; no action executes
a build or changes persistence. A continuous Create/Run/Manage/Evolve rail leads
into a flat platform index. Starter briefs and planning documentation are available;
Brain, Versions, Deployments, Runtime/Logs, natural-language changes and external
connections are explicitly planned. Layout is in operating-entry.css; shared
planning behavior and existing dashboard/create layouts remain intact.


## 13. Historical Phase 1 quality — M6

At the M6 checkpoint, availability labels distinguished real draft planning, saved Brain/context, simulated versions/deployment records and recorded change intent; source execution and external release were unavailable. Completed 2B now has real source/verification/repair and isolated preview. Production release remains proposed only; the homepage sample remains a labeled illustration.

The saved workspace shows connection health outside the inspector; offline content stays visible and Retry connection resumes ordered replay without clearing loaded history. Pulse announces lifecycle changes politely; sequence increments are not repeated live announcements. Current and historical versions/attempts remain visibly distinct.

Compact-rail links retain explicit accessible names. Skip links focus the main region; modal Tab/Shift+Tab wraps inside reachable controls, Escape closes and focus returns to its opener. Desktop inspectors remain nonmodal. Essential controls use the existing visible focus and semantic contrast tokens.

Trace metadata is at least 12px. Its compact inspector title uses 18/24px type. A keyboard-accessible Simulation disclosure holds explanatory scope and timezone metadata, leaving event space in short viewports; phase labels, follow controls and structured event references remain reachable. Linked fixture issues/repairs pause follow and focus the referenced row. Obsolete competing Trace height rules are consolidated.

Acceptance includes long 100-character titles and 10,000-character briefs, 375/768/1280/1440px surfaces plus the compact rail, reduced motion, keyboard/focus review and 200% reflow (1440×1000 physical-equivalent area at 720×500 CSS pixels and DPR 2). Actual screenshots were inspected and visible WCAG A/AA scans passed; this is scoped verification, not an accessibility certification.


## 14. Completed Phase 2B and proposed Phase 2C presentation

Real build phases and source/evidence metadata use the existing Trace, Pulse, typography and state tokens. Verified preview is identified by its real source/version; older Simulation records remain explicitly labeled. Verification does not imply production deployment or completion of every user requirement.

The bounded 2C plan proposes separate Current preview and Current production labels, exact artifact/configuration review, observed public URL/health and immutable release inspection. Pending, failed and reconciling releases must not visually replace the previous working production state. Historical inspection is read-only. Use existing drawers/tables/focus/recovery patterns; no redesign, new tokens, release controls or weakened preview sandbox is implemented in this documentation task.
