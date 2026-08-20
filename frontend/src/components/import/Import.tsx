import React, { useState, useEffect } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { transactionsAPI, accountsAPI } from '../../utils/api';

import { ImportBatchRecord } from '../../types/transaction';

interface AccountOption {
  id: string;
  name: string;
  institution?: string;
  type: string;
  is_active?: boolean;
  color?: string;
}

interface ImportResult {
  imported_count: number;
  error_count: number;
  errors?: string[];
  categories_created?: number;
  categories_created_list?: string[];
  account_created?: boolean;
  account_name?: string;
  [key: string]: unknown;
}

type ActiveTab = 'debit' | 'credit_card' | 'history';

const Import = () => {
  const { isAuthenticated, loading: authLoading } = useAuth();
  const [accounts, setAccounts] = useState<AccountOption[]>([]);
  const [creditCards, setCreditCards] = useState<AccountOption[]>([]);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [selectedAccountId, setSelectedAccountId] = useState<string>('');
  const [selectedCreditCardId, setSelectedCreditCardId] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [progressMessage, setProgressMessage] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const [activeTab, setActiveTab] = useState<ActiveTab>('debit');

  // Estado para histórico de lotes
  const [batches, setBatches] = useState<ImportBatchRecord[]>([]);
  const [loadingBatches, setLoadingBatches] = useState(false);
  const [rollingBackId, setRollingBackId] = useState<string | null>(null);

  useEffect(() => {
    if (isAuthenticated && !authLoading) {
      loadAccounts();
    }
  }, [isAuthenticated, authLoading]);

  const loadBatches = async () => {
    setLoadingBatches(true);
    try {
      const res = await transactionsAPI.getImportBatches();
      setBatches(res.data?.batches || []);
    } catch (err: any) {
      console.error('Erro ao carregar lotes:', err);
      setError('Não foi possível carregar o histórico de importações.');
    } finally {
      setLoadingBatches(false);
    }
  };

  const handleRollbackBatch = async (batchId: string, filename: string) => {
    if (!window.confirm(`Tem certeza que deseja desfazer a importação do arquivo "${filename}"?\n\nTodas as transações deste lote serão excluídas e os saldos revertidos atomicamente.`)) {
      return;
    }
    setRollingBackId(batchId);
    setError('');
    setSuccess('');
    try {
      const res = await transactionsAPI.rollbackImportBatch(batchId);
      setSuccess(res.data?.message || 'Lote revertido com sucesso!');
      await loadBatches();
    } catch (err: any) {
      console.error('Erro ao reverter lote:', err);
      setError(err.response?.data?.error || 'Falha ao reverter lote de importação.');
    } finally {
      setRollingBackId(null);
    }
  };

  const loadAccounts = async () => {
    try {
      const response = await accountsAPI.getAll();
      if (response.data) {
        const data = response.data;
        const activeAccounts = data.filter(
          (acc: any) => acc.is_active !== false && acc.active !== false
        );
        
        // Separa contas normais e cartões de crédito
        const normalAccounts = activeAccounts.filter((acc: AccountOption) => acc.type !== 'credit_card');
        const cards = activeAccounts.filter((acc: AccountOption) => acc.type === 'credit_card');
        
        setAccounts(normalAccounts);
        setCreditCards(cards);
        
        // Se houver apenas uma conta ativa, seleciona automaticamente
        if (normalAccounts.length === 1 && activeTab === 'debit') {
          setSelectedAccountId(normalAccounts[0].id);
        }
        if (cards.length === 1 && activeTab === 'credit_card') {
          setSelectedCreditCardId(cards[0].id);
        }
      }
    } catch (err) {
      console.error('Load accounts error:', err);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    
    setSelectedFile(file);
    setError('');
    setSuccess('');
    setImportResult(null);
    
    // Tenta detectar automaticamente a conta baseado no nome do arquivo
    const filename = file.name.toLowerCase();
    
    if (activeTab === 'debit' && accounts.length > 0) {
      if (filename.includes('nubank')) {
        const nubankAccount = accounts.find((acc: any) => 
          acc.name.toLowerCase().includes('nubank') || 
          acc.institution?.toLowerCase().includes('nubank')
        );
        if (nubankAccount) {
          setSelectedAccountId(nubankAccount.id);
        }
      }
    } else if (activeTab === 'credit_card' && creditCards.length > 0) {
      if (filename.includes('nubank')) {
        const nubankCard = creditCards.find((acc: any) => 
          acc.name.toLowerCase().includes('nubank') || 
          acc.institution?.toLowerCase().includes('nubank')
        );
        if (nubankCard) {
          setSelectedCreditCardId(nubankCard.id);
        }
      }
    }
  };

  const handleImport = async () => {
    if (!selectedFile) {
      setError('Selecione um arquivo CSV, OFX ou PDF');
      return;
    }

    const filename = selectedFile.name.toLowerCase();
    const validExtensions = ['.csv', '.ofx', '.pdf'];
    if (!validExtensions.some(ext => filename.endsWith(ext))) {
      setError('Apenas arquivos CSV, OFX e PDF são aceitos');
      return;
    }

    setLoading(true);
    setError('');
    setSuccess('');
    setProgressMessage('Enviando arquivo...');

    try {
      let response: { data: ImportResult };

      if (activeTab === 'credit_card' && selectedCreditCardId) {
        // Importação de cartão de crédito
        setProgressMessage('Processando fatura do cartão de crédito...');
        const formData = new FormData();
        formData.append('file', selectedFile);

        const fetchResponse = await accountsAPI.import(selectedCreditCardId, selectedFile);
        response = { data: fetchResponse.data as ImportResult };
      } else {
        // Importação geral (débito)
        setProgressMessage('Processando transações...');
        const apiResponse = await transactionsAPI.import(selectedFile, selectedAccountId || undefined);
        response = { data: apiResponse.data as ImportResult };
      }

      setProgressMessage('Finalizando importação...');
      
      setImportResult(response.data);
      
      if (response.data.imported_count > 0) {
        let successMessage = `${response.data.imported_count} transações importadas com sucesso`;
        
        if (response.data.account_created && response.data.account_name) {
          successMessage += ` A conta "${response.data.account_name}" foi criada automaticamente.`;
        } else if (selectedAccountId || selectedCreditCardId) {
          successMessage += ` e o saldo foi atualizado!`;
        } else {
          successMessage += '!';
        }
        
        if (response.data.categories_created && response.data.categories_created > 0) {
          const categoriesList = response.data.categories_created_list?.join(', ') || '';
          successMessage += ` ${response.data.categories_created} ${response.data.categories_created === 1 ? 'categoria foi criada' : 'categorias foram criadas'} automaticamente${categoriesList ? `: ${categoriesList}` : ''}.`;
        }
        
        setSuccess(successMessage);
        
        if (response.data.account_created) {
          loadAccounts();
        }
      }
      
      // Limpa o arquivo selecionado
      setSelectedFile(null);
      setSelectedAccountId('');
      setSelectedCreditCardId('');
      const fileInput = document.getElementById(activeTab === 'debit' ? 'importFile' : 'importFileCreditCard') as HTMLInputElement;
      if (fileInput) fileInput.value = '';
      
    } catch (err: any) {
      setError(err.response?.data?.error || err.message || 'Erro ao importar arquivo');
      setImportResult(err.response?.data);
    } finally {
      setLoading(false);
      setProgressMessage('');
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-primary">Importar dados</h1>
          <p className="text-sm text-secondary mt-1">Importe transações de contas e cartões de crédito</p>
        </div>
      </div>

      {/* Card Principal */}
      <div className="card-base">
        <div className="p-6">
          {/* Título e Link de Ajuda */}
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-semibold text-primary">Importar dados do banco</h2>
            <a
              href="#"
              className="text-sm text-blue-600 dark:text-blue-400 hover:underline flex items-center gap-1"
              onClick={(e) => {
                e.preventDefault();
                // TODO: Abrir modal de ajuda
              }}
            >
              <i className="bi bi-question-circle"></i>
              Saiba como funciona
            </a>
          </div>

          {/* Tabs */}
          <div className="flex border-b border-slate-200 dark:border-slate-700/50 mb-6">
            <button
              onClick={() => {
                setActiveTab('debit');
                setSelectedFile(null);
                setSelectedAccountId('');
                setSelectedCreditCardId('');
                setError('');
                setSuccess('');
                setImportResult(null);
                const fileInput = document.getElementById('importFile') as HTMLInputElement;
                if (fileInput) fileInput.value = '';
                const fileInputCC = document.getElementById('importFileCreditCard') as HTMLInputElement;
                if (fileInputCC) fileInputCC.value = '';
              }}
              className={`px-6 py-3 text-sm font-medium transition-colors relative ${
                activeTab === 'debit'
                  ? 'text-blue-600 dark:text-blue-400'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
              }`}
            >
              DÉBITO
              {activeTab === 'debit' && (
                <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-600 dark:bg-blue-400"></div>
              )}
            </button>
            <button
              onClick={() => {
                setActiveTab('credit_card');
                setSelectedFile(null);
                setSelectedAccountId('');
                setSelectedCreditCardId('');
                setError('');
                setSuccess('');
                setImportResult(null);
                const fileInput = document.getElementById('importFile') as HTMLInputElement;
                if (fileInput) fileInput.value = '';
                const fileInputCC = document.getElementById('importFileCreditCard') as HTMLInputElement;
                if (fileInputCC) fileInputCC.value = '';
              }}
              className={`px-6 py-3 text-sm font-medium transition-colors relative ${
                activeTab === 'credit_card'
                  ? 'text-blue-600 dark:text-blue-400'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
              }`}
            >
              CARTÃO DE CRÉDITO
              {activeTab === 'credit_card' && (
                <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-600 dark:bg-blue-400"></div>
              )}
            </button>
            <button
              onClick={() => {
                setActiveTab('history');
                setError('');
                setSuccess('');
                setImportResult(null);
                loadBatches();
              }}
              className={`px-6 py-3 text-sm font-medium transition-colors relative ${
                activeTab === 'history'
                  ? 'text-blue-600 dark:text-blue-400'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
              }`}
            >
              HISTÓRICO DE LOTES & ROLLBACK
              {activeTab === 'history' && (
                <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-600 dark:bg-blue-400"></div>
              )}
            </button>
          </div>

          {/* Mensagens de Erro/Sucesso */}
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

          {/* Feedback de Progresso */}
          {loading && progressMessage && (
            <div className="mb-4 p-4 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg">
              <div className="flex items-center gap-3">
                <div className="relative">
                  <i className="bi bi-arrow-repeat text-2xl text-blue-600 dark:text-blue-400 animate-spin"></i>
                </div>
                <div className="flex-1">
                  <p className="text-sm font-medium text-blue-900 dark:text-blue-200">
                    {progressMessage}
                  </p>
                  <p className="text-xs text-blue-700 dark:text-blue-300 mt-1">
                    Por favor, aguarde enquanto processamos suas transações...
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Conteúdo Aba Histórico de Lotes */}
          {activeTab === 'history' ? (
            <div className="space-y-4">
              <div className="flex items-center justify-between pb-2 border-b border-slate-200 dark:border-slate-700/50">
                <p className="text-sm text-slate-600 dark:text-slate-300">
                  Gerenciamento de lotes importados com auditoria e reversão atômica (Rollback).
                </p>
                <button
                  onClick={loadBatches}
                  disabled={loadingBatches}
                  className="px-3 py-1.5 text-xs font-medium bg-slate-100 dark:bg-slate-700 hover:bg-slate-200 dark:hover:bg-slate-600 rounded-lg transition-colors flex items-center gap-1.5"
                >
                  <i className={`bi bi-arrow-clockwise ${loadingBatches ? 'animate-spin' : ''}`}></i>
                  Atualizar
                </button>
              </div>

              {loadingBatches ? (
                <div className="p-8 text-center text-slate-500 dark:text-slate-400">
                  <i className="bi bi-arrow-repeat text-3xl animate-spin block mb-2"></i>
                  Carregando histórico de lotes...
                </div>
              ) : batches.length === 0 ? (
                <div className="p-8 text-center text-slate-500 dark:text-slate-400">
                  <i className="bi bi-inbox text-4xl block mb-2 text-slate-400"></i>
                  Nenhum lote de importação registrado até o momento.
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead className="bg-slate-50 dark:bg-slate-800/50 text-xs font-medium text-slate-500 uppercase tracking-wider">
                      <tr>
                        <th className="px-4 py-3">Data / Lote</th>
                        <th className="px-4 py-3">Arquivo</th>
                        <th className="px-4 py-3">Status</th>
                        <th className="px-4 py-3">Contadores</th>
                        <th className="px-4 py-3">Totalizadores</th>
                        <th className="px-4 py-3 text-right">Ação</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200 dark:divide-slate-700/50">
                      {batches.map((batch) => {
                        const isRolledBack = batch.status === 'rolled_back';
                        const isRolling = rollingBackId === batch.id;
                        return (
                          <tr key={batch.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/30">
                            <td className="px-4 py-3 text-xs text-slate-600 dark:text-slate-300">
                              <div className="font-medium text-slate-900 dark:text-white">
                                {new Date(batch.created_at).toLocaleString('pt-BR')}
                              </div>
                              <span className="text-[10px] text-slate-400 font-mono" title={batch.id}>
                                {batch.id.slice(0, 8)}...
                              </span>
                            </td>
                            <td className="px-4 py-3">
                              <div className="font-medium text-slate-900 dark:text-white flex items-center gap-1.5">
                                <i className="bi bi-file-earmark-text text-blue-600"></i>
                                {batch.filename}
                              </div>
                              <span className="text-xs text-slate-500 uppercase">
                                {batch.file_format || 'OFX'}
                              </span>
                            </td>
                            <td className="px-4 py-3">
                              <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                                isRolledBack
                                  ? 'bg-amber-100 dark:bg-amber-900/30 text-amber-800 dark:text-amber-300'
                                  : batch.status === 'completed'
                                    ? 'bg-emerald-100 dark:bg-emerald-900/30 text-emerald-800 dark:text-emerald-300'
                                    : 'bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-300'
                              }`}>
                                {isRolledBack ? 'Revertido' : batch.status === 'completed' ? 'Concluído' : batch.status}
                              </span>
                            </td>
                            <td className="px-4 py-3 text-xs text-slate-600 dark:text-slate-300">
                              <div><span className="font-semibold text-emerald-600">+{batch.imported_count}</span> importadas</div>
                              {batch.duplicate_count > 0 && (
                                <div className="text-slate-400">{batch.duplicate_count} duplicatas ignoradas</div>
                              )}
                              {batch.ignored_count > 0 && (
                                <div className="text-slate-400">{batch.ignored_count} espelhos ignorados</div>
                              )}
                            </td>
                            <td className="px-4 py-3 text-xs">
                              {Number(batch.total_income || 0) > 0 && (
                                <div className="text-emerald-600 font-medium">Rec: R$ {Number(batch.total_income).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</div>
                              )}
                              {Number(batch.total_expense || 0) > 0 && (
                                <div className="text-red-600 font-medium">Desp: R$ {Number(batch.total_expense).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</div>
                              )}
                              {Number(batch.total_transfer || 0) > 0 && (
                                <div className="text-blue-600 font-medium">Trf: R$ {Number(batch.total_transfer).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</div>
                              )}
                            </td>
                            <td className="px-4 py-3 text-right">
                              <button
                                onClick={() => handleRollbackBatch(batch.id, batch.filename)}
                                disabled={isRolledBack || isRolling}
                                className={`px-3 py-1 text-xs font-medium rounded-lg transition-colors ${
                                  isRolledBack
                                    ? 'bg-slate-100 text-slate-400 dark:bg-slate-800 dark:text-slate-600 cursor-not-allowed'
                                    : 'bg-red-50 text-red-600 hover:bg-red-100 dark:bg-red-900/20 dark:text-red-400 dark:hover:bg-red-900/40'
                                }`}
                                title={isRolledBack ? 'Lote já revertido' : 'Excluir transações e reverter saldo'}
                              >
                                {isRolling ? (
                                  <>
                                    <i className="bi bi-arrow-repeat animate-spin me-1"></i>
                                    Revertendo...
                                  </>
                                ) : isRolledBack ? (
                                  'Revertido'
                                ) : (
                                  <>
                                    <i className="bi bi-arrow-counterclockwise me-1"></i>
                                    Desfazer Lote
                                  </>
                                )}
                              </button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          ) : activeTab === 'debit' ? (
            <div className="space-y-4">
              {/* Seleção de Conta */}
              <div>
                <label htmlFor="import-account" className="block text-sm font-medium text-secondary mb-2">
                  Conta
                </label>
                <select
                  id="import-account"
                  name="account_id"
                  className="select-base"
                  value={selectedAccountId}
                  onChange={(e) => setSelectedAccountId(e.target.value)}
                  disabled={loading}
                >
                  <option value="">Detectar/criar automaticamente</option>
                  {accounts.map((account: any) => (
                    <option key={account.id} value={account.id}>
                      {account.name} {account.institution ? `(${account.institution})` : ''}
                    </option>
                  ))}
                </select>
              </div>

              {/* Upload de Arquivo */}
              <div>
                <label htmlFor="importFile" className="block text-sm font-medium text-secondary mb-2">
                  Arquivo
                </label>
                <div className="flex items-center gap-3">
                  <input
                    type="file"
                    id="importFile"
                    name="file"
                    className="input-base flex-1"
                    accept=".csv,.ofx"
                    onChange={handleFileChange}
                    disabled={loading}
                  />
                  <button
                    type="button"
                    onClick={() => document.getElementById('importFile')?.click()}
                    className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    disabled={loading}
                  >
                    IMPORTAR OFX
                  </button>
                </div>
                <div className="text-xs text-tertiary mt-2">
                  Formatos aceitos: CSV (padrão ou Nubank) e OFX (Nubank e outros bancos)
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
            </div>
          ) : (
            <div className="space-y-4">
              {/* Seleção de Cartão */}
              <div>
                <label htmlFor="import-credit-card" className="block text-sm font-medium text-secondary mb-2">
                  Cartão de crédito
                </label>
                <select
                  id="import-credit-card"
                  name="credit_card_id"
                  className="select-base"
                  value={selectedCreditCardId}
                  onChange={(e) => setSelectedCreditCardId(e.target.value)}
                  disabled={loading}
                  required
                >
                  <option value="">Selecione um cartão</option>
                  {creditCards.map((card: any) => (
                    <option key={card.id} value={card.id}>
                      {card.name} {card.institution ? `(${card.institution})` : ''}
                    </option>
                  ))}
                </select>
              </div>

              {/* Upload de Arquivo */}
              <div>
                <label htmlFor="importFileCreditCard" className="block text-sm font-medium text-secondary mb-2">
                  Arquivo da Fatura
                </label>
                <div className="flex items-center gap-3">
                  <input
                    type="file"
                    id="importFileCreditCard"
                    name="file"
                    className="input-base flex-1"
                    accept=".csv,.ofx,.pdf"
                    onChange={handleFileChange}
                    disabled={loading || !selectedCreditCardId}
                  />
                  <button
                    type="button"
                    onClick={() => document.getElementById('importFileCreditCard')?.click()}
                    className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    disabled={loading || !selectedCreditCardId}
                  >
                    IMPORTAR OFX
                  </button>
                </div>
                <div className="text-xs text-tertiary mt-2">
                  Formatos aceitos: CSV, OFX e PDF (faturas de cartão de crédito)
                </div>
                {!selectedCreditCardId && (
                  <div className="text-xs text-amber-600 dark:text-amber-400 mt-2">
                    <i className="bi bi-exclamation-circle me-1"></i>
                    Selecione um cartão antes de escolher o arquivo
                  </div>
                )}
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
            </div>
          )}

          {/* Botão Enviar */}
          <div className="flex justify-end mt-6 pt-6 border-t border-slate-200 dark:border-slate-700/50">
            <button
              onClick={handleImport}
              className="px-6 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              disabled={!selectedFile || loading || (activeTab === 'credit_card' && !selectedCreditCardId)}
            >
              {loading ? (
                <>
                  <i className="bi bi-arrow-repeat animate-spin"></i>
                  Processando...
                </>
              ) : (
                <>
                  <i className="bi bi-upload"></i>
                  ENVIAR
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Resultado da Importação */}
      {importResult && (
        <div className="card-base">
          <div className="p-6">
            <h3 className="text-lg font-semibold text-primary mb-4">Resultado da Importação</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-center">
              <div className="bg-emerald-500 rounded-lg p-4 text-white">
                <i className="bi bi-check-circle text-4xl mb-2 block"></i>
                <h4 className="text-2xl font-bold">{importResult.imported_count || 0}</h4>
                <small className="text-sm">Importadas</small>
              </div>
              <div className="bg-red-500 rounded-lg p-4 text-white">
                <i className="bi bi-x-circle text-4xl mb-2 block"></i>
                <h4 className="text-2xl font-bold">{importResult.error_count || 0}</h4>
                <small className="text-sm">Erros</small>
              </div>
              <div className="bg-blue-500 rounded-lg p-4 text-white">
                <i className="bi bi-file-text text-4xl mb-2 block"></i>
                <h4 className="text-2xl font-bold">{(importResult.imported_count || 0) + (importResult.error_count || 0)}</h4>
                <small className="text-sm">Total</small>
              </div>
            </div>

            {importResult.errors && importResult.errors.length > 0 && (
              <div className="mt-4">
                <h6 className="text-red-600 dark:text-red-400 font-semibold mb-3">
                  <i className="bi bi-exclamation-triangle me-2"></i>
                  Erros Encontrados:
                </h6>
                <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg p-4">
                  <ul className="mb-0 space-y-1">
                    {importResult.errors.slice(0, 10).map((error: string, index: number) => (
                      <li key={index} className="text-sm text-secondary">{error}</li>
                    ))}
                    {importResult.errors.length > 10 && (
                      <li className="text-sm text-tertiary">
                        ... e mais {importResult.errors.length - 10} erros
                      </li>
                    )}
                  </ul>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default Import;
