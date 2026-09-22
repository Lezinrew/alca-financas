import { useId, useRef, useState } from 'react';
import { AppDialog } from '../shared/AppDialog';
import { CLEAR_DATA_CONFIRMATION, CLEAR_DATA_ENTITIES } from './clearDataEntities';

interface ClearDataDialogProps {
  /** Deve lançar em caso de falha; o diálogo permanece aberto com a mensagem. */
  onConfirm: () => Promise<void>;
  onClose: () => void;
}

/**
 * Confirmação da limpeza total: lista o que será apagado e exige digitar
 * a palavra de confirmação. Bloqueia envio duplicado enquanto a chamada corre.
 */
export function ClearDataDialog({ onConfirm, onClose }: ClearDataDialogProps) {
  const [typed, setTyped] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const lock = useRef(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const inputId = useId();
  const hintId = useId();
  const ready = typed === CLEAR_DATA_CONFIRMATION;

  const confirm = async () => {
    if (!ready || lock.current) return;
    lock.current = true; setBusy(true); setError('');
    try {
      await onConfirm();
    } catch (err: unknown) {
      const response = (err as { response?: { data?: { error?: string } } })?.response;
      setError(response?.data?.error || 'Não foi possível limpar os dados. Tente novamente.');
    } finally {
      lock.current = false; setBusy(false);
    }
  };

  return <AppDialog title="Limpar todos os dados" busy={busy} onClose={() => { if (!busy) onClose(); }} initialFocus={inputRef}
    description="Esta ação não pode ser desfeita. Sua conta de login é mantida.">
    <form className="app-dialog-body" onSubmit={event => { event.preventDefault(); void confirm(); }}>
      <div className="app-dialog-consequence">
        <p>Serão removidos permanentemente:</p>
        <ul className="settings-clear-list">
          {CLEAR_DATA_ENTITIES.map(entity => <li key={entity.label}>
            {entity.label}{entity.note && <span className="app-dialog-muted"> ({entity.note})</span>}
          </li>)}
        </ul>
        <p className="app-dialog-muted">Em workspaces compartilhados, o planejamento mensal comum ao workspace não é apagado. Faça um backup antes de continuar.</p>
      </div>
      <label htmlFor={inputId} className="settings-clear-label">Digite {CLEAR_DATA_CONFIRMATION} para confirmar</label>
      <input ref={inputRef} id={inputId} type="text" autoComplete="off" spellCheck={false} className="settings-clear-input"
        value={typed} onChange={event => setTyped(event.target.value)} disabled={busy} aria-describedby={hintId} />
      <p id={hintId} className="app-dialog-muted">O botão de exclusão só é habilitado com o texto exato.</p>
      {error && <p className="app-dialog-error" role="alert">{error}</p>}
      <div className="app-dialog-actions">
        <button type="button" className="app-dialog-button" disabled={busy} onClick={onClose}>Cancelar</button>
        <button type="submit" className="app-dialog-button app-dialog-button-danger" disabled={!ready || busy}>
          {busy ? 'Limpando…' : 'Excluir todos os dados'}
        </button>
      </div>
    </form>
  </AppDialog>;
}
