import { createContext, useContext, useEffect, useState } from 'react';
import api, { getApiErrorMessage } from '../services/api';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const initializeAuth = async () => {
      const storedToken = localStorage.getItem('gpgcm_token');
      if (!storedToken) {
        setLoading(false);
        return;
      }

      setToken(storedToken);
      try {
        const response = await api.get('/auth/me');
        setUser(response.data);
        localStorage.setItem('gpgcm_user', JSON.stringify(response.data));
      } catch (requestError) {
        if ([401, 403].includes(requestError.response?.status)) {
          localStorage.removeItem('gpgcm_token');
          localStorage.removeItem('gpgcm_user');
        } else {
          setError(getApiErrorMessage(requestError));
        }
        setToken(null);
        setUser(null);
      } finally {
        setLoading(false);
      }
    };

    initializeAuth();
  }, []);

  const login = async (email, password) => {
    setError(null);
    try {
      const response = await api.post('/auth/login', {
        email: email.trim().toLowerCase(),
        password,
      });
      const accessToken = response.data.access_token;
      setToken(accessToken);
      localStorage.setItem('gpgcm_token', accessToken);

      const profileResponse = await api.get('/auth/me');
      const userProfile = profileResponse.data;
      setUser(userProfile);
      localStorage.setItem('gpgcm_user', JSON.stringify(userProfile));
      return { success: true, user: userProfile };
    } catch (requestError) {
      localStorage.removeItem('gpgcm_token');
      localStorage.removeItem('gpgcm_user');
      setToken(null);
      setUser(null);

      const errorMessage = getApiErrorMessage(requestError);
      setError(errorMessage);
      return { success: false, error: errorMessage };
    }
  };

  const logout = () => {
    localStorage.removeItem('gpgcm_token');
    localStorage.removeItem('gpgcm_user');
    setToken(null);
    setUser(null);
    setError(null);
  };

  const updateUser = (updatedUser) => {
    setUser(updatedUser);
    localStorage.setItem('gpgcm_user', JSON.stringify(updatedUser));
  };

  const getRoleDashboard = (role) => {
    switch (role) {
      case 'super_admin':
        return '/admin';
      case 'hod':
        return '/hod';
      case 'faculty':
        return '/faculty';
      case 'student':
        return '/student';
      default:
        return '/login';
    }
  };

  const value = {
    user,
    token,
    loading,
    error,
    login,
    logout,
    updateUser,
    isAuthenticated: !!token && !!user,
    getRoleDashboard,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

// Keep the provider and its hook together as one Fast Refresh module.
// eslint-disable-next-line react-refresh/only-export-components
export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
