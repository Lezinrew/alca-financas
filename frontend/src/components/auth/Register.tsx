import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { Input } from '../ui/input';
import { GradientButton } from '../ui/gradient-button';
import { Eye, EyeOff, Loader2, Lock, Mail, User } from 'lucide-react';
import { cn } from '../../lib/utils';
import LoginVisualPanel from './LoginVisualPanel';

type FieldName = 'name' | 'email' | 'password' | 'confirmPassword';

const iconClass = 'absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400 pointer-events-none';
const inputClass =
  'h-11 pl-10 border-slate-200 dark:border-slate-600 focus:border-emerald-500 dark:focus:border-emerald-400 transition-all';
const toggleClass =
  'absolute right-0 top-1/2 -translate-y-1/2 inline-flex items-center justify-center min-h-[44px] min-w-[44px] rounded-lg text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200 transition-colors';

const Register: React.FC = () => {
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
  const [errorField, setErrorField] = useState<FieldName | null>(null);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  const errorId = 'register-error-message';

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    setError('');
    setErrorField(null);
  };

  const fail = (message: string, field: FieldName | null) => {
    setError(message);
    setErrorField(field);
  };

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (loading) return;
    setError('');
    setErrorField(null);

    const nameTrim = formData.name.trim();
    const emailTrim = formData.email.trim();
    if (!nameTrim) return fail('Informe seu nome.', 'name');
    if (!emailTrim) return fail('Informe seu e-mail.', 'email');
    if (formData.password.length < 6) return fail('A senha deve ter pelo menos 6 caracteres.', 'password');
    if (formData.password !== formData.confirmPassword) return fail('As senhas não coincidem.', 'confirmPassword');

    setLoading(true);
    try {
      const result = await register({ name: nameTrim, email: emailTrim, password: formData.password });

      if (result.success) {
        // Sem sessão (ex.: confirmação de e-mail): não enviar para área autenticada.
        if (result.message) {
          navigate('/login', { replace: true, state: { registrationNotice: result.message } });
        } else {
          navigate('/dashboard', { replace: true });
        }
      } else {
        fail(result.message || 'Não foi possível concluir o cadastro. Tente novamente.', null);
      }
    } catch {
      fail('Erro inesperado. Tente novamente.', null);
    } finally {
      setLoading(false);
    }
  };

  const fieldA11y = (field: FieldName) => ({
    'aria-invalid': errorField === field || undefined,
    'aria-describedby': errorField === field ? errorId : undefined,
  });

  return (
    <div className="login-page">
      <LoginVisualPanel />

      <div className="login-form-panel">
        <div className="login-form-panel__inner">
          <div className="login-form-panel__brand-mobile login-stagger-1">
            <span className="login-logo-badge">
              <img src="/alcahub-logo.png" alt="Alça Finanças" className="login-form-panel__logo-mobile" />
            </span>
          </div>

          <div className="login-glass-card login-stagger-2">
            <div className="login-glass-card__header">
              <h2 className="login-glass-card__title">Criar conta</h2>
              <p className="login-glass-card__subtitle">Preencha os dados abaixo para começar</p>
            </div>

            <form onSubmit={handleSubmit} className="login-glass-card__form" noValidate>
              <div className="space-y-2">
                <label htmlFor="name" className="text-sm font-medium text-slate-700 dark:text-slate-300">
                  Nome completo
                </label>
                <div className={cn('relative rounded-lg input-with-icon', errorField === 'name' && 'input-error')}>
                  <User className={iconClass} aria-hidden="true" />
                  <Input
                    id="name"
                    name="name"
                    type="text"
                    autoComplete="name"
                    required
                    placeholder="Seu nome completo"
                    value={formData.name}
                    onChange={handleChange}
                    className={inputClass}
                    {...fieldA11y('name')}
                  />
                </div>
              </div>

              <div className="space-y-2">
                <label htmlFor="email" className="text-sm font-medium text-slate-700 dark:text-slate-300">
                  E-mail
                </label>
                <div className={cn('relative rounded-lg input-with-icon', errorField === 'email' && 'input-error')}>
                  <Mail className={iconClass} aria-hidden="true" />
                  <Input
                    id="email"
                    name="email"
                    type="email"
                    autoComplete="email"
                    required
                    placeholder="seu@email.com"
                    value={formData.email}
                    onChange={handleChange}
                    className={inputClass}
                    {...fieldA11y('email')}
                  />
                </div>
              </div>

              <div className="space-y-2">
                <label htmlFor="password" className="text-sm font-medium text-slate-700 dark:text-slate-300">
                  Senha
                </label>
                <div className={cn('relative rounded-lg input-with-icon', errorField === 'password' && 'input-error')}>
                  <Lock className={iconClass} aria-hidden="true" />
                  <Input
                    id="password"
                    name="password"
                    type={showPassword ? 'text' : 'password'}
                    autoComplete="new-password"
                    required
                    minLength={6}
                    placeholder="••••••••"
                    value={formData.password}
                    onChange={handleChange}
                    className={cn(inputClass, 'pr-12')}
                    {...fieldA11y('password')}
                  />
                  <button
                    type="button"
                    className={toggleClass}
                    onClick={() => setShowPassword((v) => !v)}
                    aria-label={showPassword ? 'Ocultar senha' : 'Mostrar senha'}
                    aria-pressed={showPassword}
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" aria-hidden="true" /> : <Eye className="h-4 w-4" aria-hidden="true" />}
                  </button>
                </div>
              </div>

              <div className="space-y-2">
                <label htmlFor="confirmPassword" className="text-sm font-medium text-slate-700 dark:text-slate-300">
                  Confirmar senha
                </label>
                <div className={cn('relative rounded-lg input-with-icon', errorField === 'confirmPassword' && 'input-error')}>
                  <Lock className={iconClass} aria-hidden="true" />
                  <Input
                    id="confirmPassword"
                    name="confirmPassword"
                    type={showConfirmPassword ? 'text' : 'password'}
                    autoComplete="new-password"
                    required
                    minLength={6}
                    placeholder="••••••••"
                    value={formData.confirmPassword}
                    onChange={handleChange}
                    className={cn(inputClass, 'pr-12')}
                    {...fieldA11y('confirmPassword')}
                  />
                  <button
                    type="button"
                    className={toggleClass}
                    onClick={() => setShowConfirmPassword((v) => !v)}
                    aria-label={showConfirmPassword ? 'Ocultar confirmação de senha' : 'Mostrar confirmação de senha'}
                    aria-pressed={showConfirmPassword}
                  >
                    {showConfirmPassword ? <EyeOff className="h-4 w-4" aria-hidden="true" /> : <Eye className="h-4 w-4" aria-hidden="true" />}
                  </button>
                </div>
              </div>

              {error && (
                <div
                  id={errorId}
                  className="text-sm text-slate-800 dark:text-slate-100 bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-600 border-l-4 border-l-amber-500 dark:border-l-amber-400 rounded-lg px-3 py-2.5 animate-shake"
                  role="alert"
                >
                  <i className="bi bi-exclamation-triangle-fill text-amber-600 dark:text-amber-400 mr-2" aria-hidden="true"></i>
                  {error}
                </div>
              )}

              <GradientButton type="submit" variant="default" className="w-full" disabled={loading}>
                {loading ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                    Criando conta...
                  </>
                ) : (
                  'Criar conta'
                )}
              </GradientButton>
            </form>

            <p className="login-glass-card__footer">
              Já tem uma conta?{' '}
              <Link to="/login" className="login-glass-card__link">
                Entrar
              </Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Register;
