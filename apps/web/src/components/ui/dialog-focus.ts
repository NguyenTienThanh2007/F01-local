import type { KeyboardEvent } from 'react';

/** Keep keyboard traversal inside an open modal, including the browser-chrome edge. */
export function containDialogFocus(event: KeyboardEvent<HTMLDialogElement>) {
  const dialog = event.currentTarget;
  if (event.key !== 'Tab' || !dialog.matches(':modal')) return;
  const controls = Array.from(dialog.querySelectorAll<HTMLElement>('a[href],button,input,textarea,select,summary,[tabindex]'))
    .filter(element => element.tabIndex >= 0 && !element.matches(':disabled') && !element.closest('[hidden],[inert]') && element.getClientRects().length > 0);
  const first = controls[0], last = controls.at(-1);
  if (!first || !last) { event.preventDefault(); dialog.focus(); return; }
  if (event.shiftKey && (document.activeElement === first || document.activeElement === dialog)) { event.preventDefault(); last.focus(); }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
}
