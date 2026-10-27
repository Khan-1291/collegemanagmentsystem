import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ThemeProvider } from './context/ThemeContext';
import ProtectedRoute from './components/ProtectedRoute';
import DashboardLayout from './components/layout/DashboardLayout';
import RoleDashboard from './pages/RoleDashboard';
import EnrollmentPage from './pages/EnrollmentPage';
import SubjectManagement from './pages/SubjectManagement';
import ProfileSettings from './pages/ProfileSettings';
import UserManagement from './pages/UserManagement';
import FacultyAcademic from './pages/FacultyAcademic';
import StudentAcademic from './pages/StudentAcademic';
import DepartmentActivities from './pages/DepartmentActivities';
import DepartmentManagement from './pages/DepartmentManagement';

// Pages
import Login from './pages/Login';

/**
 * Root Redirector:
 * Sends authenticated users to their role-specific dashboard,
 * or unauthenticated users to the Login page.
 */
const RootRedirect = () => {
  const { isAuthenticated, user, loading, getRoleDashboard } = useAuth();

  if (loading) {
    return (
      <div className="app-shell loading-screen">
        Loading GPGCM Portal...
      </div>
    );
  }

  if (isAuthenticated && user) {
    return <Navigate to={getRoleDashboard(user.role)} replace />;
  }

  return <Navigate to="/login" replace />;
};

export default function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
          {/* Public Authentication Route */}
          <Route path="/login" element={<Login />} />

          {/* Root Redirector */}
          <Route path="/" element={<RootRedirect />} />

          {/* Super Admin Protected Routes */}
          <Route
            path="/admin"
            element={
              <ProtectedRoute allowedRoles={['super_admin']}>
                <DashboardLayout />
              </ProtectedRoute>
            }
          >
            <Route index element={<RoleDashboard role="super_admin" />} />
            <Route path="enrollment" element={<EnrollmentPage />} />
            <Route path="subjects" element={<SubjectManagement />} />
            <Route path="profile" element={<ProfileSettings />} />
            <Route path="users" element={<UserManagement />} />
            <Route path="departments" element={<DepartmentManagement />} />
            <Route path="activities" element={<DepartmentActivities />} />
          </Route>

          {/* Head of Department (HOD) Protected Routes */}
          <Route
            path="/hod"
            element={
              <ProtectedRoute allowedRoles={['hod', 'super_admin']}>
                <DashboardLayout />
              </ProtectedRoute>
            }
          >
            <Route index element={<RoleDashboard role="hod" />} />
            <Route path="enrollment" element={<EnrollmentPage />} />
            <Route path="subjects" element={<SubjectManagement />} />
            <Route path="profile" element={<ProfileSettings />} />
            <Route path="users" element={<UserManagement />} />
            <Route path="activities" element={<DepartmentActivities />} />
          </Route>

          {/* Faculty Protected Routes */}
          <Route
            path="/faculty"
            element={
              <ProtectedRoute allowedRoles={['faculty', 'hod', 'super_admin']}>
                <DashboardLayout />
              </ProtectedRoute>
            }
          >
            <Route index element={<RoleDashboard role="faculty" />} />
            <Route path="profile" element={<ProfileSettings />} />
            <Route path="activities" element={<DepartmentActivities />} />
            <Route
              path="academic"
              element={
                <ProtectedRoute allowedRoles={['faculty']}>
                  <FacultyAcademic />
                </ProtectedRoute>
              }
            />
          </Route>

          {/* Student Protected Routes */}
          <Route
            path="/student"
            element={
              <ProtectedRoute allowedRoles={['student']}>
                <DashboardLayout />
              </ProtectedRoute>
            }
          >
            <Route index element={<RoleDashboard role="student" />} />
            <Route path="profile" element={<ProfileSettings />} />
            <Route path="academics" element={<StudentAcademic />} />
            <Route path="activities" element={<DepartmentActivities />} />
          </Route>

          {/* Fallback 404 handler */}
          <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  );
}
