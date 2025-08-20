import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../contexts/AuthContext';
import { authAPI } from '../../utils/api';

const Settings = () => {
  const { t, i18n } = useTranslation();
  const { user, updateUser } = useAuth();
  const [settings, setSettings] = useState({
    currency: 'BRL',
    theme: 'light',
    language: 'pt'
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  useEffect(() => {
    loadSettings();
  }, []);

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

    // Aplica mudança de idioma imediatamente
    if (field === 'language') {
      i18n.changeLanguage(value);
    }
  };

  const handleSave = async () => {
    setLoading(true);
    setError('');
    setSuccess('');

    try {
      await authAPI.updateSettings(settings);
      
      // Atualiza dados do usuário no contexto
      const updatedUser = { ...user, settings };
      updateUser(updatedUser);
      
      setSuccess(t('settings.saveSuccess'));
    } catch (err) {
      setError('Erro ao salvar configurações');
      console.error('Save settings error:', err);
    } finally {
      setLoading(false);
    }
  };

  const currencies = [
    { code: 'BRL', name: 'Real Brasileiro (R$)', symbol: 'R$' },
    { code: 'USD', name: 'Dólar Americano ($)', symbol: '$' },
    { code: 'EUR', name: 'Euro (€)', symbol: '€' },
    { code: 'GBP', name: 'Libra Esterlina (£)', symbol: '£' }
  ];

  const languages = [
    { code: 'pt', name: 'Português', flag: '🇧🇷' },
    { code: 'en', name: 'English', flag: '🇺🇸' },
    { code: 'es', name: 'Español', flag: '🇪🇸' }
  ];

  const themes = [
    { code: 'light', name: t('settings.light'), icon: 'bi-sun' },
    { code: 'dark', name: t('settings.dark'), icon: 'bi-moon' }
  ];

  return (
    <div className="settings">
      <div className="d-flex justify-content-between align-items-center mb-4">
        <h2 className="h3 mb-0">{t('settings.title')}</h2>
      </div>

      {error && (
        <div className="alert alert-danger" role="alert">
          <i className="bi bi-exclamation-triangle-fill me-2"></i>
          {error}
        </div>
      )}

      {success && (
        <div className="alert alert-success" role="alert">
          <i className="bi bi-check-circle-fill me-2"></i>
          {success}
        </div>
      )}

      <div className="row">
        <div className="col-lg-8">
          <div className="card">
            <div className="card-header">
              <h5 className="card-title mb-0">
                <i className="bi bi-gear me-2"></i>
                Preferências da Aplicação
              </h5>
            </div>
            <div className="card-body">
              <div className="row g-4">
                {/* Moeda */}
                <div className="col-md-6">
                  <label className="form-label fw-semibold">
                    <i className="bi bi-currency-exchange me-2"></i>
                    {t('settings.currency')}
                  </label>
                  <select
                    className="form-select"
                    value={settings.currency}
                    onChange={(e) => handleChange('currency', e.target.value)}
                    disabled={loading}
                  >
                    {currencies.map((currency) => (
                      <option key={currency.code} value={currency.code}>
                        {currency.name}
                      </option>
                    ))}
                  </select>
                  <div className="form-text">
                    Moeda padrão para exibição de valores
                  </div>
                </div>

                {/* Idioma */}
                <div className="col-md-6">
                  <label className="form-label fw-semibold">
                    <i className="bi bi-translate me-2"></i>
                    {t('settings.language')}
                  </label>
                  <select
                    className="form-select"
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
                  <div className="form-text">
                    Idioma da interface da aplicação
                  </div>
                </div>

                {/* Tema */}
                <div className="col-12">
                  <label className="form-label fw-semibold">
                    <i className="bi bi-palette me-2"></i>
                    {t('settings.theme')}
                  </label>
                  <div className="row">
                    {themes.map((theme) => (
                      <div key={theme.code} className="col-md-6 mb-3">
                        <div 
                          className={`card border-2 cursor-pointer ${
                            settings.theme === theme.code ? 'border-primary' : 'border-light'
                          }`}
                          onClick={() => handleChange('theme', theme.code)}
                          style={{ cursor: 'pointer' }}
                        >
                          <div className="card-body text-center">
                            <i className={`${theme.icon} display-6 mb-2`}></i>
                            <h6 className="card-title">{theme.name}</h6>
                            {settings.theme === theme.code && (
                              <i className="bi bi-check-circle-fill text-primary"></i>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                  <div className="form-text">
                    Aparência da aplicação (em desenvolvimento)
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Informações da Conta */}
          <div className="card mt-4">
            <div className="card-header">
              <h5 className="card-title mb-0">
                <i className="bi bi-person-circle me-2"></i>
                Informações da Conta
              </h5>
            </div>
            <div className="card-body">
              <div className="row g-3">
                <div className="col-md-6">
                  <label className="form-label">Nome</label>
                  <input
                    type="text"
                    className="form-control"
                    value={user?.name || ''}
                    disabled
                  />
                </div>
                
                <div className="col-md-6">
                  <label className="form-label">Email</label>
                  <input
                    type="email"
                    className="form-control"
                    value={user?.email || ''}
                    disabled
                  />
                </div>
              </div>
              
              <div className="mt-3">
                <small className="text-muted">
                  Para alterar dados da conta, acesse a seção Perfil
                </small>
              </div>
            </div>
          </div>

          {/* Botão Salvar */}
          <div className="d-flex justify-content-end mt-4">
            <button
              onClick={handleSave}
              className="btn btn-primary btn-lg"
              disabled={loading}
            >
              {loading ? (
                <>
                  <span className="loading-spinner me-2"></span>
                  {t('common.loading')}
                </>
              ) : (
                <>
                  <i className="bi bi-check-lg me-2"></i>
                  {t('settings.save')}
                </>
              )}
            </button>
          </div>
        </div>

        {/* Sidebar com Informações */}
        <div className="col-lg-4">
          <div className="card">
            <div className="card-header">
              <h6 className="card-title mb-0">
                <i className="bi bi-info-circle me-2"></i>
                Sobre as Configurações
              </h6>
            </div>
            <div className="card-body">
              <div className="mb-3">
                <h6 className="text-primary">
                  <i className="bi bi-currency-exchange me-2"></i>
                  Moeda
                </h6>
                <p className="small text-muted mb-3">
                  Define a moeda padrão para exibição de valores em toda a aplicação.
                </p>
              </div>

              <div className="mb-3">
                <h6 className="text-primary">
                  <i className="bi bi-translate me-2"></i>
                  Idioma
                </h6>
                <p className="small text-muted mb-3">
                  Altera o idioma da interface. A mudança é aplicada imediatamente.
                </p>
              </div>

              <div className="mb-3">
                <h6 className="text-primary">
                  <i className="bi bi-palette me-2"></i>
                  Tema
                </h6>
                <p className="small text-muted mb-0">
                  Escolha entre tema claro ou escuro. Funcionalidade em desenvolvimento.
                </p>
              </div>
            </div>
          </div>

          <div className="card mt-4">
            <div className="card-header">
              <h6 className="card-title mb-0">
                <i className="bi bi-shield-check me-2"></i>
                Privacidade
              </h6>
            </div>
            <div className="card-body">
              <p className="small text-muted">
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