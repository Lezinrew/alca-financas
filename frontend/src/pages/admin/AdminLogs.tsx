import React, { useEffect, useState } from 'react';
import { adminAPI } from '../../utils/api';
import { Shield, User, Ban, Trash2, Clock } from 'lucide-react';

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
    'block_user': { label: 'Bloqueou usuário', icon: <Ban className="w-4 h-4" />, color: 'text-orange-600 dark:text-orange-400' },
    'unblock_user': { label: 'Desbloqueou usuário', icon: <User className="w-4 h-4" />, color: 'text-green-600 dark:text-green-400' },
    'promote_admin': { label: 'Promoveu a admin', icon: <Shield className="w-4 h-4" />, color: 'text-purple-600 dark:text-purple-400' },
    'demote_admin': { label: 'Removeu admin', icon: <Shield className="w-4 h-4" />, color: 'text-blue-600 dark:text-blue-400' },
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
            color: 'text-slate-600 dark:text-slate-400'
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
                <p className="text-slate-600 dark:text-slate-400 mt-2">
                    Histórico de todas as ações realizadas por administradores
                </p>
            </div>

            <div className="bg-white dark:bg-[#1a1d29] rounded-2xl border border-slate-100 dark:border-slate-800 shadow-sm overflow-hidden">
                {logs.length === 0 ? (
                    <div className="p-12 text-center text-slate-500 dark:text-slate-400">
                        Nenhum log registrado ainda
                    </div>
                ) : (
                    <div className="divide-y divide-slate-100 dark:divide-slate-800">
                        {logs.map((log) => {
                            const actionInfo = getActionInfo(log.action);
                            return (
                                <div key={log.id} className="p-4 hover:bg-slate-50 dark:hover:bg-slate-800/30 transition-colors">
                                    <div className="flex items-start justify-between">
                                        <div className="flex items-start space-x-4">
                                            <div className={`p-2 rounded-lg ${actionInfo.color} bg-opacity-10`}>
                                                {actionInfo.icon}
                                            </div>
                                            <div>
                                                <div className="flex items-center gap-2 mb-1">
                                                    <span className={`font-medium ${actionInfo.color}`}>
                                                        {actionInfo.label}
                                                    </span>
                                                    {log.details.user_name && (
                                                        <span className="text-slate-600 dark:text-slate-400">
                                                            → {log.details.user_name}
                                                        </span>
                                                    )}
                                                </div>
                                                <div className="text-sm text-slate-500 dark:text-slate-400">
                                                    Por: <span className="font-medium">{log.admin_email}</span>
                                                </div>
                                                {log.details.user_email && log.details.user_email !== log.details.user_name && (
                                                    <div className="text-xs text-slate-400 dark:text-slate-500 mt-1">
                                                        {log.details.user_email}
                                                    </div>
                                                )}
                                                {log.ip_address && (
                                                    <div className="text-xs text-slate-400 dark:text-slate-500 mt-1">
                                                        IP: {log.ip_address}
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                        <div className="text-right">
                                            <div className="text-sm text-slate-600 dark:text-slate-400">
                                                {formatTimestamp(log.timestamp)}
                                            </div>
                                            <div className="text-xs text-slate-400 dark:text-slate-500 mt-1">
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
                        className="px-4 py-2 bg-white dark:bg-[#1a1d29] border border-slate-200 dark:border-slate-700 rounded-lg text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        Anterior
                    </button>
                    <span className="px-4 py-2 text-slate-600 dark:text-slate-400">Página {page}</span>
                    <button
                        onClick={() => setPage(page + 1)}
                        disabled={logs.length < 50}
                        className="px-4 py-2 bg-white dark:bg-[#1a1d29] border border-slate-200 dark:border-slate-700 rounded-lg text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        Próxima
                    </button>
                </div>
            )}
        </div>
    );
};

export default AdminLogs;
