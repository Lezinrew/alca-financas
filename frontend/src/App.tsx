import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { ThemeProvider } from './contexts/ThemeContext';

// Componentes de Autenticação
import Login from './components/auth/Login';
import Register from './components/auth/Register';
import ForgotPassword from './components/auth/ForgotPassword';
import ResetPassword from './components/auth/ResetPassword';

// Componentes Principais
import AppShell from './components/layout/AppShell';
import { ChatWidget } from './components/chat/ChatWidget';

// Lazy loading para melhor performance
import { lazy } from 'react';

const Dashboard = lazy(() => import('./components/dashboard/Dashboard'));
const Transactions = lazy(() => import('./components/transactions/Transactions'));
const Categories = lazy(() => import('./components/categories/Categories'));
const Settings = lazy(() => import('./components/settings/Settings'));
const Profile = lazy(() => import('./components/profile/Profile'));
const Import = lazy(() => import('./components/import/Import'));
const Reports = lazy(() => import('./components/reports/Reports'));
const Accounts = lazy(() => import('./components/accounts/Accounts'));
const Planning = lazy(() => import('./components/planning/Planning'));
const CreditCards = lazy(() => import('./components/credit-cards/CreditCards'));
const CreditCardDetail = lazy(() => import('./components/credit-cards/CreditCardDetail'));
const AdminDashboard = lazy(() => import('./pages/admin/AdminDashboard'));
const UserManagement = lazy(() => import('./pages/admin/UserManagement'));
const UserDetail = lazy(() => import('./pages/admin/UserDetail'));
const AdminLogs = lazy(() => import('./pages/admin/AdminLogs'));

// Type definitions
interface RouteWrapperProps {
  children: React.ReactNode;
}

// Componente de Loading
const LoadingSpinner = () => (
  <div className="d-flex justify-content-center align-items-center" style={{ minHeight: '100vh' }}>
    <div className="text-center">
      <div className="loading-spinner mb-3"></div>
      <p className="text-muted">Carregando...</p>
    </div>
  </div>
);

// Componente de Rota Protegida
const ProtectedRoute: React.FC<RouteWrapperProps> = ({ children }) => {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return <LoadingSpinner />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return children;
};

// Componente de Rota Pública (apenas para usuários não autenticados)
const PublicRoute: React.FC<RouteWrapperProps> = ({ children }) => {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return <LoadingSpinner />;
  }

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }

  return <>{children}</>;
};

// Componente que cria as rotas dentro do contexto do AuthProvider
const AppRoutes: React.FC = () => {
  return (
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <Routes>
        {/* Rotas Públicas */}
        <Route
          path="/login"
          element={
            <PublicRoute>
              <Login />
            </PublicRoute>
          }
        />
        <Route
          path="/register"
          element={
            <PublicRoute>
              <Register />
            </PublicRoute>
          }
        />
        <Route
          path="/forgot-password"
          element={
            <PublicRoute>
              <ForgotPassword />
            </PublicRoute>
          }
        />
        <Route
          path="/reset-password"
          element={
            <PublicRoute>
              <ResetPassword />
            </PublicRoute>
          }
        />

        {/* Rotas Protegidas */}
        <Route
          path="/*"
          element={
            <ProtectedRoute>
              <AppShell />
            </ProtectedRoute>
          }
        >
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="transactions" element={<Transactions />} />
          <Route path="categories" element={<Categories />} />
          <Route path="accounts" element={<Accounts />} />
          <Route path="planning" element={<Planning />} />
          <Route path="credit-cards" element={<CreditCards />} />
          <Route path="credit-cards/:cardId" element={<CreditCardDetail />} />
          <Route path="reports" element={<Reports />} />
          <Route path="settings" element={<Settings />} />
          <Route path="profile" element={<Profile />} />
          <Route path="import" element={<Import />} />

          {/* Admin Routes */}
          <Route path="admin" element={<Navigate to="/admin/dashboard" replace />} />
          <Route path="admin/dashboard" element={<AdminDashboard />} />
          <Route path="admin/users" element={<UserManagement />} />
          <Route path="admin/users/:userId" element={<UserDetail />} />
          <Route path="admin/logs" element={<AdminLogs />} />
        </Route>

        {/* Redirecionar qualquer outra rota */}
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  );
};

// Componente App Principal
const App: React.FC = () => {
  return (
    <ThemeProvider>
      <AuthProvider>
        <div className="App">
          <AppRoutes />
          <ChatWidget />
        </div>
      </AuthProvider>
    </ThemeProvider>
  );
};

export default App;