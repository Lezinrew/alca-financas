import React, { useState } from 'react';
import { Outlet, NavLink, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../contexts/AuthContext';

const MainLayout = () => {
  const { t } = useTranslation();
  const { user, logout } = useAuth();
  const location = useLocation();
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  const navigationItems = [
    {
      path: '/dashboard',
      icon: 'bi-speedometer2',
      label: t('navigation.dashboard')
    },
    {
      path: '/transactions',
      icon: 'bi-arrow-left-right',
      label: t('navigation.transactions')
    },
    {
      path: '/categories',
      icon: 'bi-tags',
      label: t('navigation.categories')
    },
    {
      path: '/accounts',
      icon: 'bi-wallet2',
      label: 'Contas'
    },
    {
      path: '/reports',
      icon: 'bi-bar-chart',
      label: 'Relatórios'
    },
    {
      path: '/import',
      icon: 'bi-upload',
      label: t('navigation.import')
    },
    {
      path: '/settings',
      icon: 'bi-gear',
      label: t('navigation.settings')
    }
  ];

  const handleLogout = () => {
    if (window.confirm('Tem certeza que deseja sair?')) {
      logout();
    }
  };

  const toggleSidebar = () => {
    setSidebarCollapsed(!sidebarCollapsed);
  };

  return (
    <div className="main-layout d-flex">
      {/* Sidebar */}
      <div className={`sidebar ${sidebarCollapsed ? 'collapsed' : ''}`} style={{ width: sidebarCollapsed ? '80px' : '250px' }}>
        <div className="p-4">
          <div className="d-flex align-items-center mb-4">
            <i className="bi bi-wallet2 text-white fs-3 me-2"></i>
            {!sidebarCollapsed && (
              <span className="text-white fw-bold fs-5">Mobills</span>
            )}
          </div>

          <nav className="nav flex-column">
            {navigationItems.map((item) => (
              <NavLink
                key={item.path}
                to={item.path}
                className={({ isActive }) =>
                  `nav-link d-flex align-items-center ${isActive ? 'active' : ''}`
                }
              >
                <i className={`${item.icon} ${sidebarCollapsed ? 'fs-5' : 'me-3'}`}></i>
                {!sidebarCollapsed && <span>{item.label}</span>}
              </NavLink>
            ))}
          </nav>
        </div>

        <div className="mt-auto p-4">
          <div className="d-flex align-items-center text-white mb-3">
            <div className="bg-primary rounded-circle d-flex align-items-center justify-content-center me-3" style={{ width: '40px', height: '40px' }}>
              <i className="bi bi-person-fill"></i>
            </div>
            {!sidebarCollapsed && (
              <div>
                <div className="fw-semibold">{user?.name}</div>
                <small className="opacity-75">{user?.email}</small>
              </div>
            )}
          </div>
          
          <button
            onClick={handleLogout}
            className="btn btn-outline-light btn-sm w-100 d-flex align-items-center justify-content-center"
          >
            <i className={`bi bi-box-arrow-right ${sidebarCollapsed ? '' : 'me-2'}`}></i>
            {!sidebarCollapsed && <span>{t('auth.logout')}</span>}
          </button>
        </div>
      </div>

      {/* Main Content */}
      <div className="main-content flex-grow-1">
        {/* Header */}
        <header className="header d-flex align-items-center justify-content-between p-3">
          <div className="d-flex align-items-center">
            <button
              onClick={toggleSidebar}
              className="btn btn-outline-secondary me-3"
              type="button"
            >
              <i className={`bi ${sidebarCollapsed ? 'bi-list' : 'bi-chevron-left'}`}></i>
            </button>
            
            <h1 className="h4 mb-0 text-capitalize">
              {location.pathname.replace('/', '') || 'dashboard'}
            </h1>
          </div>

          <div className="d-flex align-items-center">
            <div className="dropdown">
              <button
                className="btn btn-light dropdown-toggle d-flex align-items-center"
                type="button"
                id="userDropdown"
                data-bs-toggle="dropdown"
                aria-expanded="false"
              >
                <div className="bg-primary rounded-circle d-flex align-items-center justify-content-center me-2" style={{ width: '32px', height: '32px' }}>
                  <i className="bi bi-person-fill text-white"></i>
                </div>
                <span className="d-none d-sm-inline">{user?.name}</span>
              </button>
              
              <ul className="dropdown-menu dropdown-menu-end" aria-labelledby="userDropdown">
                <li>
                  <NavLink to="/profile" className="dropdown-item">
                    <i className="bi bi-person me-2"></i>
                    {t('navigation.profile')}
                  </NavLink>
                </li>
                <li>
                  <NavLink to="/settings" className="dropdown-item">
                    <i className="bi bi-gear me-2"></i>
                    {t('navigation.settings')}
                  </NavLink>
                </li>
                <li><hr className="dropdown-divider" /></li>
                <li>
                  <button onClick={handleLogout} className="dropdown-item">
                    <i className="bi bi-box-arrow-right me-2"></i>
                    {t('auth.logout')}
                  </button>
                </li>
              </ul>
            </div>
          </div>
        </header>

        {/* Page Content */}
        <main className="p-4">
          <Outlet />
        </main>
      </div>
    </div>
  );
};

export default MainLayout;