import { NavLink } from 'react-router-dom';
import { Activity, BookOpen, Building2, ClipboardCheck, GraduationCap, LayoutDashboard, Settings, ShieldCheck, UserPlus, X } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import ProfileAvatar from '../ProfileAvatar';

const Sidebar = ({ isOpen, onClose }) => {
  const { user } = useAuth();
  if (!user) return null;

  const basePath = user.role === 'super_admin' ? '/admin' : `/${user.role}`;
  const links = [
    { label: 'Dashboard', path: basePath, icon: LayoutDashboard },
    { label: 'Department activities', path: `${basePath}/activities`, icon: Activity },
    { label: 'My Profile', path: `${basePath}/profile`, icon: Settings },
    ...(user.role === 'faculty'
      ? [{ label: 'Academic tools', path: `${basePath}/academic`, icon: ClipboardCheck }]
      : []),
    ...(user.role === 'student'
      ? [{ label: 'My academics', path: `${basePath}/academics`, icon: GraduationCap }]
      : []),
    ...(user.role === 'super_admin'
      ? [
        { label: 'Departments', path: `${basePath}/departments`, icon: Building2 },
        { label: 'Faculty management', path: `${basePath}/enrollment`, icon: UserPlus },
        { label: 'Subjects', path: `${basePath}/subjects`, icon: BookOpen },
        { label: 'User management', path: `${basePath}/users`, icon: ShieldCheck },
      ]
      : user.role === 'hod'
        ? [
          { label: 'Enroll students', path: `${basePath}/enrollment`, icon: UserPlus },
          { label: 'Subjects & faculty allocation', path: `${basePath}/subjects`, icon: BookOpen },
          { label: 'User management', path: `${basePath}/users`, icon: ShieldCheck },
        ]
        : []),
  ];

  return (
    <>
      {isOpen && <button type="button" onClick={onClose} className="sidebar-backdrop" aria-label="Close navigation" />}
      <aside className={`sidebar ${isOpen ? 'sidebar-open' : ''}`}>
        <div className="sidebar-mobile-heading">
          <span>Navigation</span>
          <button type="button" onClick={onClose} className="icon-button" aria-label="Close navigation">
            <X size={18} />
          </button>
        </div>
        <div className="sidebar-user-card">
          <ProfileAvatar name={user.full_name} imageUrl={user.profile_image_url} size={42} />
          <div className="sidebar-user-copy">
            <strong>{user.full_name}</strong>
            <span>{user.role.replace('_', ' ')}</span>
          </div>
        </div>
        <nav className="sidebar-links" aria-label="Main navigation">
          <div className="sidebar-section-label">
            {user.role === 'super_admin' ? 'Administration' : user.role === 'hod' ? 'Department' : user.role}
          </div>
          {links.map(({ label, path, icon: Icon }) => (
            <NavLink
              key={path}
              to={path}
              end={path === basePath}
              onClick={onClose}
              className={({ isActive }) => `nav-link ${isActive ? 'nav-link-active' : ''}`}
            >
              <Icon size={17} />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-info">
          <div className="sidebar-info-title">
            GPGCM · {user.role === 'super_admin' ? 'College-wide' : user.department_name || 'Department'}
          </div>
          <div className="sidebar-info-text">College Management System</div>
        </div>
      </aside>
    </>
  );
};

export default Sidebar;
