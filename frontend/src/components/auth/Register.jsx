import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../contexts/AuthContext';
import { oauthAPI } from '../../utils/api';

const Register = () => {
  const { t } = useTranslation();
  const { register } = useAuth();
  const navigate = useNavigate();

  const [formData, setFormData] = useState({
    name: '',
    email: '',
    password: '',
    confirmPassword: '',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
    });
    setError('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    // Validação de senha
    if (formData.password !== formData.confirmPassword) {
      setError('As senhas não coincidem');
      setLoading(false);
      return;
    }

    if (formData.password.length < 6) {
      setError('A senha deve ter pelo menos 6 caracteres');
      setLoading(false);
      return;
    }

    const result = await register({
      name: formData.name,
      email: formData.email,
      password: formData.password,
    });

    if (result.success) {
      navigate('/dashboard');
    } else {
      setError(result.message || t('auth.registerError'));
    }

    setLoading(false);
  };

  const handleSocialLogin = (provider) => {
    let loginUrl;
    switch (provider) {
      case 'google':
        loginUrl = oauthAPI.googleLogin();
        break;
      case 'microsoft':
        loginUrl = oauthAPI.microsoftLogin();
        break;
      case 'apple':
        loginUrl = oauthAPI.appleLogin();
        break;
      default:
        return;
    }
    
    window.location.href = loginUrl;
  };

  return (
    <div className="auth-container d-flex align-items-center justify-content-center">
      <div className="auth-card">
        <div className="text-center mb-4">
          <h2 className="h4 mb-2">{t('app.title')}</h2>
          <p className="text-muted">{t('auth.register')}</p>
        </div>

        {error && (
          <div className="alert alert-danger" role="alert">
            <i className="bi bi-exclamation-triangle-fill me-2"></i>
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="mb-3">
            <label htmlFor="name" className="form-label">
              {t('auth.name')}
            </label>
            <input
              type="text"
              className="form-control"
              id="name"
              name="name"
              value={formData.name}
              onChange={handleChange}
              required
              disabled={loading}
              placeholder="Seu nome completo"
            />
          </div>

          <div className="mb-3">
            <label htmlFor="email" className="form-label">
              {t('auth.email')}
            </label>
            <input
              type="email"
              className="form-control"
              id="email"
              name="email"
              value={formData.email}
              onChange={handleChange}
              required
              disabled={loading}
              placeholder="seu@email.com"
            />
          </div>

          <div className="mb-3">
            <label htmlFor="password" className="form-label">
              {t('auth.password')}
            </label>
            <input
              type="password"
              className="form-control"
              id="password"
              name="password"
              value={formData.password}
              onChange={handleChange}
              required
              disabled={loading}
              placeholder="••••••••"
              minLength="6"
            />
          </div>

          <div className="mb-4">
            <label htmlFor="confirmPassword" className="form-label">
              {t('auth.confirmPassword')}
            </label>
            <input
              type="password"
              className="form-control"
              id="confirmPassword"
              name="confirmPassword"
              value={formData.confirmPassword}
              onChange={handleChange}
              required
              disabled={loading}
              placeholder="••••••••"
              minLength="6"
            />
          </div>

          <button
            type="submit"
            className="btn btn-primary w-100 mb-3"
            disabled={loading}
          >
            {loading ? (
              <>
                <span className="loading-spinner me-2"></span>
                {t('common.loading')}
              </>
            ) : (
              t('auth.register')
            )}
          </button>
        </form>

        <div className="text-center mb-3">
          <small className="text-muted">ou</small>
        </div>

        {/* Login Social */}
        <div className="mb-4">
          <button
            type="button"
            className="social-login-btn"
            onClick={() => handleSocialLogin('google')}
            disabled={loading}
          >
            <i className="bi bi-google"></i>
            {t('auth.loginWithGoogle')}
          </button>

          <button
            type="button"
            className="social-login-btn"
            onClick={() => handleSocialLogin('microsoft')}
            disabled={loading}
          >
            <i className="bi bi-microsoft"></i>
            {t('auth.loginWithMicrosoft')}
          </button>

          <button
            type="button"
            className="social-login-btn"
            onClick={() => handleSocialLogin('apple')}
            disabled={loading}
          >
            <i className="bi bi-apple"></i>
            {t('auth.loginWithApple')}
          </button>
        </div>

        <div className="text-center">
          <span className="text-muted">{t('auth.alreadyHaveAccount')} </span>
          <Link to="/login" className="text-decoration-none">
            {t('auth.login')}
          </Link>
        </div>
      </div>
    </div>
  );
};

export default Register;