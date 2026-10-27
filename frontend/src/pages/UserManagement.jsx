import { useEffect, useMemo, useState } from 'react';
import { AlertCircle, CheckCircle2, Search, ShieldCheck, UserRoundCheck, UserRoundX } from 'lucide-react';
import api from '../services/api';
import { useAuth } from '../context/AuthContext';

const getErrorMessage = (error) => {
  const detail = error.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail.map((issue) => `${issue.loc?.join('.') || 'Request'}: ${issue.msg}`).join(' ');
  }
  return detail?.message || error.message || 'The request could not be completed.';
};

export default function UserManagement() {
  const { user } = useAuth();
  const canManageFaculty = user?.role === 'super_admin';
  const [userType, setUserType] = useState('student');
  const [students, setStudents] = useState([]);
  const [faculty, setFaculty] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busyUserId, setBusyUserId] = useState(null);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [notice, setNotice] = useState(null);

  useEffect(() => {
    let mounted = true;
    Promise.all([
      api.get('/students/'),
      canManageFaculty ? api.get('/faculty/') : Promise.resolve({ data: [] }),
    ])
      .then(([studentResponse, facultyResponse]) => {
        if (!mounted) return;
        setStudents(studentResponse.data.filter((student) => student.user?.role === 'student'));
        setFaculty(facultyResponse.data.filter((member) => member.user?.role === 'faculty'));
      })
      .catch((error) => {
        if (mounted) setNotice({ type: 'error', message: getErrorMessage(error) });
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });
    return () => { mounted = false; };
  }, [canManageFaculty]);

  const records = userType === 'student' ? students : faculty;
  const visibleRecords = useMemo(() => {
    const normalizedSearch = search.trim().toLowerCase();
    return records.filter((record) => {
      const user = record.user || {};
      const matchesStatus = statusFilter === 'all' ||
        (statusFilter === 'active' ? user.is_active : !user.is_active);
      const haystack = userType === 'student'
        ? `${user.full_name || ''} ${user.email || ''} ${record.roll_number || ''} ${record.reg_number || ''}`
        : `${user.full_name || ''} ${user.email || ''} ${record.designation || ''}`;
      return matchesStatus && (!normalizedSearch || haystack.toLowerCase().includes(normalizedSearch));
    });
  }, [records, search, statusFilter, userType]);

  const changeStatus = async (record) => {
    const account = record.user;
    if (!account) {
      setNotice({ type: 'error', message: 'This profile is missing its linked account.' });
      return;
    }
    const nextStatus = !account.is_active;
    if (!nextStatus && !window.confirm(`Deactivate ${account.full_name}'s account? Their records will be retained.`)) {
      return;
    }
    setBusyUserId(account.id);
    setNotice(null);
    try {
      const response = await api.patch(`/users/${account.id}/status`, { is_active: nextStatus });
      const updateRecords = (current) => current.map((item) =>
        item.user?.id === account.id
          ? { ...item, user: { ...item.user, is_active: response.data.is_active } }
          : item,
      );
      setStudents(updateRecords);
      setFaculty(updateRecords);
      setNotice({ type: 'success', message: response.data.message });
    } catch (error) {
      setNotice({ type: 'error', message: getErrorMessage(error) });
    } finally {
      setBusyUserId(null);
    }
  };

  const changeType = (type) => {
    setUserType(type);
    setSearch('');
    setNotice(null);
  };

  return (
    <section className="page-stack">
      <div>
        <p className="eyebrow">Administration</p>
        <h1 className="page-title">User management</h1>
        <p className="page-description">
          {canManageFaculty
            ? 'Activate or deactivate student and global faculty sign-in accounts. Deactivation retains all academic records.'
            : `Activate or deactivate student accounts in ${user?.department_name || 'your department'}. Faculty accounts are managed by Super Admin.`}
        </p>
      </div>

      {notice && (
        <div className={`notice notice-${notice.type}`} role="status" aria-live="polite">
          {notice.type === 'error' ? <AlertCircle size={18} /> : <CheckCircle2 size={18} />}
          <span>{notice.message}</span>
        </div>
      )}

      <div className="panel">
        <div className="choice-row user-type-tabs" aria-label="Choose account type">
          {canManageFaculty && (
            <>
              <button
                type="button"
                className={`choice-button ${userType === 'student' ? 'choice-button-active' : ''}`}
                onClick={() => changeType('student')}
              >
                Students <span className="tab-count">{students.length}</span>
              </button>
              <button
                type="button"
                className={`choice-button ${userType === 'faculty' ? 'choice-button-active' : ''}`}
                onClick={() => changeType('faculty')}
              >
                Faculty <span className="tab-count">{faculty.length}</span>
              </button>
            </>
          )}
        </div>

        <div className="user-list-controls">
          <label className="field-label user-search-field" htmlFor="user-search">
            Search name, email, or {userType === 'student' ? 'roll number' : 'designation'}
            <span className="search-input-wrap">
              <Search size={15} />
              <input
                id="user-search"
                className="text-input"
                type="search"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder={userType === 'student' ? 'Search students' : 'Search faculty'}
              />
            </span>
          </label>
          <label className="field-label user-status-field" htmlFor="account-status-filter">
            Account status
            <select
              id="account-status-filter"
              className="text-input"
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value)}
            >
              <option value="all">All accounts</option>
              <option value="active">Active</option>
              <option value="inactive">Deactivated</option>
            </select>
          </label>
        </div>

        <div className="panel-heading user-results-heading">
          <h2 className="section-title">{userType === 'student' ? 'Student accounts' : 'Faculty accounts'}</h2>
          <span className="record-count">{visibleRecords.length} shown</span>
        </div>

        {loading ? (
          <div className="empty-state">Loading accounts…</div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Name / email</th>
                  {userType === 'student'
                    ? <><th>Roll number</th><th>Semester / section</th><th>Admission session</th></>
                    : <><th>Designation</th><th>Qualification</th></>}
                  <th>Status</th>
                  <th>Account action</th>
                </tr>
              </thead>
              <tbody>
                {visibleRecords.map((record) => {
                  const account = record.user;
                  const active = account?.is_active;
                  return (
                    <tr key={record.id}>
                      <td>
                        <span className="user-table-name">{account?.full_name || 'Unknown user'}</span>
                        <span className="table-secondary">{account?.email || 'No email available'}</span>
                      </td>
                      {userType === 'student' ? (
                        <>
                          <td>{record.roll_number}</td>
                          <td>{record.semester} · {record.section}</td>
                          <td>{record.session}</td>
                        </>
                      ) : (
                        <>
                          <td>{record.designation}</td>
                          <td>{record.qualification}</td>
                        </>
                      )}
                      <td>
                        <span className={`status-pill ${active ? 'status-active' : 'status-inactive'}`}>
                          {active ? 'Active' : 'Deactivated'}
                        </span>
                      </td>
                      <td>
                        <button
                          type="button"
                          className={`account-status-button ${active ? 'account-status-deactivate' : 'account-status-activate'}`}
                          disabled={busyUserId === account?.id || !account}
                          onClick={() => changeStatus(record)}
                        >
                          {active ? <UserRoundX size={15} /> : <UserRoundCheck size={15} />}
                          {busyUserId === account?.id ? 'Saving…' : active ? 'Deactivate' : 'Activate'}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {visibleRecords.length === 0 && (
              <div className="empty-state">
                {records.length ? 'No accounts match the selected filters.' : `No ${userType} profiles are registered.`}
              </div>
            )}
          </div>
        )}
        {!loading && (
          <p className="user-management-note">
            <ShieldCheck size={14} />
            Deactivated users cannot sign in. Existing profiles, enrollments, and academic records are not deleted.
          </p>
        )}
      </div>
    </section>
  );
}
