import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { Input } from '../ui/input';
import { GradientButton } from '../ui/gradient-button';
import { ArrowLeft, Loader2, Mail } from 'lucide-react';
import { cn } from '../../lib/utils';
import { supabase } from '../../utils/supabaseClient';
import { formatSupabaseAuthError } from '../../utils/supabaseAuthErrors';
import LoginVisualPanel from './LoginVisualPanel';

const ForgotPassword: React.FC = () => {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [emailInvalid, setEmailInvalid] = useState(false);
  const [sent, setSent] = useState(false);

  const errorId = 'forgot-error-message';

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (loading) return;
    setError('');
    setEmailInvalid(false);

    const emailTrim = email.trim();
    if (!emailTrim) {
      setEmailInvalid(true);
      setError('Informe seu e-mail.');
      return;
    }

    setLoading(true);
    try {
      const redirectTo = `${window.location.origin}/reset-password`;
      const { error: resetError } = await supabase.auth.resetPasswordForEmail(emailTrim, { redirectTo });
      if (resetError) throw resetError;
      setSent(true);
    } catch (err) {
      setError(formatSupabaseAuthError(err as { message?: string }, 'Não foi possível enviar o link. Tente novamente.'));
    } finally {
      setLoading(false);
    }
  };

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
              <h2 className="login-glass-card__title">Esqueci a senha</h2>
              <p className="login-glass-card__subtitle">
                {sent
                  ? 'Se existir uma conta com esse e-mail, você receberá um link para redefinir sua senha.'
                  : 'Informe seu e-mail e enviaremos um link para redefinir sua senha.'}
              </p>
            </div>

            {!sent ? (
              <form onSubmit={handleSubmit} className="login-glass-card__form" noValidate>
                <div className="space-y-2">
                  <label htmlFor="forgot-email" className="text-sm font-medium text-slate-700 dark:text-slate-300">
                    E-mail
                  </label>
                  <div className={cn('relative rounded-lg input-with-icon', emailInvalid && 'input-error')}>
                    <Mail
                      className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400 pointer-events-none"
                      aria-hidden="true"
                    />
                    <Input
                      id="forgot-email"
                      name="email"
                      type="email"
                      autoComplete="email"
                      required
                      placeholder="seu@email.com"
                      value={email}
                      onChange={(e) => {
                        setEmail(e.target.value);
                        setError('');
                        setEmailInvalid(false);
                      }}
                      className="h-11 pl-10 border-slate-200 dark:border-slate-600 focus:border-emerald-500 dark:focus:border-emerald-400 transition-all"
                      aria-invalid={emailInvalid || undefined}
                      aria-describedby={emailInvalid ? errorId : undefined}
                    />
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
                      Enviando...
                    </>
                  ) : (
                    'Enviar link'
                  )}
                </GradientButton>
              </form>
            ) : (
              <div className="login-glass-card__form">
                <p className="text-sm text-slate-600 dark:text-slate-300 text-center" role="status">
                  Verifique sua caixa de entrada e o spam. O link expira em 1 hora.
                </p>
                <GradientButton asChild variant="default" className="w-full">
                  <Link to="/login">Voltar ao login</Link>
                </GradientButton>
              </div>
            )}

            {!sent && (
              <p className="login-glass-card__footer">
                <Link to="/login" className="login-glass-card__link inline-flex items-center gap-2">
                  <ArrowLeft className="h-4 w-4" aria-hidden="true" />
                  Voltar ao login
                </Link>
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default ForgotPassword;
