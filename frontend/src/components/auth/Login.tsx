import React, { useState, useEffect } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { Input } from '../ui/input';
import { GradientButton } from '../ui/gradient-button';
import { Eye, EyeOff, Loader2, Mail, Lock } from 'lucide-react';
import { cn } from '../../lib/utils';
import LoginVisualPanel from './LoginVisualPanel';

const Login: React.FC = () => {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [formData, setFormData] = useState({
    email: '',
    password: '',
    rememberMe: false,
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [postRegisterInfo, setPostRegisterInfo] = useState('');
  const [showPassword, setShowPassword] = useState(false);

  useEffect(() => {
    const notice = (location.state as { registrationNotice?: string } | null)?.registrationNotice;
    if (notice) {
      setPostRegisterInfo(notice);
      navigate(location.pathname, { replace: true, state: {} });
    }
  }, [location.pathname, location.state, navigate]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value, type, checked } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value,
    }));
    setError('');
    setPostRegisterInfo('');
  };

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setPostRegisterInfo('');

    if (!formData.email?.trim() || !formData.password) {
      setError('Preencha e-mail e senha.');
      setLoading(false);
      return;
    }

    try {
      const result = await login(
        { email: formData.email.trim(), password: formData.password },
        formData.rememberMe
      );

      if (result.success) {
        navigate('/dashboard');
      } else {
        const msg = result.message || 'Erro no login';
        setError(
          msg === 'Network Error'
            ? 'Não foi possível conectar. Verifique sua internet ou se o servidor está ativo.'
            : msg
        );
      }
    } catch {
      setError('Erro inesperado. Tente novamente.');
    } finally {
      setLoading(false);
    }
  };

  const errorId = 'login-error-message';

  return (
    <div className="login-page">
      <LoginVisualPanel />

      <div className="login-form-panel">
        <div className="login-form-panel__inner">
          <div className="login-form-panel__brand-mobile login-stagger-1">
            <span className="login-logo-badge">
              <img
                src="/alcahub-logo.png"
                alt="Alça Finanças"
                className="login-form-panel__logo-mobile"
              />
            </span>
          </div>

          <div className="login-form-panel__copy-tablet login-stagger-1">
            <h1 className="login-form-panel__copy-tablet-headline">
              Sua vida financeira, organizada em um só lugar.
            </h1>
            <p className="login-form-panel__copy-tablet-subtext">
              Visualize seus gastos, acompanhe suas metas e tome decisões com mais clareza.
            </p>
          </div>

          <div className="login-glass-card login-stagger-2">
            <div className="login-glass-card__header">
              <h2 className="login-glass-card__title">Bem-vindo de volta</h2>
              <p className="login-glass-card__subtitle">
                Entre para continuar no Alça Finanças
              </p>
            </div>

            <form onSubmit={handleSubmit} className="login-glass-card__form" noValidate>
              <div className="space-y-2">
                <label htmlFor="email" className="text-sm font-medium text-slate-700 dark:text-slate-300">
                  E-mail
                </label>
                <div className={cn('relative rounded-lg input-with-icon', error && 'input-error')}>
                  <Mail
                    className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400 pointer-events-none"
                    aria-hidden="true"
                  />
                  <Input
                    id="email"
                    name="email"
                    type="email"
                    autoComplete="email"
                    required
                    placeholder="seu@email.com"
                    value={formData.email}
                    onChange={handleChange}
                    className="h-11 pl-10 border-slate-200 dark:border-slate-600 focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 dark:focus:border-emerald-400 transition-all"
                    aria-invalid={!!error}
                    aria-describedby={error ? errorId : undefined}
                  />
                </div>
              </div>

              <div className="space-y-2">
                <label htmlFor="password" className="text-sm font-medium text-slate-700 dark:text-slate-300">
                  Senha
                </label>
                <div className={cn('relative rounded-lg input-with-icon', error && 'input-error')}>
                  <Lock
                    className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400 pointer-events-none"
                    aria-hidden="true"
                  />
                  <Input
                    id="password"
                    name="password"
                    type={showPassword ? 'text' : 'password'}
                    autoComplete="current-password"
                    required
                    placeholder="••••••••"
                    value={formData.password}
                    onChange={handleChange}
                    className="h-11 pl-10 pr-10 border-slate-200 dark:border-slate-600 focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 dark:focus:border-emerald-400 transition-all"
                    aria-invalid={!!error}
                    aria-describedby={error ? errorId : undefined}
                  />
                  <button
                    type="button"
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 p-1 transition-colors"
                    onClick={() => setShowPassword(!showPassword)}
                    tabIndex={-1}
                    aria-label={showPassword ? 'Ocultar senha' : 'Mostrar senha'}
                  >
                    {showPassword ? (
                      <EyeOff className="h-4 w-4" aria-hidden="true" />
                    ) : (
                      <Eye className="h-4 w-4" aria-hidden="true" />
                    )}
                  </button>
                </div>
              </div>

              <div className="flex items-center justify-between gap-2">
                <label className="flex items-center gap-2 cursor-pointer select-none py-1">
                  <input
                    id="remember-me"
                    name="rememberMe"
                    type="checkbox"
                    checked={formData.rememberMe}
                    onChange={handleChange}
                    className="h-4 w-4 rounded border-slate-300 dark:border-slate-600 text-emerald-600 focus:ring-emerald-500"
                  />
                  <span className="text-sm text-slate-600 dark:text-slate-300">Lembrar-me</span>
                </label>
                <Link
                  to="/forgot-password"
                  className="text-sm font-medium text-emerald-600 dark:text-emerald-400 hover:underline py-1"
                >
                  Esqueci a senha
                </Link>
              </div>

              {postRegisterInfo && (
                <div
                  className="text-sm text-slate-700 dark:text-slate-200 bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 rounded-lg px-3 py-2.5 animate-fade-in"
                  role="status"
                >
                  {postRegisterInfo}
                </div>
              )}

              {error && (
                <div
                  id={errorId}
                  className="text-sm text-slate-700 dark:text-slate-300 bg-slate-100 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-600 border-l-4 border-l-amber-500 dark:border-l-amber-400 rounded-lg px-3 py-2.5 animate-shake"
                  role="alert"
                >
                  <i className="bi bi-exclamation-triangle-fill text-amber-500 dark:text-amber-400 mr-2" aria-hidden="true"></i>
                  {error}
                </div>
              )}

              <GradientButton
                type="submit"
                variant="default"
                className="w-full"
                disabled={loading}
              >
                {loading ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                    Entrando...
                  </>
                ) : (
                  'Entrar'
                )}
              </GradientButton>
            </form>

            <p className="login-glass-card__footer">
              Não tem uma conta?{' '}
              <Link to="/register" className="login-glass-card__link">
                Cadastre-se
              </Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Login;
