import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../contexts/AuthContext';
import { oauthAPI } from '../../utils/api';

const Login = () => {
  const { t } = useTranslation();
  const { login } = useAuth();
  const navigate = useNavigate();

  const [formData, setFormData] = useState({
    email: '',
    password: '',
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

    const result = await login(formData);

    if (result.success) {
      navigate('/dashboard');
    } else {
      setError(result.message || t('auth.loginError'));
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
          <p className="text-muted">{t('auth.login')}</p>
        </div>

        {error && (
          <div className="alert alert-danger" role="alert">
            <i className="bi bi-exclamation-triangle-fill me-2"></i>
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
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

          <div className="mb-4">
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
              t('auth.login')
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
          <Link to="/forgot-password" className="text-decoration-none me-3">
            {t('auth.forgotPassword')}
          </Link>
        </div>

        <hr className="my-4" />

        <div className="text-center">
          <span className="text-muted">{t('auth.dontHaveAccount')} </span>
          <Link to="/register" className="text-decoration-none">
            {t('auth.register')}
          </Link>
        </div>
      </div>
    </div>
  );
};

export default Login;