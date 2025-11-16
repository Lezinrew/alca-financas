import React, { useState } from 'react';

interface CreditCardImportModalProps {
  show: boolean;
  onHide: () => void;
  onSuccess: () => void;
  cardId: string;
}

const CreditCardImportModal: React.FC<CreditCardImportModalProps> = ({
  show,
  onHide,
  onSuccess,
  cardId
}) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const filename = file.name.toLowerCase();
      const validExtensions = ['.pdf', '.ofx', '.csv'];
      const isValid = validExtensions.some(ext => filename.endsWith(ext));

      if (!isValid) {
        setError('Apenas arquivos PDF, OFX e CSV são aceitos');
        setSelectedFile(null);
        return;
      }

      setSelectedFile(file);
      setError('');
      setSuccess('');
    }
  };

  const handleImport = async () => {
    if (!selectedFile) {
      setError('Selecione um arquivo para importar');
      return;
    }

    setLoading(true);
    setError('');
    setSuccess('');

    try {
      const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001';
      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('card_id', cardId);

      const response = await fetch(`${API_URL}/api/accounts/${cardId}/import`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        },
        body: formData
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Erro ao importar fatura');
      }

      const result = await response.json();
      let successMessage = `Fatura importada com sucesso! ${result.imported_count || 0} transações adicionadas.`;
      
      if (result.categories_created && result.categories_created > 0) {
        const categoriesList = result.categories_created_list?.join(', ') || '';
        successMessage += ` ${result.categories_created} ${result.categories_created === 1 ? 'categoria foi criada' : 'categorias foram criadas'} automaticamente${categoriesList ? `: ${categoriesList}` : ''}.`;
      }
      
      setSuccess(successMessage);
      
      setTimeout(() => {
        onSuccess();
      }, 3000);
    } catch (err: any) {
      setError(err.message || 'Erro ao importar fatura');
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    if (!loading) {
      setSelectedFile(null);
      setError('');
      setSuccess('');
      onHide();
    }
  };

  if (!show) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="modal-backdrop"
        onClick={handleClose}
      ></div>

      {/* Modal */}
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-none">
        <div className="modal-content pointer-events-auto max-w-lg w-full">
          {/* Header */}
          <div className="flex items-center justify-between p-6 border-b border-slate-200 dark:border-slate-700/50">
            <h2 className="text-xl font-semibold text-primary">
              Importar Fatura do Cartão
            </h2>
            <button
              type="button"
              onClick={handleClose}
              disabled={loading}
              className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 transition-colors disabled:opacity-50"
              aria-label="Fechar"
            >
              <i className="bi bi-x-lg text-xl"></i>
            </button>
          </div>

          {/* Body */}
          <div className="p-6">
            {error && (
              <div className="mb-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg flex items-center gap-2">
                <i className="bi bi-exclamation-triangle-fill text-red-600 dark:text-red-400"></i>
                <span className="text-red-800 dark:text-red-200 text-sm">{error}</span>
              </div>
            )}

            {success && (
              <div className="mb-4 p-3 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg flex items-center gap-2">
                <i className="bi bi-check-circle-fill text-green-600 dark:text-green-400"></i>
                <span className="text-green-800 dark:text-green-200 text-sm">{success}</span>
              </div>
            )}

            <div className="space-y-4">
              <div>
                <label htmlFor="import-file" className="block text-sm font-medium text-secondary mb-2">
                  Selecione o arquivo da fatura
                </label>
                <input
                  type="file"
                  id="import-file"
                  name="file"
                  className="input-base"
                  accept=".pdf,.ofx,.csv"
                  onChange={handleFileChange}
                  disabled={loading}
                />
                <div className="text-xs text-tertiary mt-2">
                  Formatos aceitos: PDF, OFX e CSV
                </div>
              </div>

              {selectedFile && (
                <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
                  <div className="flex items-center gap-2">
                    <i className="bi bi-file-earmark text-blue-600 dark:text-blue-400"></i>
                    <div className="flex-1">
                      <p className="text-sm font-medium text-blue-900 dark:text-blue-200">
                        {selectedFile.name}
                      </p>
                      <p className="text-xs text-blue-700 dark:text-blue-300">
                        {(selectedFile.size / 1024).toFixed(2)} KB
                      </p>
                    </div>
                  </div>
                </div>
              )}

              <div className="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-4">
                <p className="text-sm font-medium text-secondary mb-2">
                  <i className="bi bi-info-circle me-2"></i>
                  Como importar:
                </p>
                <ul className="text-xs text-tertiary space-y-1 list-disc list-inside">
                  <li>Baixe a fatura do seu cartão no formato PDF, OFX ou CSV</li>
                  <li>Selecione o arquivo usando o botão acima</li>
                  <li>Clique em "Importar" para processar a fatura</li>
                  <li>As transações serão adicionadas automaticamente</li>
                </ul>
              </div>
            </div>
          </div>

          {/* Footer */}
          <div className="flex items-center justify-end gap-3 p-6 border-t border-slate-200 dark:border-slate-700/50">
            <button
              type="button"
              onClick={handleClose}
              disabled={loading}
              className="btn-secondary"
            >
              Cancelar
            </button>
            <button
              type="button"
              onClick={handleImport}
              disabled={loading || !selectedFile}
              className="btn-base bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? (
                <>
                  <i className="bi bi-hourglass-split animate-spin mr-2"></i>
                  Importando...
                </>
              ) : (
                <>
                  <i className="bi bi-upload mr-2"></i>
                  Importar
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </>
  );
};

export default CreditCardImportModal;

