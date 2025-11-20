import React, { useEffect, useState } from 'react';
import { adminAPI, formatCurrency } from '../../utils/api';
import Layout from '../../components/Layout';
import { useAuth } from '../../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';

interface Stats {
    users: {
        total: number;
        new_this_month: number;
    };
    data: {
        transactions: number;
        categories: number;
        accounts: number;
    };
    system_status: string;
}

const AdminDashboard: React.FC = () => {
    const [stats, setStats] = useState<Stats | null>(null);
    const [loading, setLoading] = useState(true);
    const { user } = useAuth();
    const navigate = useNavigate();

    useEffect(() => {
        if (user && !user.is_admin) {
            navigate('/dashboard');
            return;
        }

        const fetchStats = async () => {
            try {
                const response = await adminAPI.getStats();
                setStats(response.data);
            } catch (error) {
                console.error('Erro ao carregar estatísticas:', error);
            } finally {
                setLoading(false);
            }
        };

        fetchStats();
    }, [user, navigate]);

    if (loading) {
        return (
            <Layout title="Admin Dashboard">
                <div className="flex justify-center items-center h-64">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
                </div>
            </Layout>
        );
    }

    return (
        <Layout title="Admin Dashboard">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
                {/* Card Usuários */}
                <div className="bg-white dark:bg-[#1a1d29] p-6 rounded-2xl border border-slate-100 dark:border-slate-800 shadow-sm">
                    <div className="flex justify-between items-start mb-4">
                        <div>
                            <p className="text-sm text-slate-500 dark:text-slate-400 font-medium">Total de Usuários</p>
                            <h3 className="text-2xl font-bold text-slate-900 dark:text-white mt-1">{stats?.users.total}</h3>
                        </div>
                        <div className="p-2 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
                            <svg className="w-6 h-6 text-blue-600 dark:text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
                            </svg>
                        </div>
                    </div>
                    <div className="flex items-center text-sm">
                        <span className="text-green-500 font-medium flex items-center">
                            +{stats?.users.new_this_month}
                        </span>
                        <span className="text-slate-400 ml-2">novos este mês</span>
                    </div>
                </div>

                {/* Card Transações */}
                <div className="bg-white dark:bg-[#1a1d29] p-6 rounded-2xl border border-slate-100 dark:border-slate-800 shadow-sm">
                    <div className="flex justify-between items-start mb-4">
                        <div>
                            <p className="text-sm text-slate-500 dark:text-slate-400 font-medium">Total de Transações</p>
                            <h3 className="text-2xl font-bold text-slate-900 dark:text-white mt-1">{stats?.data.transactions}</h3>
                        </div>
                        <div className="p-2 bg-green-50 dark:bg-green-900/20 rounded-lg">
                            <svg className="w-6 h-6 text-green-600 dark:text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                        </div>
                    </div>
                    <div className="flex items-center text-sm">
                        <span className="text-slate-400">Registros no banco</span>
                    </div>
                </div>

                {/* Card Categorias */}
                <div className="bg-white dark:bg-[#1a1d29] p-6 rounded-2xl border border-slate-100 dark:border-slate-800 shadow-sm">
                    <div className="flex justify-between items-start mb-4">
                        <div>
                            <p className="text-sm text-slate-500 dark:text-slate-400 font-medium">Categorias</p>
                            <h3 className="text-2xl font-bold text-slate-900 dark:text-white mt-1">{stats?.data.categories}</h3>
                        </div>
                        <div className="p-2 bg-purple-50 dark:bg-purple-900/20 rounded-lg">
                            <svg className="w-6 h-6 text-purple-600 dark:text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" />
                            </svg>
                        </div>
                    </div>
                    <div className="flex items-center text-sm">
                        <span className="text-slate-400">Total global</span>
                    </div>
                </div>

                {/* Card Status */}
                <div className="bg-white dark:bg-[#1a1d29] p-6 rounded-2xl border border-slate-100 dark:border-slate-800 shadow-sm">
                    <div className="flex justify-between items-start mb-4">
                        <div>
                            <p className="text-sm text-slate-500 dark:text-slate-400 font-medium">Status do Sistema</p>
                            <h3 className="text-2xl font-bold text-green-500 mt-1 capitalize">{stats?.system_status}</h3>
                        </div>
                        <div className="p-2 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg">
                            <svg className="w-6 h-6 text-yellow-600 dark:text-yellow-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                        </div>
                    </div>
                    <div className="flex items-center text-sm">
                        <span className="text-slate-400">Operacional</span>
                    </div>
                </div>
            </div>

            {/* Quick Actions */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="bg-white dark:bg-[#1a1d29] p-6 rounded-2xl border border-slate-100 dark:border-slate-800 shadow-sm">
                    <h3 className="text-lg font-bold text-slate-900 dark:text-white mb-4">Ações Rápidas</h3>
                    <div className="space-y-3">
                        <button
                            onClick={() => navigate('/admin/users')}
                            className="w-full flex items-center justify-between p-4 bg-slate-50 dark:bg-slate-800/50 rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                        >
                            <div className="flex items-center">
                                <div className="p-2 bg-blue-100 dark:bg-blue-900/30 rounded-lg mr-3">
                                    <svg className="w-5 h-5 text-blue-600 dark:text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
                                    </svg>
                                </div>
                                <div className="text-left">
                                    <p className="font-medium text-slate-900 dark:text-white">Gerenciar Usuários</p>
                                    <p className="text-sm text-slate-500 dark:text-slate-400">Listar, bloquear ou remover usuários</p>
                                </div>
                            </div>
                            <svg className="w-5 h-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                            </svg>
                        </button>
                    </div>
                </div>
            </div>
        </Layout>
    );
};

export default AdminDashboard;
