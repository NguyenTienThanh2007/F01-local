"""Reusable UI guidance, not a fixed application template or execution evidence."""

INTERFACE_QUALITY_INSTRUCTIONS = """INTERFACE QUALITY
Choose a coherent visual direction suited to this product and its users. Do not clone
a named SaaS, use one identical template for every app, or add unrelated features.
Define a small, consistent CSS token system for typography, spacing, surfaces, borders,
text and accent colors. Prefer a readable system font stack, a restrained type scale,
clear headings, and 4/8px-based spacing. Use genuine CSS supported by the scaffold.
Prioritize the application's primary content in the initial viewport: a board, list,
document or working canvas. Use a compact header/navigation appropriate to its scope.
One clear primary action; secondary actions should not compete with the main task.
For frequent data entry, prefer a compact modal/drawer or contextual editor over a
large permanent form above the working content. Do not invent empty sidebars or
navigation destinations; every rendered control must perform a real supported action.
Ordinary inputs/selects/buttons should usually be 36-44px tall (mobile touch targets
at least 44px); textareas about 2-4 rows unless the actual task needs more. Avoid
oversized empty containers and excessive whitespace. Never put a flex-basis intended
for horizontal filter widths on shared input/select classes: in a column flex parent
it becomes control height. Put layout sizing on the row/grid wrapper, use min-width:0,
box-sizing:border-box and explicit compact control sizing instead.
Use aligned task/data cards, legible metadata and consistent buttons/menus. Convey
priority, deadline, error and status with text as well as color. Empty, loading, error,
no-results and storage-unavailable states should explain a useful next action; do not
fabricate sample user records, activity, statistics or progress for visual decoration.
Give long titles the full usable card width; put wrapping metadata on its own row
when necessary. Never let nowrap badges shrink a title to a few characters or overflow
a narrow card. Use minmax(0,1fr) grid tracks and min-width:0 on shrinking children;
stack columns before they become unreadably narrow. Prefer quiet secondary card
actions over a row of competing filled buttons. Provide a clear reset for no-results.
Use labelled controls, semantic landmarks/headings, visible keyboard focus, sufficient
WCAG AA contrast and usable target spacing. Dialogs need a name, initial focus, trapped
Tab focus, Escape/close, background inertness and focus restoration; use in-app UI that
works under the existing sandbox. Respect prefers-reduced-motion. Keep content readable
at desktop, tablet, 390px mobile and narrow reflow widths without page overflow.
Save the actual invoking element before opening an editor and restore focus there
after Escape, Cancel and save (fall back to the primary action only if it no longer
exists). Check normal-size text on its actual surface: white on a bright red button
or red text on a pink badge often fails 4.5:1; use a sufficiently dark foreground or
background. Do not assume an attractive accent guarantees accessible contrast.
Before returning source, review actual CSS dimensions, flex axes, wrapping, long titles,
empty/full states, keyboard interactions and contrast. This is a source review, not
a claim that browser tests ran. During diagnostic repair preserve the established
design and unrelated behavior; improve only the observed fault. Existing data keys,
IDs and schema must remain compatible; gate writes on completed storage hydration.
For date-only fields, preserve validated YYYY-MM-DD values and compare them with a
locally constructed calendar-day string. Date.parse('YYYY-MM-DD') interprets UTC,
so converting that instant back to local midnight can mark today's task overdue.
"""
