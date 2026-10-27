import { useCallback, useEffect, useState } from 'react';
import { AlertCircle, Building2, CheckCircle2, Plus, UserRoundCog } from 'lucide-react';
import api, { getApiErrorMessage } from '../services/api';

const emptyForm = {
  name: '',
  code: '',
  description: '',
  hod_full_name: '',
  hod_email: '',
  hod_password: '',
  hod_phone: '',
  hod_designation: '',
  hod_qualification: '',
};

export default function DepartmentManagement() {
  const [departments, setDepartments] = useState([]);
  const [faculty, setFaculty] = useState([]);
  const [form, setForm] = useState(emptyForm);
  const [createHod, setCreateHod] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [assigningId, setAssigningId] = useState(null);
  const [notice, setNotice] = useState(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [departmentResponse, facultyResponse] = await Promise.all([
        api.get('/departments/'),
        api.get('/faculty/'),
      ]);
      setDepartments(departmentResponse.data);
      setFaculty(facultyResponse.data);
      setNotice(null);
    } catch (error) {
      setNotice({ type: 'error', message: getApiErrorMessage(error) });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    Promise.all([api.get('/departments/'), api.get('/faculty/')])
      .then(([departmentResponse, facultyResponse]) => {
        if (!active) return;
        setDepartments(departmentResponse.data);
        setFaculty(facultyResponse.data);
      })
      .catch((error) => {
        if (active) setNotice({ type: 'error', message: getApiErrorMessage(error) });
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, []);

  const setField = (field, value) => setForm((current) => ({ ...current, [field]: value }));

  const submitDepartment = async (event) => {
    event.preventDefault();
    setSaving(true);
    setNotice(null);
    const payload = {
      name: form.name.trim(),
      code: form.code.trim().toUpperCase(),
      description: form.description.trim() || null,
    };
    if (createHod) {
      payload.hod_full_name = form.hod_full_name.trim();
      payload.hod_email = form.hod_email.trim();
      payload.hod_password = form.hod_password;
      payload.hod_phone = form.hod_phone.trim() || null;
      payload.hod_designation = form.hod_designation.trim();
      payload.hod_qualification = form.hod_qualification.trim();
    }
    try {
      const response = await api.post('/departments/', payload);
      setNotice({
        type: 'success',
        message: `${response.data.name} was created${response.data.hod_name ? ` with ${response.data.hod_name} as HOD` : ''}.`,
      });
      setForm(emptyForm);
      setCreateHod(false);
      await loadData();
    } catch (error) {
      setNotice({ type: 'error', message: getApiErrorMessage(error) });
    } finally {
      setSaving(false);
    }
  };

  const assignHod = async (department, userId) => {
    if (!userId || String(department.hod_user_id || '') === userId) return;
    setAssigningId(department.id);
    setNotice(null);
    try {
      const response = await api.patch(`/departments/${department.id}/hod`, {
        faculty_user_id: Number(userId),
      });
      setDepartments((current) => current.map((item) => (
        item.id === department.id ? response.data : item
      )));
      setFaculty((current) => current.map((member) => (
        member.user?.id === response.data.hod_user_id
          ? { ...member, user: { ...member.user, role: 'hod' } }
          : member.user?.id === department.hod_user_id
            ? { ...member, user: { ...member.user, role: 'faculty' } }
            : member
      )));
      setNotice({ type: 'success', message: `${response.data.hod_name} is now HOD of ${department.name}.` });
    } catch (error) {
      setNotice({ type: 'error', message: getApiErrorMessage(error) });
    } finally {
      setAssigningId(null);
    }
  };

  const field = (name, label, options = {}) => (
    <label className="field-label" key={name}>
      {label}
      <input
        className="text-input"
        type={options.type || 'text'}
        minLength={options.minLength}
        maxLength={options.maxLength}
        required={options.required}
        value={form[name]}
        onChange={(event) => setField(name, event.target.value)}
      />
    </label>
  );

  return (
    <section className="page-stack">
      <div>
        <p className="eyebrow">College administration</p>
        <h1 className="page-title">Departments</h1>
        <p className="page-description">Create departments and assign each department's Head of Department.</p>
      </div>

      {notice && (
        <div className={`notice notice-${notice.type}`} role="status">
          {notice.type === 'error' ? <AlertCircle size={18} /> : <CheckCircle2 size={18} />}
          <span>{notice.message}</span>
        </div>
      )}

      <form className="panel department-create-form" onSubmit={submitDepartment}>
        <div className="activity-compose-heading">
          <Plus size={18} />
          <h2 className="section-title">Create a department</h2>
        </div>
        <div className="field-grid">
          {field('name', 'Department name', { required: true, maxLength: 100 })}
          {field('code', 'Department code', { required: true, maxLength: 20 })}
          <label className="field-label department-description">
            Description
            <textarea
              className="text-input textarea-input"
              maxLength={1000}
              rows={2}
              value={form.description}
              onChange={(event) => setField('description', event.target.value)}
            />
          </label>
        </div>
        <label className="department-hod-toggle">
          <input type="checkbox" checked={createHod} onChange={(event) => setCreateHod(event.target.checked)} />
          <span>Create the HOD account with this department</span>
        </label>
        {createHod && (
          <div className="field-grid department-hod-fields">
            {field('hod_full_name', 'HOD full name', { required: true, minLength: 2, maxLength: 120 })}
            {field('hod_email', 'HOD email address', { required: true, type: 'email' })}
            {field('hod_password', 'Initial password', { required: true, type: 'password', minLength: 6 })}
            {field('hod_phone', 'Phone number', { maxLength: 25 })}
            {field('hod_designation', 'Designation', { required: true, maxLength: 80 })}
            {field('hod_qualification', 'Qualification', { required: true, maxLength: 120 })}
          </div>
        )}
        <button className="primary-button" type="submit" disabled={saving}>
          <Building2 size={16} /> {saving ? 'Creating…' : 'Create department'}
        </button>
      </form>

      <div className="department-list-heading">
        <div>
          <h2 className="section-title">All departments</h2>
          <p className="page-description">HOD accounts are managed within their department boundary.</p>
        </div>
        <span className="record-count">{departments.length} departments</span>
      </div>
      {loading ? (
        <div className="panel empty-state">Loading departments…</div>
      ) : departments.length ? (
        <div className="department-grid">
          {departments.map((department) => {
            const eligibleFaculty = faculty.filter((member) => (
              member.department_id === department.id
              && member.user?.is_active
              && ['faculty', 'hod'].includes(member.user?.role)
            ));
            return (
              <article className="panel department-card" key={department.id}>
                <div className="department-card-heading">
                  <span className="department-card-icon"><Building2 size={20} /></span>
                  <div>
                    <h3>{department.name}</h3>
                    <span>{department.code}</span>
                  </div>
                </div>
                {department.description && <p className="page-description">{department.description}</p>}
                <div className="department-hod-row">
                  <UserRoundCog size={17} />
                  <div>
                    <strong>{department.hod_name || 'HOD not assigned'}</strong>
                    <span>{department.hod_email || 'Assign an existing faculty member below.'}</span>
                  </div>
                </div>
                <label className="field-label">
                  Assign HOD from this department's faculty
                  <select
                    className="text-input"
                    value={department.hod_user_id || ''}
                    onChange={(event) => assignHod(department, event.target.value)}
                    disabled={assigningId === department.id || eligibleFaculty.length === 0}
                  >
                    <option value="">Select faculty</option>
                    {eligibleFaculty.map((member) => (
                      <option key={member.user.id} value={member.user.id}>
                        {member.user.full_name} · {member.user.email}
                      </option>
                    ))}
                  </select>
                </label>
              </article>
            );
          })}
        </div>
      ) : (
        <div className="panel empty-state">No departments have been created.</div>
      )}
    </section>
  );
}
