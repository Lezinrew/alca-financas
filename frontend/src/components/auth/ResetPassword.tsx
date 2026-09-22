import React, { useState, useEffect } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { Input } from '../ui/input';
import { GradientButton } from '../ui/gradient-button';
import { Eye, EyeOff, Loader2, Lock } from 'lucide-react';
import { cn } from '../../lib/utils';
import { supabase } from '../../utils/supabaseClient';
import { formatSupabaseAuthError } from '../../utils/supabaseAuthErrors';
import LoginVisualPanel from './LoginVisualPanel';

const INVALID_LINK = 'Link inválido ou expirado. Solicite um novo link.';
type FieldName = 'password' | 'confirm';

const iconClass = 'absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400 pointer-events-none';
const inputClass =
  'h-11 pl-10 pr-12 border-slate-200 dark:border-slate-600 focus:border-emerald-500 dark:focus:border-emerald-400 transition-all';
const toggleClass =
  'absolute right-0 top-1/2 -translate-y-1/2 inline-flex items-center justify-center min-h-[44px] min-w-[44px] rounded-lg text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200 transition-colors';

const ResetPassword: React.FC = () => {
  const { isAuthenticated } = useAuth();
  const [searchParams] = useSearchParams();
  const code = searchParams.get('code') ?? '';
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [validating, setValidating] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [errorField, setErrorField] = useState<FieldName | null>(null);
  const [success, setSuccess] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);

  const errorId = 'reset-error-message';

  useEffect(() => {
    // No Supabase, o recovery link pode chegar como `?code=...` (PKCE).
    // Trocamos o código por sessão para permitir update de senha.
    let cancelled = false;
    const ensureSession = async () => {
      try {
        if (code) {
          const { error: exchangeError } = await supabase.auth.exchangeCodeForSession(window.location.href);
          if (exchangeError) throw exchangeError;
          return;
        }
        const { data } = await supabase.auth.getSession();
        if (!data.session && !cancelled) setError(INVALID_LINK);
      } catch (e) {
        if (!cancelled) setError(formatSupabaseAuthError(e as { message?: string }, INVALID_LINK));
      } finally {
        if (!cancelled) setValidating(false);
      }
    };
    ensureSession();
    return () => {
      cancelled = true;
    };
  }, [code]);

  const fail = (message: string, field: FieldName | null) => {
    setError(message);
    setErrorField(field);
  };

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (loading || validating) return;
    setError('');
    setErrorField(null);
    if (password.length < 6) return fail('A senha deve ter pelo menos 6 caracteres.', 'password');
    if (password !== confirm) return fail('As senhas não coincidem.', 'confirm');

    setLoading(true);
    try {
      const { error: updateError } = await supabase.auth.updateUser({ password });
      if (updateError) throw updateError;
      setSuccess(true);
    } catch (err) {
      fail(
        formatSupabaseAuthError(
          err as { message?: string },
          'Não foi possível redefinir a senha. Use o link mais recente do e-mail.'
        ),
        null
      );
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
              <h2 className="login-glass-card__title">Nova senha</h2>
              <p className="login-glass-card__subtitle">
                {success
                  ? isAuthenticated
                    ? 'Sua senha foi alterada. Você já pode continuar no painel.'
                    : 'Sua senha foi alterada. Faça login com a nova senha.'
                  : 'Digite e confirme sua nova senha.'}
              </p>
            </div>

            {success ? (
              <GradientButton asChild variant="default" className="w-full">
                {isAuthenticated ? (
                  <Link to="/dashboard">Ir para o painel</Link>
                ) : (
                  <Link to="/login">Ir para o login</Link>
                )}
              </GradientButton>
            ) : (
              <form onSubmit={handleSubmit} className="login-glass-card__form" noValidate aria-busy={validating}>
                {validating && (
                  <p
                    className="text-sm text-slate-600 dark:text-slate-300 inline-flex items-center gap-2"
                    role="status"
                  >
                    <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                    Validando link...
                  </p>
                )}

                <fieldset disabled={validating} className="login-glass-card__form min-w-0 border-0 p-0 m-0">
                  <div className="space-y-2">
                    <label htmlFor="reset-password" className="text-sm font-medium text-slate-700 dark:text-slate-300">
                      Nova senha
                    </label>
                    <div className={cn('relative rounded-lg input-with-icon', errorField === 'password' && 'input-error')}>
                      <Lock className={iconClass} aria-hidden="true" />
                      <Input
                        id="reset-password"
                        name="password"
                        type={showPassword ? 'text' : 'password'}
                        autoComplete="new-password"
                        required
                        minLength={6}
                        placeholder="••••••••"
                        value={password}
                        onChange={(e) => {
                          setPassword(e.target.value);
                          setError('');
                          setErrorField(null);
                        }}
                        className={inputClass}
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
                    <label htmlFor="reset-confirm" className="text-sm font-medium text-slate-700 dark:text-slate-300">
                      Confirmar senha
                    </label>
                    <div className={cn('relative rounded-lg input-with-icon', errorField === 'confirm' && 'input-error')}>
                      <Lock className={iconClass} aria-hidden="true" />
                      <Input
                        id="reset-confirm"
                        name="confirm"
                        type={showConfirm ? 'text' : 'password'}
                        autoComplete="new-password"
                        required
                        minLength={6}
                        placeholder="••••••••"
                        value={confirm}
                        onChange={(e) => {
                          setConfirm(e.target.value);
                          setError('');
                          setErrorField(null);
                        }}
                        className={inputClass}
                        {...fieldA11y('confirm')}
                      />
                      <button
                        type="button"
                        className={toggleClass}
                        onClick={() => setShowConfirm((v) => !v)}
                        aria-label={showConfirm ? 'Ocultar confirmação de senha' : 'Mostrar confirmação de senha'}
                        aria-pressed={showConfirm}
                      >
                        {showConfirm ? <EyeOff className="h-4 w-4" aria-hidden="true" /> : <Eye className="h-4 w-4" aria-hidden="true" />}
                      </button>
                    </div>
                  </div>
                </fieldset>

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

                <GradientButton type="submit" variant="default" className="w-full" disabled={loading || validating}>
                  {loading ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                      Salvando...
                    </>
                  ) : (
                    'Redefinir senha'
                  )}
                </GradientButton>
              </form>
            )}

            {!success && (
              <p className="login-glass-card__footer">
                <Link to="/forgot-password" className="login-glass-card__link">
                  Solicitar novo link
                </Link>
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default ResetPassword;
