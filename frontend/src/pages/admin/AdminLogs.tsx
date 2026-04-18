import React, { useEffect, useState } from 'react';
import { adminAPI } from '../../utils/api';
import { Shield, User, Ban, Trash2, Clock, Mail, Download, Skull } from 'lucide-react';

const ADMIN_CARD = 'admin-card-shell';

interface AdminLog {
    id: string;
    admin_id: string;
    admin_email: string;
    action: string;
    target_id: string | null;
    details: Record<string, any>;
    ip_address: string | null;
    timestamp: string;
}

const ACTION_LABELS: Record<string, { label: string; icon: React.ReactNode; color: string }> = {
    'delete_user': { label: 'Deletou usuário', icon: <Trash2 className="w-4 h-4" />, color: 'text-red-600 dark:text-red-400' },
    'deactivate_user': { label: 'Desativou conta', icon: <Ban className="w-4 h-4" />, color: 'text-red-600 dark:text-red-400' },
    'reactivate_user': { label: 'Reativou conta', icon: <User className="w-4 h-4" />, color: 'text-green-600 dark:text-green-400' },
    'block_user': { label: 'Bloqueou usuário', icon: <Ban className="w-4 h-4" />, color: 'text-orange-600 dark:text-orange-400' },
    'unblock_user': { label: 'Desbloqueou usuário', icon: <User className="w-4 h-4" />, color: 'text-green-600 dark:text-green-400' },
    'promote_admin': { label: 'Promoveu a admin', icon: <Shield className="w-4 h-4" />, color: 'text-purple-600 dark:text-purple-400' },
    'demote_admin': { label: 'Removeu admin', icon: <Shield className="w-4 h-4" />, color: 'text-blue-600 dark:text-blue-400' },
    'status_change': { label: 'Alterou estado da conta', icon: <Clock className="w-4 h-4" />, color: 'text-amber-600 dark:text-amber-400' },
    'send_inactive_warning': { label: 'Enviou aviso de inatividade', icon: <Mail className="w-4 h-4" />, color: 'text-cyan-600 dark:text-cyan-400' },
    'send_inactive_warning_skipped': { label: 'Aviso inatividade (ignorado)', icon: <Clock className="w-4 h-4" />, color: 'text-slate-500 dark:text-dark-text-muted' },
    'bulk_inactive_warning': { label: 'Avisos em lote', icon: <Mail className="w-4 h-4" />, color: 'text-cyan-600 dark:text-cyan-400' },
    'new_account_notification': { label: 'Notificação nova conta (sistema)', icon: <User className="w-4 h-4" />, color: 'text-slate-600 dark:text-dark-text-muted' },
    'legacy_update_user': { label: 'Atualização legada (PUT)', icon: <User className="w-4 h-4" />, color: 'text-slate-500 dark:text-dark-text-muted' },
    'export_user_data': { label: 'Exportou dados do utilizador', icon: <Download className="w-4 h-4" />, color: 'text-emerald-600 dark:text-emerald-400' },
    'create_user_admin': { label: 'Criou utilizador (admin)', icon: <User className="w-4 h-4" />, color: 'text-blue-600 dark:text-blue-400' },
    'purge_user': { label: 'Exclusão total da conta', icon: <Skull className="h-4 w-4" />, color: 'text-red-700 dark:text-red-300' },
};

const AdminLogs: React.FC = () => {
    const [logs, setLogs] = useState<AdminLog[]>([]);
    const [loading, setLoading] = useState(true);
    const [page, setPage] = useState(1);

    useEffect(() => {
        fetchLogs();
    }, [page]);

    const fetchLogs = async () => {
        setLoading(true);
        try {
            const response = await adminAPI.getLogs(page, 50);
            setLogs(response.data.logs);
        } catch (error) {
            console.error('Erro ao carregar logs:', error);
        } finally {
            setLoading(false);
        }
    };

    const formatTimestamp = (timestamp: string) => {
        const date = new Date(timestamp);
        return date.toLocaleString('pt-BR', {
            day: '2-digit',
            month: '2-digit',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
        });
    };

    const getActionInfo = (action: string) => {
        return ACTION_LABELS[action] || {
            label: action,
            icon: <Clock className="w-4 h-4" />,
            color: 'text-slate-600 dark:text-dark-text-muted'
        };
    };

    if (loading) {
        return (
            <div className="flex justify-center items-center h-64">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
            </div>
        );
    }

    return (
        <div className="p-6">
            <div className="mb-6">
                <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Logs de Ações Administrativas</h1>
                <p className="mt-2 text-slate-600 dark:text-dark-text-secondary">
                    Histórico de todas as ações realizadas por administradores
                </p>
            </div>

            <div className={`${ADMIN_CARD} overflow-hidden`}>
                {logs.length === 0 ? (
                    <div className="p-12 text-center text-slate-500 dark:text-dark-text-muted">
                        Nenhum log registrado ainda
                    </div>
                ) : (
                    <div className="divide-y divide-slate-100 dark:divide-dark-border">
                        {logs.map((log) => {
                            const actionInfo = getActionInfo(log.action);
                            const detailName =
                                log.details.user_name ||
                                (log.action === 'purge_user' && log.details.email
                                    ? String(log.details.email)
                                    : null);
                            return (
                                <div
                                    key={log.id}
                                    className="p-4 transition-colors hover:bg-slate-50 dark:hover:bg-dark-surface-hover/35"
                                >
                                    <div className="flex items-start justify-between gap-3">
                                        <div className="flex min-w-0 flex-1 items-start space-x-4">
                                            <div
                                                className={`shrink-0 rounded-lg bg-slate-100 p-2 dark:bg-dark-surface-elevated/80 ${actionInfo.color}`}
                                            >
                                                {actionInfo.icon}
                                            </div>
                                            <div className="min-w-0">
                                                <div className="mb-1 flex flex-wrap items-center gap-2">
                                                    <span className={`font-medium ${actionInfo.color}`}>
                                                        {actionInfo.label}
                                                    </span>
                                                    {detailName && (
                                                        <span className="text-slate-600 dark:text-dark-text-secondary">
                                                            → {detailName}
                                                        </span>
                                                    )}
                                                </div>
                                                <div className="text-sm text-slate-500 dark:text-dark-text-muted">
                                                    Por:{' '}
                                                    <span className="font-medium text-slate-700 dark:text-dark-text-secondary">
                                                        {log.admin_email || '—'}
                                                    </span>
                                                </div>
                                                {log.details.user_email &&
                                                    log.details.user_email !== log.details.user_name &&
                                                    log.action !== 'purge_user' && (
                                                        <div className="mt-1 text-xs text-slate-500 dark:text-dark-text-muted">
                                                            {log.details.user_email}
                                                        </div>
                                                    )}
                                                {log.action === 'purge_user' && log.details.purged_user_id && (
                                                    <div className="mt-1 font-mono text-xs text-slate-500 dark:text-dark-text-muted">
                                                        id: {String(log.details.purged_user_id)}
                                                    </div>
                                                )}
                                                {log.ip_address && (
                                                    <div className="mt-1 text-xs text-slate-500 dark:text-dark-text-muted">
                                                        IP: {log.ip_address}
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                        <div className="shrink-0 text-right">
                                            <div className="text-sm text-slate-600 dark:text-dark-text-secondary">
                                                {formatTimestamp(log.timestamp)}
                                            </div>
                                            <div className="mt-1 text-xs text-slate-500 dark:text-dark-text-muted">
                                                {new Date(log.timestamp).toLocaleDateString('pt-BR', { weekday: 'short' })}
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>

            {/* Pagination */}
            {logs.length > 0 && (
                <div className="flex justify-center mt-6 gap-2">
                    <button
                        onClick={() => setPage(page - 1)}
                        disabled={page === 1}
                        className="admin-outline-btn rounded-lg text-slate-600 hover:bg-slate-50 dark:text-dark-text-secondary"
                    >
                        Anterior
                    </button>
                    <span className="px-4 py-2 text-slate-600 dark:text-dark-text-muted">Página {page}</span>
                    <button
                        onClick={() => setPage(page + 1)}
                        disabled={logs.length < 50}
                        className="admin-outline-btn rounded-lg text-slate-600 hover:bg-slate-50 dark:text-dark-text-secondary"
                    >
                        Próxima
                    </button>
                </div>
            )}
        </div>
    );
};

export default AdminLogs;
