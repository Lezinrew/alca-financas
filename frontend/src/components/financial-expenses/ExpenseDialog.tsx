import React, { useEffect, useId, useRef } from 'react';
import { createPortal } from 'react-dom';

export interface ExpenseDialogProps {
  title: string;
  children: React.ReactNode;
  onClose: () => void;
  busy?: boolean;
  initialFocus?: React.RefObject<HTMLElement>;
}

/** Mount while open. The caller handles unsaved changes in onClose. */
export function ExpenseDialog({ title, children, onClose, busy = false, initialFocus }: ExpenseDialogProps) {
  const titleId = useId();
  const panel = useRef<HTMLDivElement>(null);
  const latest = useRef({ onClose, busy });
  latest.current = { onClose, busy };

  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const bodyOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const focusable = () => Array.from(panel.current?.querySelectorAll<HTMLElement>(
      'button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), a[href], [tabindex="0"]',
    ) ?? []).filter(element => !element.closest('[hidden]'));
    (initialFocus?.current ?? focusable()[0] ?? panel.current)?.focus();
    const keydown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        if (!latest.current.busy) latest.current.onClose();
      }
      if (event.key === 'Tab') {
        const elements = focusable();
        const first = elements[0];
        const last = elements[elements.length - 1];
        if (!first) { event.preventDefault(); panel.current?.focus(); return; }
        if (event.shiftKey && (document.activeElement === first || document.activeElement === panel.current)) {
          event.preventDefault(); last.focus();
        } else if (!event.shiftKey && (document.activeElement === last || document.activeElement === panel.current)) {
          event.preventDefault(); first.focus();
        }
      }
    };
    const keepFocus = (event: FocusEvent) => {
      if (!panel.current?.contains(event.target as Node)) (focusable()[0] ?? panel.current)?.focus();
    };
    document.addEventListener('keydown', keydown);
    document.addEventListener('focusin', keepFocus);
    return () => {
      document.removeEventListener('keydown', keydown);
      document.removeEventListener('focusin', keepFocus);
      document.body.style.overflow = bodyOverflow;
      if (previous?.isConnected) previous.focus();
    };
  }, [initialFocus]);

  return createPortal(
    <div className="payables fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-3 sm:p-6">
      <div ref={panel} role="dialog" aria-modal="true" aria-labelledby={titleId} aria-busy={busy} tabIndex={-1}
        className="modal-content w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-xl bg-white text-slate-900 dark:bg-slate-900 dark:text-white">
        <div className="flex items-center justify-between gap-3 border-b border-slate-200 p-4 dark:border-slate-700">
          <h2 id={titleId} className="text-lg font-semibold">{title}</h2>
          <button type="button" onClick={onClose} disabled={busy} aria-label="Fechar diálogo"
            className="min-h-[44px] min-w-[44px] rounded-lg focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-600 disabled:opacity-50">✕</button>
        </div>
        {children}
      </div>
    </div>, document.body,
  );
}
