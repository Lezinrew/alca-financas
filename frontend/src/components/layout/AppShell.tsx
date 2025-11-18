import { Outlet, NavLink, useLocation, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard,
  ArrowLeftRight,
  Wallet,
  PieChart,
  Upload,
  Settings,
  User,
  LogOut,
  Tag,
  Calendar,
  CreditCard
} from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';

const AppShell = () => {
  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  const navItems = [
    { path: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
    { path: '/transactions', icon: ArrowLeftRight, label: 'Transações' },
    { path: '/categories', icon: Tag, label: 'Categorias' },
    { path: '/accounts', icon: Wallet, label: 'Contas' },
    { path: '/credit-cards', icon: CreditCard, label: 'Cartões de crédito' },
    { path: '/planning', icon: Calendar, label: 'Planejamento' },
    { path: '/reports', icon: PieChart, label: 'Relatórios' },
    { path: '/import', icon: Upload, label: 'Importar' },
  ];

  const handleLogout = () => {
    if (window.confirm('Deseja sair?')) {
      logout();
      navigate('/login');
    }
  };

  const currentPath = location.pathname;
  const currentPage = navItems.find(item => item.path === currentPath)?.label || 'Dashboard';

  return (
    <div className="flex h-screen bg-slate-50 dark:bg-[#0f172a]">
      {/* Sidebar */}
      <aside className="w-60 bg-[#1a1d29] dark:bg-[#1a1d29] flex flex-col">
        {/* Logo */}
        <div className="h-16 flex items-center px-6 border-b border-slate-700">
          <Wallet className="w-6 h-6 text-emerald-500" />
          <span className="ml-2 text-white font-bold text-lg">Alça Finanças</span>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 py-4 space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = currentPath === item.path;
            return (
              <NavLink
                key={item.path}
                to={item.path}
                className={`flex items-center px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-slate-800 text-white'
                    : 'text-slate-400 hover:bg-slate-800/50 hover:text-white'
                }`}
              >
                <Icon className="w-5 h-5" />
                <span className="ml-3">{item.label}</span>
              </NavLink>
            );
          })}
        </nav>

        {/* User Section */}
        <div className="p-4 border-t border-slate-700">
          <div className="flex items-center mb-3">
            <div className="w-9 h-9 rounded-full bg-emerald-500 flex items-center justify-center">
              <User className="w-5 h-5 text-white" />
            </div>
            <div className="ml-3 flex-1 min-w-0">
              <p className="text-sm font-medium text-white truncate">{user?.name}</p>
              <p className="text-xs text-slate-400 truncate">{user?.email}</p>
            </div>
          </div>
          <button
            onClick={handleLogout}
            className="w-full flex items-center justify-center px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white rounded-lg text-sm font-medium transition-colors"
          >
            <LogOut className="w-4 h-4 mr-2" />
            Sair
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden bg-slate-50 dark:bg-[#0f172a]">
        {/* Top Bar */}
        <header className="header-base">
          <div className="flex items-center">
            <h1 className="text-xl font-semibold text-slate-900 dark:text-white">{currentPage}</h1>
          </div>

          <div className="flex items-center space-x-4">
            <NavLink
              to="/settings"
              className="p-2 text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700/50 transition-colors"
            >
              <Settings className="w-5 h-5" />
            </NavLink>
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 overflow-auto bg-slate-50 dark:bg-[#0f172a]">
          <div className="p-6">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
};

export default AppShell;
