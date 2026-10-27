import { useEffect, useState } from 'react';
import { AlertCircle, CheckCircle2, Download, Upload } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';
import { useAuth } from '../context/AuthContext';

const studentFields = [
  { name: 'full_name', label: 'Full name', required: true },
  { name: 'email', label: 'Email address', type: 'email', required: true },
  { name: 'password', label: 'Initial password', type: 'password', required: true },
  { name: 'phone', label: 'Phone number' },
  { name: 'roll_number', label: 'College roll number', required: true },
  { name: 'reg_number', label: 'AWKUM registration number', required: true },
  { name: 'session', label: 'Academic session', required: true },
  { name: 'semester', label: 'Semester', type: 'number', min: 1, max: 8, required: true },
  { name: 'section', label: 'Section' },
  { name: 'guardian_name', label: 'Guardian name' },
  { name: 'guardian_phone', label: 'Guardian phone' },
];

const facultyFields = [
  { name: 'full_name', label: 'Full name', required: true },
  { name: 'email', label: 'Email address', type: 'email', required: true },
  { name: 'password', label: 'Initial password', type: 'password', required: true },
  { name: 'phone', label: 'Phone number' },
  { name: 'designation', label: 'Designation', required: true },
  { name: 'qualification', label: 'Qualification', required: true },
  { name: 'specialization', label: 'Specialization' },
  { name: 'office_room', label: 'Office room' },
  { name: 'joining_date', label: 'Joining date', type: 'date' },
];

const templates = {
  student: 'email,password,full_name,phone,roll_number,reg_number,session,semester,section,guardian_name,guardian_phone',
  faculty: 'email,password,full_name,phone,designation,qualification,specialization,office_room,joining_date',
};

const explainError = (detail) => {
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail.map((issue) => `${issue.loc?.join('.') || 'Request'}: ${issue.msg}`).join(' ');
  }
  if (detail?.rows) {
    return detail.rows.map((row) => {
      const problems = row.errors?.map((issue) => `${issue.field}: ${issue.message}`).join(', ');
      return `Row ${row.row}: ${problems || `${row.field}: ${row.message}`}`;
    }).join(' ');
  }
  if (detail?.missing_headers?.length || detail?.unknown_headers?.length) {
    return `${detail.message || 'Invalid CSV headers.'} Missing: ${detail.missing_headers?.join(', ') || 'none'}. Unknown: ${detail.unknown_headers?.join(', ') || 'none'}.`;
  }
  return detail?.message || 'The request could not be completed. Check the entered data and try again.';
};

const EnrollmentPage = () => {
  const { user, getRoleDashboard } = useAuth();
  const navigate = useNavigate();
  const [personType, setPersonType] = useState(() => (
    user?.role === 'super_admin' ? 'faculty' : 'student'
  ));
  const [method, setMethod] = useState('bulk');
  const [formValues, setFormValues] = useState({});
  const [file, setFile] = useState(null);
  const [fileInputKey, setFileInputKey] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [departments, setDepartments] = useState([]);
  const [departmentId, setDepartmentId] = useState('');

  useEffect(() => {
    if (user?.role !== 'super_admin') return;
    let active = true;
    api.get('/departments/')
      .then((response) => {
        if (!active) return;
        setDepartments(response.data);
        setDepartmentId((current) => current || String(
          response.data.find((department) => department.code === 'CS')?.id
          || response.data[0]?.id
          || '',
        ));
      })
      .catch((error) => {
        if (active) setError(explainError(error.response?.data?.detail) || error.message);
      });
    return () => { active = false; };
  }, [user?.role]);

  const fields = personType === 'student' ? studentFields : facultyFields;
  const endpoint = personType === 'student' ? '/students' : '/faculty';
  const availableTypes = user?.role === 'super_admin' ? ['faculty'] : ['student'];

  const changeType = (type) => {
    setPersonType(type);
    setFormValues({});
    setFile(null);
    setFileInputKey((key) => key + 1);
    setError('');
    setSuccess('');
  };

  const submitSingle = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError('');
    setSuccess('');
    try {
      const payload = Object.fromEntries(
        Object.entries(formValues).filter(([, value]) => value !== ''),
      );
      if (user.role === 'super_admin') payload.department_id = Number(departmentId);
      const response = await api.post(`${endpoint}/register`, payload);
      setFormValues({});
      if (!response.data) {
        throw new Error('The server did not return a created profile.');
      }
      setSuccess(`${personType === 'student' ? 'Student' : 'Faculty'} account and profile created.`);
    } catch (requestError) {
      setError(explainError(requestError.response?.data?.detail) || requestError.message);
    } finally {
      setBusy(false);
    }
  };

  const submitBulk = async (event) => {
    event.preventDefault();
    if (!file) {
      setError('Select a CSV file to import.');
      return;
    }

    setBusy(true);
    setError('');
    setSuccess('');
    try {
      const data = new FormData();
      data.append('file', file);
      const response = await api.post(`${endpoint}/bulk-import`, data, {
        params: user.role === 'super_admin' ? { department_id: Number(departmentId) } : {},
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setSuccess(`${response.data.created} ${personType === 'student' ? 'student' : 'faculty'} account(s) and profile(s) created.`);
      setFile(null);
      setFileInputKey((key) => key + 1);
    } catch (requestError) {
      setError(explainError(requestError.response?.data?.detail) || requestError.message);
    } finally {
      setBusy(false);
    }
  };

  const downloadTemplate = () => {
    const blob = new Blob([`${templates[personType]}\r\n`], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${personType}-enrollment-template.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <section className="page-stack">
      <div>
        <p className="eyebrow">Account administration</p>
        <h1 className="page-title">{user?.role === 'super_admin' ? 'Faculty management' : 'Student enrollment'}</h1>
        <p className="page-description">
          {user?.role === 'super_admin'
            ? 'Create faculty accounts for the college-wide directory. A faculty member can be allocated to subjects across departments.'
            : `Create student accounts for ${user?.department_name || 'your department'} with a single registration or CSV import. Each import is validated before any records are saved.`}
        </p>
      </div>

      <div className="panel">
        {user.role === 'super_admin' && (
          <label className="field-label enrollment-department-field">
            Faculty home department
            <select
              className="text-input"
              value={departmentId}
              onChange={(event) => setDepartmentId(event.target.value)}
              required
            >
              <option value="">Select department</option>
              {departments.map((department) => (
                <option key={department.id} value={department.id}>{department.name} ({department.code})</option>
              ))}
            </select>
          </label>
        )}
        {user?.role === 'super_admin' && (
          <p className="form-hint">This department records the faculty member’s primary affiliation; teaching assignments can cross department boundaries.</p>
        )}
        {availableTypes.length > 1 && <div className="choice-row" aria-label="Choose enrollment type">
          {availableTypes.map((type) => (
            <button
              key={type}
              type="button"
              className={`choice-button ${personType === type ? 'choice-button-active' : ''}`}
              onClick={() => changeType(type)}
            >
              {type === 'student' ? 'Students' : 'Faculty'}
            </button>
          ))}
        </div>}

        <div className="choice-row method-row" aria-label="Choose registration method">
          <button type="button" className={`choice-button ${method === 'bulk' ? 'choice-button-active' : ''}`} onClick={() => { setMethod('bulk'); setError(''); setSuccess(''); }}>
            Bulk CSV import
          </button>
          <button type="button" className={`choice-button ${method === 'single' ? 'choice-button-active' : ''}`} onClick={() => { setMethod('single'); setError(''); setSuccess(''); }}>
            Single registration
          </button>
        </div>

        {error && <div className="notice notice-error"><AlertCircle size={18} /> <span>{error}</span></div>}
        {success && <div className="notice notice-success"><CheckCircle2 size={18} /> <span>{success}</span></div>}

        {method === 'bulk' ? (
          <form className="form-stack" onSubmit={submitBulk}>
            <div className="help-block">
              <p>Use the template for the selected enrollment type. Required columns are <strong>email, password, full_name</strong> and the relevant profile fields. Passwords must be at least six characters.</p>
              <p>Imports accept UTF-8 CSV files up to 2 MB and 500 records. If any row is invalid or conflicts with an existing account, nothing is created.</p>
            </div>
            <button type="button" className="secondary-button" onClick={downloadTemplate}>
              <Download size={16} /> Download CSV template
            </button>
            <label className="field-label" htmlFor="enrollment-csv">CSV file</label>
            <input
              id="enrollment-csv"
              key={fileInputKey}
              type="file"
              accept=".csv,text/csv"
              required
              onChange={(event) => setFile(event.target.files?.[0] || null)}
              className="file-input"
            />
            <button type="submit" className="primary-button" disabled={busy}>
              <Upload size={16} /> {busy ? 'Importing…' : `Import ${personType === 'student' ? 'students' : 'faculty'}`}
            </button>
          </form>
        ) : (
          <form className="form-stack" onSubmit={submitSingle}>
            <div className="field-grid">
              {fields.map((field) => (
                <label className="field-label" key={field.name}>
                  {field.label}{field.required && <span aria-hidden="true"> *</span>}
                  <input
                    name={field.name}
                    type={field.type || 'text'}
                    min={field.min}
                    max={field.max}
                    minLength={field.name === 'password' ? 6 : undefined}
                    required={field.required}
                    value={formValues[field.name] ?? ''}
                    onChange={(event) => setFormValues((values) => ({ ...values, [field.name]: event.target.value }))}
                    className="text-input"
                  />
                </label>
              ))}
            </div>
            <button type="submit" className="primary-button" disabled={busy}>
              {busy ? 'Creating account…' : `Create ${personType === 'student' ? 'student' : 'faculty'} account`}
            </button>
          </form>
        )}
      </div>
      <button className="text-button back-button" type="button" onClick={() => navigate(getRoleDashboard(user.role))}>Back to dashboard</button>
    </section>
  );
};

export default EnrollmentPage;
