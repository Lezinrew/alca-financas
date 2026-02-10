import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { Input } from '../ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card';
import { GradientButton } from '../ui/gradient-button';
import { Eye, EyeOff, Loader2, Mail, Lock, Wallet } from 'lucide-react';
import { cn } from '../../lib/utils';

const Login: React.FC = () => {
  const { login } = useAuth();
  const navigate = useNavigate();

  const [formData, setFormData] = useState({
    email: '',
    password: '',
    rememberMe: false,
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showPassword, setShowPassword] = useState(false);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value, type, checked } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value,
    }));
    setError('');
  };

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setLoading(true);
    setError('');

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

  return (
    <div className="min-h-screen flex items-center justify-center bg-login-page dark:bg-login-page p-4 transition-colors duration-200">
      <div className="w-full max-w-md relative z-10">
        {/* Logo/Brand */}
        <div className="text-center mb-8">
          <div className="flex items-center justify-center mb-4">
            <div className="bg-gradient-to-br from-emerald-500 to-emerald-600 p-3 rounded-2xl shadow-lg">
              <Wallet className="w-10 h-10 text-white" aria-hidden />
            </div>
          </div>
          <h1 className="text-3xl font-bold text-slate-900 dark:text-white mb-2 transition-colors">
            Alça Finanças
          </h1>
          <p className="text-slate-600 dark:text-slate-300 transition-colors">
            Controle financeiro inteligente
          </p>
        </div>

        <Card className="card-login shadow-xl border-0">
          <CardHeader className="space-y-1 pb-4">
            <CardTitle className="text-2xl font-semibold text-center text-slate-900 dark:text-white">
              Bem-vindo de volta
            </CardTitle>
            <CardDescription className="text-center text-slate-600 dark:text-slate-400">
              Entre com seu e-mail e senha
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <form onSubmit={handleSubmit} className="space-y-4" noValidate>
              <div className="space-y-2">
                <label htmlFor="email" className="text-sm font-medium text-slate-700 dark:text-slate-300">
                  E-mail
                </label>
                <div className={cn('relative rounded-lg input-with-icon', error && 'input-error')}>
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400 pointer-events-none" />
                  <Input
                    id="email"
                    name="email"
                    type="email"
                    autoComplete="email"
                    required
                    placeholder="seu@email.com"
                    value={formData.email}
                    onChange={handleChange}
                    className="h-11 pl-10 border-slate-200 dark:border-slate-600"
                    aria-invalid={!!error}
                  />
                </div>
              </div>

              <div className="space-y-2">
                <label htmlFor="password" className="text-sm font-medium text-slate-700 dark:text-slate-300">
                  Senha
                </label>
                <div className={cn('relative rounded-lg input-with-icon', error && 'input-error')}>
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400 pointer-events-none" />
                  <Input
                    id="password"
                    name="password"
                    type={showPassword ? 'text' : 'password'}
                    autoComplete="current-password"
                    required
                    placeholder="••••••••"
                    value={formData.password}
                    onChange={handleChange}
                    className="h-11 pl-10 pr-10 border-slate-200 dark:border-slate-600"
                    aria-invalid={!!error}
                  />
                  <button
                    type="button"
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 p-1"
                    onClick={() => setShowPassword(!showPassword)}
                    tabIndex={-1}
                    aria-label={showPassword ? 'Ocultar senha' : 'Mostrar senha'}
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </div>

              <div className="flex items-center justify-between gap-2">
                <label className="flex items-center gap-2 cursor-pointer select-none">
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
                  className="text-sm font-medium text-emerald-600 dark:text-emerald-400 hover:underline"
                >
                  Esqueci a senha
                </Link>
              </div>

              {error && (
                <div
                  className="text-sm text-slate-700 dark:text-slate-300 bg-slate-100 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-600 border-l-4 border-l-amber-500 dark:border-l-amber-400 rounded-lg px-3 py-2.5"
                  role="alert"
                >
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
                    <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
                    Entrando...
                  </>
                ) : (
                  'Entrar'
                )}
              </GradientButton>
            </form>

            <p className="text-center text-sm text-slate-600 dark:text-slate-400">
              Não tem uma conta?{' '}
              <Link
                to="/register"
                className="font-medium text-emerald-600 dark:text-emerald-400 hover:underline"
              >
                Cadastre-se
              </Link>
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default Login;
