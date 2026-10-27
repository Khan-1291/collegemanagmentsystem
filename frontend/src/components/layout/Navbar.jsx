import { LogOut, Menu, Moon, Sun } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { useTheme } from '../../context/ThemeContext';
import ProfileAvatar from '../ProfileAvatar';

const roleLabels = {
  super_admin: 'Super Admin',
  hod: 'HOD',
  faculty: 'Faculty',
  student: 'Student',
};

const Navbar = ({ onToggleSidebar }) => {
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();

  return (
    <header className="topbar">
      <div className="topbar-brand-group">
        <button
          type="button"
          onClick={onToggleSidebar}
          className="icon-button mobile-menu-button"
          aria-label="Toggle navigation"
        >
          <Menu size={19} />
        </button>
        <div className="brand-icon">
         < img src="/logo.jpg" alt="GPGCM Mardan Logo" className="logo-image" width={60} height={60} />
        </div>
        
        <div className="brand-copy">
          <h1 className="brand-title">GPGCM Mardan <span className="affiliation-tag">AWKUM affiliated</span></h1>
          <p className="brand-subtitle">Government Post Graduate College · Computer Science</p>
        </div>
      </div>
      <div className="topbar-actions">
        <button
          type="button"
          onClick={toggleTheme}
          className="icon-button"
          aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
          title={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
        >
          {theme === 'light' ? <Moon size={18} /> : <Sun size={18} />}
        </button>
        {user && (
          <>
            <div className="user-summary">
              <ProfileAvatar name={user.full_name} imageUrl={user.profile_image_url} size={36} />
              <div className="user-summary-copy">
                <span className="user-name">{user.full_name}</span>
                <span className="user-email">{user.email}</span>
              </div>
            </div>
            <span className="role-badge">{roleLabels[user.role] || user.role}</span>
            <button type="button" onClick={logout} className="secondary-button logout-button" title="Sign out">
              <LogOut size={16} /><span>Sign out</span>
            </button>
          </>
        )}
      </div>
    </header>
  );
};

export default Navbar;
