import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { AlertCircle, Eye, EyeOff, Loader2, Lock, Mail, Moon, Sun } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useTheme } from '../context/ThemeContext';

const Login = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [localError, setLocalError] = useState('');
  const { login, getRoleDashboard, error: authError } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const navigate = useNavigate();
  const location = useLocation();

  const handleSubmit = async (event) => {
    event.preventDefault();
    setLocalError('');
    setIsSubmitting(true);
    const result = await login(email, password);
    setIsSubmitting(false);

    if (result.success) {
      const destination = location.state?.from?.pathname || getRoleDashboard(result.user.role);
      navigate(destination, { replace: true });
    } else {
      setLocalError(result.error);
    }
  };

  return (
    <main className="app-shell login-page">
      <button
        type="button"
        onClick={toggleTheme}
        className="icon-button login-theme"
        aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
        title={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
      >
        {theme === 'light' ? <Moon size={18} /> : <Sun size={18} />}
      </button>
      <section className="login-card">
        <div className="login-brand">
          <div >
           <img src="/logo.jpg" alt="collage logo" width={120} height={40  } />
          </div>
          <h1>Government Post Graduate College Mardan</h1>
          <p>College Management System · Computer Science Department</p>
        </div>
        <h2>Sign in to your portal</h2>
        <p className="page-description">Use the college account credentials provided by your administrator.</p>

        {(localError || authError) && (
          <div className="notice notice-error" role="alert">
            <AlertCircle size={17} />
            <span>{localError || authError}</span>
          </div>
        )}

        <form className="form-stack" onSubmit={handleSubmit}>
          <label className="field-label">
            College email address
            <span className="input-with-icon">
              <Mail size={16} />
              <input
                type="email"
                autoComplete="username"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                className="text-input"
              />
            </span>
          </label>
          <label className="field-label">
            Password
            <span className="input-with-icon">
              <Lock size={16} />
              <input
                type={showPassword ? 'text' : 'password'}
                autoComplete="current-password"
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                className="text-input"
              />
              <button
                type="button"
                onClick={() => setShowPassword((visible) => !visible)}
                className="password-toggle"
                aria-label={showPassword ? 'Hide password' : 'Show password'}
              >
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </span>
          </label>
          <button type="submit" className="primary-button" disabled={isSubmitting}>
            {isSubmitting ? <Loader2 size={16} className="spin" /> : null}
            {isSubmitting ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
        <p className="login-footer">For account access, contact the Computer Science Department administrator.</p>
      </section>
    </main>
  );
};

export default Login;
