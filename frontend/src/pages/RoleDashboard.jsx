import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Building2, ClipboardCheck, GraduationCap, RefreshCw, Users } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import api, { getApiErrorMessage } from '../services/api';

const fetchDashboardRecords = async (role) => {
  if (role === 'super_admin') {
    const [departments, faculty, students, subjects] = await Promise.all([
      api.get('/departments/'),
      api.get('/faculty'),
      api.get('/students'),
      api.get('/subjects'),
    ]);
    return {
      departments: departments.data,
      faculty: faculty.data,
      students: students.data,
      subjects: subjects.data,
      profile: null,
    };
  }

  if (role === 'hod') {
    const [faculty, students, subjects, profile] = await Promise.all([
      api.get('/faculty'),
      api.get('/students'),
      api.get('/subjects'),
      api.get('/auth/me'),
    ]);
    return {
      departments: [],
      faculty: faculty.data,
      students: students.data,
      subjects: subjects.data,
      profile: profile.data,
    };
  }

  const [profile, subjects] = await Promise.all([
    api.get('/auth/me'),
    api.get('/subjects/my-subjects'),
  ]);
  return {
    departments: [],
    faculty: [],
    students: [],
    subjects: subjects.data,
    profile: profile.data,
  };
};

const RoleDashboard = ({ role }) => {
  const { user } = useAuth();
  const [records, setRecords] = useState({
    departments: [],
    faculty: [],
    students: [],
    subjects: [],
    profile: null,
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const loadRecords = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      setRecords(await fetchDashboardRecords(role));
    } catch (requestError) {
      setError(getApiErrorMessage(requestError));
      setRecords({ departments: [], faculty: [], students: [], subjects: [], profile: null });
    } finally {
      setLoading(false);
    }
  }, [role]);

  useEffect(() => {
    let cancelled = false;
    fetchDashboardRecords(role)
      .then((data) => {
        if (!cancelled) setRecords(data);
      })
      .catch((requestError) => {
        if (!cancelled) {
          setError(getApiErrorMessage(requestError));
          setRecords({ departments: [], faculty: [], students: [], subjects: [], profile: null });
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [role]);

  const refreshRecords = () => {
    setLoading(true);
    setError('');
    loadRecords();
  };

  const administrative = role === 'super_admin' || role === 'hod';
  const heading = {
    super_admin: 'Administration dashboard',
    hod: 'Department dashboard',
    faculty: 'Faculty dashboard',
    student: 'Student dashboard',
  }[role];
  const profile = records.profile || user;

  return (
    <section className="page-stack">
      <div className="page-heading-row">
        <div>
          <p className="eyebrow">{profile?.department_name || 'College-wide administration'}</p>
          <h1 className="page-title">{heading}</h1>
          <p className="page-description">Verified account: {profile?.full_name || user?.full_name} · {profile?.email || user?.email}</p>
        </div>
        <button type="button" className="secondary-button" onClick={refreshRecords} disabled={loading}>
          <RefreshCw size={16} className={loading ? 'spin' : ''} /> Refresh
        </button>
      </div>

      {error && <div className="notice notice-error" role="alert">{String(error)}</div>}
      {loading ? <div className="panel empty-state">Loading records from the backend…</div> : (
        <>
          {administrative ? (
            <div className="stat-grid">
              {role === 'super_admin' && (
                <article className="stat-card"><Building2 size={20} /><span>Departments</span><strong>{records.departments.length}</strong></article>
              )}
              <article className="stat-card"><Users size={20} /><span>Faculty accounts</span><strong>{records.faculty.length}</strong></article>
              <article className="stat-card"><GraduationCap size={20} /><span>Student accounts</span><strong>{records.students.length}</strong></article>
            </div>
          ) : (
            <div className="panel profile-panel">
              <h2 className="section-title">Account profile</h2>
              <dl className="profile-grid">
                {Object.entries(profile?.profile || {}).map(([key, value]) => (
                  value !== null && value !== undefined && value !== '' && (
                    <div key={key}><dt>{key.replaceAll('_', ' ')}</dt><dd>{String(value)}</dd></div>
                  )
                ))}
              </dl>
            </div>
          )}

          {administrative && (
            <div className="panel action-panel">
              <div>
                <h2 className="section-title">{role === 'super_admin' ? 'Faculty and department management' : 'Student enrollment'}</h2>
                <p className="page-description">
                  {role === 'super_admin'
                    ? 'Manage departments and create faculty accounts for the college-wide shared faculty directory.'
                    : `Enroll and manage students in ${profile?.department_name || 'your department'}.`}
                </p>
              </div>
              {role === 'super_admin' ? (
                <div className="dashboard-actions">
                  <Link className="primary-button" to="/admin/departments"><Building2 size={16} /> Manage departments</Link>
                  <Link className="secondary-button" to="/admin/enrollment"><Users size={16} /> Manage faculty</Link>
                </div>
              ) : (
                <Link className="primary-button" to="/hod/enrollment">Enroll students</Link>
              )}
            </div>
          )}

          {role === 'faculty' && (
            <div className="panel action-panel">
              <div>
                <h2 className="section-title">Teaching and assessment</h2>
                <p className="page-description">Mark attendance, manage assignments and quizzes, enter marks, and calculate internal results for your allocated classes.</p>
              </div>
              <Link className="primary-button" to="/faculty/academic"><ClipboardCheck size={15} /> Open academic tools</Link>
            </div>
          )}

          {role === 'student' && (
            <div className="panel action-panel">
              <div>
                <h2 className="section-title">Attendance and coursework</h2>
                <p className="page-description">See attendance updates, assignment deadlines and submission status, quiz marks, and internal results.</p>
              </div>
              <Link className="primary-button" to="/student/academics"><GraduationCap size={15} /> Open my academics</Link>
            </div>
          )}

          <div className="panel">
            <div className="panel-heading">
              <div>
                <h2 className="section-title">
                  {role === 'super_admin' ? 'College-wide subjects' : role === 'hod' ? 'Department subjects' : 'Your subjects'}
                </h2>
                <p className="page-description">Records shown here are returned by the backend API.</p>
              </div>
              <span className="record-count">{records.subjects.length} records</span>
            </div>
            {records.subjects.length ? (
              <div className="table-wrap">
                <table>
                  <thead><tr><th>Code</th><th>Subject</th><th>Semester</th><th>Credits</th><th>Academic session</th></tr></thead>
                  <tbody>
                    {records.subjects.map((item) => (
                      <tr key={`${item.subject_id || item.id}-${item.academic_session || ''}`}>
                        <td>{item.code || '—'}</td>
                        <td>{item.title || '—'}</td>
                        <td>{item.semester || '—'}</td>
                        <td>{item.credit_hours || '—'}</td>
                        <td>{item.academic_session || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : <div className="empty-state">No subject records are available in the backend yet.</div>}
          </div>

          {administrative && (
            <div className="panel">
              <div className="panel-heading">
                <div>
                  <h2 className="section-title">Recently added students</h2>
                  <p className="page-description">The directory is populated from registered backend profiles.</p>
                </div>
                <span className="record-count">{records.students.length} records</span>
              </div>
              {records.students.length ? (
                <div className="table-wrap">
                  <table>
                    <thead><tr><th>Name</th><th>Roll number</th><th>Registration number</th><th>Semester</th><th>Session</th></tr></thead>
                    <tbody>{records.students.slice(0, 10).map((student) => (
                      <tr key={student.id}>
                        <td>{student.user?.full_name || '—'}</td>
                        <td>{student.roll_number}</td>
                        <td>{student.reg_number}</td>
                        <td>{student.semester}</td>
                        <td>{student.session}</td>
                      </tr>
                    ))}</tbody>
                  </table>
                </div>
              ) : <div className="empty-state">No student profiles have been registered yet.</div>}
            </div>
          )}
        </>
      )}
    </section>
  );
};

export default RoleDashboard;
