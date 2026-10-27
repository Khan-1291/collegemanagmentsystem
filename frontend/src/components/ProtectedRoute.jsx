import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Loader2 } from 'lucide-react';

/**
 * ProtectedRoute Component:
 * Guards routes against unauthenticated access and unauthorized roles.
 * 
 * Props:
 * - allowedRoles: Array of role strings (e.g. ['super_admin', 'hod', 'faculty', 'student'])
 */
const ProtectedRoute = ({ children, allowedRoles }) => {
  const { user, loading, isAuthenticated, getRoleDashboard } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center text-slate-300">
        <Loader2 className="w-10 h-10 animate-spin text-emerald-500 mb-3" />
        <p className="text-sm font-medium">Verifying GPGCM session credentials...</p>
      </div>
    );
  }

  // Not authenticated -> redirect to login
  if (!isAuthenticated || !user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  // Role not permitted -> redirect to user's assigned dashboard
  if (allowedRoles && !allowedRoles.includes(user.role)) {
    return <Navigate to={getRoleDashboard(user.role)} replace />;
  }

  return children;
};

export default ProtectedRoute;
