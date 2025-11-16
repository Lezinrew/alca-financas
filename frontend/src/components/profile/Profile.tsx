import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../contexts/AuthContext';

const Profile = () => {
  const { t } = useTranslation();
  const { user } = useAuth();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const [profileData, setProfileData] = useState({
    name: user?.name || '',
    email: user?.email || ''
  });

  const [passwordData, setPasswordData] = useState({
    currentPassword: '',
    newPassword: '',
    confirmPassword: ''
  });

  const handleProfileChange = (e) => {
    setProfileData({
      ...profileData,
      [e.target.name]: e.target.value
    });
    setError('');
    setSuccess('');
  };

  const handlePasswordChange = (e) => {
    setPasswordData({
      ...passwordData,
      [e.target.name]: e.target.value
    });
    setError('');
    setSuccess('');
  };

  const handleProfileSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setSuccess('');

    // Simulação - em produção implementar API
    setTimeout(() => {
      setLoading(false);
      setSuccess('Perfil atualizado com sucesso!');
      setTimeout(() => setSuccess(''), 3000);
    }, 1000);
  };

  const handlePasswordSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setSuccess('');

    if (passwordData.newPassword !== passwordData.confirmPassword) {
      setError('As senhas não coincidem');
      setLoading(false);
      return;
    }

    if (passwordData.newPassword.length < 6) {
      setError('A nova senha deve ter pelo menos 6 caracteres');
      setLoading(false);
      return;
    }

    // Simulação - em produção implementar API
    setTimeout(() => {
      setLoading(false);
      setSuccess('Senha alterada com sucesso!');
      setPasswordData({
        currentPassword: '',
        newPassword: '',
        confirmPassword: ''
      });
      setTimeout(() => setSuccess(''), 3000);
    }, 1000);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">{t('navigation.profile')}</h1>
          <p className="text-sm text-slate-600 mt-1">Gerencie suas informações pessoais e segurança</p>
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
          {/* Personal Information */}
          <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
            <div className="bg-slate-50 border-b border-slate-200 px-6 py-4">
              <div className="flex items-center gap-2">
                <i className="bi bi-person-circle text-slate-600"></i>
                <h2 className="text-lg font-semibold text-slate-900">Informações Pessoais</h2>
              </div>
            </div>
            <div className="p-6">
              <form onSubmit={handleProfileSubmit}>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label htmlFor="profile-name" className="block text-sm font-medium text-slate-700 mb-2">Nome Completo</label>
                    <input
                      type="text"
                      id="profile-name"
                      name="name"
                      autoComplete="name"
                      className="w-full px-4 py-2.5 bg-white border border-slate-300 rounded-lg text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                      value={profileData.name}
                      onChange={handleProfileChange}
                      required
                      disabled={loading}
                    />
                  </div>

                  <div>
                    <label htmlFor="profile-email" className="block text-sm font-medium text-slate-700 mb-2">Email</label>
                    <input
                      type="email"
                      id="profile-email"
                      name="email"
                      autoComplete="email"
                      className="w-full px-4 py-2.5 bg-white border border-slate-300 rounded-lg text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                      value={profileData.email}
                      onChange={handleProfileChange}
                      required
                      disabled={loading}
                    />
                  </div>
                </div>

                <div className="mt-6 flex justify-end">
                  <button
                    type="submit"
                    className="px-6 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium flex items-center gap-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
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
                        Atualizar Perfil
                      </>
                    )}
                  </button>
                </div>
              </form>
            </div>
          </div>

          {/* Change Password */}
          <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
            <div className="bg-slate-50 border-b border-slate-200 px-6 py-4">
              <div className="flex items-center gap-2">
                <i className="bi bi-shield-lock text-slate-600"></i>
                <h2 className="text-lg font-semibold text-slate-900">Alterar Senha</h2>
              </div>
            </div>
            <div className="p-6">
              <form onSubmit={handlePasswordSubmit}>
                <div className="space-y-4">
                  <div>
                    <label htmlFor="profile-current-password" className="block text-sm font-medium text-slate-700 mb-2">Senha Atual</label>
                    <input
                      type="password"
                      id="profile-current-password"
                      name="currentPassword"
                      autoComplete="current-password"
                      className="w-full px-4 py-2.5 bg-white border border-slate-300 rounded-lg text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                      value={passwordData.currentPassword}
                      onChange={handlePasswordChange}
                      required
                      disabled={loading}
                      placeholder="Digite sua senha atual"
                    />
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label htmlFor="profile-new-password" className="block text-sm font-medium text-slate-700 mb-2">Nova Senha</label>
                      <input
                        type="password"
                        id="profile-new-password"
                        name="newPassword"
                        autoComplete="new-password"
                        className="w-full px-4 py-2.5 bg-white border border-slate-300 rounded-lg text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                        value={passwordData.newPassword}
                        onChange={handlePasswordChange}
                        required
                        disabled={loading}
                        minLength="6"
                        placeholder="Digite a nova senha"
                      />
                    </div>

                    <div>
                      <label htmlFor="profile-confirm-password" className="block text-sm font-medium text-slate-700 mb-2">Confirmar Nova Senha</label>
                      <input
                        type="password"
                        id="profile-confirm-password"
                        name="confirmPassword"
                        autoComplete="new-password"
                        className="w-full px-4 py-2.5 bg-white border border-slate-300 rounded-lg text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                        value={passwordData.confirmPassword}
                        onChange={handlePasswordChange}
                        required
                        disabled={loading}
                        minLength="6"
                        placeholder="Confirme a nova senha"
                      />
                    </div>
                  </div>
                </div>

                <div className="mt-6 flex justify-end">
                  <button
                    type="submit"
                    className="px-6 py-2.5 bg-amber-600 hover:bg-amber-700 text-white rounded-lg font-medium flex items-center gap-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    disabled={loading}
                  >
                    {loading ? (
                      <>
                        <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent"></div>
                        {t('common.loading')}
                      </>
                    ) : (
                      <>
                        <i className="bi bi-shield-check"></i>
                        Alterar Senha
                      </>
                    )}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Profile Card */}
          <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
            <div className="p-6 text-center">
              <div
                className="bg-gradient-to-br from-blue-600 to-blue-700 rounded-full inline-flex items-center justify-center mb-4"
                style={{ width: '100px', height: '100px' }}
              >
                <i className="bi bi-person-fill text-white" style={{ fontSize: '3rem' }}></i>
              </div>
              <h3 className="text-lg font-bold text-slate-900">{user?.name}</h3>
              <p className="text-sm text-slate-600 mb-6">{user?.email}</p>

              <div className="grid grid-cols-2 gap-4 pt-4 border-t border-slate-200">
                <div className="text-center">
                  <div className="text-xs text-slate-500 mb-1">Membro desde</div>
                  <div className="font-semibold text-slate-900">Ago 2025</div>
                </div>
                <div className="text-center">
                  <div className="text-xs text-slate-500 mb-1">Último acesso</div>
                  <div className="font-semibold text-slate-900">Hoje</div>
                </div>
              </div>
            </div>
          </div>

          {/* Connected Accounts */}
          {user?.auth_providers && user.auth_providers.length > 0 && (
            <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
              <div className="bg-slate-50 border-b border-slate-200 px-6 py-4">
                <div className="flex items-center gap-2">
                  <i className="bi bi-shield-check text-slate-600"></i>
                  <h3 className="text-sm font-semibold text-slate-900">Contas Conectadas</h3>
                </div>
              </div>
              <div className="p-6">
                <div className="space-y-3">
                  {user.auth_providers.map((provider, index) => (
                    <div key={index} className="flex items-center gap-3 p-3 bg-slate-50 rounded-lg">
                      <i className={`bi bi-${provider.provider} text-slate-600 text-xl`}></i>
                      <div className="flex-1">
                        <div className="font-medium text-sm text-slate-900 capitalize">{provider.provider}</div>
                        <div className="text-xs text-slate-500">
                          {provider.email_verified ? (
                            <span className="text-emerald-600">
                              <i className="bi bi-check-circle-fill"></i> Verificado
                            </span>
                          ) : (
                            <span className="text-amber-600">
                              <i className="bi bi-exclamation-circle-fill"></i> Não verificado
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Security Tips */}
          <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
            <div className="bg-slate-50 border-b border-slate-200 px-6 py-4">
              <div className="flex items-center gap-2">
                <i className="bi bi-info-circle text-slate-600"></i>
                <h3 className="text-sm font-semibold text-slate-900">Dicas de Segurança</h3>
              </div>
            </div>
            <div className="p-6">
              <ul className="space-y-3">
                <li className="flex items-start gap-2 text-sm text-slate-600">
                  <i className="bi bi-check-circle-fill text-emerald-500 mt-0.5 flex-shrink-0"></i>
                  <span>Use senhas fortes e únicas</span>
                </li>
                <li className="flex items-start gap-2 text-sm text-slate-600">
                  <i className="bi bi-check-circle-fill text-emerald-500 mt-0.5 flex-shrink-0"></i>
                  <span>Altere sua senha regularmente</span>
                </li>
                <li className="flex items-start gap-2 text-sm text-slate-600">
                  <i className="bi bi-check-circle-fill text-emerald-500 mt-0.5 flex-shrink-0"></i>
                  <span>Não compartilhe suas credenciais</span>
                </li>
                <li className="flex items-start gap-2 text-sm text-slate-600">
                  <i className="bi bi-check-circle-fill text-emerald-500 mt-0.5 flex-shrink-0"></i>
                  <span>Mantenha seu email atualizado</span>
                </li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Profile;
