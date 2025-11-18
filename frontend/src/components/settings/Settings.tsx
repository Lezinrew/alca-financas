import React, { useState, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../contexts/AuthContext';
import { useTheme } from '../../contexts/ThemeContext';
import { authAPI, categoriesAPI } from '../../utils/api';

const Settings = () => {
  const { t, i18n } = useTranslation();
  const { user, updateUser } = useAuth();
  const { theme, setTheme } = useTheme();
  const [settings, setSettings] = useState({
    currency: 'BRL',
    theme: theme,
    language: 'pt'
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [backupLoading, setBackupLoading] = useState(false);
  const [importLoading, setImportLoading] = useState(false);
  const [clearLoading, setClearLoading] = useState(false);
  const [categoryImportLoading, setCategoryImportLoading] = useState(false);
  const backupFileInputRef = useRef<HTMLInputElement>(null);
  const categoryFileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    loadSettings();
  }, []);

  // Sincroniza o tema do contexto com o estado local
  useEffect(() => {
    setSettings(prev => ({
      ...prev,
      theme: theme
    }));
  }, [theme]);

  const loadSettings = async () => {
    try {
      const response = await authAPI.getSettings();
      setSettings(response.data);
    } catch (err) {
      console.error('Load settings error:', err);
    }
  };

  const handleChange = (field: string, value: any) => {
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
      setTheme(value);
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
      
      setSuccess('Backup exportado com sucesso!');
      setTimeout(() => setSuccess(''), 3000);
    } catch (err: any) {
      setError(err.response?.data?.error || 'Erro ao exportar backup');
    } finally {
      setBackupLoading(false);
    }
  };

  const handleImportBackup = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      setImportLoading(true);
      setError('');
      setSuccess('');
      
      const fileContent = await file.text();
      const backupData = JSON.parse(fileContent);
      
      if (!window.confirm('Esta ação irá importar os dados do backup. Categorias, contas e transações duplicadas serão ignoradas. Deseja continuar?')) {
        e.target.value = '';
        return;
      }
      
      const response = await authAPI.importBackup(backupData);
      const imported = response.data.imported;
      
      setSuccess(
        `Backup importado com sucesso! ` +
        `${imported.categories} categorias, ${imported.accounts} contas e ${imported.transactions} transações importadas.`
      );
      setTimeout(() => setSuccess(''), 5000);
      
      // Recarrega a página após 2 segundos para atualizar os dados
      setTimeout(() => {
        window.location.reload();
      }, 2000);
    } catch (err: any) {
      setError(err.response?.data?.error || 'Erro ao importar backup');
    } finally {
      setImportLoading(false);
      e.target.value = '';
    }
  };

  const handleImportCategories = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
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
      
      setSuccess(message);
      setTimeout(() => setSuccess(''), 5000);
      
      // Recarrega a página após 2 segundos
      setTimeout(() => {
        window.location.reload();
      }, 2000);
    } catch (err: any) {
      setError(err.response?.data?.error || 'Erro ao importar categorias');
    } finally {
      setCategoryImportLoading(false);
      e.target.value = '';
    }
  };

  const handleClearAllData = async () => {
    if (!window.confirm(
      'ATENÇÃO: Esta ação irá deletar PERMANENTEMENTE todas as suas categorias, transações e contas. ' +
      'Esta ação NÃO PODE ser desfeita. Tem certeza que deseja continuar?'
    )) {
      return;
    }

    // Confirmação dupla
    if (!window.confirm(
      'Última confirmação: Você tem CERTEZA ABSOLUTA que deseja deletar todos os seus dados? ' +
      'Esta é a última chance de cancelar.'
    )) {
      return;
    }

    try {
      setClearLoading(true);
      setError('');
      setSuccess('');
      
      const response = await authAPI.clearAllData();
      const deleted = response.data.deleted;
      
      setSuccess(
        `Todos os dados foram limpos com sucesso! ` +
        `${deleted.categories} categorias, ${deleted.accounts} contas e ${deleted.transactions} transações deletadas.`
      );
      setTimeout(() => setSuccess(''), 5000);
      
      // Recarrega a página após 2 segundos
      setTimeout(() => {
        window.location.reload();
      }, 2000);
    } catch (err: any) {
      setError(err.response?.data?.error || 'Erro ao limpar dados');
    } finally {
      setClearLoading(false);
    }
  };

  const handleSave = async () => {
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

      setSuccess(t('settings.saveSuccess'));

      // Clear success message after 3 seconds
      setTimeout(() => setSuccess(''), 3000);
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

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">{t('settings.title')}</h1>
          <p className="text-sm text-slate-600 dark:text-slate-300 mt-1">Gerencie suas preferências da aplicação</p>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center gap-2">
          <i className="bi bi-exclamation-triangle-fill text-red-600"></i>
          <span className="text-red-800">{error}</span>
        </div>
      )}

      {success && (
        <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-4 flex items-center gap-2">
          <i className="bi bi-check-circle-fill text-emerald-600"></i>
          <span className="text-emerald-800">{success}</span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Content */}
        <div className="lg:col-span-2 space-y-6">
          {/* Application Preferences */}
          <div className="card-base overflow-hidden">
            <div className="card-header px-6 py-4">
              <div className="flex items-center gap-2">
                <i className="bi bi-gear text-slate-600 dark:text-slate-300"></i>
                <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Preferências da Aplicação</h2>
              </div>
            </div>
            <div className="p-6">
              <div className="space-y-6">
                {/* Currency */}
                <div>
                  <label htmlFor="settings-currency" className="flex items-center gap-2 text-sm font-medium text-slate-900 dark:text-slate-100 mb-3">
                    <i className="bi bi-currency-exchange text-slate-600 dark:text-slate-400"></i>
                    {t('settings.currency')}
                  </label>
                  <select
                    id="settings-currency"
                    name="currency"
                    className="w-full px-4 py-2.5 bg-white dark:bg-[#1a1d29] border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
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
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-2">
                    Moeda padrão para exibição de valores
                  </p>
                </div>

                {/* Language */}
                <div>
                  <label htmlFor="settings-language" className="flex items-center gap-2 text-sm font-medium text-slate-900 dark:text-slate-100 mb-3">
                    <i className="bi bi-translate text-slate-600 dark:text-slate-400"></i>
                    {t('settings.language')}
                  </label>
                  <select
                    id="settings-language"
                    name="language"
                    className="w-full px-4 py-2.5 bg-white dark:bg-[#1a1d29] border border-slate-300 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
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
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-2">
                    Idioma da interface da aplicação
                  </p>
                </div>

                {/* Theme */}
                <div>
                  <label htmlFor="theme-selector" className="flex items-center gap-2 text-sm font-medium text-slate-900 dark:text-slate-100 mb-3">
                    <i className="bi bi-palette text-slate-600 dark:text-slate-400"></i>
                    {t('settings.theme')}
                  </label>
                  <div id="theme-selector" className="grid grid-cols-2 gap-3" role="group" aria-label="Selecionar tema">
                    {themes.map((themeOption) => (
                      <button
                        key={themeOption.code}
                        type="button"
                        name={`theme-${themeOption.code}`}
                        aria-label={`Selecionar tema ${themeOption.name}`}
                        className={`p-6 rounded-xl border-2 transition-all ${
                          settings.theme === themeOption.code
                            ? 'border-blue-600 bg-blue-50 dark:bg-blue-900/30 dark:border-blue-500'
                            : 'border-slate-200 dark:border-slate-700 bg-white dark:bg-[#1a1d29] hover:border-slate-300 dark:hover:border-slate-600'
                        }`}
                        onClick={() => handleChange('theme', themeOption.code)}
                        disabled={loading}
                      >
                        <div className="text-center">
                          <i className={`${themeOption.icon} text-4xl mb-3 ${
                            settings.theme === themeOption.code ? 'text-blue-600 dark:text-blue-400' : 'text-slate-400 dark:text-slate-500'
                          }`}></i>
                          <h3 className={`font-semibold text-sm ${
                            settings.theme === themeOption.code ? 'text-blue-900 dark:text-blue-200' : 'text-slate-900 dark:text-slate-100'
                          }`}>
                            {themeOption.name}
                          </h3>
                          {settings.theme === themeOption.code && (
                            <i className="bi bi-check-circle-fill text-blue-600 dark:text-blue-400 mt-2 block"></i>
                          )}
                        </div>
                      </button>
                    ))}
                  </div>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-2">
                    Aparência da aplicação
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Account Information */}
          <div className="card-base overflow-hidden">
            <div className="card-header px-6 py-4">
              <div className="flex items-center gap-2">
                <i className="bi bi-person-circle text-slate-600 dark:text-slate-300"></i>
                <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">Informações da Conta</h2>
              </div>
            </div>
            <div className="p-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label htmlFor="settings-name" className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">Nome</label>
                  <input
                    type="text"
                    id="settings-name"
                    name="name"
                    className="w-full px-4 py-2.5 bg-slate-50 dark:bg-[#1a1d29] border border-slate-200 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white"
                    value={user?.name || ''}
                    disabled
                  />
                </div>

                <div>
                  <label htmlFor="settings-email" className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">Email</label>
                  <input
                    type="email"
                    id="settings-email"
                    name="email"
                    className="w-full px-4 py-2.5 bg-slate-50 dark:bg-[#1a1d29] border border-slate-200 dark:border-slate-700 rounded-lg text-slate-900 dark:text-white"
                    value={user?.email || ''}
                    disabled
                  />
                </div>
              </div>

              <div className="mt-4 p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
                <p className="text-sm text-blue-800 dark:text-blue-300 flex items-center gap-2">
                  <i className="bi bi-info-circle-fill"></i>
                  Para alterar dados da conta, acesse a seção Perfil
                </p>
              </div>
            </div>
          </div>

          {/* Save Button */}
          <div className="flex justify-end">
            <button
              onClick={handleSave}
              className="px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium flex items-center gap-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              disabled={loading}
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
                <i className="bi bi-info-circle text-slate-600 dark:text-slate-300"></i>
                <h3 className="text-sm font-semibold text-slate-900 dark:text-white">Sobre as Configurações</h3>
              </div>
            </div>
            <div className="p-6 space-y-4">
              <div>
                <h4 className="flex items-center gap-2 text-sm font-semibold text-blue-600 dark:text-blue-400 mb-2">
                  <i className="bi bi-currency-exchange"></i>
                  Moeda
                </h4>
                <p className="text-xs text-slate-600 dark:text-slate-400">
                  Define a moeda padrão para exibição de valores em toda a aplicação.
                </p>
              </div>

              <div>
                <h4 className="flex items-center gap-2 text-sm font-semibold text-blue-600 dark:text-blue-400 mb-2">
                  <i className="bi bi-translate"></i>
                  Idioma
                </h4>
                <p className="text-xs text-slate-600 dark:text-slate-400">
                  Altera o idioma da interface. A mudança é aplicada imediatamente.
                </p>
              </div>

              <div>
                <h4 className="flex items-center gap-2 text-sm font-semibold text-blue-600 dark:text-blue-400 mb-2">
                  <i className="bi bi-palette"></i>
                  Tema
                </h4>
                <p className="text-xs text-slate-600 dark:text-slate-400">
                  Escolha entre tema claro ou escuro. Funcionalidade em desenvolvimento.
                </p>
              </div>
            </div>
          </div>

          {/* Privacy Card */}
          <div className="card-base overflow-hidden">
            <div className="card-header px-6 py-4">
              <div className="flex items-center gap-2">
                <i className="bi bi-shield-check text-slate-600 dark:text-slate-300"></i>
                <h3 className="text-sm font-semibold text-slate-900 dark:text-white">Privacidade</h3>
              </div>
            </div>
            <div className="p-6">
              <p className="text-xs text-slate-600 dark:text-slate-400">
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
            <i className="bi bi-database text-slate-600 dark:text-slate-300"></i>
            <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Gerenciamento de Dados</h2>
          </div>
        </div>
        <div className="p-6 space-y-6">
          {/* Backup Section */}
          <div className="space-y-4">
            <div>
              <h3 className="text-sm font-semibold text-slate-900 dark:text-white mb-2">Backup e Restauração</h3>
              <p className="text-xs text-slate-600 dark:text-slate-400 mb-4">
                Exporte todos os seus dados (categorias, transações e contas) para um arquivo JSON ou importe um backup anterior.
              </p>
            </div>
            
            <div className="flex flex-wrap gap-3">
              <button
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
                onChange={handleImportBackup}
              />
            </div>
          </div>

          {/* Category Import Section */}
          <div className="space-y-4 pt-4 border-t border-slate-200 dark:border-slate-700/50">
            <div>
              <h3 className="text-sm font-semibold text-slate-900 dark:text-white mb-2">Importar Categorias</h3>
              <p className="text-xs text-slate-600 dark:text-slate-400 mb-4">
                Importe categorias de um arquivo JSON ou CSV. O arquivo deve conter as colunas: name, type, color, icon, description.
              </p>
            </div>
            
            <div className="flex flex-wrap gap-3">
              <button
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
                onChange={handleImportCategories}
              />
            </div>
          </div>

          {/* Clear Data Section */}
          <div className="space-y-4 pt-4 border-t border-slate-200 dark:border-slate-700/50">
            <div>
              <h3 className="text-sm font-semibold text-red-600 dark:text-red-400 mb-2">Zona de Perigo</h3>
              <p className="text-xs text-slate-600 dark:text-slate-400 mb-4">
                <strong className="text-red-600 dark:text-red-400">Atenção:</strong> Esta ação irá deletar permanentemente todas as suas categorias, transações e contas. Esta ação não pode ser desfeita. Certifique-se de ter um backup antes de continuar.
              </p>
            </div>
            
            <button
              onClick={handleClearAllData}
              disabled={clearLoading}
              className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg font-medium flex items-center gap-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {clearLoading ? (
                <>
                  <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent"></div>
                  Limpando...
                </>
              ) : (
                <>
                  <i className="bi bi-trash"></i>
                  Limpar Todos os Dados
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Settings;
