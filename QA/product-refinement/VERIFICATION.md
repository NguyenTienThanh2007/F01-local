# Product refinement verification · 2026-10-08

The application changes were checked on `codex/f01-commercial-v1`, product source commit `8c145c8`. GitHub's launcher commits were incorporated before the refinement was pushed. Main remains `449b0588e072cda102144c0c629d776049b4f2d2`.

## Results

| Check | Result |
| --- | --- |
| Backend regression | 334 passed; 4 explicit Docker/live acceptance cases skipped in the ordinary suite |
| Strict mypy | No issues in 102 files |
| Frontend tests | 61 passed |
| Generated-client tests | 2 passed |
| OpenAPI / generated TypeScript consistency | Passed |
| Typecheck / production build | Passed |
| Homepage planning browser acceptance | 14 passed |
| Original journey, keyboard, focus, offline/history, 200% reflow | 6 passed |
| Signed-in planning, provider errors, cancellation, lost response, ownership | 4 passed |
| Real-command receipt recovery, blocked storage, cancellation, expired recovery | 5 passed |
| Commercial Docker browser journey and visual audit | Passed |
| Route/state accessibility | 52 axe WCAG A/AA scans passed; loading skeleton captures inspected separately |
| Responsive layouts | All 27 states fit 375, 768, 1280 and 1440px without page overflow |

The final commercial journey creates, plans, reviews, builds, verifies, previews, packages, deploys, modifies, rebuilds, previews the update, redeploys and inspects versions/history. It also resolves a lost release response with the original command and retains the previous release while a newer preview is built. Reviewed-build and reviewed-rebuild states check a single primary workspace action. Dashboard recovery returns from a controlled failure to the saved project list.

## Visual inspection

Desktop and mobile full-page and viewport captures are in [screenshots](screenshots). The audit covers Start, Sign-in, empty/populated/error/loading Projects, Create, saved empty workspace, initial Planning, plan review/approval, reviewed build, queued build, verified Preview, deployment review, Live, reviewed rebuild, updated Preview, Versions, historical Preview, Brief, Brain, Activity, Settings, Account and Build Trace. Reduced motion is checked separately. Short-height Trace following is captured in [trace-reflow-200.png](screenshots/trace-reflow-200.png).

The inspected pass corrected Brain hash wrapping, filter clipping and cursors, active mobile tab visibility, competing build/release actions, adjacent error actions, short-height Trace following and disclosure state during context refresh. The original request, source/Brain/version lineage, history and release-recovery checks remain in the browser suites.

## Evidence boundaries

Docker builds, production packaging and isolated previews are real and use the already accepted immutable sandbox image. Identity and model responses are controlled fixtures. Deployment UI/protocol checks use a controlled provider; the public URLs shown in these screenshots are fixture values, not new live Vercel deployments. This frontend pass does not claim a new live-provider acceptance run. Earlier actual Vercel acceptance remains in [commercial-v1 verification](../commercial-v1/VERIFICATION.md).

[checks.json](checks.json) records results and log hashes; [audit.json](audit.json) records each route/state scan; [journey.json](journey.json) identifies the two verified versions and release records. Successful command output is retained in [checks](checks).
