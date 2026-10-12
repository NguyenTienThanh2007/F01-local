# Before and after screenshots

Actual production-build browser captures at 1440px and 375px. Choose the page, theme environment and width in [gallery.html](gallery.html).

Baseline: `2fe82d3`. Implementation: `d3ad86e`. The baseline had one appearance: OS Dark still rendered the old Light interface. The Dark-before images document that limitation; they are not a fabricated prior Dark design.

The baseline sign-in used the previous generic controlled OIDC configuration. After captures enable the already-existing Google/email test connections. These images do not verify actual Google login or email delivery. Generated applications are minimal controlled test source running in genuine isolated Docker previews; their appearance is intentionally independent of F01.

## 1440px comparison

| Page | Light before | Light after | OS Dark before (single Light appearance) | Dark after |
|---|---|---|---|---|
| Homepage | [View](before/before-light-start-1440.png) | [View](after/light-start-1440.png) | [View](before/before-dark-start-1440.png) | [View](after/dark-start-1440.png) |
| Projects Dashboard | [View](before/before-light-projects-1440.png) | [View](after/light-projects-1440.png) | [View](before/before-dark-projects-1440.png) | [View](after/dark-projects-1440.png) |
| Sign in | [View](before/before-light-sign-in-1440.png) | [View](after/light-sign-in-1440.png) | [View](before/before-dark-sign-in-1440.png) | [View](after/dark-sign-in-1440.png) |
| Project Workspace | [View](before/before-light-preview-verified-1440.png) | [View](after/light-preview-verified-1440.png) | [View](before/before-dark-preview-verified-1440.png) | [View](after/dark-preview-verified-1440.png) |

## 375px comparison

| Page | Light before | Light after | OS Dark before (single Light appearance) | Dark after |
|---|---|---|---|---|
| Homepage | [View](before/before-light-start-375.png) | [View](after/light-start-375.png) | [View](before/before-dark-start-375.png) | [View](after/dark-start-375.png) |
| Projects Dashboard | [View](before/before-light-projects-375.png) | [View](after/light-projects-375.png) | [View](before/before-dark-projects-375.png) | [View](after/dark-projects-375.png) |
| Sign in | [View](before/before-light-sign-in-375.png) | [View](after/light-sign-in-375.png) | [View](before/before-dark-sign-in-375.png) | [View](after/dark-sign-in-375.png) |
| Project Workspace | [View](before/before-light-preview-verified-375.png) | [View](after/light-preview-verified-375.png) | [View](before/before-dark-preview-verified-375.png) | [View](after/dark-preview-verified-375.png) |

## Other real product states

Each state is saved in Light/Dark at desktop/mobile widths in `after/`: Signup, Create, plan approval, queued build, reviewed deployment, Live, Versions, Account, Build Trace, dashboard error and first-project empty state. `build-states/` adds repair, failure, cancellation, stall and preserved-live presentation captures. `actual-worker/` contains the freshly observed real Docker/process-loss states.

`bootstrap/` shows Light, Dark and System before React hydration. The same-origin theme bootstrap and native selector remain correct while all React chunks are blocked.
