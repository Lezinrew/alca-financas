import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { ThemeProvider } from './contexts/ThemeContext';

// Componentes de Autenticação
import Login from './components/auth/Login';
import Register from './components/auth/Register';

// Componentes Principais
import AppShell from './components/layout/AppShell';
import Dashboard from './components/dashboard/Dashboard';
import Transactions from './components/transactions/Transactions';
import Categories from './components/categories/Categories';
import Settings from './components/settings/Settings';
import Profile from './components/profile/Profile';
import Import from './components/import/Import';
import Reports from './components/reports/Reports';
import Accounts from './components/accounts/Accounts';
import Planning from './components/planning/Planning';
import CreditCards from './components/credit-cards/CreditCards';
import CreditCardDetail from './components/credit-cards/CreditCardDetail';
import AdminDashboard from './pages/admin/AdminDashboard';
import UserManagement from './pages/admin/UserManagement';
import { ChatWidget } from './components/chat/ChatWidget';

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