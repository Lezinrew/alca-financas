import React, { useState, useRef, useId } from 'react';
import { accountsAPI } from '../../utils/api';
import { AppDialog } from '../shared/AppDialog';
import { apiErrorMessage } from './creditCardUtils';
import './credit-cards.css';

interface CreditCardImportModalProps {
  onHide: () => void;
  /** Chamado ao fechar após uma importação concluída, para recarregar os dados. */
  onSuccess: () => void;
  cardId: string;
}

interface ImportResult {
  imported_count?: number;
  duplicates_skipped?: number;
  categories_created?: number;
  categories_created_list?: string[];
}

const VALID_EXTENSIONS = ['.pdf', '.ofx', '.csv'];

/** Diálogo de importação de fatura. Monte apenas enquanto estiver aberto. */
const CreditCardImportModal: React.FC<CreditCardImportModalProps> = ({ onHide, onSuccess, cardId }) => {
  const prefix = useId();
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const submitting = useRef(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);

  const close = () => {
    if (busy) return;
    if (success) { onSuccess(); return; }
    if (selectedFile && !window.confirm('Fechar sem importar o arquivo selecionado?')) return;
    onHide();
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const filename = file.name.toLowerCase();
    if (!VALID_EXTENSIONS.some(ext => filename.endsWith(ext))) {
      setError('Apenas arquivos PDF, OFX e CSV são aceitos');
      setSelectedFile(null);
      return;
    }
    setSelectedFile(file);
    setError('');
  };

  const handleImport = async () => {
    if (submitting.current) return;
    if (!selectedFile) { setError('Selecione um arquivo para importar'); return; }
    submitting.current = true;
    setBusy(true);
    setError('');
    try {
      const response = await accountsAPI.import(cardId, selectedFile);
      const result: ImportResult = response.data || {};
      const imported = result.imported_count || 0;
      const skipped = result.duplicates_skipped || 0;
      let message = `Fatura importada com sucesso: ${imported} transação(ões) adicionada(s).`;
      if (skipped > 0) message += ` ${skipped} duplicada(s) ignorada(s).`;
      if (result.categories_created && result.categories_created > 0) {
        const list = result.categories_created_list?.join(', ') || '';
        message += ` ${result.categories_created} ${result.categories_created === 1 ? 'categoria foi criada' : 'categorias foram criadas'} automaticamente${list ? `: ${list}` : ''}.`;
      }
      setSuccess(message);
      setSelectedFile(null);
    } catch (err) {
      setError(apiErrorMessage(err, 'Não foi possível importar a fatura. Confira o arquivo e tente novamente.'));
    } finally {
      submitting.current = false;
      setBusy(false);
    }
  };

  return (
    <AppDialog title="Importar fatura do cartão" onClose={close} busy={busy} initialFocus={success ? closeRef : fileRef} size="sm">
      <div className="app-dialog-body cc">
        {error && <p className="app-dialog-error mb-4" role="alert" style={{ marginTop: 0 }}>{error}</p>}

        {success ? (
          <>
            <p className="cc-success" role="status">{success}</p>
            <div className="app-dialog-actions">
              <button ref={closeRef} type="button" className="app-dialog-button app-dialog-button-primary" onClick={onSuccess}>Fechar</button>
            </div>
          </>
        ) : (
          <>
            <div className="space-y-4">
              <div className="cc-field">
                <label htmlFor={`${prefix}-file`}>Selecione o arquivo da fatura</label>
                <input
                  ref={fileRef}
                  type="file"
                  id={`${prefix}-file`}
                  name="file"
                  className="input-base"
                  accept=".pdf,.ofx,.csv"
                  onChange={handleFileChange}
                  disabled={busy}
                  aria-describedby={`${prefix}-formats`}
                />
                <span id={`${prefix}-formats`} className="cc-field-hint">Formatos aceitos: PDF, OFX e CSV</span>
              </div>

              {selectedFile && (
                <div className="cc-file-summary">
                  <i className="bi bi-file-earmark text-blue-600 dark:text-blue-400 text-lg" aria-hidden="true"></i>
                  <div className="min-w-0">
                    <p className="font-medium break-all m-0">{selectedFile.name}</p>
                    <p className="cc-field-hint m-0">{(selectedFile.size / 1024).toFixed(2)} KB</p>
                  </div>
                </div>
              )}

              <div className="cc-help">
                <p className="font-medium m-0">Como importar:</p>
                <ul>
                  <li>Baixe a fatura do seu cartão no formato PDF, OFX ou CSV</li>
                  <li>Selecione o arquivo usando o campo acima</li>
                  <li>Clique em &ldquo;Importar&rdquo; para processar a fatura</li>
                  <li>As transações serão adicionadas automaticamente</li>
                </ul>
              </div>
            </div>

            <div className="app-dialog-actions">
              <button type="button" onClick={close} disabled={busy} className="app-dialog-button">Cancelar</button>
              <button type="button" onClick={() => void handleImport()} disabled={busy || !selectedFile} className="app-dialog-button app-dialog-button-primary">
                {busy ? 'Importando…' : 'Importar'}
              </button>
            </div>
          </>
        )}
      </div>
    </AppDialog>
  );
};

export default CreditCardImportModal;
