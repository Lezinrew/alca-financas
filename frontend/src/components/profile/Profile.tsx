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
    }, 1000);
  };

  return (
    <div className="profile">
      <div className="d-flex justify-content-between align-items-center mb-4">
        <h2 className="h3 mb-0">{t('navigation.profile')}</h2>
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
        {/* Informações do Perfil */}
        <div className="col-lg-8">
          <div className="card mb-4">
            <div className="card-header">
              <h5 className="card-title mb-0">
                <i className="bi bi-person-circle me-2"></i>
                Informações Pessoais
              </h5>
            </div>
            <div className="card-body">
              <form onSubmit={handleProfileSubmit}>
                <div className="row g-3">
                  <div className="col-md-6">
                    <label className="form-label">Nome Completo</label>
                    <input
                      type="text"
                      name="name"
                      className="form-control"
                      value={profileData.name}
                      onChange={handleProfileChange}
                      required
                      disabled={loading}
                    />
                  </div>
                  
                  <div className="col-md-6">
                    <label className="form-label">Email</label>
                    <input
                      type="email"
                      name="email"
                      className="form-control"
                      value={profileData.email}
                      onChange={handleProfileChange}
                      required
                      disabled={loading}
                    />
                  </div>
                </div>
                
                <div className="mt-4">
                  <button
                    type="submit"
                    className="btn btn-primary"
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
                        Atualizar Perfil
                      </>
                    )}
                  </button>
                </div>
              </form>
            </div>
          </div>

          {/* Alterar Senha */}
          <div className="card">
            <div className="card-header">
              <h5 className="card-title mb-0">
                <i className="bi bi-shield-lock me-2"></i>
                Alterar Senha
              </h5>
            </div>
            <div className="card-body">
              <form onSubmit={handlePasswordSubmit}>
                <div className="row g-3">
                  <div className="col-12">
                    <label className="form-label">Senha Atual</label>
                    <input
                      type="password"
                      name="currentPassword"
                      className="form-control"
                      value={passwordData.currentPassword}
                      onChange={handlePasswordChange}
                      required
                      disabled={loading}
                      placeholder="Digite sua senha atual"
                    />
                  </div>
                  
                  <div className="col-md-6">
                    <label className="form-label">Nova Senha</label>
                    <input
                      type="password"
                      name="newPassword"
                      className="form-control"
                      value={passwordData.newPassword}
                      onChange={handlePasswordChange}
                      required
                      disabled={loading}
                      minLength="6"
                      placeholder="Digite a nova senha"
                    />
                  </div>
                  
                  <div className="col-md-6">
                    <label className="form-label">Confirmar Nova Senha</label>
                    <input
                      type="password"
                      name="confirmPassword"
                      className="form-control"
                      value={passwordData.confirmPassword}
                      onChange={handlePasswordChange}
                      required
                      disabled={loading}
                      minLength="6"
                      placeholder="Confirme a nova senha"
                    />
                  </div>
                </div>
                
                <div className="mt-4">
                  <button
                    type="submit"
                    className="btn btn-warning"
                    disabled={loading}
                  >
                    {loading ? (
                      <>
                        <span className="loading-spinner me-2"></span>
                        {t('common.loading')}
                      </>
                    ) : (
                      <>
                        <i className="bi bi-shield-check me-2"></i>
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
        <div className="col-lg-4">
          {/* Avatar */}
          <div className="card mb-4">
            <div className="card-body text-center">
              <div 
                className="bg-primary rounded-circle d-inline-flex align-items-center justify-content-center mb-3"
                style={{ width: '100px', height: '100px' }}
              >
                <i className="bi bi-person-fill text-white" style={{ fontSize: '3rem' }}></i>
              </div>
              <h5>{user?.name}</h5>
              <p className="text-muted mb-3">{user?.email}</p>
              
              <div className="row text-center">
                <div className="col-6">
                  <div className="text-muted small">Membro desde</div>
                  <div className="fw-bold">Ago 2025</div>
                </div>
                <div className="col-6">
                  <div className="text-muted small">Último acesso</div>
                  <div className="fw-bold">Hoje</div>
                </div>
              </div>
            </div>
          </div>

          {/* Provedores de Login */}
          {user?.auth_providers && user.auth_providers.length > 0 && (
            <div className="card mb-4">
              <div className="card-header">
                <h6 className="card-title mb-0">
                  <i className="bi bi-shield-check me-2"></i>
                  Contas Conectadas
                </h6>
              </div>
              <div className="card-body">
                {user.auth_providers.map((provider, index) => (
                  <div key={index} className="d-flex align-items-center mb-2">
                    <i className={`bi bi-${provider.provider} me-3`}></i>
                    <div>
                      <div className="fw-medium text-capitalize">{provider.provider}</div>
                      <small className="text-muted">
                        {provider.email_verified ? 'Verificado' : 'Não verificado'}
                      </small>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Dicas de Segurança */}
          <div className="card">
            <div className="card-header">
              <h6 className="card-title mb-0">
                <i className="bi bi-info-circle me-2"></i>
                Dicas de Segurança
              </h6>
            </div>
            <div className="card-body">
              <ul className="list-unstyled small mb-0">
                <li className="mb-2">
                  <i className="bi bi-check-circle text-success me-2"></i>
                  Use senhas fortes e únicas
                </li>
                <li className="mb-2">
                  <i className="bi bi-check-circle text-success me-2"></i>
                  Altere sua senha regularmente
                </li>
                <li className="mb-2">
                  <i className="bi bi-check-circle text-success me-2"></i>
                  Não compartilhe suas credenciais
                </li>
                <li>
                  <i className="bi bi-check-circle text-success me-2"></i>
                  Mantenha seu email atualizado
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