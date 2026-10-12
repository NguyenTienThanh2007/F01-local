# Before / after browser screenshots

Before: remote baseline `c5ce0f414c1aa1cb9917677b01a9879592a33f29`. After: tested product source committed as `98513ee47da88478a169de514e6f05c33170e04c`. All captures are actual rendered production-build pages, not mockups.

[Open the comparison gallery](gallery.html). Desktop is 1440×1000; phone is 375×1000. Full-page originals are alongside viewport crops.

| Page | Desktop before | Desktop after | Phone before | Phone after |
| --- | --- | --- | --- | --- |
| Homepage | [Before](before/start-1440-viewport.png) | [After](after/start-1440-viewport.png) | [Before](before/start-375-viewport.png) | [After](after/start-375-viewport.png) |
| Sign in | [Before](before/sign-in-1440-viewport.png) | [After](authentication/signed-out-1440.png) | [Before](before/sign-in-375-viewport.png) | [After](authentication/signed-out-375.png) |
| Sign up | [Before](before/sign-in-1440-viewport.png) | [After](authentication/signup-methods-1440.png) | [Before](before/sign-in-375-viewport.png) | [After](authentication/signup-methods-375.png) |
| Projects | [Before](before/projects-1440-viewport.png) | [After](after/projects-filters-1440-viewport.png) | [Before](before/projects-375-viewport.png) | [After](after/projects-filters-375-viewport.png) |
| Create Project | [Before](before/create-1440-viewport.png) | [After](after/create-1440-viewport.png) | [Before](before/create-375-viewport.png) | [After](after/create-375-viewport.png) |
| Planning | [Before](before/plan-review-1440-viewport.png) | [After](after/plan-review-1440-viewport.png) | [Before](before/plan-review-375-viewport.png) | [After](after/plan-review-375-viewport.png) |
| Build progress | [Before](before/build-queued-1440-viewport.png) | [After](after/build-queued-1440-viewport.png) | [Before](before/build-queued-375-viewport.png) | [After](after/build-queued-375-viewport.png) |
| Preview | [Before](before/preview-verified-1440-viewport.png) | [After](after/preview-verified-1440-viewport.png) | [Before](before/preview-verified-375-viewport.png) | [After](after/preview-verified-375-viewport.png) |
| Deploy | [Before](before/deploy-review-1440-viewport.png) | [After](after/deploy-review-1440-viewport.png) | [Before](before/deploy-review-375-viewport.png) | [After](after/deploy-review-375-viewport.png) |
| Live | [Before](before/live-1440-viewport.png) | [After](after/live-1440-viewport.png) | [Before](before/live-375-viewport.png) | [After](after/live-375-viewport.png) |
| Modify | [Before](before/rebuild-reviewed-1440-viewport.png) | [After](after/modify-1440-viewport.png) | [Before](before/rebuild-reviewed-375-viewport.png) | [After](after/modify-375-viewport.png) |
| Versions | [Before](before/versions-1440-viewport.png) | [After](after/versions-1440-viewport.png) | [Before](before/versions-375-viewport.png) | [After](after/versions-375-viewport.png) |
| Account Settings | [Before](before/account-1440-viewport.png) | [After](authentication/profile-reloaded-1440.png) | [Before](before/account-375-viewport.png) | [After](authentication/profile-reloaded-375.png) |

Comparison limits: signup is a new route; Modify uses different update stages as captioned in the gallery. Identity/model/publishing providers are controlled; Docker build, verification and isolated preview are real. Homepage examples are explicitly illustrative. Factory WCAG audits exclude generated iframes.

The after audit covers 30 product states (60 desktop/mobile captures), 58 passing WCAG scans and two transient loading captures without axe. Auth adds nine states and 36 scans. Layout reflow also covers 320/720/768/1280px.

[Authentication verification and missing configuration](AUTHENTICATION.md) · [Full-system reliability](FULL_SYSTEM_RELIABILITY.md) · [Acceptance and review instructions](VERIFICATION.md).
