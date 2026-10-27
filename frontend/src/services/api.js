import axios from 'axios';

/**
 * Axios instance configured for GPGCM College Management System (Phase 1)
 * Points to the FastAPI backend API base URL
 */
const pageHost = typeof window === 'undefined' ? 'localhost' : window.location.hostname;
const defaultApiHost = ['localhost', '::1', '[::1]'].includes(pageHost)
  ? '127.0.0.1'
  : pageHost;
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL
  || `http://${defaultApiHost}:8000/api/v1`;

export const getApiErrorMessage = (error) => {
  if (!error.response) {
    const target = error.config?.baseURL || API_BASE_URL;
    if (error.code === 'ECONNABORTED') {
      return `The college API at ${target} did not respond in time. Check that the backend is running and reachable.`;
    }
    return `No response from the college API at ${target}. Check that the backend is running, VITE_API_BASE_URL points to the backend, and the frontend origin is allowed by backend CORS settings.`;
  }

  const detail = error.response.data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => `${item.loc?.join('.') || 'Request'}: ${item.msg}`).join(' ');
  }
  return detail?.message || error.message || 'The request could not be completed.';
};

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 10000,
});

/**
 * Request Interceptor:
 * Attaches the JWT access token from localStorage to every outgoing request.
 */
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('gpgcm_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

/**
 * Response Interceptor:
 * Handles global error responses (401 Unauthorized, token expiration).
 */
api.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    if (error.response && error.response.status === 401) {
      // Clear expired credentials
      localStorage.removeItem('gpgcm_token');
      localStorage.removeItem('gpgcm_user');
      
      // If not already on login page, redirect
      if (window.location.pathname !== '/login') {
        window.location.href = '/login?session_expired=true';
      }
    }
    return Promise.reject(error);
  }
);

export default api;
