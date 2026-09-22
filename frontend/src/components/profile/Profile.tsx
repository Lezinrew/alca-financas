import { useEffect, useRef, useState, ChangeEvent, FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../contexts/AuthContext';
import { authAPI } from '../../utils/api';
import { supabase } from '../../utils/supabaseClient';
import './profile.css';

interface PasswordData {
  currentPassword: string;
  newPassword: string;
  confirmPassword: string;
}

interface PasswordFieldErrors {
  newPassword?: string;
  confirmPassword?: string;
}

const MIN_PASSWORD_LENGTH = 6;
const NAME_MIN_LENGTH = 2;
const NAME_MAX_LENGTH = 120;
const NAME_SAVE_ERROR = 'Não foi possível salvar o nome. Tente novamente.';
const NAME_SAVE_SUCCESS = 'Nome atualizado com sucesso!';
const EMAIL_READONLY_HINT = 'Para alterar o e-mail, fale com o suporte.';
// Mesmas regras do backend (PUT /auth/profile): controle/formatação invisíveis e separadores de linha.
const NAME_INVALID_CHARS = /[\p{C}\u2028\u2029]/u;

/** Validação local do nome (espelha o backend); devolve a mensagem ou ''. */
function validateName(raw: string): string {
  const name = raw.trim();
  if (name.length < NAME_MIN_LENGTH) return `O nome deve ter pelo menos ${NAME_MIN_LENGTH} caracteres.`;
  if (name.length > NAME_MAX_LENGTH) return `O nome deve ter no máximo ${NAME_MAX_LENGTH} caracteres.`;
  if (NAME_INVALID_CHARS.test(name)) return 'O nome contém caracteres inválidos.';
  return '';
}

/** Validação local da nova senha; devolve mensagens por campo. */
function validatePassword(data: PasswordData): PasswordFieldErrors {
  const errors: PasswordFieldErrors = {};
  if (data.newPassword.length < MIN_PASSWORD_LENGTH) {
    errors.newPassword = `A nova senha deve ter pelo menos ${MIN_PASSWORD_LENGTH} caracteres.`;
  }
  if (data.confirmPassword !== data.newPassword) {
    errors.confirmPassword = 'As senhas não coincidem.';
  }
  return errors;
}

const Profile = () => {
  const { t } = useTranslation();
  const { user, updateUser } = useAuth();
  // Nome: PUT /auth/profile (public.users). E-mail: somente leitura (troca exige fluxo do Supabase).
  // Senha: Supabase Auth.
  const [nameValue, setNameValue] = useState(user?.name ?? '');
  const [nameFieldError, setNameFieldError] = useState('');
  const [nameError, setNameError] = useState('');
  const [nameSuccess, setNameSuccess] = useState('');
  const [nameSaving, setNameSaving] = useState(false);
  const nameLock = useRef(false);

  useEffect(() => {
    setNameValue(user?.name ?? '');
  }, [user?.name]);

  const handleNameChange = (e: ChangeEvent<HTMLInputElement>) => {
    setNameValue(e.target.value);
    setNameFieldError('');
    setNameError('');
    setNameSuccess('');
  };

  const handleNameSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (nameLock.current) return;
    setNameError('');
    setNameSuccess('');

    const validation = validateName(nameValue);
    setNameFieldError(validation);
    if (validation) {
      document.getElementById('profile-name')?.focus();
      return;
    }

    nameLock.current = true;
    setNameSaving(true);
    try {
      const response = await authAPI.updateProfile({ name: nameValue.trim() });
      const updated = response?.data;
      if (!updated || typeof updated.name !== 'string' || !updated.id) {
        setNameError(NAME_SAVE_ERROR);
        return;
      }
      updateUser(updated);
      setNameValue(updated.name);
      setNameSuccess(NAME_SAVE_SUCCESS);
    } catch {
      setNameError(NAME_SAVE_ERROR);
    } finally {
      nameLock.current = false;
      setNameSaving(false);
    }
  };

  const nameUnchanged = nameValue.trim() === (user?.name ?? '');

  const [passwordLoading, setPasswordLoading] = useState(false);
  const passwordLock = useRef(false);
  const [passwordError, setPasswordError] = useState('');
  const [passwordSuccess, setPasswordSuccess] = useState('');
  const [fieldErrors, setFieldErrors] = useState<PasswordFieldErrors>({});

  const [passwordData, setPasswordData] = useState<PasswordData>({
    currentPassword: '',
    newPassword: '',
    confirmPassword: ''
  });

  // Conferência em tempo real: só avalia depois que a confirmação começa a ser digitada.
  const confirmStatus: 'empty' | 'mismatch' | 'match' = !passwordData.confirmPassword
    ? 'empty'
    : passwordData.confirmPassword === passwordData.newPassword ? 'match' : 'mismatch';
  const confirmError = fieldErrors.confirmPassword || (confirmStatus === 'mismatch' ? 'As senhas não coincidem.' : '');

  const handlePasswordChange = (e: ChangeEvent<HTMLInputElement>) => {
    const name = e.target.name as keyof PasswordData;
    setPasswordData(prev => ({ ...prev, [name]: e.target.value }));
    setFieldErrors(prev => (prev[name as keyof PasswordFieldErrors] ? { ...prev, [name]: undefined } : prev));
    setPasswordError('');
    setPasswordSuccess('');
  };

  const handlePasswordSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (passwordLock.current) return;
    setPasswordError('');
    setPasswordSuccess('');

    const errors = validatePassword(passwordData);
    setFieldErrors(errors);
    if (errors.newPassword || errors.confirmPassword) {
      const firstInvalid = errors.newPassword ? 'profile-new-password' : 'profile-confirm-password';
      document.getElementById(firstInvalid)?.focus();
      return;
    }

    if (!user?.email) {
      setPasswordError('Sessão inválida. Faça login novamente.');
      return;
    }

    passwordLock.current = true;
    setPasswordLoading(true);
    try {
      const { error: signInErr } = await supabase.auth.signInWithPassword({
        email: user.email,
        password: passwordData.currentPassword,
      });
      if (signInErr) {
        setPasswordError('Senha atual incorreta.');
        return;
      }

      const { error: updateErr } = await supabase.auth.updateUser({
        password: passwordData.newPassword,
      });
      if (updateErr) {
        setPasswordError(updateErr.message || 'Não foi possível alterar a senha.');
        return;
      }

      await supabase.auth.refreshSession();

      setPasswordSuccess('Senha alterada com sucesso!');
      setPasswordData({
        currentPassword: '',
        newPassword: '',
        confirmPassword: '',
      });
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Erro ao alterar senha.';
      setPasswordError(msg);
    } finally {
      passwordLock.current = false;
      setPasswordLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">{t('navigation.profile')}</h1>
          <p className="text-sm text-slate-600 dark:text-slate-300 mt-1">Gerencie suas informações pessoais e segurança</p>
        </div>
      </div>

      {passwordError && (
        <div role="alert" className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 flex items-center gap-2">
          <i className="bi bi-exclamation-triangle-fill text-red-600 dark:text-red-400"></i>
          <span className="text-red-800 dark:text-red-200">{passwordError}</span>
        </div>
      )}

      {passwordSuccess && (
        <div role="status" className="bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-800 rounded-lg p-4 flex items-center gap-2">
          <i className="bi bi-check-circle-fill text-emerald-600 dark:text-emerald-400"></i>
          <span className="text-emerald-800 dark:text-emerald-200">{passwordSuccess}</span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Content */}
        <div className="lg:col-span-2 space-y-6">
          {/* Personal Information */}
          <div className="card-base overflow-hidden">
            <div className="card-header px-6 py-4">
              <div className="flex items-center gap-2">
                <i className="bi bi-person-circle text-slate-600 dark:text-slate-300"></i>
                <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Informações Pessoais</h2>
              </div>
            </div>
            <div className="p-6">
              <form onSubmit={handleNameSubmit} noValidate aria-busy={nameSaving}>
                {nameError && (
                  <div role="alert" className="mb-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-3 flex items-center gap-2">
                    <i className="bi bi-exclamation-triangle-fill text-red-600 dark:text-red-400" aria-hidden="true"></i>
                    <span className="text-sm text-red-800 dark:text-red-200">{nameError}</span>
                  </div>
                )}
                {nameSuccess && (
                  <div role="status" className="mb-4 bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-800 rounded-lg p-3 flex items-center gap-2">
                    <i className="bi bi-check-circle-fill text-emerald-600 dark:text-emerald-400" aria-hidden="true"></i>
                    <span className="text-sm text-emerald-800 dark:text-emerald-200">{nameSuccess}</span>
                  </div>
                )}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label htmlFor="profile-name" className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">Nome Completo</label>
                    <input
                      type="text"
                      id="profile-name"
                      name="name"
                      autoComplete="name"
                      className="input-base w-full"
                      value={nameValue}
                      onChange={handleNameChange}
                      required
                      disabled={nameSaving}
                      maxLength={NAME_MAX_LENGTH}
                      aria-invalid={Boolean(nameFieldError)}
                      aria-describedby={nameFieldError ? 'profile-name-error profile-name-hint' : 'profile-name-hint'}
                    />
                    <p id="profile-name-hint" className="text-xs text-slate-500 dark:text-slate-400 mt-1">Entre {NAME_MIN_LENGTH} e {NAME_MAX_LENGTH} caracteres.</p>
                    {nameFieldError && (
                      <p id="profile-name-error" className="profile-field-error" role="alert">{nameFieldError}</p>
                    )}
                  </div>

                  <div>
                    <label htmlFor="profile-email" className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">Email</label>
                    <input
                      type="email"
                      id="profile-email"
                      name="email"
                      autoComplete="email"
                      className="input-base profile-readonly-field w-full"
                      value={user?.email || ''}
                      readOnly
                      aria-readonly="true"
                      aria-describedby="profile-email-hint"
                    />
                    <p id="profile-email-hint" className="text-xs text-slate-500 dark:text-slate-400 mt-1">{EMAIL_READONLY_HINT}</p>
                  </div>
                </div>

                <div className="mt-6 flex justify-end">
                  <button
                    type="submit"
                    className="px-6 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium flex items-center gap-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    disabled={nameSaving || nameUnchanged}
                  >
                    {nameSaving ? (
                      <>
                        <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent" aria-hidden="true"></div>
                        Salvando...
                      </>
                    ) : (
                      <>
                        <i className="bi bi-check2" aria-hidden="true"></i>
                        Salvar nome
                      </>
                    )}
                  </button>
                </div>
              </form>
            </div>
          </div>

          {/* Change Password */}
          <div className="card-base overflow-hidden">
            <div className="card-header px-6 py-4">
              <div className="flex items-center gap-2">
                <i className="bi bi-shield-lock text-slate-600 dark:text-slate-300"></i>
                <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Alterar Senha</h2>
              </div>
            </div>
            <div className="p-6">
              <form onSubmit={handlePasswordSubmit} noValidate aria-busy={passwordLoading}>
                {/* Campo de usuário oculto: permite ao navegador e ao gerenciador de senhas
                    associar a nova senha à conta correta. */}
                <input type="text" name="username" autoComplete="username" value={user?.email ?? ''} readOnly hidden />
                <div className="space-y-4">
                  <div>
                    <label htmlFor="profile-current-password" className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">Senha Atual</label>
                    <input
                      type="password"
                      id="profile-current-password"
                      name="currentPassword"
                      autoComplete="current-password"
                      className="input-base w-full"
                      value={passwordData.currentPassword}
                      onChange={handlePasswordChange}
                      required
                      disabled={passwordLoading}
                      placeholder="Digite sua senha atual"
                    />
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label htmlFor="profile-new-password" className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">Nova Senha</label>
                      <input
                        type="password"
                        id="profile-new-password"
                        name="newPassword"
                        autoComplete="new-password"
                        className="input-base w-full"
                        value={passwordData.newPassword}
                        onChange={handlePasswordChange}
                        required
                        disabled={passwordLoading}
                        minLength={MIN_PASSWORD_LENGTH}
                        placeholder="Digite a nova senha"
                        aria-invalid={Boolean(fieldErrors.newPassword)}
                        aria-describedby={fieldErrors.newPassword ? 'profile-new-password-error profile-new-password-hint' : 'profile-new-password-hint'}
                      />
                      <p id="profile-new-password-hint" className="text-xs text-slate-500 dark:text-slate-400 mt-1">Mínimo de {MIN_PASSWORD_LENGTH} caracteres.</p>
                      {fieldErrors.newPassword && (
                        <p id="profile-new-password-error" className="profile-field-error" role="alert">{fieldErrors.newPassword}</p>
                      )}
                    </div>

                    <div>
                      <label htmlFor="profile-confirm-password" className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">Confirmar Nova Senha</label>
                      <input
                        type="password"
                        id="profile-confirm-password"
                        name="confirmPassword"
                        autoComplete="new-password"
                        className={`input-base w-full ${confirmError ? 'profile-input-invalid' : confirmStatus === 'match' ? 'profile-input-valid' : ''}`}
                        value={passwordData.confirmPassword}
                        onChange={handlePasswordChange}
                        required
                        disabled={passwordLoading}
                        minLength={MIN_PASSWORD_LENGTH}
                        placeholder="Confirme a nova senha"
                        aria-invalid={Boolean(confirmError)}
                        aria-describedby="profile-confirm-password-status"
                      />
                      <p id="profile-confirm-password-status" aria-live="polite"
                        className={confirmError ? 'profile-field-error' : confirmStatus === 'match' ? 'profile-field-ok' : 'sr-only'}>
                        {confirmError || (confirmStatus === 'match' ? 'As senhas conferem.' : '')}
                      </p>
                    </div>
                  </div>
                </div>

                <div className="mt-6 flex justify-end">
                  <button
                    type="submit"
                    className="px-6 py-2.5 bg-amber-600 hover:bg-amber-700 text-white rounded-lg font-medium flex items-center gap-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    disabled={passwordLoading}
                  >
                    {passwordLoading ? (
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
          <div className="card-base overflow-hidden">
            <div className="p-6 text-center">
              <div
                className="bg-gradient-to-br from-blue-600 to-blue-700 rounded-full inline-flex items-center justify-center mb-4"
                style={{ width: '100px', height: '100px' }}
                aria-hidden="true"
              >
                <i className="bi bi-person-fill text-white" style={{ fontSize: '3rem' }}></i>
              </div>
              <h3 className="text-lg font-bold text-slate-900 dark:text-white">{user?.name}</h3>
              <p className="text-sm text-slate-600 dark:text-slate-300">{user?.email}</p>
              {/* "Membro desde" e "Último acesso" foram removidos: a API de perfil não expõe essas datas. */}
            </div>
          </div>

          {/* Connected Accounts */}
          {user?.auth_providers && user.auth_providers.length > 0 && (
            <div className="card-base overflow-hidden">
              <div className="card-header px-6 py-4">
                <div className="flex items-center gap-2">
                  <i className="bi bi-shield-check text-slate-600 dark:text-slate-300"></i>
                  <h3 className="text-sm font-semibold text-slate-900 dark:text-white">Contas Conectadas</h3>
                </div>
              </div>
              <div className="p-6">
                <div className="space-y-3">
                  {user.auth_providers.map((provider, index) => (
                    <div key={index} className="flex items-center gap-3 p-3 bg-slate-50 dark:bg-slate-800 rounded-lg">
                      <i className={`bi bi-${provider.provider} text-slate-600 dark:text-slate-300 text-xl`}></i>
                      <div className="flex-1">
                        <div className="font-medium text-sm text-slate-900 dark:text-white capitalize">{provider.provider}</div>
                        <div className="text-xs text-slate-500 dark:text-slate-400">
                          {provider.email_verified ? (
                            <span className="text-emerald-600 dark:text-emerald-300">
                              <i className="bi bi-check-circle-fill"></i> Verificado
                            </span>
                          ) : (
                            <span className="text-amber-600 dark:text-amber-300">
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
          <div className="card-base overflow-hidden">
            <div className="card-header px-6 py-4">
              <div className="flex items-center gap-2">
                <i className="bi bi-info-circle text-slate-600 dark:text-slate-300"></i>
                <h3 className="text-sm font-semibold text-slate-900 dark:text-white">Dicas de Segurança</h3>
              </div>
            </div>
            <div className="p-6">
              <ul className="space-y-3">
                <li className="flex items-start gap-2 text-sm text-slate-600 dark:text-slate-300">
                  <i className="bi bi-check-circle-fill text-emerald-500 mt-0.5 flex-shrink-0"></i>
                  <span>Use senhas fortes e únicas</span>
                </li>
                <li className="flex items-start gap-2 text-sm text-slate-600 dark:text-slate-300">
                  <i className="bi bi-check-circle-fill text-emerald-500 mt-0.5 flex-shrink-0"></i>
                  <span>Altere sua senha regularmente</span>
                </li>
                <li className="flex items-start gap-2 text-sm text-slate-600 dark:text-slate-300">
                  <i className="bi bi-check-circle-fill text-emerald-500 mt-0.5 flex-shrink-0"></i>
                  <span>Não compartilhe suas credenciais</span>
                </li>
                <li className="flex items-start gap-2 text-sm text-slate-600 dark:text-slate-300">
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
