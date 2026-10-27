import { useEffect, useState } from 'react';
import { AlertCircle, Camera, CheckCircle2, LockKeyhole } from 'lucide-react';
import api, { getApiErrorMessage } from '../services/api';
import { useAuth } from '../context/AuthContext';
import ProfileAvatar from '../components/ProfileAvatar';

const EMPTY_PROFILE = {
  full_name: '',
  email: '',
  phone: '',
  guardian_name: '',
  guardian_phone: '',
  qualification: '',
  specialization: '',
  office_room: '',
  joining_date: '',
};

const errorMessage = (error) => {
  const detail = error.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail.map((issue) => `${issue.loc?.join('.') || 'Request'}: ${issue.msg}`).join(' ');
  }
  return detail?.message || error.message || 'The request could not be completed.';
};

const profileFields = {
  student: [
    { name: 'guardian_name', label: 'Guardian name', maxLength: 120 },
    { name: 'guardian_phone', label: 'Guardian phone', maxLength: 25 },
  ],
  faculty: [
    { name: 'qualification', label: 'Qualification', maxLength: 120 },
    { name: 'specialization', label: 'Specialization', maxLength: 150 },
    { name: 'office_room', label: 'Office room', maxLength: 50 },
    { name: 'joining_date', label: 'Joining date', type: 'date' },
  ],
  hod: [
    { name: 'qualification', label: 'Qualification', maxLength: 120 },
    { name: 'specialization', label: 'Specialization', maxLength: 150 },
    { name: 'office_room', label: 'Office room', maxLength: 50 },
    { name: 'joining_date', label: 'Joining date', type: 'date' },
  ],
};

const readOnlyProfileFields = {
  student: [
    ['Roll number', 'roll_number'],
    ['Registration number', 'reg_number'],
    ['Semester', 'semester'],
    ['Admission session', 'session'],
    ['Program', 'program'],
    ['Section', 'section'],
    ['Department', 'department'],
  ],
  faculty: [
    ['Designation', 'designation'],
    ['Department', 'department'],
  ],
  hod: [
    ['Designation', 'designation'],
    ['Department', 'department'],
  ],
  super_admin: [
    ['Access scope', 'scope'],
  ],
};

export default function ProfileSettings() {
  const { updateUser } = useAuth();
  const [profile, setProfile] = useState(null);
  const [form, setForm] = useState(EMPTY_PROFILE);
  const [passwords, setPasswords] = useState({
    current_password: '',
    new_password: '',
    confirm_password: '',
  });
  const [loading, setLoading] = useState(true);
  const [savingProfile, setSavingProfile] = useState(false);
  const [savingPassword, setSavingPassword] = useState(false);
  const [uploadingImage, setUploadingImage] = useState(false);
  const [notice, setNotice] = useState(null);

  useEffect(() => {
    let mounted = true;
    api.get('/auth/me')
      .then((response) => {
        if (!mounted) return;
        const data = response.data;
        setProfile(data);
        setForm({
          ...EMPTY_PROFILE,
          full_name: data.full_name || '',
          email: data.email || '',
          phone: data.phone || '',
          guardian_name: data.profile?.guardian_name || '',
          guardian_phone: data.profile?.guardian_phone || '',
          qualification: data.profile?.qualification || '',
          specialization: data.profile?.specialization || '',
          office_room: data.profile?.office_room || '',
          joining_date: data.profile?.joining_date || '',
        });
      })
      .catch((error) => {
        if (mounted) setNotice({ type: 'error', message: errorMessage(error) });
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });
    return () => { mounted = false; };
  }, []);

  const changeProfileField = (field, value) => {
    setForm((current) => ({ ...current, [field]: value }));
  };

  const uploadProfileImage = async (event) => {
    const image = event.target.files?.[0];
    event.target.value = '';
    if (!image) return;
    if (image.size > 5 * 1024 * 1024) {
      setNotice({ type: 'error', message: 'Profile images are limited to 5 MB.' });
      return;
    }

    setUploadingImage(true);
    setNotice(null);
    const data = new FormData();
    data.append('image', image);
    try {
      const response = await api.post('/auth/me/profile-image', data, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      const updatedProfile = { ...profile, profile_image_url: response.data.profile_image_url };
      setProfile(updatedProfile);
      updateUser(updatedProfile);
      setNotice({ type: 'success', message: 'Your profile image has been updated.' });
    } catch (error) {
      setNotice({ type: 'error', message: getApiErrorMessage(error) });
    } finally {
      setUploadingImage(false);
    }
  };

  const submitProfile = async (event) => {
    event.preventDefault();
    setSavingProfile(true);
    setNotice(null);
    const fields = ['email', 'full_name', 'phone', ...(profileFields[profile.role] || []).map((field) => field.name)];
    const payload = Object.fromEntries(
      fields.map((field) => [field, form[field] === '' ? null : form[field]]),
    );
    try {
      const response = await api.put('/auth/me', payload);
      setProfile(response.data);
      updateUser(response.data);
      setForm((current) => ({
        ...current,
        email: response.data.email || '',
        full_name: response.data.full_name || '',
        phone: response.data.phone || '',
      }));
      setNotice({ type: 'success', message: 'Your profile was updated successfully.' });
    } catch (error) {
      setNotice({ type: 'error', message: errorMessage(error) });
    } finally {
      setSavingProfile(false);
    }
  };

  const submitPassword = async (event) => {
    event.preventDefault();
    setNotice(null);
    if (passwords.new_password !== passwords.confirm_password) {
      setNotice({ type: 'error', message: 'New password and confirmation do not match.' });
      return;
    }
    if (passwords.new_password.length < 6) {
      setNotice({ type: 'error', message: 'New password must be at least 6 characters.' });
      return;
    }
    setSavingPassword(true);
    try {
      const response = await api.put('/auth/me/password', {
        current_password: passwords.current_password,
        new_password: passwords.new_password,
      });
      setPasswords({ current_password: '', new_password: '', confirm_password: '' });
      setNotice({ type: 'success', message: response.data.message });
    } catch (error) {
      setNotice({ type: 'error', message: errorMessage(error) });
    } finally {
      setSavingPassword(false);
    }
  };

  const roleFields = profile?.profile?.faculty_id
    ? profileFields[profile.role] || []
    : profile?.profile?.student_id
      ? profileFields.student
      : [];
  const details = profile ? readOnlyProfileFields[profile.role] || [] : [];
  const roleLabel = profile?.role?.replace('_', ' ') || '';

  return (
    <section className="page-stack">
      <div>
        <p className="eyebrow">Account</p>
        <h1 className="page-title">My profile</h1>
        <p className="page-description">Update your contact details and manage your sign-in password.</p>
      </div>

      {notice && (
        <div className={`notice notice-${notice.type}`} role="status" aria-live="polite">
          {notice.type === 'error' ? <AlertCircle size={18} /> : <CheckCircle2 size={18} />}
          <span>{notice.message}</span>
        </div>
      )}

      {loading ? (
        <div className="panel empty-state">Loading your profile…</div>
      ) : profile ? (
        <>
          <div className="panel">
            <div className="profile-card-heading">
              <ProfileAvatar
                name={profile.full_name}
                imageUrl={profile.profile_image_url}
                size={64}
                className="profile-avatar-large"
              />
              <div>
                <h2 className="section-title">{profile.full_name}</h2>
                <p className="page-description profile-role-label">{roleLabel}</p>
              </div>
              <label className={`secondary-button profile-image-upload ${uploadingImage ? 'is-disabled' : ''}`}>
                <Camera size={15} />
                {uploadingImage ? 'Uploading…' : 'Change photo'}
                <input
                  type="file"
                  accept=".png,.jpg,.jpeg,.gif,.webp,image/png,image/jpeg,image/gif,image/webp"
                  onChange={uploadProfileImage}
                  disabled={uploadingImage}
                />
              </label>
            </div>
            <form className="form-stack profile-form" onSubmit={submitProfile}>
              <div className="field-grid">
                <label className="field-label" htmlFor="profile-full-name">
                  Full name
                  <input
                    id="profile-full-name"
                    className="text-input"
                    value={form.full_name}
                    onChange={(event) => changeProfileField('full_name', event.target.value)}
                    minLength="2"
                    maxLength="120"
                    required
                  />
                </label>
                <label className="field-label" htmlFor="profile-email">
                  Email address
                  <input
                    id="profile-email"
                    className="text-input"
                    type="email"
                    value={form.email}
                    onChange={(event) => changeProfileField('email', event.target.value)}
                    required
                  />
                </label>
                <label className="field-label" htmlFor="profile-phone">
                  Phone number
                  <input
                    id="profile-phone"
                    className="text-input"
                    type="tel"
                    value={form.phone}
                    onChange={(event) => changeProfileField('phone', event.target.value)}
                    maxLength="25"
                  />
                </label>
                {roleFields.map(({ name, label, type = 'text', maxLength }) => (
                  <label key={name} className="field-label" htmlFor={`profile-${name}`}>
                    {label}
                    <input
                      id={`profile-${name}`}
                      className="text-input"
                      type={type}
                      value={form[name]}
                      onChange={(event) => changeProfileField(name, event.target.value)}
                      maxLength={maxLength}
                    />
                  </label>
                ))}
              </div>

              {details.length > 0 && (
                <div className="profile-locked-details">
                  <div>
                    <h3 className="section-title">Academic and account details</h3>
                    <p className="page-description">
                      These institutional records are maintained by authorized department staff.
                    </p>
                  </div>
                  <dl className="profile-grid">
                    {details.map(([label, field]) => (
                      <div key={field}>
                        <dt>{label}</dt>
                        <dd>{profile.profile?.[field] ?? '—'}</dd>
                      </div>
                    ))}
                  </dl>
                </div>
              )}
              <div className="subject-form-actions">
                <button type="submit" className="primary-button" disabled={savingProfile}>
                  {savingProfile ? 'Saving…' : 'Save profile'}
                </button>
              </div>
            </form>
          </div>

          <div className="panel">
            <div className="profile-card-heading">
              <span className="profile-avatar"><LockKeyhole size={20} /></span>
              <div>
                <h2 className="section-title">Change password</h2>
                <p className="page-description">Confirm your current password. New passwords must be at least 6 characters.</p>
              </div>
            </div>
            <form className="form-stack password-form" onSubmit={submitPassword}>
              <div className="field-grid">
                <label className="field-label" htmlFor="current-password">
                  Current password
                  <input
                    id="current-password"
                    className="text-input"
                    type="password"
                    autoComplete="current-password"
                    value={passwords.current_password}
                    onChange={(event) => setPasswords((current) => ({ ...current, current_password: event.target.value }))}
                    required
                  />
                </label>
                <label className="field-label" htmlFor="new-password">
                  New password
                  <input
                    id="new-password"
                    className="text-input"
                    type="password"
                    autoComplete="new-password"
                    minLength="6"
                    value={passwords.new_password}
                    onChange={(event) => setPasswords((current) => ({ ...current, new_password: event.target.value }))}
                    required
                  />
                </label>
                <label className="field-label" htmlFor="confirm-password">
                  Confirm new password
                  <input
                    id="confirm-password"
                    className="text-input"
                    type="password"
                    autoComplete="new-password"
                    minLength="6"
                    value={passwords.confirm_password}
                    onChange={(event) => setPasswords((current) => ({ ...current, confirm_password: event.target.value }))}
                    required
                  />
                </label>
              </div>
              <div className="subject-form-actions">
                <button type="submit" className="primary-button" disabled={savingPassword}>
                  {savingPassword ? 'Updating…' : 'Update password'}
                </button>
              </div>
            </form>
          </div>
        </>
      ) : (
        <div className="panel empty-state">Your profile could not be loaded.</div>
      )}
    </section>
  );
}
