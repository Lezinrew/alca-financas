import React, { useEffect, useId, useRef } from 'react';
import { createPortal } from 'react-dom';
import './app-dialog.css';

export interface AppDialogProps {
  title: string;
  children: React.ReactNode;
  onClose: () => void;
  /** Enquanto verdadeiro, Escape e o botão de fechar ficam bloqueados. */
  busy?: boolean;
  initialFocus?: React.RefObject<HTMLElement>;
  /** Largura máxima do painel. */
  size?: 'sm' | 'md' | 'lg';
  /** Texto descritivo lido junto com o título. */
  description?: string;
}

const FOCUSABLE = 'button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), a[href], [tabindex="0"]';

/**
 * Diálogo modal acessível: foco inicial, ciclo de Tab, Escape, bloqueio de rolagem
 * e retorno do foco ao elemento que o abriu. Monte apenas enquanto estiver aberto.
 */
export function AppDialog({ title, children, onClose, busy = false, initialFocus, size = 'md', description }: AppDialogProps) {
  const titleId = useId();
  const descriptionId = useId();
  const panel = useRef<HTMLDivElement>(null);
  const latest = useRef({ onClose, busy });
  latest.current = { onClose, busy };

  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const bodyOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const focusable = () => Array.from(panel.current?.querySelectorAll<HTMLElement>(FOCUSABLE) ?? [])
      .filter(element => !element.closest('[hidden]'));
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
    <div className="app-dialog-backdrop">
      <div ref={panel} role="dialog" aria-modal="true" aria-labelledby={titleId} aria-describedby={description ? descriptionId : undefined}
        aria-busy={busy} tabIndex={-1} className={`app-dialog-panel app-dialog-${size}`}>
        <div className="app-dialog-header">
          <div className="app-dialog-heading">
            <h2 id={titleId} className="app-dialog-title">{title}</h2>
            {description && <p id={descriptionId} className="app-dialog-description">{description}</p>}
          </div>
          <button type="button" onClick={onClose} disabled={busy} aria-label="Fechar diálogo" className="app-dialog-close">✕</button>
        </div>
        {children}
      </div>
    </div>, document.body,
  );
}
