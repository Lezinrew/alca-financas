import React, { useCallback, useEffect, useState } from 'react';
import toast from 'react-hot-toast';
import { adminAPI } from '../../utils/api';
import { useAuth } from '../../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';

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
  const [purgeEmail, setPurgeEmail] = useState('');
  const [purging, setPurging] = useState(false);
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
      toast.error('Não foi possível carregar utilizadores.');
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

  const patchStatus = async (id: string, status: string) => {
    try {
      await adminAPI.patchUserStatus(id, status);
      toast.success('Estado atualizado.');
      await fetchUsers();
      await fetchStats();
    } catch {
      toast.error('Falha ao atualizar estado.');
    }
  };

  const patchRole = async (id: string, role: 'admin' | 'user') => {
    if (!window.confirm(role === 'admin' ? 'Promover a administrador?' : 'Remover privilégios de administrador?')) return;
    try {
      await adminAPI.patchUserRole(id, role);
      toast.success('Papel atualizado.');
      await fetchUsers();
      await fetchStats();
    } catch {
      toast.error('Falha ao atualizar papel.');
    }
  };

  const sendWarning = async (id: string) => {
    try {
      const res = await adminAPI.sendInactiveWarning(id);
      if (res.data?.skipped) toast('Aviso já tinha sido registado para este utilizador.');
      else toast.success('Aviso enviado (ou registado em log se SMTP não configurado).');
      await fetchUsers();
    } catch {
      toast.error('Falha ao enviar aviso.');
    }
  };

  const deactivate = async (id: string) => {
    if (!window.confirm('Desativar esta conta? O utilizador deixará de aceder (remoção lógica).')) return;
    try {
      await adminAPI.deleteUser(id);
      toast.success('Conta desativada.');
      await fetchUsers();
      await fetchStats();
    } catch {
      toast.error('Não foi possível desativar.');
    }
  };

  const openPurge = (u: AdminUserRow) => {
    setPurgeTarget(u);
    setPurgeEmail('');
  };

  const closePurge = () => {
    setPurgeTarget(null);
    setPurgeEmail('');
  };

  const submitPurge = async () => {
    if (!purgeTarget) return;
    setPurging(true);
    try {
      await adminAPI.purgeUser(purgeTarget.id, { confirm_email: purgeEmail.trim() });
      toast.success('Conta e dados apagados permanentemente.');
      closePurge();
      await fetchUsers();
      await fetchStats();
    } catch (e: unknown) {
      const msg =
        (e as { response?: { data?: { error?: string; detail?: string } } })?.response?.data?.error ||
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(msg ? String(msg) : 'Falha na exclusão total.');
    } finally {
      setPurging(false);
    }
  };

  const reactivate = async (id: string) => {
    try {
      await adminAPI.reactivateUser(id);
      toast.success('Conta reativada.');
      await fetchUsers();
      await fetchStats();
    } catch {
      toast.error('Falha ao reativar.');
    }
  };

  const authProvider = (u: AdminUserRow) => {
    const p = u.auth_providers?.[0];
    return (p?.provider as string) || 'email';
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Administração — Utilizadores</h1>
        <button
          type="button"
          onClick={() => {
            void fetchUsers();
            void fetchStats();
          }}
          className="admin-outline-btn rounded-xl text-slate-600 hover:bg-slate-50 dark:text-dark-text-secondary"
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
          <input
            id="admin-user-search"
            name="admin-user-search"
            type="text"
            placeholder="Nome ou e-mail…"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && applySearch()}
            className="native-input-themed w-full rounded-xl py-2 pl-10 pr-24 outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20"
          />
          <svg
            className="absolute left-3 top-2.5 h-5 w-5 text-slate-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <button
            type="button"
            onClick={applySearch}
            className="absolute right-2 top-1.5 rounded-lg bg-primary px-3 py-1 text-xs font-medium text-white"
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
        <div className="overflow-x-auto">
          <table className="w-full min-w-[960px] text-left text-sm">
            <thead className="table-header">
              <tr className="text-xs font-semibold uppercase tracking-wide text-slate-600 dark:text-dark-text-muted">
                <th className="px-4 py-3">Utilizador</th>
                <th className="px-4 py-3">Papel</th>
                <th className="px-4 py-3">Estado</th>
                <th className="px-4 py-3">Criado</th>
                <th className="px-4 py-3">Último login</th>
                <th className="px-4 py-3">Última atividade</th>
                <th className="px-4 py-3">Aviso inat.</th>
                <th className="px-4 py-3">Exclusão agend.</th>
                <th className="px-4 py-3 text-right">Ações</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-dark-border">
              {loading ? (
                <tr>
                  <td colSpan={9} className="px-4 py-10 text-center text-slate-500 dark:text-dark-text-muted">
                    A carregar…
                  </td>
                </tr>
              ) : users.length === 0 ? (
                <tr>
                  <td colSpan={9} className="px-4 py-10 text-center text-slate-500 dark:text-dark-text-muted">
                    Nenhum utilizador encontrado.
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
                        {u.role === 'admin' ? 'admin' : 'user'}
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
                    <td className="px-4 py-3 text-right">
                      <div className="flex flex-wrap justify-end gap-1">
                        <button
                          type="button"
                          onClick={() => navigate(`/admin/users/${u.id}`)}
                          className="rounded-lg px-2 py-1 text-xs font-medium text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/20"
                        >
                          Detalhe
                        </button>
                        {u.role !== 'admin' ? (
                          <button
                            type="button"
                            onClick={() => patchRole(u.id, 'admin')}
                            className="rounded-lg px-2 py-1 text-xs font-medium text-purple-600 hover:bg-purple-50 dark:hover:bg-purple-900/20"
                          >
                            Admin
                          </button>
                        ) : (
                          <button
                            type="button"
                            onClick={() => patchRole(u.id, 'user')}
                            className="rounded-lg px-2 py-1 text-xs font-medium text-slate-600 hover:bg-slate-100 dark:hover:bg-slate-800"
                          >
                            Remover admin
                          </button>
                        )}
                        <button
                          type="button"
                          onClick={() => patchStatus(u.id, 'inactive')}
                          className="rounded-lg px-2 py-1 text-xs text-amber-700 hover:bg-amber-50 dark:text-amber-400 dark:hover:bg-amber-900/20"
                        >
                          Inativo
                        </button>
                        <button
                          type="button"
                          onClick={() => patchStatus(u.id, 'pending_deletion')}
                          className="rounded-lg px-2 py-1 text-xs text-orange-700 hover:bg-orange-50 dark:text-orange-300 dark:hover:bg-orange-900/20"
                        >
                          Pend. exclusão
                        </button>
                        <button
                          type="button"
                          onClick={() => reactivate(u.id)}
                          className="rounded-lg px-2 py-1 text-xs text-green-700 hover:bg-green-50 dark:text-green-300 dark:hover:bg-green-900/20"
                        >
                          Reativar
                        </button>
                        <button
                          type="button"
                          onClick={() => sendWarning(u.id)}
                          className="rounded-lg px-2 py-1 text-xs text-cyan-700 hover:bg-cyan-50 dark:text-cyan-300 dark:hover:bg-cyan-900/20"
                        >
                          Aviso
                        </button>
                        <button
                          type="button"
                          onClick={() => deactivate(u.id)}
                          className="rounded-lg px-2 py-1 text-xs text-red-600 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-900/20"
                        >
                          Desativar
                        </button>
                        {currentUser?.id !== u.id && (
                          <button
                            type="button"
                            onClick={() => openPurge(u)}
                            className="rounded-lg border border-red-200/80 bg-red-50/80 px-2 py-1 text-xs font-semibold text-red-700 hover:bg-red-100 dark:border-red-900/50 dark:bg-red-950/40 dark:text-red-300 dark:hover:bg-red-950/70"
                          >
                            Excluir total
                          </button>
                        )}
                      </div>
                    </td>
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
            className="admin-outline-btn rounded-lg px-3 py-1.5 font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-40 dark:text-slate-300"
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
            className="admin-outline-btn rounded-lg px-3 py-1.5 font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-40 dark:text-slate-300"
          >
            Seguinte
          </button>
        </div>
      </div>

      {purgeTarget && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="purge-dialog-title"
        >
          <div className="admin-modal-panel">
            <h2 id="purge-dialog-title" className="text-lg font-bold text-slate-900 dark:text-white">
              Exclusão total da conta
            </h2>
            <p className="mt-2 text-sm text-slate-600 dark:text-dark-text-secondary">
              Isto remove o utilizador do Auth, apaga o perfil em <span className="font-mono">public.users</span> e todos
              os dados em cascata. Não pode ser desfeito.
            </p>
            <p className="mt-2 text-sm font-medium text-slate-900 dark:text-white">
              Alvo: {purgeTarget.name}{' '}
              <span className="font-normal text-slate-500 dark:text-dark-text-muted">({purgeTarget.email})</span>
            </p>
            <label htmlFor="purge-confirm-email" className="mt-4 block text-sm font-medium text-slate-700 dark:text-dark-text-secondary">
              Escreva o e-mail do utilizador para confirmar
            </label>
            <input
              id="purge-confirm-email"
              name="purge-confirm-email"
              type="email"
              autoComplete="off"
              value={purgeEmail}
              onChange={(e) => setPurgeEmail(e.target.value)}
              className="native-input-themed mt-1 w-full rounded-xl px-3 py-2 outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
              placeholder={purgeTarget.email}
            />
            <div className="mt-6 flex justify-end gap-2">
              <button
                type="button"
                onClick={closePurge}
                disabled={purging}
                className="admin-outline-btn rounded-xl font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50 dark:text-dark-text-secondary"
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={() => void submitPurge()}
                disabled={purging}
                className="rounded-xl bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-700 disabled:opacity-50"
              >
                {purging ? 'A apagar…' : 'Apagar permanentemente'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default UserManagement;
