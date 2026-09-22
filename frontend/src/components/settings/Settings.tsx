import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../contexts/AuthContext';
import { useTheme } from '../../contexts/ThemeContext';
import { authAPI, categoriesAPI, invalidateLookupCache } from '../../utils/api';
import { ConfirmDialog } from '../shared/ConfirmDialog';
import { ClearDataDialog } from './ClearDataDialog';
import { CLEAR_DATA_ENTITIES, summarizeDeleted } from './clearDataEntities';
import './settings.css';

interface UserSettings {
  currency: string;
  theme: string;
  language: string;
}

type SettingsStatus = 'loading' | 'ready' | 'error';

interface BackupPayload {
  categories?: unknown[];
  accounts?: unknown[];
  transactions?: unknown[];
}

const BACKUP_SECTIONS: Array<keyof BackupPayload> = ['categories', 'accounts', 'transactions'];
const INVALID_BACKUP_MESSAGE = 'O arquivo não é um backup válido.';

/** Aceita apenas um objeto JSON com pelo menos uma das listas exportadas pelo backup. */
function parseBackup(content: string): BackupPayload | null {
  let parsed: unknown;
  try {
    parsed = JSON.parse(content);
  } catch {
    return null;
  }
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return null;
  const payload = parsed as Record<string, unknown>;
  const hasSection = BACKUP_SECTIONS.some(section => Array.isArray(payload[section]));
  return hasSection ? (payload as BackupPayload) : null;
}

/** Lê o arquivo como texto com FileReader (File.text() não existe em todos os ambientes). */
const readFileText = (file: File) => new Promise<string>((resolve, reject) => {
  const reader = new FileReader();
  reader.onload = () => resolve(typeof reader.result === 'string' ? reader.result : '');
  reader.onerror = () => reject(reader.error ?? new Error('read failed'));
  reader.readAsText(file);
});

const errorFrom = (err: unknown, fallback: string) =>
  (err as { response?: { data?: { error?: string } } })?.response?.data?.error || fallback;

const Settings = () => {
  const { t, i18n } = useTranslation();
  const { user, updateUser } = useAuth();
  const { theme, setTheme } = useTheme();
  const [settings, setSettings] = useState<UserSettings>({
    currency: 'BRL',
    theme: theme,
    language: 'pt'
  });
  const [settingsStatus, setSettingsStatus] = useState<SettingsStatus>('loading');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [backupLoading, setBackupLoading] = useState(false);
  const [importLoading, setImportLoading] = useState(false);
  const [categoryImportLoading, setCategoryImportLoading] = useState(false);
  const [pendingBackup, setPendingBackup] = useState<{ name: string; data: BackupPayload } | null>(null);
  const [clearDialogOpen, setClearDialogOpen] = useState(false);
  const backupFileInputRef = useRef<HTMLInputElement>(null);
  const categoryFileInputRef = useRef<HTMLInputElement>(null);
  const settingsLoadInFlightRef = useRef<Promise<void> | null>(null);
  const successTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const showSuccess = useCallback((message: string, ms = 5000) => {
    if (successTimerRef.current) clearTimeout(successTimerRef.current);
    setSuccess(message);
    successTimerRef.current = setTimeout(() => setSuccess(''), ms);
  }, []);

  useEffect(() => () => { if (successTimerRef.current) clearTimeout(successTimerRef.current); }, []);

  const loadSettings = useCallback(async () => {
    if (settingsLoadInFlightRef.current) {
      await settingsLoadInFlightRef.current;
      return;
    }
    const task = (async () => {
      setSettingsStatus('loading');
      try {
        const response = await authAPI.getSettings();
        const data = (response.data ?? {}) as Partial<UserSettings>;
        setSettings(prev => ({ ...prev, ...data }));
        setSettingsStatus('ready');
      } catch (err) {
        console.error('Load settings error:', err);
        setSettingsStatus('error');
      }
    })();
    settingsLoadInFlightRef.current = task;
    await task.finally(() => {
      settingsLoadInFlightRef.current = null;
    });
  }, []);

  useEffect(() => {
    void loadSettings();
  }, [loadSettings]);

  // Sincroniza o tema do contexto com o estado local
  useEffect(() => {
    setSettings(prev => ({
      ...prev,
      theme: theme
    }));
  }, [theme]);

  const handleChange = (field: keyof UserSettings, value: string) => {
    setSettings(prev => ({
      ...prev,
      [field]: value
    }));

    setError('');
    setSuccess('');

    // Apply language change immediately
    if (field === 'language') {
      i18n.changeLanguage(value);
    }

    // Apply theme change immediately
    if (field === 'theme') {
      setTheme(value as 'light' | 'dark');
    }
  };

  const handleExportBackup = async () => {
    try {
      setBackupLoading(true);
      setError('');
      setSuccess('');

      const response = await authAPI.exportBackup();
      const backupData = response.data;

      // Cria um blob e faz download
      const blob = new Blob([JSON.stringify(backupData, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `alca-financas-backup-${new Date().toISOString().split('T')[0]}.json`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);

      showSuccess('Backup exportado com sucesso!', 3000);
    } catch (err: unknown) {
      setError(errorFrom(err, 'Erro ao exportar backup'));
    } finally {
      setBackupLoading(false);
    }
  };

  /** Lê e valida o arquivo; a importação só acontece após confirmação no diálogo. */
  const handleBackupFileSelected = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const input = e.target;
    const file = input.files?.[0];
    if (!file) return;
    setError('');
    setSuccess('');
    let content = '';
    try {
      content = await readFileText(file);
    } catch {
      setError('Não foi possível ler o arquivo selecionado.');
      input.value = '';
      return;
    }
    const data = parseBackup(content);
    input.value = '';
    if (!data) {
      setError(INVALID_BACKUP_MESSAGE);
      return;
    }
    setPendingBackup({ name: file.name, data });
  };

  const confirmImportBackup = async () => {
    if (!pendingBackup) return;
    const { data } = pendingBackup;
    setImportLoading(true);
    try {
      const response = await authAPI.importBackup(data);
      const imported = response.data.imported ?? {};
      invalidateLookupCache();
      setPendingBackup(null);
      showSuccess(
        'Backup importado com sucesso! ' +
        `${imported.categories ?? 0} categorias, ${imported.accounts ?? 0} contas e ${imported.transactions ?? 0} transações importadas. ` +
        'As demais telas exibirão os novos dados ao serem abertas.'
      );
    } catch (err: unknown) {
      setPendingBackup(null);
      setError(errorFrom(err, 'Erro ao importar backup. Nenhum dado foi alterado.'));
    } finally {
      setImportLoading(false);
    }
  };

  const handleImportCategories = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const input = e.target;
    const file = input.files?.[0];
    if (!file) return;

    try {
      setCategoryImportLoading(true);
      setError('');
      setSuccess('');

      const response = await categoriesAPI.import(file);
      const result = response.data;

      let message = result.message;
      if (result.errors && result.errors.length > 0) {
        message += ` Alguns erros ocorreram: ${result.errors.slice(0, 3).join(', ')}`;
        if (result.errors.length > 3) {
          message += ` e mais ${result.errors.length - 3} erros.`;
        }
      }

      showSuccess(message);
    } catch (err: unknown) {
      setError(errorFrom(err, 'Erro ao importar categorias'));
    } finally {
      setCategoryImportLoading(false);
      input.value = '';
    }
  };

  /** Chamado pelo diálogo; lança em caso de falha para manter o diálogo aberto. */
  const clearAllData = async () => {
    setError('');
    setSuccess('');
    const response = await authAPI.clearAllData();
    const parts = summarizeDeleted(response.data?.deleted as Record<string, number | undefined> | undefined);
    invalidateLookupCache();
    setClearDialogOpen(false);
    showSuccess(
      parts.length > 0
        ? `Limpeza concluída: ${parts.join(', ')}.`
        : 'Limpeza concluída; não havia registros para remover.'
    );
  };

  const handleSave = async () => {
    if (settingsStatus !== 'ready' || loading) return;
    setLoading(true);
    setError('');
    setSuccess('');

    try {
      await authAPI.updateSettings(settings);

      // Update user data in context
      if (user) {
        const updatedUser = { ...user, settings };
        updateUser(updatedUser);
      }

      showSuccess(t('settings.saveSuccess'), 3000);
    } catch (err) {
      setError('Erro ao salvar configurações');
      console.error('Save settings error:', err);
    } finally {
      setLoading(false);
    }
  };

  const currencies = [
    { code: 'BRL', name: 'Real Brasileiro', symbol: 'R$' },
    { code: 'USD', name: 'Dólar Americano', symbol: '$' },
    { code: 'EUR', name: 'Euro', symbol: '€' },
    { code: 'GBP', name: 'Libra Esterlina', symbol: '£' }
  ];

  const languages = [
    { code: 'pt', name: 'Português', flag: '🇧🇷' },
    { code: 'en', name: 'English', flag: '🇺🇸' },
    { code: 'es', name: 'Español', flag: '🇪🇸' }
  ];

  const themes = [
    { code: 'light', name: t('settings.light'), icon: 'bi-sun-fill' },
    { code: 'dark', name: t('settings.dark'), icon: 'bi-moon-stars-fill' }
  ];

  const preferencesUnavailable = settingsStatus === 'error';
  const saveDisabled = loading || settingsStatus !== 'ready';
  const clearDataSummary = CLEAR_DATA_ENTITIES.map(entity => entity.label).join(', ');

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">{t('settings.title')}</h1>
          <p className="text-sm text-slate-600 dark:text-dark-text-secondary mt-1">Gerencie suas preferências da aplicação</p>
        </div>
      </div>

      {error && (
        <div role="alert" className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 flex items-center gap-2">
          <i className="bi bi-exclamation-triangle-fill text-red-600 dark:text-red-400"></i>
          <span className="text-red-800 dark:text-red-200">{error}</span>
        </div>
      )}

      {success && (
        <div role="status" className="bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-800 rounded-lg p-4 flex items-center gap-2">
          <i className="bi bi-check-circle-fill text-emerald-600 dark:text-emerald-400"></i>
          <span className="text-emerald-800 dark:text-emerald-200">{success}</span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Content */}
        <div className="lg:col-span-2 space-y-6">
          {/* Application Preferences */}
          <div className="card-base overflow-hidden">
            <div className="card-header px-6 py-4">
              <div className="flex items-center gap-2">
                <i className="bi bi-gear text-slate-600 dark:text-dark-text-secondary"></i>
                <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Preferências da Aplicação</h2>
              </div>
            </div>
            <div className="p-6">
              {preferencesUnavailable && (
                <div role="alert" className="mb-6 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 rounded-lg p-4 flex flex-wrap items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <i className="bi bi-exclamation-triangle-fill text-amber-600 dark:text-amber-300"></i>
                    <span className="text-amber-900 dark:text-amber-100">
                      <strong>Preferências indisponíveis.</strong> Não foi possível carregar suas preferências; salvar está bloqueado para não sobrescrevê-las.
                    </span>
                  </div>
                  <button type="button" onClick={() => void loadSettings()}
                    className="px-3 py-1.5 rounded-lg border border-amber-400 dark:border-amber-500 text-sm font-medium text-amber-900 dark:text-amber-100 hover:bg-amber-100 dark:hover:bg-amber-900/40">
                    Tentar novamente
                  </button>
                </div>
              )}
              <div className="space-y-6">
                {/* Currency */}
                <div>
                  <label htmlFor="settings-currency" className="flex items-center gap-2 text-sm font-medium text-slate-900 dark:text-slate-100 mb-3">
                    <i className="bi bi-currency-exchange text-slate-600 dark:text-dark-text-secondary"></i>
                    {t('settings.currency')}
                  </label>
                  <select
                    id="settings-currency"
                    name="currency"
                    className="native-select-themed"
                    value={settings.currency}
                    onChange={(e) => handleChange('currency', e.target.value)}
                    disabled={loading}
                  >
                    {currencies.map((currency) => (
                      <option key={currency.code} value={currency.code}>
                        {currency.symbol} {currency.name}
                      </option>
                    ))}
                  </select>
                  <p className="text-xs text-slate-500 dark:text-dark-text-secondary mt-2">
                    Moeda padrão para exibição de valores
                  </p>
                </div>

                {/* Language */}
                <div>
                  <label htmlFor="settings-language" className="flex items-center gap-2 text-sm font-medium text-slate-900 dark:text-slate-100 mb-3">
                    <i className="bi bi-translate text-slate-600 dark:text-dark-text-secondary"></i>
                    {t('settings.language')}
                  </label>
                  <select
                    id="settings-language"
                    name="language"
                    className="native-select-themed"
                    value={settings.language}
                    onChange={(e) => handleChange('language', e.target.value)}
                    disabled={loading}
                  >
                    {languages.map((lang) => (
                      <option key={lang.code} value={lang.code}>
                        {lang.flag} {lang.name}
                      </option>
                    ))}
                  </select>
                  <p className="text-xs text-slate-500 dark:text-dark-text-secondary mt-2">
                    Idioma da interface da aplicação
                  </p>
                </div>

                {/* Theme */}
                <div>
                  <label htmlFor="theme-selector" className="flex items-center gap-2 text-sm font-medium text-slate-900 dark:text-slate-100 mb-3">
                    <i className="bi bi-palette text-slate-600 dark:text-dark-text-secondary"></i>
                    {t('settings.theme')}
                  </label>
                  <div id="theme-selector" className="grid grid-cols-2 gap-3" role="group" aria-label="Selecionar tema">
                    {themes.map((themeOption) => (
                      <button
                        key={themeOption.code}
                        type="button"
                        name={`theme-${themeOption.code}`}
                        aria-label={`Selecionar tema ${themeOption.name}`}
                        aria-pressed={settings.theme === themeOption.code}
                        className={`settings-theme-card ${
                          settings.theme === themeOption.code
                            ? 'settings-theme-card--selected'
                            : 'settings-theme-card--idle'
                        }`}
                        onClick={() => handleChange('theme', themeOption.code)}
                        disabled={loading}
                      >
                        <div className="text-center">
                          <i className={`${themeOption.icon} text-4xl mb-3 ${
                            settings.theme === themeOption.code ? 'text-blue-600 dark:text-blue-300' : 'text-slate-400 dark:text-slate-300'
                          }`}></i>
                          <h3 className={`font-semibold text-sm ${
                            settings.theme === themeOption.code ? 'text-blue-900 dark:text-blue-100' : 'text-slate-900 dark:text-white'
                          }`}>
                            {themeOption.name}
                          </h3>
                          {settings.theme === themeOption.code && (
                            <i className="bi bi-check-circle-fill text-blue-600 dark:text-blue-300 mt-2 block"></i>
                          )}
                        </div>
                      </button>
                    ))}
                  </div>
                  <p className="text-xs text-slate-500 dark:text-dark-text-secondary mt-2">
                    Aparência da aplicação. A mudança é aplicada imediatamente.
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Account Information */}
          <div className="card-base overflow-hidden">
            <div className="card-header px-6 py-4">
              <div className="flex items-center gap-2">
                <i className="bi bi-person-circle text-slate-600 dark:text-dark-text-secondary"></i>
                <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Informações da Conta</h2>
              </div>
            </div>
            <div className="p-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label htmlFor="settings-name" className="block text-sm font-medium text-slate-700 dark:text-dark-text-secondary mb-2">Nome</label>
                  <input
                    type="text"
                    id="settings-name"
                    name="name"
                    className="native-input-themed settings-readonly-field w-full px-4 py-2.5"
                    value={user?.name || ''}
                    disabled
                  />
                </div>

                <div>
                  <label htmlFor="settings-email" className="block text-sm font-medium text-slate-700 dark:text-dark-text-secondary mb-2">Email</label>
                  <input
                    type="email"
                    id="settings-email"
                    name="email"
                    className="native-input-themed settings-readonly-field w-full px-4 py-2.5"
                    value={user?.email || ''}
                    disabled
                  />
                </div>
              </div>

              <div className="mt-4 p-3 bg-blue-50 dark:bg-blue-950/40 border border-blue-100 dark:border-blue-800/50 rounded-lg">
                <p className="text-sm text-blue-800 dark:text-blue-100 flex items-center gap-2">
                  <i className="bi bi-info-circle-fill"></i>
                  Os dados da conta são somente leitura. Para alterar a senha, acesse a seção Perfil.
                </p>
              </div>
            </div>
          </div>

          {/* Save Button */}
          <div className="flex justify-end">
            <button
              type="button"
              onClick={handleSave}
              className="px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium flex items-center gap-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              disabled={saveDisabled}
              aria-disabled={saveDisabled}
            >
              {loading ? (
                <>
                  <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent"></div>
                  {t('common.loading')}
                </>
              ) : (
                <>
                  <i className="bi bi-check-lg"></i>
                  {t('settings.save')}
                </>
              )}
            </button>
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* About Settings */}
          <div className="card-base overflow-hidden">
            <div className="card-header px-6 py-4">
              <div className="flex items-center gap-2">
                <i className="bi bi-info-circle text-slate-600 dark:text-dark-text-secondary"></i>
                <h3 className="text-sm font-semibold text-slate-900 dark:text-white">Sobre as Configurações</h3>
              </div>
            </div>
            <div className="p-6 space-y-4">
              <div>
                <h4 className="flex items-center gap-2 text-sm font-semibold text-blue-600 dark:text-blue-300 mb-2">
                  <i className="bi bi-currency-exchange"></i>
                  Moeda
                </h4>
                <p className="text-xs text-slate-600 dark:text-dark-text-secondary">
                  Define a moeda padrão para exibição de valores em toda a aplicação.
                </p>
              </div>

              <div>
                <h4 className="flex items-center gap-2 text-sm font-semibold text-blue-600 dark:text-blue-300 mb-2">
                  <i className="bi bi-translate"></i>
                  Idioma
                </h4>
                <p className="text-xs text-slate-600 dark:text-dark-text-secondary">
                  Altera o idioma da interface. A mudança é aplicada imediatamente.
                </p>
              </div>

              <div>
                <h4 className="flex items-center gap-2 text-sm font-semibold text-blue-600 dark:text-blue-300 mb-2">
                  <i className="bi bi-palette"></i>
                  Tema
                </h4>
                <p className="text-xs text-slate-600 dark:text-dark-text-secondary">
                  Escolha entre tema claro ou escuro. A mudança é aplicada imediatamente.
                </p>
              </div>
            </div>
          </div>

          {/* Privacy Card */}
          <div className="card-base overflow-hidden">
            <div className="card-header px-6 py-4">
              <div className="flex items-center gap-2">
                <i className="bi bi-shield-check text-slate-600 dark:text-dark-text-secondary"></i>
                <h3 className="text-sm font-semibold text-slate-900 dark:text-white">Privacidade</h3>
              </div>
            </div>
            <div className="p-6">
              <p className="text-xs text-slate-600 dark:text-dark-text-secondary">
                Suas configurações são salvas de forma segura e criptografada.
                Apenas você tem acesso aos seus dados financeiros.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Data Management Section */}
      <div className="card-base overflow-hidden">
        <div className="card-header px-6 py-4 border-b border-slate-200 dark:border-slate-700/50">
          <div className="flex items-center gap-2">
            <i className="bi bi-database text-slate-600 dark:text-dark-text-secondary"></i>
            <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Gerenciamento de Dados</h2>
          </div>
        </div>
        <div className="p-6 space-y-6">
          {/* Backup Section */}
          <div className="space-y-4">
            <div>
              <h3 className="text-sm font-semibold text-slate-900 dark:text-white mb-2">Backup e Restauração</h3>
              <p className="text-xs text-slate-600 dark:text-dark-text-secondary mb-4">
                Exporte todos os seus dados (categorias, transações e contas) para um arquivo JSON ou importe um backup anterior.
              </p>
            </div>

            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                onClick={handleExportBackup}
                disabled={backupLoading}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium flex items-center gap-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {backupLoading ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent"></div>
                    Exportando...
                  </>
                ) : (
                  <>
                    <i className="bi bi-download"></i>
                    Exportar Backup
                  </>
                )}
              </button>

              <button
                type="button"
                onClick={() => backupFileInputRef.current?.click()}
                disabled={importLoading}
                className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg font-medium flex items-center gap-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {importLoading ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent"></div>
                    Importando...
                  </>
                ) : (
                  <>
                    <i className="bi bi-upload"></i>
                    Importar Backup
                  </>
                )}
              </button>
              <input
                ref={backupFileInputRef}
                type="file"
                accept=".json"
                className="hidden"
                aria-label="Selecionar arquivo de backup"
                onChange={handleBackupFileSelected}
              />
            </div>
          </div>

          {/* Category Import Section */}
          <div className="space-y-4 pt-4 border-t border-slate-200 dark:border-slate-700/50">
            <div>
              <h3 className="text-sm font-semibold text-slate-900 dark:text-white mb-2">Importar Categorias</h3>
              <p className="text-xs text-slate-600 dark:text-dark-text-secondary mb-4">
                Importe categorias de um arquivo JSON ou CSV. O arquivo deve conter as colunas: name, type, color, icon, description.
              </p>
            </div>

            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                onClick={() => categoryFileInputRef.current?.click()}
                disabled={categoryImportLoading}
                className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg font-medium flex items-center gap-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {categoryImportLoading ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent"></div>
                    Importando...
                  </>
                ) : (
                  <>
                    <i className="bi bi-file-earmark-plus"></i>
                    Importar Categorias
                  </>
                )}
              </button>
              <input
                ref={categoryFileInputRef}
                type="file"
                accept=".json,.csv"
                className="hidden"
                aria-label="Selecionar arquivo de categorias"
                onChange={handleImportCategories}
              />
            </div>
          </div>

          {/* Clear Data Section */}
          <div className="space-y-4 pt-4 border-t border-slate-200 dark:border-slate-700/50">
            <div>
              <h3 className="text-sm font-semibold text-red-600 dark:text-red-300 mb-2">Zona de Perigo</h3>
              <p className="text-xs text-slate-600 dark:text-dark-text-secondary mb-4">
                <strong className="text-red-600 dark:text-red-300">Atenção:</strong> esta ação apaga permanentemente {clearDataSummary}. A conta de login é mantida. Esta ação não pode ser desfeita; certifique-se de ter um backup antes de continuar.
              </p>
            </div>

            <button
              type="button"
              onClick={() => { setError(''); setSuccess(''); setClearDialogOpen(true); }}
              className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg font-medium flex items-center gap-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <i className="bi bi-trash"></i>
              Limpar Todos os Dados
            </button>
          </div>
        </div>
      </div>

      {clearDialogOpen && (
        <ClearDataDialog onConfirm={clearAllData} onClose={() => setClearDialogOpen(false)} />
      )}

      {pendingBackup && (
        <ConfirmDialog
          title="Importar backup"
          subject={pendingBackup.name}
          details={BACKUP_SECTIONS.map(section => {
            const list = pendingBackup.data[section];
            const labels: Record<keyof BackupPayload, string> = { categories: 'Categorias', accounts: 'Contas', transactions: 'Transações' };
            return [labels[section], Array.isArray(list) ? String(list.length) : '0'] as [string, React.ReactNode];
          })}
          consequence={<p>Os dados do backup serão adicionados à sua conta. Categorias e contas com o mesmo nome serão ignoradas; transações duplicadas podem ser criadas.</p>}
          confirmLabel="Importar"
          onConfirm={confirmImportBackup}
          onClose={() => { if (!importLoading) setPendingBackup(null); }}
        />
      )}
    </div>
  );
};

export default Settings;
