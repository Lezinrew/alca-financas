import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../contexts/AuthContext';
import { useTheme } from '../../contexts/ThemeContext';
import { authAPI } from '../../utils/api';

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

  const handleChange = (field, value) => {
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

  const handleSave = async () => {
    setLoading(true);
    setError('');
    setSuccess('');

    try {
      await authAPI.updateSettings(settings);

      // Update user data in context
      const updatedUser = { ...user, settings };
      updateUser(updatedUser);

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
    </div>
  );
};

export default Settings;
