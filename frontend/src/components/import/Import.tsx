import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { transactionsAPI, accountsAPI } from '../../utils/api';
import { ConfirmDialog } from '../shared/ConfirmDialog';
import { ImportBatchRecord } from '../../types/transaction';
import './import.css';

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
type AccountsStatus = 'loading' | 'ready' | 'error';

const ACCOUNTS_ERROR_MESSAGE = 'Não foi possível carregar suas contas. A importação fica bloqueada até as contas serem carregadas, para evitar importar na conta errada.';
const IMPORT_ERROR_MESSAGE = 'Não foi possível importar o arquivo. Nenhuma transação foi registrada por esta tentativa.';
const ROLLBACK_ERROR_MESSAGE = 'Não foi possível desfazer a importação. Confira o histórico atualizado antes de tentar novamente.';
const ERRORS_PREVIEW_LIMIT = 10;

const TABS: Array<{ id: ActiveTab; label: string }> = [
  { id: 'debit', label: 'Conta corrente' },
  { id: 'credit_card', label: 'Cartão de crédito' },
  { id: 'history', label: 'Histórico de importações' },
];

/** Aceita apenas respostas com a forma esperada; qualquer outra coisa é tratada como falha. */
const parseImportResult = (payload: unknown): ImportResult | null => {
  if (!payload || typeof payload !== 'object') return null;
  const record = payload as Record<string, unknown>;
  if (typeof record.imported_count !== 'number') return null;
  return {
    ...record,
    imported_count: record.imported_count,
    error_count: typeof record.error_count === 'number' ? record.error_count : 0,
    errors: Array.isArray(record.errors) ? record.errors.map(String) : undefined,
  } as ImportResult;
};

const formatMoney = (value: unknown) => Number(value || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2 });

const Import = () => {
  const { isAuthenticated, loading: authLoading } = useAuth();
  const [accounts, setAccounts] = useState<AccountOption[]>([]);
  const [creditCards, setCreditCards] = useState<AccountOption[]>([]);
  const [accountsStatus, setAccountsStatus] = useState<AccountsStatus>('loading');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [selectedAccountId, setSelectedAccountId] = useState<string>('');
  const [selectedCreditCardId, setSelectedCreditCardId] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [progressMessage, setProgressMessage] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const [activeTab, setActiveTab] = useState<ActiveTab>('debit');
  const submitLock = useRef(false);

  // Estado para histórico de lotes
  const [batches, setBatches] = useState<ImportBatchRecord[]>([]);
  const [loadingBatches, setLoadingBatches] = useState(false);
  const [rollbackTarget, setRollbackTarget] = useState<ImportBatchRecord | null>(null);
  const [rollingBackId, setRollingBackId] = useState<string | null>(null);

  const loadAccounts = useCallback(async () => {
    setAccountsStatus('loading');
    try {
      const response = await accountsAPI.getAll();
      const data = Array.isArray(response.data) ? response.data : [];
      const activeAccounts = data.filter(
        (acc: any) => acc.is_active !== false && acc.active !== false
      );

      // Separa contas normais e cartões de crédito
      const normalAccounts = activeAccounts.filter((acc: AccountOption) => acc.type !== 'credit_card');
      const cards = activeAccounts.filter((acc: AccountOption) => acc.type === 'credit_card');

      setAccounts(normalAccounts);
      setCreditCards(cards);
      setAccountsStatus('ready');

      // Se houver apenas uma conta ativa, seleciona automaticamente
      if (normalAccounts.length === 1) {
        setSelectedAccountId((current) => current || normalAccounts[0].id);
      }
      if (cards.length === 1) {
        setSelectedCreditCardId((current) => current || cards[0].id);
      }
    } catch (err) {
      console.error('Load accounts error:', err);
      setAccounts([]);
      setCreditCards([]);
      setAccountsStatus('error');
    }
  }, []);

  useEffect(() => {
    if (isAuthenticated && !authLoading) {
      void loadAccounts();
    }
  }, [isAuthenticated, authLoading, loadAccounts]);

  const loadBatches = async () => {
    setLoadingBatches(true);
    try {
      const res = await transactionsAPI.getImportBatches();
      setBatches(res.data?.batches || []);
    } catch (err) {
      console.error('Erro ao carregar lotes:', err);
      setError('Não foi possível carregar o histórico de importações.');
    } finally {
      setLoadingBatches(false);
    }
  };

  const confirmRollback = async () => {
    if (!rollbackTarget) return;
    const batch = rollbackTarget;
    setRollingBackId(batch.id);
    setError('');
    setSuccess('');
    try {
      const res = await transactionsAPI.rollbackImportBatch(batch.id);
      setSuccess(res.data?.message || 'Importação desfeita. As transações do lote foram removidas e os saldos revertidos.');
      setRollbackTarget(null);
      await loadBatches();
    } finally {
      setRollingBackId(null);
    }
  };

  const resetFileInputs = () => {
    const fileInput = document.getElementById('importFile') as HTMLInputElement | null;
    if (fileInput) fileInput.value = '';
    const fileInputCC = document.getElementById('importFileCreditCard') as HTMLInputElement | null;
    if (fileInputCC) fileInputCC.value = '';
  };

  const switchTab = (tab: ActiveTab) => {
    setActiveTab(tab);
    setError('');
    setSuccess('');
    setImportResult(null);
    if (tab === 'history') {
      void loadBatches();
      return;
    }
    setSelectedFile(null);
    setSelectedAccountId('');
    setSelectedCreditCardId('');
    resetFileInputs();
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
    const matchesNubank = (acc: AccountOption) =>
      acc.name.toLowerCase().includes('nubank') || acc.institution?.toLowerCase().includes('nubank');

    if (activeTab === 'debit' && accounts.length > 0) {
      if (filename.includes('nubank')) {
        const nubankAccount = accounts.find(matchesNubank);
        if (nubankAccount) {
          setSelectedAccountId(nubankAccount.id);
        }
      }
    } else if (activeTab === 'credit_card' && creditCards.length > 0) {
      if (filename.includes('nubank')) {
        const nubankCard = creditCards.find(matchesNubank);
        if (nubankCard) {
          setSelectedCreditCardId(nubankCard.id);
        }
      }
    }
  };

  const accountsReady = accountsStatus === 'ready';
  const canSubmit = Boolean(selectedFile) && !loading && accountsReady
    && (activeTab !== 'credit_card' || Boolean(selectedCreditCardId));

  const handleImport = async () => {
    if (submitLock.current) return;
    if (!accountsReady) {
      setError(ACCOUNTS_ERROR_MESSAGE);
      return;
    }
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

    submitLock.current = true;
    setLoading(true);
    setError('');
    setSuccess('');
    setImportResult(null);
    setProgressMessage('Enviando…');

    try {
      let payload: unknown;

      if (activeTab === 'credit_card' && selectedCreditCardId) {
        // Importação de cartão de crédito
        const fetchResponse = await accountsAPI.import(selectedCreditCardId, selectedFile);
        payload = fetchResponse.data;
      } else {
        // Importação geral (débito)
        const apiResponse = await transactionsAPI.import(selectedFile, selectedAccountId || undefined);
        payload = apiResponse.data;
      }

      setProgressMessage('Processando…');
      const result = parseImportResult(payload);
      if (!result) {
        throw new Error('Resposta inválida do servidor');
      }

      setImportResult(result);

      if (result.imported_count > 0) {
        let successMessage = `${result.imported_count} transações importadas com sucesso`;

        if (result.account_created && result.account_name) {
          successMessage += `. A conta "${result.account_name}" foi criada automaticamente.`;
        } else if (selectedAccountId || selectedCreditCardId) {
          successMessage += ' e o saldo foi atualizado!';
        } else {
          successMessage += '!';
        }

        if (result.categories_created && result.categories_created > 0) {
          const categoriesList = result.categories_created_list?.join(', ') || '';
          successMessage += ` ${result.categories_created} ${result.categories_created === 1 ? 'categoria foi criada' : 'categorias foram criadas'} automaticamente${categoriesList ? `: ${categoriesList}` : ''}.`;
        }

        setSuccess(successMessage);

        if (result.account_created) {
          void loadAccounts();
        }
      }

      // Limpa o arquivo selecionado
      setSelectedFile(null);
      setSelectedAccountId('');
      setSelectedCreditCardId('');
      resetFileInputs();
    } catch (err) {
      console.error('Import error:', err);
      setError(IMPORT_ERROR_MESSAGE);
      setImportResult(null);
    } finally {
      submitLock.current = false;
      setLoading(false);
      setProgressMessage('');
    }
  };

  const renderSelectedFile = () => selectedFile && (
    <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
      <div className="flex items-center gap-2">
        <i className="bi bi-file-earmark text-blue-600 dark:text-blue-400" aria-hidden="true"></i>
        <div className="flex-1">
          <p className="text-sm font-medium text-blue-900 dark:text-blue-200">
            {selectedFile.name}
          </p>
          <p className="text-xs text-blue-800 dark:text-blue-300">
            {(selectedFile.size / 1024).toFixed(2)} KB
          </p>
        </div>
      </div>
    </div>
  );

  const renderAccountsBanner = () => accountsStatus === 'error' && (
    <div className="mb-4 p-3 bg-amber-50 dark:bg-amber-900/20 border border-amber-300 dark:border-amber-800 rounded-lg flex flex-wrap items-center gap-3" role="alert">
      <i className="bi bi-exclamation-triangle-fill text-amber-700 dark:text-amber-300" aria-hidden="true"></i>
      <span className="text-amber-900 dark:text-amber-100 text-sm flex-1 min-w-[200px]">{ACCOUNTS_ERROR_MESSAGE}</span>
      <button
        type="button"
        onClick={() => void loadAccounts()}
        className="min-h-[44px] px-3 rounded-lg text-sm font-medium border border-amber-400 dark:border-amber-700 text-amber-900 dark:text-amber-100 hover:bg-amber-100 dark:hover:bg-amber-900/40"
      >
        Tentar novamente
      </button>
    </div>
  );

  const rollbackDate = rollbackTarget ? new Date(rollbackTarget.created_at).toLocaleString('pt-BR') : '';

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
          {/* Título e ajuda */}
          <div className="mb-6">
            <h2 className="text-xl font-semibold text-primary">Importar dados do banco</h2>
            <details className="mt-2 text-sm text-secondary">
              <summary className="cursor-pointer text-blue-700 dark:text-blue-300 hover:underline inline-flex items-center gap-1">
                <i className="bi bi-question-circle" aria-hidden="true"></i>
                Saiba como funciona
              </summary>
              <ul className="mt-2 ml-5 list-disc space-y-1">
                <li>Conta corrente: formatos aceitos CSV (padrão ou Nubank) e OFX (Nubank e outros bancos). Se nenhuma conta for escolhida, a conta é detectada ou criada automaticamente.</li>
                <li>Cartão de crédito: formatos aceitos CSV, OFX e PDF (faturas). Escolha o cartão antes do arquivo.</li>
                <li>Histórico de importações: cada envio gera um lote; é possível desfazer um lote, removendo suas transações e revertendo os saldos.</li>
              </ul>
            </details>
          </div>

          {/* Tabs */}
          <div role="tablist" aria-label="Tipo de importação" className="flex flex-wrap border-b border-slate-200 dark:border-slate-700/50 mb-6">
            {TABS.map((tab) => {
              const selected = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  type="button"
                  role="tab"
                  id={`import-tab-${tab.id}`}
                  aria-selected={selected}
                  aria-controls={`import-panel-${tab.id}`}
                  tabIndex={selected ? 0 : -1}
                  onClick={() => switchTab(tab.id)}
                  className={`px-6 py-3 text-sm font-medium transition-colors relative ${
                    selected
                      ? 'text-blue-700 dark:text-blue-300'
                      : 'text-slate-700 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white'
                  }`}
                >
                  {tab.label}
                  {selected && (
                    <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-600 dark:bg-blue-400" aria-hidden="true"></div>
                  )}
                </button>
              );
            })}
          </div>

          {/* Mensagens de Erro/Sucesso */}
          {error && (
            <div className="mb-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg flex items-center gap-2" role="alert">
              <i className="bi bi-exclamation-triangle-fill text-red-600 dark:text-red-400" aria-hidden="true"></i>
              <span className="text-red-800 dark:text-red-200 text-sm">{error}</span>
            </div>
          )}

          {success && (
            <div className="mb-4 p-3 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg flex items-center gap-2" role="status">
              <i className="bi bi-check-circle-fill text-green-600 dark:text-green-400" aria-hidden="true"></i>
              <span className="text-green-800 dark:text-green-200 text-sm">{success}</span>
            </div>
          )}

          {/* Feedback de Progresso */}
          {loading && progressMessage && (
            <div className="mb-4 p-4 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg" role="status" aria-live="polite">
              <div className="flex items-center gap-3">
                <i className="bi bi-arrow-repeat text-2xl text-blue-600 dark:text-blue-400 animate-spin" aria-hidden="true"></i>
                <div className="flex-1">
                  <p className="text-sm font-medium text-blue-900 dark:text-blue-200">
                    {progressMessage}
                  </p>
                  <p className="text-xs text-blue-800 dark:text-blue-300 mt-1">
                    Aguarde. Não feche esta página até a importação terminar.
                  </p>
                </div>
              </div>
            </div>
          )}

          {activeTab !== 'history' && renderAccountsBanner()}

          {/* Conteúdo Aba Histórico de Lotes */}
          {activeTab === 'history' ? (
            <div id="import-panel-history" role="tabpanel" aria-labelledby="import-tab-history" className="space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-3 pb-2 border-b border-slate-200 dark:border-slate-700/50">
                <p className="text-sm text-slate-700 dark:text-slate-300">
                  Cada arquivo enviado gera um lote. Desfazer um lote remove suas transações e reverte os saldos.
                </p>
                <button
                  type="button"
                  onClick={() => void loadBatches()}
                  disabled={loadingBatches}
                  className="min-h-[44px] px-3 text-sm font-medium bg-slate-100 dark:bg-slate-700 hover:bg-slate-200 dark:hover:bg-slate-600 text-slate-800 dark:text-slate-100 rounded-lg transition-colors flex items-center gap-1.5"
                >
                  <i className={`bi bi-arrow-clockwise ${loadingBatches ? 'animate-spin' : ''}`} aria-hidden="true"></i>
                  Atualizar
                </button>
              </div>

              {loadingBatches ? (
                <div className="p-8 text-center text-slate-600 dark:text-slate-300" role="status">
                  <i className="bi bi-arrow-repeat text-3xl animate-spin block mb-2" aria-hidden="true"></i>
                  Carregando histórico de importações...
                </div>
              ) : batches.length === 0 ? (
                <div className="p-8 text-center text-slate-600 dark:text-slate-300">
                  <i className="bi bi-inbox text-4xl block mb-2" aria-hidden="true"></i>
                  Nenhuma importação registrada até o momento.
                </div>
              ) : (
                <table className="import-batches">
                  <thead className="bg-slate-50 dark:bg-slate-800/50 text-xs font-medium text-slate-600 dark:text-slate-300 uppercase tracking-wider">
                    <tr>
                      <th scope="col">Data / Lote</th>
                      <th scope="col">Arquivo</th>
                      <th scope="col">Situação</th>
                      <th scope="col">Quantidades</th>
                      <th scope="col">Totais</th>
                      <th scope="col" className="text-right">Ação</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200 dark:divide-slate-700/50">
                    {batches.map((batch) => {
                      const isRolledBack = batch.status === 'rolled_back';
                      const isRolling = rollingBackId === batch.id;
                      return (
                        <tr key={batch.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/30">
                          <td data-label="Data / Lote" className="text-sm text-slate-700 dark:text-slate-300">
                            <div className="font-medium text-slate-900 dark:text-white">
                              {new Date(batch.created_at).toLocaleString('pt-BR')}
                            </div>
                            <span className="text-xs text-slate-600 dark:text-slate-400 font-mono" title={batch.id}>
                              {batch.id.slice(0, 8)}…
                            </span>
                          </td>
                          <td data-label="Arquivo">
                            <div className="font-medium text-slate-900 dark:text-white flex items-center gap-1.5 break-all">
                              <i className="bi bi-file-earmark-text text-blue-600 dark:text-blue-400" aria-hidden="true"></i>
                              {batch.filename}
                            </div>
                            <span className="text-xs text-slate-600 dark:text-slate-400 uppercase">
                              {batch.file_format || 'OFX'}
                            </span>
                          </td>
                          <td data-label="Situação">
                            <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                              isRolledBack
                                ? 'bg-amber-100 dark:bg-amber-900/30 text-amber-800 dark:text-amber-300'
                                : batch.status === 'completed'
                                  ? 'bg-emerald-100 dark:bg-emerald-900/30 text-emerald-800 dark:text-emerald-300'
                                  : 'bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-300'
                            }`}>
                              {isRolledBack ? 'Desfeita' : batch.status === 'completed' ? 'Concluída' : batch.status}
                            </span>
                          </td>
                          <td data-label="Quantidades" className="text-sm text-slate-700 dark:text-slate-300">
                            <div><span className="font-semibold text-emerald-700 dark:text-emerald-300">+{batch.imported_count}</span> importadas</div>
                            {batch.duplicate_count > 0 && (
                              <div className="text-slate-600 dark:text-slate-400">{batch.duplicate_count} duplicadas ignoradas</div>
                            )}
                            {batch.ignored_count > 0 && (
                              <div className="text-slate-600 dark:text-slate-400">{batch.ignored_count} espelhos ignorados</div>
                            )}
                          </td>
                          <td data-label="Totais" className="text-sm">
                            {Number(batch.total_income || 0) > 0 && (
                              <div className="text-emerald-700 dark:text-emerald-300 font-medium">Receitas: R$ {formatMoney(batch.total_income)}</div>
                            )}
                            {Number(batch.total_expense || 0) > 0 && (
                              <div className="text-red-700 dark:text-red-300 font-medium">Despesas: R$ {formatMoney(batch.total_expense)}</div>
                            )}
                            {Number(batch.total_transfer || 0) > 0 && (
                              <div className="text-blue-700 dark:text-blue-300 font-medium">Transferências: R$ {formatMoney(batch.total_transfer)}</div>
                            )}
                          </td>
                          <td data-label="Ação" className="text-right import-batches-action">
                            <button
                              type="button"
                              onClick={() => setRollbackTarget(batch)}
                              disabled={isRolledBack || isRolling}
                              aria-label={isRolledBack ? `Importação de ${batch.filename} já desfeita` : `Desfazer importação de ${batch.filename}`}
                              className={`min-h-[44px] px-3 text-sm font-medium rounded-lg transition-colors ${
                                isRolledBack
                                  ? 'bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400 cursor-not-allowed'
                                  : 'bg-red-50 text-red-700 hover:bg-red-100 dark:bg-red-900/20 dark:text-red-300 dark:hover:bg-red-900/40'
                              }`}
                            >
                              {isRolling ? (
                                <>
                                  <i className="bi bi-arrow-repeat animate-spin me-1" aria-hidden="true"></i>
                                  Desfazendo…
                                </>
                              ) : isRolledBack ? (
                                'Desfeita'
                              ) : (
                                <>
                                  <i className="bi bi-arrow-counterclockwise me-1" aria-hidden="true"></i>
                                  Desfazer importação
                                </>
                              )}
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </div>
          ) : activeTab === 'debit' ? (
            <div id="import-panel-debit" role="tabpanel" aria-labelledby="import-tab-debit" className="space-y-4">
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
                  disabled={loading || !accountsReady}
                >
                  <option value="">{accountsStatus === 'error' ? 'Contas indisponíveis' : 'Detectar/criar automaticamente'}</option>
                  {accounts.map((account) => (
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
                <div className="flex flex-wrap items-center gap-3">
                  <input
                    type="file"
                    id="importFile"
                    name="file"
                    className="input-base flex-1 min-w-0"
                    accept=".csv,.ofx"
                    onChange={handleFileChange}
                    disabled={loading || !accountsReady}
                  />
                  <button
                    type="button"
                    onClick={() => document.getElementById('importFile')?.click()}
                    className="min-h-[44px] px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    disabled={loading || !accountsReady}
                  >
                    Escolher arquivo
                  </button>
                </div>
                <div className="text-xs text-secondary mt-2">
                  Formatos aceitos: CSV (padrão ou Nubank) e OFX (Nubank e outros bancos)
                </div>
              </div>

              {renderSelectedFile()}
            </div>
          ) : (
            <div id="import-panel-credit_card" role="tabpanel" aria-labelledby="import-tab-credit_card" className="space-y-4">
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
                  disabled={loading || !accountsReady}
                  required
                >
                  <option value="">{accountsStatus === 'error' ? 'Cartões indisponíveis' : 'Selecione um cartão'}</option>
                  {creditCards.map((card) => (
                    <option key={card.id} value={card.id}>
                      {card.name} {card.institution ? `(${card.institution})` : ''}
                    </option>
                  ))}
                </select>
              </div>

              {/* Upload de Arquivo */}
              <div>
                <label htmlFor="importFileCreditCard" className="block text-sm font-medium text-secondary mb-2">
                  Arquivo da fatura
                </label>
                <div className="flex flex-wrap items-center gap-3">
                  <input
                    type="file"
                    id="importFileCreditCard"
                    name="file"
                    className="input-base flex-1 min-w-0"
                    accept=".csv,.ofx,.pdf"
                    onChange={handleFileChange}
                    disabled={loading || !accountsReady || !selectedCreditCardId}
                  />
                  <button
                    type="button"
                    onClick={() => document.getElementById('importFileCreditCard')?.click()}
                    className="min-h-[44px] px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    disabled={loading || !accountsReady || !selectedCreditCardId}
                  >
                    Escolher arquivo
                  </button>
                </div>
                <div className="text-xs text-secondary mt-2">
                  Formatos aceitos: CSV, OFX e PDF (faturas de cartão de crédito)
                </div>
                {accountsReady && !selectedCreditCardId && (
                  <div className="text-xs text-amber-800 dark:text-amber-300 mt-2">
                    <i className="bi bi-exclamation-circle me-1" aria-hidden="true"></i>
                    Selecione um cartão antes de escolher o arquivo
                  </div>
                )}
              </div>

              {renderSelectedFile()}
            </div>
          )}

          {/* Botão Importar */}
          {activeTab !== 'history' && (
            <div className="flex justify-end mt-6 pt-6 border-t border-slate-200 dark:border-slate-700/50">
              <button
                type="button"
                onClick={() => void handleImport()}
                className="min-h-[44px] px-6 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                disabled={!canSubmit}
              >
                {loading ? (
                  <>
                    <i className="bi bi-arrow-repeat animate-spin" aria-hidden="true"></i>
                    {progressMessage || 'Importando…'}
                  </>
                ) : (
                  <>
                    <i className="bi bi-upload" aria-hidden="true"></i>
                    Importar
                  </>
                )}
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Resultado da Importação */}
      {importResult && (
        <div className="card-base">
          <div className="p-6">
            <h3 className="text-lg font-semibold text-primary mb-4">Resultado da importação</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-center">
              <div className="bg-emerald-600 rounded-lg p-4 text-white">
                <i className="bi bi-check-circle text-4xl mb-2 block" aria-hidden="true"></i>
                <h4 className="text-2xl font-bold">{importResult.imported_count}</h4>
                <small className="text-sm">Importadas</small>
              </div>
              <div className="bg-red-600 rounded-lg p-4 text-white">
                <i className="bi bi-x-circle text-4xl mb-2 block" aria-hidden="true"></i>
                <h4 className="text-2xl font-bold">{importResult.error_count}</h4>
                <small className="text-sm">Com erro</small>
              </div>
              <div className="bg-blue-600 rounded-lg p-4 text-white">
                <i className="bi bi-file-text text-4xl mb-2 block" aria-hidden="true"></i>
                <h4 className="text-2xl font-bold">{importResult.imported_count + importResult.error_count}</h4>
                <small className="text-sm">Total</small>
              </div>
            </div>

            {importResult.errors && importResult.errors.length > 0 && (
              <div className="mt-4">
                <h6 className="text-red-700 dark:text-red-300 font-semibold mb-3">
                  <i className="bi bi-exclamation-triangle me-2" aria-hidden="true"></i>
                  Linhas com erro ({importResult.errors.length})
                </h6>
                <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg p-4">
                  <ul className="mb-0 space-y-1">
                    {importResult.errors.slice(0, ERRORS_PREVIEW_LIMIT).map((line, index) => (
                      <li key={index} className="text-sm text-secondary">{line}</li>
                    ))}
                  </ul>
                  {importResult.errors.length > ERRORS_PREVIEW_LIMIT && (
                    <details className="mt-2">
                      <summary className="cursor-pointer text-sm font-medium text-blue-700 dark:text-blue-300 hover:underline">
                        Mostrar todos ({importResult.errors.length - ERRORS_PREVIEW_LIMIT} restantes)
                      </summary>
                      <ul className="mt-2 space-y-1">
                        {importResult.errors.slice(ERRORS_PREVIEW_LIMIT).map((line, index) => (
                          <li key={ERRORS_PREVIEW_LIMIT + index} className="text-sm text-secondary">{line}</li>
                        ))}
                      </ul>
                    </details>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {rollbackTarget && (
        <ConfirmDialog
          title="Desfazer importação"
          subject={rollbackTarget.filename}
          details={[
            ['Transações', `${rollbackTarget.imported_count}`],
            ['Importado em', rollbackDate],
          ]}
          consequence="Todas as transações deste lote serão removidas e os saldos das contas voltarão ao valor anterior. Esta ação não pode ser desfeita."
          confirmLabel="Desfazer importação"
          danger
          onConfirm={confirmRollback}
          onClose={() => { if (!rollingBackId) setRollbackTarget(null); }}
          errorMessage={ROLLBACK_ERROR_MESSAGE}
        />
      )}
    </div>
  );
};

export default Import;
