import { useId, useRef, useState, type FormEvent, type ReactNode } from 'react';
import { AppDialog } from '../shared/AppDialog';
import { ErrorNotice } from './AiBits';
import { type AiApiError, toAiApiError } from './aiErrors';
import './ai-operator.css';

const MIN_REASON = 3;
const MAX_REASON = 500;

/**
 * Diálogo que pede um motivo antes de uma ação (corrigir proposta, desfazer).
 *
 * O motivo vai para a auditoria do servidor, por isso é obrigatório. Reaproveita
 * o `AppDialog` (foco inicial, ciclo de Tab, Escape, devolução do foco); o
 * conteúdo recebe a classe `.ai-operator` porque o diálogo é montado em
 * `document.body`, fora do escopo de tokens da página.
 */
export function ReasonDialog({ title, description, children, reasonLabel, confirmLabel, danger = false, onSubmit, onClose }: {
  title: string;
  description?: string;
  children?: ReactNode;
  reasonLabel: string;
  confirmLabel: string;
  danger?: boolean;
  /** Deve lançar em caso de falha; o diálogo continua aberto e mostra o erro. */
  onSubmit: (reason: string) => Promise<void>;
  onClose: () => void;
}) {
  const fieldId = useId();
  const hintId = useId();
  const field = useRef<HTMLTextAreaElement>(null);
  const lock = useRef(false);
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [invalid, setInvalid] = useState(false);
  const [error, setError] = useState<AiApiError | null>(null);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    // A trava por ref fecha a janela entre o clique e o re-render com `disabled`.
    if (lock.current) return;
    const text = reason.trim();
    if (text.length < MIN_REASON) { setInvalid(true); field.current?.focus(); return; }
    lock.current = true; setBusy(true); setError(null); setInvalid(false);
    try {
      await onSubmit(text);
    } catch (failure) {
      setError(toAiApiError(failure));
    } finally {
      lock.current = false; setBusy(false);
    }
  };

  return <AppDialog title={title} description={description} busy={busy} onClose={() => { if (!busy) onClose(); }} initialFocus={field} size="sm">
    <form className="ai-operator ai-dialog" onSubmit={event => void submit(event)} noValidate>
      {children}
      <label htmlFor={fieldId} className="ai-label">{reasonLabel}</label>
      <textarea id={fieldId} ref={field} className="ai-textarea" rows={3} maxLength={MAX_REASON} value={reason}
        aria-describedby={hintId} aria-invalid={invalid} disabled={busy}
        onChange={event => { setReason(event.target.value); if (invalid) setInvalid(false); }} />
      <p id={hintId} className={invalid ? 'ai-field-error' : 'ai-muted ai-small'} role={invalid ? 'alert' : undefined}>
        {invalid ? 'Escreva o motivo em poucas palavras para continuar.' : 'O motivo fica registrado no histórico da operação.'}
      </p>
      {error && <ErrorNotice error={error} />}
      <div className="ai-actions ai-actions-end">
        <button type="button" className="ai-button" disabled={busy} onClick={onClose}>Cancelar</button>
        <button type="submit" className={`ai-button ${danger ? 'ai-button-danger' : 'ai-button-primary'}`} disabled={busy}>{busy ? 'Enviando…' : confirmLabel}</button>
      </div>
    </form>
  </AppDialog>;
}
