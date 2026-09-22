import React, { useRef, useState } from 'react';
import { AppDialog } from './AppDialog';

export interface ConfirmDialogProps {
  title: string;
  /** Nome do item afetado, exibido em destaque. */
  subject?: string;
  /** Pares rótulo/valor mostrados antes da consequência. */
  details?: Array<[string, React.ReactNode]>;
  /** Consequência da ação em linguagem simples. */
  consequence: React.ReactNode;
  confirmLabel: string;
  cancelLabel?: string;
  /** Ações destrutivas usam o estilo de perigo. */
  danger?: boolean;
  onConfirm: () => Promise<void> | void;
  onClose: () => void;
  /** Mensagem fixa exibida quando a confirmação falha. */
  errorMessage?: string;
}

/**
 * Confirmação com bloqueio de envio duplicado. `onConfirm` deve lançar em caso de
 * falha; o diálogo permanece aberto com a mensagem de erro e permite tentar de novo.
 */
export function ConfirmDialog({
  title, subject, details = [], consequence, confirmLabel, cancelLabel = 'Cancelar', danger = false,
  onConfirm, onClose, errorMessage = 'Não foi possível concluir a operação. Confira os dados atualizados antes de tentar novamente.',
}: ConfirmDialogProps) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const lock = useRef(false);
  const cancelRef = useRef<HTMLButtonElement>(null);

  const confirm = async () => {
    if (lock.current) return;
    lock.current = true; setBusy(true); setError('');
    try {
      await onConfirm();
    } catch {
      setError(errorMessage);
    } finally {
      lock.current = false; setBusy(false);
    }
  };

  return <AppDialog title={title} busy={busy} onClose={() => { if (!busy) onClose(); }} initialFocus={cancelRef} size="sm">
    <div className="app-dialog-body">
      {subject && <p className="app-dialog-subject">{subject}</p>}
      {details.length > 0 && <dl className="app-dialog-details">
        {details.map(([label, value]) => <React.Fragment key={label}><dt>{label}</dt><dd>{value}</dd></React.Fragment>)}
      </dl>}
      <div className="app-dialog-consequence">{consequence}</div>
      {error && <p className="app-dialog-error" role="alert">{error}</p>}
      <div className="app-dialog-actions">
        <button ref={cancelRef} type="button" className="app-dialog-button" disabled={busy} onClick={onClose}>{cancelLabel}</button>
        <button type="button" className={`app-dialog-button ${danger ? 'app-dialog-button-danger' : 'app-dialog-button-primary'}`} disabled={busy} onClick={() => void confirm()}>
          {busy ? 'Confirmando…' : confirmLabel}
        </button>
      </div>
    </div>
  </AppDialog>;
}
