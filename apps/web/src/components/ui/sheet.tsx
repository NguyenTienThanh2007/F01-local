'use client';
import { useEffect, useLayoutEffect, useRef, useId, type ReactNode } from 'react';
import { containDialogFocus } from './dialog-focus';
export function Sheet({ open, onClose, title, children }: { open: boolean; onClose: () => void; title: string; children: ReactNode }) {
  const titleId = useId();
  const ref = useRef<HTMLDialogElement>(null);
  const returnFocus = useRef<HTMLElement | null>(null);
  useLayoutEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) {
      returnFocus.current = document.activeElement as HTMLElement;
      dialog.showModal();
    } else if (!open && returnFocus.current) {
      if (dialog.open) dialog.close();
      if (returnFocus.current.isConnected) returnFocus.current.focus();
      returnFocus.current = null;
    }
  }, [open]);
  useEffect(() => () => { ref.current?.close(); }, []);
  return <dialog ref={ref} tabIndex={-1} className="sheet" aria-labelledby={titleId} onCancel={event => { event.preventDefault(); onClose(); }} onKeyDown={containDialogFocus} onClick={event => { if (event.target === ref.current) onClose(); }}>
    <div className="sheet-heading"><h2 id={titleId}>{title}</h2><button className="icon-button" onClick={onClose} aria-label="Close panel">×</button></div>
    {children}
  </dialog>;
}
