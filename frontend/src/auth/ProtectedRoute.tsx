import { Navigate, useLocation } from 'react-router-dom';
import type { ReactNode } from 'react';
import { useAuth } from './AuthContext';
import type { AccountRole } from '../services/auth';

export default function ProtectedRoute({
  role,
  children,
}: {
  role: AccountRole;
  children: ReactNode;
}) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return <main className="auth-loading" role="status">Checking your secure session…</main>;
  }
  if (!user) {
    return <Navigate to={`/${role}/login`} replace state={{ from: location.pathname }} />;
  }
  if (user.role !== role) {
    return <Navigate to={`/${user.role}/dashboard`} replace />;
  }
  return children;
}
