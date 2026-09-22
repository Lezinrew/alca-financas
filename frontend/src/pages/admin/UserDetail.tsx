import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import { adminAPI } from '../../utils/api';
import { useAuth } from '../../contexts/AuthContext';
import { ArrowLeft, Mail, Calendar, Shield, Ban, Trash2, Download, Skull } from 'lucide-react';
import { ConfirmDialog } from '../../components/shared/ConfirmDialog';
import { PurgeUserDialog } from './PurgeUserDialog';

const ADMIN_CARD = 'admin-card-shell p-6';

interface PendingAction {
    title: string;
    consequence: string;
    confirmLabel: string;
    danger?: boolean;
    run: () => Promise<void>;
}

interface UserDetails {
    user: {
        id: string;
        name: string;
        email: string;
        role?: string;
        status?: string;
        is_admin: boolean;
        is_blocked: boolean;
        created_at: string;
        auth_provider: string;
        last_login_at?: string | null;
        last_activity_at?: string | null;
        inactive_warning_sent_at?: string | null;
        scheduled_deletion_at?: string | null;
    };
    stats: {
        transactions: number;
        categories: number;
        accounts: number;
        total_income: number;
        total_expense: number;
        balance: number;
    };
    recent_transactions: Array<{
        id: string;
        description: string;
        amount: number;
        type: string;
        date: string;
        category_id: string;
    }>;
    accounts: Array<{
        id: string;
        name: string;
        balance: number;
        type: string;
    }>;
}

const UserDetail: React.FC = () => {
    const { userId } = useParams<{ userId: string }>();
    const navigate = useNavigate();
    const { user: currentUser } = useAuth();
    const [userDetails, setUserDetails] = useState<UserDetails | null>(null);
    const [loading, setLoading] = useState(true);
    const [purgeOpen, setPurgeOpen] = useState(false);
    const [pending, setPending] = useState<PendingAction | null>(null);

    useEffect(() => {
        if (!userId) return;

        const fetchUserDetails = async () => {
            try {
                const response = await adminAPI.getUserDetails(userId);
                setUserDetails(response.data);
            } catch (error) {
                console.error('Erro ao carregar detalhes do usuário:', error);
                toast.error('Não foi possível carregar os detalhes do usuário.');
            } finally {
                setLoading(false);
            }
        };

        fetchUserDetails();
    }, [userId]);

    const reload = async () => {
        if (!userId) return;
        const response = await adminAPI.getUserDetails(userId);
        setUserDetails(response.data);
    };

    // Cada ação abre um ConfirmDialog; a API só é chamada após confirmar.
    const handleBlockUser = () => {
        if (!userDetails || !userId) return;
        const blocked = userDetails.user.is_blocked;
        setPending(blocked ? {
            title: 'Desbloquear usuário',
            consequence: 'A conta volta ao estado ativo e o usuário poderá entrar novamente.',
            confirmLabel: 'Desbloquear',
            run: async () => { await adminAPI.reactivateUser(userId); await reload(); toast.success('Conta reativada.'); },
        } : {
            title: 'Bloquear usuário',
            consequence: 'A conta passa a "desativada" e o usuário deixa de conseguir entrar até ser reativado.',
            confirmLabel: 'Bloquear',
            danger: true,
            run: async () => { await adminAPI.patchUserStatus(userId, 'disabled'); await reload(); toast.success('Conta bloqueada.'); },
        });
    };

    const handleDeleteUser = () => {
        if (!userId) return;
        setPending({
            title: 'Desativar conta',
            consequence: 'O usuário deixa de ter acesso. Os dados ficam guardados e a conta pode ser reativada depois.',
            confirmLabel: 'Desativar',
            danger: true,
            run: async () => { await adminAPI.deleteUser(userId); toast.success('Conta desativada.'); navigate('/admin/users'); },
        });
    };

    const submitPurge = async (confirmEmail: string) => {
        if (!userId) return;
        await adminAPI.purgeUser(userId, { confirm_email: confirmEmail });
        toast.success('Conta e dados apagados permanentemente.');
        setPurgeOpen(false);
        navigate('/admin/users');
    };

    const handlePromoteAdmin = () => {
        if (!userDetails || !userId) return;
        const isAdm = userDetails.user.role === 'admin' || userDetails.user.is_admin;
        setPending(isAdm ? {
            title: 'Remover privilégios de administrador',
            consequence: 'O usuário perde o acesso ao painel administrativo e passa a ter permissões comuns.',
            confirmLabel: 'Remover admin',
            danger: true,
            run: async () => { await adminAPI.patchUserRole(userId, 'user'); await reload(); toast.success('Privilégios removidos.'); },
        } : {
            title: 'Promover a administrador',
            consequence: 'O usuário passa a ter acesso total ao painel administrativo, incluindo dados de outros usuários.',
            confirmLabel: 'Promover',
            run: async () => { await adminAPI.patchUserRole(userId, 'admin'); await reload(); toast.success('Usuário promovido a administrador.'); },
        });
    };

    const handleExportData = async () => {
        if (!userId || !userDetails) return;

        try {
            const response = await adminAPI.exportUserData(userId);
            const blob = new Blob([response.data], { type: 'text/csv' });
            const url = window.URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.download = `dados_${userDetails.user.name.replace(/\s+/g, '_')}_${new Date().toISOString().split('T')[0]}.csv`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            window.URL.revokeObjectURL(url);
        } catch (error) {
            console.error('Erro ao exportar dados:', error);
            toast.error('Não foi possível exportar os dados. Tente novamente.');
        }
    };

    if (loading) {
        return (
            <div className="flex justify-center items-center h-64">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
            </div>
        );
    }

    if (!userDetails) {
        return (
            <div className="text-center py-12">
                <p className="text-slate-600 dark:text-slate-400">Usuário não encontrado</p>
            </div>
        );
    }

    return (
        <div className="p-6">
            {/* Header */}
            <div className="mb-6">
                <button
                    onClick={() => navigate('/admin/users')}
                    className="flex items-center text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white mb-4"
                >
                    <ArrowLeft className="w-4 h-4 mr-2" />
                    Voltar para lista de usuários
                </button>
                <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Detalhes do Usuário</h1>
            </div>

            {/* User Info Card */}
            <div className={`${ADMIN_CARD} mb-6`}>
                <div className="flex items-start justify-between mb-6">
                    <div className="flex items-center">
                        <div className="w-16 h-16 rounded-full bg-emerald-500 flex items-center justify-center text-white text-2xl font-bold mr-4">
                            {userDetails.user.name.charAt(0).toUpperCase()}
                        </div>
                        <div>
                            <h2 className="text-xl font-bold text-slate-900 dark:text-white">{userDetails.user.name}</h2>
                            <div className="mt-1 flex items-center text-sm text-slate-600 dark:text-dark-text-secondary">
                                <Mail className="w-4 h-4 mr-2" />
                                {userDetails.user.email}
                            </div>
                            <div className="flex items-center gap-2 mt-2">
                                {(userDetails.user.role === 'admin' || userDetails.user.is_admin) && (
                                    <span className="px-2 py-1 bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400 text-xs font-medium rounded">
                                        Admin
                                    </span>
                                )}
                                {userDetails.user.status && (
                                    <span className="px-2 py-1 bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 text-xs font-medium rounded">
                                        {userDetails.user.status}
                                    </span>
                                )}
                                {userDetails.user.is_blocked && (
                                    <span className="px-2 py-1 bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 text-xs font-medium rounded">
                                        Bloqueado
                                    </span>
                                )}
                                <span className="px-2 py-1 bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 text-xs font-medium rounded">
                                    {userDetails.user.auth_provider}
                                </span>
                            </div>
                        </div>
                    </div>
                    <div className="text-right text-sm text-slate-500 dark:text-dark-text-muted">
                        <div className="flex items-center">
                            <Calendar className="w-4 h-4 mr-2" />
                            Cadastrado em {new Date(userDetails.user.created_at).toLocaleDateString('pt-BR')}
                        </div>
                    </div>
                </div>

                {/* Action Buttons */}
                <div className="flex flex-wrap gap-3">
                    <button
                        onClick={handlePromoteAdmin}
                        className="flex items-center px-4 py-2 bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 rounded-lg hover:bg-blue-100 dark:hover:bg-blue-900/30 transition-colors"
                    >
                        <Shield className="w-4 h-4 mr-2" />
                        {userDetails.user.role === 'admin' || userDetails.user.is_admin ? 'Remover Admin' : 'Promover a Admin'}
                    </button>
                    <button
                        onClick={handleBlockUser}
                        className="flex items-center px-4 py-2 bg-yellow-50 dark:bg-yellow-900/20 text-yellow-600 dark:text-yellow-400 rounded-lg hover:bg-yellow-100 dark:hover:bg-yellow-900/30 transition-colors"
                    >
                        <Ban className="w-4 h-4 mr-2" />
                        {userDetails.user.is_blocked ? 'Desbloquear' : 'Bloquear'}
                    </button>
                    <button
                        onClick={handleExportData}
                        className="flex items-center px-4 py-2 bg-green-50 dark:bg-green-900/20 text-green-600 dark:text-green-400 rounded-lg hover:bg-green-100 dark:hover:bg-green-900/30 transition-colors"
                    >
                        <Download className="w-4 h-4 mr-2" />
                        Exportar Dados
                    </button>
                    <button
                        onClick={handleDeleteUser}
                        className="flex items-center px-4 py-2 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 rounded-lg hover:bg-red-100 dark:hover:bg-red-900/30 transition-colors"
                    >
                        <Trash2 className="w-4 h-4 mr-2" />
                        Desativar conta
                    </button>
                    {currentUser?.id !== userId && (
                        <button
                            type="button"
                            onClick={() => setPurgeOpen(true)}
                            className="flex items-center rounded-lg border border-red-200/90 bg-red-50 px-4 py-2 text-red-800 transition-colors hover:bg-red-100 dark:border-red-900/50 dark:bg-red-950/40 dark:text-red-300 dark:hover:bg-red-950/70"
                        >
                            <Skull className="mr-2 h-4 w-4" />
                            Exclusão total
                        </button>
                    )}
                </div>
            </div>

            {/* Statistics */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
                <div className={ADMIN_CARD}>
                    <p className="text-sm text-slate-500 dark:text-slate-400 font-medium">Total de Transações</p>
                    <h3 className="text-2xl font-bold text-slate-900 dark:text-white mt-1">{userDetails.stats.transactions}</h3>
                </div>
                <div className={ADMIN_CARD}>
                    <p className="text-sm text-slate-500 dark:text-slate-400 font-medium">Categorias</p>
                    <h3 className="text-2xl font-bold text-slate-900 dark:text-white mt-1">{userDetails.stats.categories}</h3>
                </div>
                <div className={ADMIN_CARD}>
                    <p className="text-sm text-slate-500 dark:text-slate-400 font-medium">Contas</p>
                    <h3 className="text-2xl font-bold text-slate-900 dark:text-white mt-1">{userDetails.stats.accounts}</h3>
                </div>
            </div>

            {/* Financial Summary */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
                <div className={ADMIN_CARD}>
                    <p className="text-sm text-green-600 dark:text-green-400 font-medium">Total Receitas</p>
                    <h3 className="text-2xl font-bold text-green-600 dark:text-green-400 mt-1">
                        R$ {userDetails.stats.total_income.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
                    </h3>
                </div>
                <div className={ADMIN_CARD}>
                    <p className="text-sm text-red-600 dark:text-red-400 font-medium">Total Despesas</p>
                    <h3 className="text-2xl font-bold text-red-600 dark:text-red-400 mt-1">
                        R$ {userDetails.stats.total_expense.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
                    </h3>
                </div>
                <div className={ADMIN_CARD}>
                    <p className="text-sm text-slate-500 dark:text-slate-400 font-medium">Saldo Total</p>
                    <h3 className={`text-2xl font-bold mt-1 ${userDetails.stats.balance >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                        R$ {userDetails.stats.balance.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
                    </h3>
                </div>
            </div>

            {/* Recent Transactions */}
            {userDetails.recent_transactions.length > 0 && (
                <div className={`${ADMIN_CARD} mb-6`}>
                    <h3 className="text-lg font-bold text-slate-900 dark:text-white mb-4">Transações Recentes</h3>
                    <div className="overflow-x-auto">
                        <table className="w-full">
                            <thead className="table-header">
                                <tr>
                                    <th className="text-left py-3 px-4 text-sm font-medium text-slate-500 dark:text-slate-400">Data</th>
                                    <th className="text-left py-3 px-4 text-sm font-medium text-slate-500 dark:text-slate-400">Descrição</th>
                                    <th className="text-left py-3 px-4 text-sm font-medium text-slate-500 dark:text-slate-400">Tipo</th>
                                    <th className="text-right py-3 px-4 text-sm font-medium text-slate-500 dark:text-slate-400">Valor</th>
                                </tr>
                            </thead>
                            <tbody>
                                {userDetails.recent_transactions.map((trans) => (
                                    <tr key={trans.id} className="table-row border-b border-slate-100 dark:border-slate-800">
                                        <td className="py-3 px-4 text-sm text-slate-600 dark:text-slate-300">
                                            {new Date(trans.date).toLocaleDateString('pt-BR')}
                                        </td>
                                        <td className="py-3 px-4 text-sm text-slate-900 dark:text-white">{trans.description}</td>
                                        <td className="py-3 px-4">
                                            <span className={`px-2 py-1 text-xs font-medium rounded ${trans.type === 'income'
                                                ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400'
                                                : 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400'
                                                }`}>
                                                {trans.type === 'income' ? 'Receita' : 'Despesa'}
                                            </span>
                                        </td>
                                        <td className={`py-3 px-4 text-sm text-right font-medium ${trans.type === 'income' ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'
                                            }`}>
                                            R$ {trans.amount.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}

            {/* Accounts */}
            {userDetails.accounts.length > 0 && (
                <div className={ADMIN_CARD}>
                    <h3 className="text-lg font-bold text-slate-900 dark:text-white mb-4">Contas</h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {userDetails.accounts.map((account) => (
                            <div
                                key={account.id}
                                className="rounded-lg bg-slate-50 p-4 dark:bg-dark-surface-elevated/80"
                            >
                                <p className="text-sm text-slate-600 dark:text-dark-text-muted">{account.type}</p>
                                <p className="text-lg font-bold text-slate-900 dark:text-white mt-1">{account.name}</p>
                                <p className="text-xl font-bold text-emerald-600 dark:text-emerald-400 mt-2">
                                    R$ {account.balance.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
                                </p>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {purgeOpen && (
                <PurgeUserDialog
                    name={userDetails.user.name}
                    email={userDetails.user.email}
                    onConfirm={submitPurge}
                    onClose={() => setPurgeOpen(false)}
                />
            )}

            {pending && (
                <ConfirmDialog
                    title={pending.title}
                    subject={`${userDetails.user.name} (${userDetails.user.email})`}
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

export default UserDetail;
