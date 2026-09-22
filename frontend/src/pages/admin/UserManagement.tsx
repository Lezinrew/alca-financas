import React, { useCallback, useEffect, useState } from 'react';
import toast from 'react-hot-toast';
import { adminAPI } from '../../utils/api';
import { useAuth } from '../../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import { ConfirmDialog } from '../../components/shared/ConfirmDialog';
import { PurgeUserDialog } from './PurgeUserDialog';

interface AdminUserRow {
  id: string;
  name: string;
  email: string;
  role: string;
  status: string;
  is_admin?: boolean;
  created_at?: string | null;
  last_login_at?: string | null;
  last_activity_at?: string | null;
  inactive_warning_sent_at?: string | null;
  scheduled_deletion_at?: string | null;
  auth_providers?: { provider?: string }[];
}

const ADMIN_CARD = 'admin-card-shell';
const ADMIN_TABLE_SHELL = `${ADMIN_CARD} overflow-hidden`;
/** Alvo mínimo de toque de 44px. */
const ACTION_BTN = 'min-h-[44px] min-w-[44px] rounded-lg px-2 py-1 text-xs font-medium';

interface PendingAction {
  user: AdminUserRow;
  title: string;
  consequence: string;
  confirmLabel: string;
  danger?: boolean;
  run: () => Promise<void>;
}

const statusLabel: Record<string, string> = {
  active: 'Ativo',
  inactive: 'Inativo',
  pending_deletion: 'Pendente exclusão',
  disabled: 'Desativado',
};

function formatDt(v?: string | null) {
  if (!v) return '—';
  try {
    return new Date(v).toLocaleString('pt-BR');
  } catch {
    return v;
  }
}

const UserManagement: React.FC = () => {
  const [users, setUsers] = useState<AdminUserRow[]>([]);
  const [stats, setStats] = useState<{
    total_users: number;
    active: number;
    inactive: number;
    pending_deletion: number;
    disabled: number;
    admins: number;
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [search, setSearch] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [adminsOnly, setAdminsOnly] = useState(false);
  const [purgeTarget, setPurgeTarget] = useState<AdminUserRow | null>(null);
  const [pending, setPending] = useState<PendingAction | null>(null);
  const { user: currentUser } = useAuth();
  const navigate = useNavigate();

  const isAdmin = currentUser?.role === 'admin' || currentUser?.is_admin;

  const fetchStats = useCallback(async () => {
    try {
      const res = await adminAPI.getUserStats();
      setStats(res.data);
    } catch {
      /* opcional */
    }
  }, []);

  const fetchUsers = useCallback(async () => {
    setLoading(true);
    try {
      const response = await adminAPI.getUsers(page, 15, search, statusFilter, adminsOnly);
      setUsers(response.data.users);
      setTotalPages(Math.max(1, response.data.pages ?? 1));
    } catch (e: unknown) {
      console.error(e);
      toast.error('Não foi possível carregar os usuários.');
    } finally {
      setLoading(false);
    }
  }, [page, search, statusFilter, adminsOnly]);

  useEffect(() => {
    if (currentUser && !isAdmin) {
      navigate('/dashboard', { replace: true });
      return;
    }
    void fetchStats();
    void fetchUsers();
  }, [currentUser, isAdmin, navigate, fetchUsers, fetchStats]);

  const applySearch = () => {
    setPage(1);
    setSearch(searchInput.trim());
  };

  const refresh = async () => {
    await fetchUsers();
    await fetchStats();
  };

  // Mudanças de estado/papel abrem um ConfirmDialog; a API só é chamada após confirmar.
  const patchStatus = (u: AdminUserRow, status: 'inactive' | 'pending_deletion') => {
    setPending({
      user: u,
      title: status === 'inactive' ? 'Marcar como inativo' : 'Marcar para exclusão',
      consequence: status === 'inactive'
        ? 'A conta passa ao estado "Inativo". O usuário continua podendo entrar, mas fica elegível para avisos de inatividade.'
        : 'A conta passa ao estado "Pendente exclusão" e entra na fila de remoção automática. Pode ser reativada antes disso.',
      confirmLabel: status === 'inactive' ? 'Marcar inativo' : 'Marcar para exclusão',
      danger: status === 'pending_deletion',
      run: async () => {
        await adminAPI.patchUserStatus(u.id, status);
        toast.success('Estado atualizado.');
        await refresh();
      },
    });
  };

  const patchRole = (u: AdminUserRow, role: 'admin' | 'user') => {
    setPending({
      user: u,
      title: role === 'admin' ? 'Promover a administrador' : 'Remover privilégios de administrador',
      consequence: role === 'admin'
        ? 'O usuário passa a ter acesso total ao painel administrativo, incluindo dados de outros usuários.'
        : 'O usuário perde o acesso ao painel administrativo e passa a ter permissões comuns.',
      confirmLabel: role === 'admin' ? 'Promover' : 'Remover admin',
      danger: role === 'user',
      run: async () => {
        await adminAPI.patchUserRole(u.id, role);
        toast.success('Papel atualizado.');
        await refresh();
      },
    });
  };

  const sendWarning = async (id: string) => {
    try {
      const res = await adminAPI.sendInactiveWarning(id);
      if (res.data?.skipped) toast('Este usuário já tinha recebido o aviso.');
      else toast.success('Aviso de inatividade registrado.');
      await fetchUsers();
    } catch {
      toast.error('Não foi possível enviar o aviso. Tente novamente.');
    }
  };

  const deactivate = (u: AdminUserRow) => {
    setPending({
      user: u,
      title: 'Desativar conta',
      consequence: 'O usuário deixa de ter acesso. Os dados ficam guardados e a conta pode ser reativada depois.',
      confirmLabel: 'Desativar',
      danger: true,
      run: async () => {
        await adminAPI.deleteUser(u.id);
        toast.success('Conta desativada.');
        await refresh();
      },
    });
  };

  const submitPurge = async (confirmEmail: string) => {
    if (!purgeTarget) return;
    await adminAPI.purgeUser(purgeTarget.id, { confirm_email: confirmEmail });
    toast.success('Conta e dados apagados permanentemente.');
    setPurgeTarget(null);
    await refresh();
  };

  const reactivate = (u: AdminUserRow) => {
    setPending({
      user: u,
      title: 'Reativar conta',
      consequence: 'A conta volta ao estado "Ativo": o usuário recupera o acesso e sai da fila de exclusão.',
      confirmLabel: 'Reativar',
      run: async () => {
        await adminAPI.reactivateUser(u.id);
        toast.success('Conta reativada.');
        await refresh();
      },
    });
  };

  const actionButtons = (u: AdminUserRow) => (
    <div className="flex flex-wrap justify-end gap-1">
      <button type="button" onClick={() => navigate(`/admin/users/${u.id}`)} className={`${ACTION_BTN} text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/20`}>
        Detalhe
      </button>
      {u.role !== 'admin' ? (
        <button type="button" onClick={() => patchRole(u, 'admin')} className={`${ACTION_BTN} text-purple-600 hover:bg-purple-50 dark:hover:bg-purple-900/20`}>
          Admin
        </button>
      ) : (
        <button type="button" onClick={() => patchRole(u, 'user')} className={`${ACTION_BTN} text-slate-600 hover:bg-slate-100 dark:hover:bg-slate-800`}>
          Remover admin
        </button>
      )}
      <button type="button" onClick={() => patchStatus(u, 'inactive')} className={`${ACTION_BTN} text-amber-700 hover:bg-amber-50 dark:text-amber-400 dark:hover:bg-amber-900/20`}>
        Inativo
      </button>
      <button type="button" onClick={() => patchStatus(u, 'pending_deletion')} className={`${ACTION_BTN} text-orange-700 hover:bg-orange-50 dark:text-orange-300 dark:hover:bg-orange-900/20`}>
        Pend. exclusão
      </button>
      <button type="button" onClick={() => reactivate(u)} className={`${ACTION_BTN} text-green-700 hover:bg-green-50 dark:text-green-300 dark:hover:bg-green-900/20`}>
        Reativar
      </button>
      <button type="button" onClick={() => sendWarning(u.id)} className={`${ACTION_BTN} text-cyan-700 hover:bg-cyan-50 dark:text-cyan-300 dark:hover:bg-cyan-900/20`}>
        Aviso
      </button>
      <button type="button" onClick={() => deactivate(u)} className={`${ACTION_BTN} text-red-600 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-900/20`}>
        Desativar
      </button>
      {currentUser?.id !== u.id && (
        <button
          type="button"
          onClick={() => setPurgeTarget(u)}
          className={`${ACTION_BTN} border border-red-200/80 bg-red-50/80 font-semibold text-red-700 hover:bg-red-100 dark:border-red-900/50 dark:bg-red-950/40 dark:text-red-300 dark:hover:bg-red-950/70`}
        >
          Excluir total
        </button>
      )}
    </div>
  );

  const authProvider = (u: AdminUserRow) => {
    const p = u.auth_providers?.[0];
    return (p?.provider as string) || 'email';
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Administração — Usuários</h1>
        <button
          type="button"
          onClick={() => {
            void fetchUsers();
            void fetchStats();
          }}
          className="admin-outline-btn min-h-[44px] rounded-xl text-slate-600 hover:bg-slate-50 dark:text-dark-text-secondary"
        >
          Atualizar
        </button>
      </div>

      {stats && (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
          {[
            { k: 'Total', v: stats.total_users },
            { k: 'Ativos', v: stats.active },
            { k: 'Inativos', v: stats.inactive },
            { k: 'Pend. exclusão', v: stats.pending_deletion },
            { k: 'Desativados', v: stats.disabled },
            { k: 'Admins', v: stats.admins },
          ].map((c) => (
            <div key={c.k} className={`${ADMIN_CARD} p-4`}>
              <p className="text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-dark-text-muted">
                {c.k}
              </p>
              <p className="mt-1 text-2xl font-bold text-slate-900 dark:text-white">{c.v}</p>
            </div>
          ))}
        </div>
      )}

      <div className="flex flex-col gap-3 lg:flex-row lg:flex-wrap lg:items-center">
        <div className="relative w-full max-w-md flex-1">
          <label htmlFor="admin-user-search" className="sr-only">Buscar por nome ou e-mail</label>
          <input
            id="admin-user-search"
            name="admin-user-search"
            type="text"
            placeholder="Nome ou e-mail…"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && applySearch()}
            className="native-input-themed min-h-[44px] w-full rounded-xl py-2 pl-10 pr-24 outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20"
          />
          <svg
            className="absolute left-3 top-3 h-5 w-5 text-slate-400"
            aria-hidden="true"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <button
            type="button"
            onClick={applySearch}
            className="absolute right-1 top-1 min-h-[36px] rounded-lg bg-primary px-3 text-xs font-medium text-white"
          >
            Buscar
          </button>
        </div>

        <div className="flex flex-wrap gap-2">
          {(['all', 'active', 'inactive', 'pending_deletion', 'disabled'] as const).map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => {
                setPage(1);
                setStatusFilter(s);
                setAdminsOnly(false);
              }}
              className={`rounded-full px-3 py-1 text-xs font-semibold transition ${
                statusFilter === s && !adminsOnly
                  ? 'bg-primary text-white'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700'
              }`}
            >
              {s === 'all' ? 'Todos' : statusLabel[s] || s}
            </button>
          ))}
          <button
            type="button"
            onClick={() => {
              setPage(1);
              setAdminsOnly(true);
              setStatusFilter('all');
            }}
            className={`rounded-full px-3 py-1 text-xs font-semibold transition ${
              adminsOnly ? 'bg-purple-600 text-white' : 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300'
            }`}
          >
            Admins
          </button>
        </div>
      </div>

      <div className={ADMIN_TABLE_SHELL}>
        {/* Abaixo de 1024px: cartões, sem rolagem horizontal. */}
        <div className="divide-y divide-slate-100 lg:hidden dark:divide-dark-border">
          {loading ? (
            <p className="px-4 py-10 text-center text-slate-500 dark:text-dark-text-muted">Carregando…</p>
          ) : users.length === 0 ? (
            <p className="px-4 py-10 text-center text-slate-500 dark:text-dark-text-muted">Nenhum usuário encontrado.</p>
          ) : (
            users.map((u) => (
              <div key={u.id} className="space-y-3 p-4">
                <div>
                  <div className="font-medium text-slate-900 dark:text-white">{u.name}</div>
                  <div className="text-xs text-slate-600 dark:text-dark-text-secondary">{u.email}</div>
                </div>
                <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
                  <dt className="text-slate-500 dark:text-dark-text-muted">Papel</dt>
                  <dd className="text-slate-700 dark:text-dark-text-secondary">{u.role === 'admin' ? 'Administrador' : 'Usuário'}</dd>
                  <dt className="text-slate-500 dark:text-dark-text-muted">Estado</dt>
                  <dd className="text-slate-700 dark:text-dark-text-secondary">{statusLabel[u.status] || u.status}</dd>
                  <dt className="text-slate-500 dark:text-dark-text-muted">Criado</dt>
                  <dd className="text-slate-700 dark:text-dark-text-secondary">{formatDt(u.created_at)}</dd>
                  <dt className="text-slate-500 dark:text-dark-text-muted">Último acesso</dt>
                  <dd className="text-slate-700 dark:text-dark-text-secondary">{formatDt(u.last_login_at)}</dd>
                  <dt className="text-slate-500 dark:text-dark-text-muted">Última atividade</dt>
                  <dd className="text-slate-700 dark:text-dark-text-secondary">{formatDt(u.last_activity_at)}</dd>
                  <dt className="text-slate-500 dark:text-dark-text-muted">Aviso de inatividade</dt>
                  <dd className="text-slate-700 dark:text-dark-text-secondary">{formatDt(u.inactive_warning_sent_at)}</dd>
                  <dt className="text-slate-500 dark:text-dark-text-muted">Exclusão agendada</dt>
                  <dd className="text-slate-700 dark:text-dark-text-secondary">{formatDt(u.scheduled_deletion_at)}</dd>
                </dl>
                {actionButtons(u)}
              </div>
            ))
          )}
        </div>

        <div className="hidden overflow-x-auto lg:block">
          <table className="w-full min-w-[960px] text-left text-sm">
            <thead className="table-header">
              <tr className="text-xs font-semibold uppercase tracking-wide text-slate-600 dark:text-dark-text-muted">
                <th className="px-4 py-3">Usuário</th>
                <th className="px-4 py-3">Papel</th>
                <th className="px-4 py-3">Estado</th>
                <th className="px-4 py-3">Criado</th>
                <th className="px-4 py-3">Último acesso</th>
                <th className="px-4 py-3">Última atividade</th>
                <th className="px-4 py-3">Aviso de inatividade</th>
                <th className="px-4 py-3">Exclusão agendada</th>
                <th className="px-4 py-3 text-right">Ações</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-dark-border">
              {loading ? (
                <tr>
                  <td colSpan={9} className="px-4 py-10 text-center text-slate-500 dark:text-dark-text-muted">
                    Carregando…
                  </td>
                </tr>
              ) : users.length === 0 ? (
                <tr>
                  <td colSpan={9} className="px-4 py-10 text-center text-slate-500 dark:text-dark-text-muted">
                    Nenhum usuário encontrado.
                  </td>
                </tr>
              ) : (
                users.map((u) => (
                  <tr key={u.id} className="table-row">
                    <td className="px-4 py-3">
                      <div className="font-medium text-slate-900 dark:text-white">{u.name}</div>
                      <div className="text-xs text-slate-600 dark:text-dark-text-secondary">{u.email}</div>
                      <div className="mt-0.5 text-[10px] uppercase text-slate-500 dark:text-dark-text-muted">
                        {authProvider(u)}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex rounded-full px-2 py-0.5 text-xs font-semibold ${
                          u.role === 'admin'
                            ? 'bg-purple-100 text-purple-800 dark:bg-purple-900/40 dark:text-purple-300'
                            : 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300'
                        }`}
                      >
                        {u.role === 'admin' ? 'Administrador' : 'Usuário'}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-xs font-medium text-slate-700 dark:text-dark-text-secondary">
                        {statusLabel[u.status] || u.status}
                      </span>
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-xs text-slate-600 dark:text-dark-text-secondary">
                      {formatDt(u.created_at)}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-xs text-slate-600 dark:text-dark-text-secondary">
                      {formatDt(u.last_login_at)}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-xs text-slate-600 dark:text-dark-text-secondary">
                      {formatDt(u.last_activity_at)}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-xs text-slate-600 dark:text-dark-text-secondary">
                      {formatDt(u.inactive_warning_sent_at)}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-xs text-slate-600 dark:text-dark-text-secondary">
                      {formatDt(u.scheduled_deletion_at)}
                    </td>
                    <td className="px-4 py-3 text-right">{actionButtons(u)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <div className="flex items-center justify-between border-t border-slate-100 px-4 py-3 dark:border-dark-border">
          <button
            type="button"
            disabled={page <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            className="admin-outline-btn min-h-[44px] rounded-lg px-3 py-1.5 font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-40 dark:text-slate-300"
          >
            Anterior
          </button>
          <span className="text-xs text-slate-500 dark:text-dark-text-muted">
            Página {page} / {totalPages}
          </span>
          <button
            type="button"
            disabled={page >= totalPages}
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            className="admin-outline-btn min-h-[44px] rounded-lg px-3 py-1.5 font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-40 dark:text-slate-300"
          >
            Seguinte
          </button>
        </div>
      </div>

      {purgeTarget && (
        <PurgeUserDialog
          name={purgeTarget.name}
          email={purgeTarget.email}
          onConfirm={submitPurge}
          onClose={() => setPurgeTarget(null)}
        />
      )}

      {pending && (
        <ConfirmDialog
          title={pending.title}
          subject={`${pending.user.name} (${pending.user.email})`}
          consequence={<p>{pending.consequence}</p>}
          confirmLabel={pending.confirmLabel}
          danger={pending.danger}
          onConfirm={async () => { await pending.run(); setPending(null); }}
          onClose={() => setPending(null)}
        />
      )}
    </div>
  );
};

export default UserManagement;
