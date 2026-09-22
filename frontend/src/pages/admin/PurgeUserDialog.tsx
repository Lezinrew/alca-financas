import { useRef, useState } from 'react';
import { AppDialog } from '../../components/shared/AppDialog';

export interface PurgeUserDialogProps {
  name: string;
  email: string;
  /** Recebe o e-mail digitado (já sem espaços). Deve lançar em caso de falha. */
  onConfirm: (confirmEmail: string) => Promise<void>;
  onClose: () => void;
}

const PURGE_ERROR_MESSAGE = 'Não foi possível apagar a conta. Tente novamente.';

/**
 * Exclusão total (irreversível). O botão "Apagar" só habilita quando o e-mail
 * digitado é igual ao do usuário alvo (sem espaços, ignorando maiúsculas) e não há envio em andamento.
 */
export function PurgeUserDialog({ name, email, onConfirm, onClose }: PurgeUserDialogProps) {
  const [typed, setTyped] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const lock = useRef(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const matches = typed.trim().toLowerCase() === email.trim().toLowerCase();
  const canSubmit = matches && !busy;

  const submit = async () => {
    if (!canSubmit || lock.current) return;
    lock.current = true; setBusy(true); setError('');
    try {
      await onConfirm(typed.trim());
    } catch (e: unknown) {
      const msg =
        (e as { response?: { data?: { error?: string; detail?: string } } })?.response?.data?.error ||
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg ? String(msg) : PURGE_ERROR_MESSAGE);
    } finally {
      lock.current = false; setBusy(false);
    }
  };

  return <AppDialog title="Exclusão total da conta" busy={busy} onClose={() => { if (!busy) onClose(); }} initialFocus={inputRef} size="sm"
    description="Apaga a conta de acesso, o perfil e todos os dados do usuário. Esta ação não pode ser desfeita.">
    <form className="app-dialog-body" onSubmit={(event) => { event.preventDefault(); void submit(); }}>
      <p className="app-dialog-subject">{name} <span className="app-dialog-muted">({email})</span></p>
      <label htmlFor="purge-confirm-email" className="block text-sm font-medium">
        Digite o e-mail do usuário para confirmar
      </label>
      <input
        ref={inputRef}
        id="purge-confirm-email"
        name="purge-confirm-email"
        type="email"
        autoComplete="off"
        value={typed}
        disabled={busy}
        onChange={(e) => setTyped(e.target.value)}
        className="native-input-themed mt-1 w-full rounded-xl px-3 py-2 outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
        placeholder={email}
        aria-describedby="purge-confirm-hint"
      />
      <p id="purge-confirm-hint" className="app-dialog-muted mt-1">
        {matches ? 'E-mail confere.' : 'O botão "Apagar" só é liberado quando o e-mail digitado é igual ao do usuário.'}
      </p>
      {error && <p className="app-dialog-error" role="alert">{error}</p>}
      <div className="app-dialog-actions">
        <button type="button" className="app-dialog-button" disabled={busy} onClick={onClose}>Cancelar</button>
        <button type="submit" className="app-dialog-button app-dialog-button-danger" disabled={!canSubmit}>
          {busy ? 'Apagando…' : 'Apagar'}
        </button>
      </div>
    </form>
  </AppDialog>;
}
