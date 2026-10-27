import { API_BASE_URL } from '../services/api';

const backendOrigin = API_BASE_URL.replace(/\/api\/v1\/?$/, '');

const initialsFor = (name = '') => {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return '?';
  return parts.length === 1
    ? parts[0].slice(0, 2).toUpperCase()
    : `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
};

export default function ProfileAvatar({ name, imageUrl, size = 42, className = '' }) {
  const src = imageUrl
    ? (/^https?:\/\//i.test(imageUrl) ? imageUrl : `${backendOrigin}${imageUrl}`)
    : null;

  return (
    <span
      className={`user-avatar ${className}`.trim()}
      style={{ width: size, height: size }}
      role="img"
      aria-label={`${name || 'User'} profile image`}
    >
      <span className="user-avatar-initials" aria-hidden="true">{initialsFor(name)}</span>
      {src && <img src={src} alt="" onError={(event) => { event.currentTarget.style.display = 'none'; }} />}
    </span>
  );
}
