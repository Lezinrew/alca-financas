import { useEffect, useState } from 'react';
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
  Target,
  Menu,
  X,
  Shield,
  ChevronDown,
  Receipt
} from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import { ConfirmDialog } from '../shared/ConfirmDialog';

const FOCUS_RING = 'focus:outline-none focus-visible:outline focus-visible:outline-[3px] focus-visible:outline-offset-2 focus-visible:outline-indigo-400';
const isMobileViewport = () => window.innerWidth < 1024;

const AppShell = () => {
  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [sidebarHidden, setSidebarHidden] = useState(() => window.innerWidth < 1024);
  const [userDropdownOpen, setUserDropdownOpen] = useState(false);
  const [logoutOpen, setLogoutOpen] = useState(false);

  // Escape fecha o menu do usuário e, no celular, o menu lateral.
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return;
      if (userDropdownOpen) { setUserDropdownOpen(false); return; }
      if (!sidebarHidden && isMobileViewport()) setSidebarHidden(true);
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [userDropdownOpen, sidebarHidden]);

  const closeSidebarOnMobile = () => { if (isMobileViewport()) setSidebarHidden(true); };

  const navItems = [
    { path: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
    { path: '/transactions', icon: ArrowLeftRight, label: 'Transações' },
    { path: '/financial-expenses', icon: Receipt, label: 'Contas a pagar' },
    { path: '/categories', icon: Tag, label: 'Categorias' },
    { path: '/accounts', icon: Wallet, label: 'Contas' },
    { path: '/credit-cards', icon: CreditCard, label: 'Cartões de crédito' },
    { path: '/planning', icon: Calendar, label: 'Planejamento' },
    { path: '/goals', icon: Target, label: 'Metas' },
    { path: '/reports', icon: PieChart, label: 'Relatórios' },
    { path: '/import', icon: Upload, label: 'Importar' },
  ];

  if (user?.role === 'admin' || user?.is_admin) {
    navItems.push({ path: '/admin/dashboard', icon: Shield, label: 'Administração' });
  }

  const handleLogout = async () => {
    try {
      // Aguardar signOut do Supabase antes de navegar — evita reload com sessão ainda no storage.
      await logout();
      navigate('/login', { replace: true });
    } catch (error) {
      console.error('Erro ao fazer logout:', error);
      window.location.href = '/login';
    }
  };

  const toggleSidebar = () => {
    setSidebarHidden(!sidebarHidden);
  };

  const currentPath = location.pathname;
  const pageTitles: Record<string, string> = { '/profile': 'Meu perfil', '/settings': 'Configurações', '/admin': 'Administração' };
  const currentPage = navItems.find(item => currentPath === item.path || currentPath.startsWith(`${item.path}/`))?.label
    || Object.entries(pageTitles).find(([prefix]) => currentPath.startsWith(prefix))?.[1]
    || 'Dashboard';

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
            <img src="/alcahub-logo.png" alt="Alça Finanças" className="w-8 h-8 object-contain flex-shrink-0" />
            {!sidebarHidden && (
              <span className="ml-2 text-white font-bold text-lg whitespace-nowrap">Alça Finanças</span>
            )}
          </div>
          {!sidebarHidden && (
            <button
              onClick={toggleSidebar}
              className={`lg:hidden min-h-[44px] min-w-[44px] inline-flex items-center justify-center rounded-lg text-slate-300 hover:text-white transition-colors ${FOCUS_RING}`}
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
            const isActive = currentPath === item.path || currentPath.startsWith(`${item.path}/`);
            return (
              <NavLink
                key={item.path}
                to={item.path}
                onClick={closeSidebarOnMobile}
                aria-current={isActive ? 'page' : undefined}
                aria-label={sidebarHidden ? item.label : undefined}
                className={`flex items-center min-h-[44px] rounded-lg text-sm font-medium transition-colors ${FOCUS_RING} ${sidebarHidden ? 'justify-center px-2 py-2.5' : 'px-3 py-2.5'
                  } ${isActive
                    ? 'bg-slate-800 text-white'
                    : 'text-slate-400 hover:bg-slate-800/50 hover:text-white'
                  }`}
                title={sidebarHidden ? item.label : ''}
              >
                <Icon className="w-5 h-5 flex-shrink-0" aria-hidden="true" />
                {!sidebarHidden && <span className="ml-3 whitespace-nowrap">{item.label}</span>}
              </NavLink>
            );
          })}
        </nav>

        {/* User Section */}
        <div className={`p-4 border-t border-slate-700 ${sidebarHidden ? 'px-2' : ''} relative`}>
          <button
            onClick={() => !sidebarHidden && setUserDropdownOpen(!userDropdownOpen)}
            className={`w-full flex items-center ${sidebarHidden ? 'justify-center' : 'justify-between'} mb-3 p-2 min-h-[44px] rounded-lg hover:bg-slate-800/50 transition-colors ${FOCUS_RING}`}
            title={sidebarHidden ? user?.name : ''}
            aria-haspopup="menu"
            aria-expanded={userDropdownOpen}
            aria-label={sidebarHidden ? `Menu de ${user?.name ?? 'usuário'}` : undefined}
          >
            <div className="flex items-center min-w-0">
              <div className="w-9 h-9 rounded-full bg-emerald-500 flex items-center justify-center flex-shrink-0">
                <User className="w-5 h-5 text-white" />
              </div>
              {!sidebarHidden && (
                <div className="ml-3 flex-1 min-w-0 text-left">
                  <p className="text-sm font-medium text-white truncate">{user?.name}</p>
                  <p className="text-xs text-slate-400 truncate">{user?.email}</p>
                </div>
              )}
            </div>
            {!sidebarHidden && <ChevronDown className={`w-4 h-4 text-slate-400 transition-transform ${userDropdownOpen ? 'rotate-180' : ''}`} />}
          </button>

          {/* Dropdown Menu */}
          {userDropdownOpen && !sidebarHidden && (
            <>
              <div
                className="fixed inset-0 z-10"
                onClick={() => setUserDropdownOpen(false)}
                aria-hidden="true"
              />
              <div role="menu" aria-label="Menu do usuário" className="absolute bottom-full left-4 right-4 mb-2 bg-slate-800 border border-slate-700 rounded-lg shadow-xl z-20 py-2">
                <button
                  onClick={() => {
                    navigate('/profile');
                    setUserDropdownOpen(false);
                  }}
                  role="menuitem" className={`w-full flex items-center min-h-[44px] px-4 py-2 text-sm text-slate-200 hover:bg-slate-700 hover:text-white transition-colors ${FOCUS_RING}`}
                >
                  <User className="w-4 h-4 mr-3" />
                  Meu Perfil
                </button>
                <button
                  onClick={() => {
                    navigate('/settings');
                    setUserDropdownOpen(false);
                  }}
                  role="menuitem" className={`w-full flex items-center min-h-[44px] px-4 py-2 text-sm text-slate-200 hover:bg-slate-700 hover:text-white transition-colors ${FOCUS_RING}`}
                >
                  <Settings className="w-4 h-4 mr-3" />
                  Configurações
                </button>
                {(user?.role === 'admin' || user?.is_admin) && (
                  <>
                    <div className="my-1 border-t border-slate-700" />
                    <button
                      onClick={() => {
                        navigate('/admin/dashboard');
                        setUserDropdownOpen(false);
                      }}
                      role="menuitem" className={`w-full flex items-center min-h-[44px] px-4 py-2 text-sm text-emerald-300 hover:bg-slate-700 hover:text-emerald-200 transition-colors ${FOCUS_RING}`}
                    >
                      <Shield className="w-4 h-4 mr-3" />
                      Painel Admin
                    </button>
                  </>
                )}
                <div className="my-1 border-t border-slate-700" />
                <button
                  onClick={() => {
                    setUserDropdownOpen(false);
                    setLogoutOpen(true);
                  }}
                  role="menuitem" className={`w-full flex items-center min-h-[44px] px-4 py-2 text-sm text-red-300 hover:bg-slate-700 hover:text-red-200 transition-colors ${FOCUS_RING}`}
                >
                  <LogOut className="w-4 h-4 mr-3" />
                  Sair
                </button>
              </div>
            </>
          )}
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
              className={`mr-3 min-h-[44px] min-w-[44px] inline-flex items-center justify-center text-slate-700 dark:text-slate-200 hover:text-slate-900 dark:hover:text-white rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700/50 transition-colors ${FOCUS_RING}`}
              aria-label={sidebarHidden ? 'Abrir menu' : 'Fechar menu'}
              aria-expanded={!sidebarHidden}
            >
              {sidebarHidden ? <Menu className="w-5 h-5" /> : <X className="w-5 h-5" />}
            </button>
            <h1 className="text-xl font-semibold text-slate-900 dark:text-white">{currentPage}</h1>
          </div>

          <div className="flex items-center space-x-4">
            <NavLink
              to="/settings"
              aria-label="Configurações"
              title="Configurações"
              className={`min-h-[44px] min-w-[44px] inline-flex items-center justify-center text-slate-700 dark:text-slate-200 hover:text-slate-900 dark:hover:text-white rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700/50 transition-colors ${FOCUS_RING}`}
            >
              <Settings className="w-5 h-5" aria-hidden="true" />
            </NavLink>
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 overflow-auto bg-slate-50 dark:bg-[#0f172a]">
          <div className="p-4 sm:p-6">
            <Outlet />
          </div>
        </main>
      </div>

      {logoutOpen && (
        <ConfirmDialog
          title="Sair da conta"
          subject={user?.email}
          consequence={<p>Você precisará entrar novamente para acessar seus dados. Nada será apagado.</p>}
          confirmLabel="Sair"
          onConfirm={handleLogout}
          onClose={() => setLogoutOpen(false)}
          errorMessage="Não foi possível sair agora. Tente novamente."
        />
      )}
    </div>
  );
};

export default AppShell;
