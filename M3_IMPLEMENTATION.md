# M3 — persisted projects journey

Status: implemented and verified; stopped before M4.

The redesigned dashboard now lists real M2 projects. Search operates on titles;
lifecycle/status and active/archived filters, plus cursor pagination, use URL query
parameters and backend queries. Rows show authoritative IDs, states and activity
timestamps. Empty, filtered-empty, initial loading, refreshing, unavailable and
retry states are explicit. Starter artifacts remain brief presets, never inventory.

/projects/new now has Save a project and Explore a draft plan. The former uses an
optional title (up to 100 characters) and an original brief (20–10,000 characters),
and explains the demonstration boundary before submission. The latter preserves
the existing planning component and gateway; model plans stay unsaved page drafts.
Creation navigates to /projects/{id} only after confirmed server success.

Each submitted command freezes its UUID key and trimmed input. Pending clicks
cannot submit again. Lost/network/server responses keep the receipt and input;
retry and reload use the same command until confirmed. Only an unresolved receipt
is stored in sessionStorage, and removed after confirmation or a definite failed
outcome. If storage is blocked the mounted form retains the receipt in memory.
An unresolved receipt older than the backend's 24-hour replay window requires
checking saved Projects; it is never silently submitted with a fresh key.
There is no localStorage project database or hardcoded project inventory.

/projects/{id} is only a persisted metadata/settings surface. It supports reload,
rename and archive/unarchive; dashboard rows offer the same inline controls. PATCH
uses the project's metadata ETag. A 412 preserves the title draft and requires a
review of current server metadata before retry. Missing/foreign records share the
same unavailable result. No workspace, Brain reader, Trace or preview UI is added.

The fixed same-origin gateways allow only session GET, project list/create and
project read/PATCH. The OpenAPI-generated server-only M2 client performs backend
calls. Private identity credentials remain server-side. Validation, timeout,
no-store, same-origin write protection and sanitized errors preserve the existing
identity boundary. No backend, schema, generated client or planning logic changed.

Important existing invariant: every M2 creation queues an active run. Archive
returns ACTIVE_RUN_EXISTS until that run ends. M3 displays this conflict and does
not add cancellation or execution. Archive/unarchive is supported for eligible
records. The disposable test fixture ends its run directly before verifying archive;
this is test setup, not a simulator or product command.

New/reworked source:
- features/projects: dashboard, creation, saved record and shared settings
- lib/projects: generated DTO aliases, private gateway, browser request wrapper,
  validation and unresolved-command receipt handling
- /api/v1/projects, /api/v1/projects/[projectId], /api/v1/session
- /projects, /projects/new, /projects/[projectId]
- styles/project-management.css and its root import
- web workspace dependency on @f01/api-client; frontend test commands
- projects.test.mjs, projects.e2e.test.mjs, existing planning browser regression
- scripts/test-m3.py, README and source-of-truth checkpoint notes

Verification:
- pnpm typecheck: passed
- pnpm test:web: 30 tests passed
- pnpm build: passed
- pnpm test:e2e: 13 planning/homepage scenarios passed (14 including parent)
- real FastAPI + freshly migrated PostgreSQL 16 browser journey: passed
- journey covers validation/input retention, duplicate prevention, response loss,
  same-key recovery across reload, one persisted result, rename, search/status/archive
  filters, archive guard, archive/unarchive/reopen, 412 review and service retry
- dashboard/create/record at 375/768/1280/1440px: no horizontal overflow;
  WCAG A/AA axe scans found no violations in tested surfaces
- empty, loading, populated, uncertain-create and unavailable UI inspected
- backend and generated-client hashes match the pre-M3 baseline; backend tests
  were not rerun because backend code did not change

All verification uses synthetic credentials and controlled provider responses or
the real local persistence API. No live model call, deployment, connector, worker,
generation, team, billing, editor or outcome engine work was performed.
