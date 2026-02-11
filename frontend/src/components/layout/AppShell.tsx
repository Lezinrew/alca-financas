import { useState } from 'react';
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
  CreditCard,
  Menu,
  X
} from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';

const AppShell = () => {
  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [sidebarHidden, setSidebarHidden] = useState(false);

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

  if (user?.is_admin) {
    navItems.push({ path: '/admin/dashboard', icon: Settings, label: 'Admin' });
  }

  const handleLogout = async () => {
    if (window.confirm('Deseja sair?')) {
      try {
        logout();
        // Usar window.location para garantir redirecionamento completo
        window.location.href = '/login';
      } catch (error) {
        console.error('Erro ao fazer logout:', error);
        // Fallback: tentar navegação normal
        navigate('/login', { replace: true });
      }
    }
  };

  const toggleSidebar = () => {
    setSidebarHidden(!sidebarHidden);
  };

  const currentPath = location.pathname;
  const currentPage = navItems.find(item => item.path === currentPath)?.label || 'Dashboard';

  return (
    <div className="flex h-screen bg-slate-50 dark:bg-[#0f172a]">
      {/* Overlay para mobile quando sidebar está aberta */}
      {!sidebarHidden && (
        <div
          className="fixed inset-0 bg-black/50 z-30 lg:hidden"
          onClick={toggleSidebar}
          aria-hidden="true"
        />
      )}

      {/* Sidebar */}
      <aside className={`bg-[#1a1d29] dark:bg-[#1a1d29] flex flex-col transition-all duration-300 ease-in-out h-full ${sidebarHidden
          ? '-translate-x-full lg:translate-x-0 lg:w-16'
          : 'translate-x-0 w-60'
        } fixed lg:relative z-40`}>
        {/* Logo */}
        <div className={`h-16 flex items-center justify-between border-b border-slate-700 ${sidebarHidden ? 'px-2 lg:justify-center' : 'px-6'
          }`}>
          <div className="flex items-center">
            <img src="/logo-alca-hub.png" alt="AlçaHub" className="w-8 h-8 object-contain flex-shrink-0" />
            {!sidebarHidden && (
              <span className="ml-2 text-white font-bold text-lg whitespace-nowrap">Alça Finanças</span>
            )}
          </div>
          {!sidebarHidden && (
            <button
              onClick={toggleSidebar}
              className="lg:hidden p-1 text-slate-400 hover:text-white transition-colors"
              aria-label="Fechar menu"
            >
              <X className="w-5 h-5" />
            </button>
          )}
        </div>

        {/* Navigation */}
        <nav className={`flex-1 py-4 space-y-1 ${sidebarHidden ? 'px-2' : 'px-3'}`}>
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = currentPath === item.path;
            return (
              <NavLink
                key={item.path}
                to={item.path}
                className={`flex items-center rounded-lg text-sm font-medium transition-colors ${sidebarHidden ? 'justify-center px-2 py-2.5' : 'px-3 py-2.5'
                  } ${isActive
                    ? 'bg-slate-800 text-white'
                    : 'text-slate-400 hover:bg-slate-800/50 hover:text-white'
                  }`}
                title={sidebarHidden ? item.label : ''}
              >
                <Icon className="w-5 h-5 flex-shrink-0" />
                {!sidebarHidden && <span className="ml-3 whitespace-nowrap">{item.label}</span>}
              </NavLink>
            );
          })}
        </nav>

        {/* User Section */}
        <div className={`p-4 border-t border-slate-700 ${sidebarHidden ? 'px-2' : ''}`}>
          <div className={`flex items-center mb-3 ${sidebarHidden ? 'justify-center' : ''}`}>
            <div className="w-9 h-9 rounded-full bg-emerald-500 flex items-center justify-center flex-shrink-0">
              <User className="w-5 h-5 text-white" />
            </div>
            {!sidebarHidden && (
              <div className="ml-3 flex-1 min-w-0">
                <p className="text-sm font-medium text-white truncate">{user?.name}</p>
                <p className="text-xs text-slate-400 truncate">{user?.email}</p>
              </div>
            )}
          </div>
          <button
            onClick={handleLogout}
            className={`w-full flex items-center ${sidebarHidden ? 'justify-center px-2' : 'justify-center px-3'} py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white rounded-lg text-sm font-medium transition-colors`}
            title={sidebarHidden ? 'Sair' : ''}
          >
            <LogOut className="w-4 h-4 flex-shrink-0" />
            {!sidebarHidden && <span className="ml-2 whitespace-nowrap">Sair</span>}
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <div className={`flex-1 flex flex-col overflow-hidden bg-slate-50 dark:bg-[#0f172a] transition-all duration-300 ${sidebarHidden ? 'lg:ml-0' : 'lg:ml-0'
        }`}>
        {/* Top Bar */}
        <header className="header-base">
          <div className="flex items-center">
            <button
              onClick={toggleSidebar}
              className="mr-3 p-2 text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700/50 transition-colors"
              aria-label={sidebarHidden ? 'Abrir menu' : 'Fechar menu'}
            >
              {sidebarHidden ? <Menu className="w-5 h-5" /> : <X className="w-5 h-5" />}
            </button>
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
