import { useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertCircle,
  BookOpen,
  CheckCircle2,
  GraduationCap,
  Pencil,
  Users,
} from 'lucide-react';
import api from '../services/api';
import { useAuth } from '../context/AuthContext';

const COMMON_SESSIONS = ['Fall 2025', 'Spring 2026', 'Fall 2026', 'Spring 2027', 'Fall 2027'];
const SECTIONS = ['A', 'B', 'C', 'D'];
const SEMESTERS = Array.from({ length: 8 }, (_, index) => index + 1);
const EMPTY_SUBJECT = {
  code: '',
  title: '',
  credit_hours: '3',
  semester: '1',
  description: '',
};

const getErrorMessage = (error) => {
  const detail = error.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail.map((issue) => `${issue.loc?.join('.') || 'Request'}: ${issue.msg}`).join(' ');
  }
  return detail?.message || error.message || 'The request could not be completed. Please try again.';
};

const AcademicSessionField = ({ id, value, onChange }) => {
  const custom = value === '__custom__' || (value && !COMMON_SESSIONS.includes(value));

  if (custom) {
    return (
      <div className="session-field">
        <input
          id={id}
          className="text-input"
          value={value === '__custom__' ? '' : value}
          onChange={(event) => onChange(event.target.value)}
          placeholder="e.g. Summer 2027"
          aria-label="Custom academic session"
          required
        />
        <button type="button" className="text-button" onClick={() => onChange('')}>
          Choose a listed session
        </button>
      </div>
    );
  }

  return (
    <select
      id={id}
      className="text-input"
      value={value}
      onChange={(event) => onChange(event.target.value)}
      required
    >
      <option value="">Select academic session</option>
      {COMMON_SESSIONS.map((session) => <option key={session} value={session}>{session}</option>)}
      <option value="__custom__">Other session…</option>
    </select>
  );
};

export default function SubjectManagement() {
  const { user } = useAuth();
  const isSuperAdmin = user?.role === 'super_admin';
  const [subjects, setSubjects] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [departmentId, setDepartmentId] = useState('');
  const [faculty, setFaculty] = useState([]);
  const [allocations, setAllocations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [activeTab, setActiveTab] = useState('subjects');
  const [notice, setNotice] = useState(null);
  const [subjectForm, setSubjectForm] = useState(EMPTY_SUBJECT);
  const [editingSubjectId, setEditingSubjectId] = useState(null);
  const [subjectSearch, setSubjectSearch] = useState('');
  const [allocationSubjectId, setAllocationSubjectId] = useState('');
  const [allocationFacultyId, setAllocationFacultyId] = useState('');
  const [allocationSection, setAllocationSection] = useState('A');
  const [enrollmentSubjectId, setEnrollmentSubjectId] = useState('');
  const [enrollmentSection, setEnrollmentSection] = useState('A');
  const [selectedSemester, setSelectedSemester] = useState('');
  const [selectedAcademicSession, setSelectedAcademicSession] = useState('');
  const [availableStudents, setAvailableStudents] = useState([]);
  const [selectedStudentIds, setSelectedStudentIds] = useState([]);
  const [studentsLoading, setStudentsLoading] = useState(false);
  const studentRequest = useRef(0);

  const activeSubjects = useMemo(
    () => subjects.filter((subject) => subject.is_active),
    [subjects],
  );
  const scopedSubjects = useMemo(
    () => activeSubjects.filter(
      (subject) => !selectedSemester || subject.semester === Number(selectedSemester),
    ),
    [activeSubjects, selectedSemester],
  );
  const scopedAllocations = useMemo(
    () => allocations.filter((allocation) => {
      const matchesSemester = !selectedSemester
        || allocation.subject?.semester === Number(selectedSemester);
      const matchesSession = !selectedAcademicSession
        || allocation.academic_session === selectedAcademicSession;
      return matchesSemester && matchesSession;
    }),
    [allocations, selectedAcademicSession, selectedSemester],
  );
  const visibleSubjects = useMemo(() => {
    const search = subjectSearch.trim().toLowerCase();
    if (!search) return subjects;
    return subjects.filter((subject) =>
      `${subject.code} ${subject.title} ${subject.semester}`.toLowerCase().includes(search),
    );
  }, [subjects, subjectSearch]);
  const activeFaculty = useMemo(
    () => faculty.filter((member) => member.user?.is_active),
    [faculty],
  );
  const enrollmentSubject = subjects.find(
    (subject) => String(subject.id) === enrollmentSubjectId,
  );
  const eligibleStudents = availableStudents.filter((student) => student.user?.is_active);
  const hasAcademicSession = Boolean(
    selectedAcademicSession.trim() && selectedAcademicSession !== '__custom__',
  );

  useEffect(() => {
    let mounted = true;
    const loadManagementData = async () => {
      setLoading(true);
      setNotice(null);
      try {
        const departmentResponse = await api.get('/departments/');
        if (!mounted) return;
        const selectedDepartment = departmentId
          || String(departmentResponse.data.find((department) => department.code === 'CS')?.id
            || departmentResponse.data[0]?.id
            || '');
        if (isSuperAdmin && !departmentId) setDepartmentId(selectedDepartment);
        const params = isSuperAdmin && selectedDepartment
          ? { department_id: Number(selectedDepartment) }
          : {};
        const [subjectResponse, facultyResponse, allocationResponse] = await Promise.all([
          api.get('/subjects/', { params }),
          api.get('/faculty/'),
          api.get('/subjects/allocations', { params }),
        ]);
        if (!mounted) return;
        setDepartments(departmentResponse.data);
        const subjectRecords = subjectResponse.data;
        setSubjects(subjectRecords);
        setFaculty(facultyResponse.data);
        setAllocations(allocationResponse.data);
        const firstActiveSubject = subjectRecords.find((subject) => subject.is_active);
        const defaultSubjectId = String(firstActiveSubject?.id || '');
        setSelectedSemester(String(firstActiveSubject?.semester || ''));
        setAllocationSubjectId(defaultSubjectId);
        setEnrollmentSubjectId(defaultSubjectId);
        setAvailableStudents([]);
        setSelectedStudentIds([]);
      } catch (error) {
        if (mounted) setNotice({ type: 'error', message: getErrorMessage(error) });
      } finally {
        if (mounted) setLoading(false);
      }
    };
    loadManagementData();
    return () => { mounted = false; };
  }, [departmentId, isSuperAdmin]);

  const setFormField = (field, value) => {
    setSubjectForm((current) => ({ ...current, [field]: value }));
  };

  const loadStudents = async (subjectId, section) => {
    const requestId = studentRequest.current + 1;
    studentRequest.current = requestId;
    const subject = subjects.find((item) => String(item.id) === subjectId);
    setAvailableStudents([]);
    setSelectedStudentIds([]);
    if (!subject) {
      setStudentsLoading(false);
      return;
    }
    setStudentsLoading(true);
    setNotice(null);
    try {
      const response = await api.get('/students/', {
        params: {
          semester: subject.semester,
          section,
          ...(isSuperAdmin ? { department_id: subject.department_id } : {}),
        },
      });
      if (studentRequest.current === requestId) setAvailableStudents(response.data);
    } catch (error) {
      if (studentRequest.current === requestId) {
        setNotice({ type: 'error', message: getErrorMessage(error) });
      }
    } finally {
      if (studentRequest.current === requestId) setStudentsLoading(false);
    }
  };

  const changeSemester = (semester) => {
    setSelectedSemester(semester);
    const nextSubject = activeSubjects.find(
      (subject) => subject.semester === Number(semester),
    );
    const nextSubjectId = String(nextSubject?.id || '');
    setAllocationSubjectId(nextSubjectId);
    setEnrollmentSubjectId(nextSubjectId);
    setSelectedStudentIds([]);
    if (activeTab === 'enrollment') {
      loadStudents(nextSubjectId, enrollmentSection);
    }
  };

  const changeAcademicSession = (session) => {
    setSelectedAcademicSession(session);
    setSelectedStudentIds([]);
  };

  const changeTab = (tab) => {
    setActiveTab(tab);
    setNotice(null);
    if (tab === 'enrollment') {
      loadStudents(enrollmentSubjectId, enrollmentSection);
    }
  };

  const resetSubjectForm = () => {
    setSubjectForm(EMPTY_SUBJECT);
    setEditingSubjectId(null);
  };

  const submitSubject = async (event) => {
    event.preventDefault();
    setBusy(true);
    setNotice(null);
    const payload = {
      ...subjectForm,
      code: subjectForm.code.trim().toUpperCase(),
      title: subjectForm.title.trim(),
      credit_hours: Number(subjectForm.credit_hours),
      semester: Number(subjectForm.semester),
      description: subjectForm.description.trim() || null,
      ...(!editingSubjectId && isSuperAdmin ? { department_id: Number(departmentId) } : {}),
    };
    try {
      const response = editingSubjectId
        ? await api.put(`/subjects/${editingSubjectId}`, payload)
        : await api.post('/subjects/', payload);
      setSubjects((current) => {
        const records = current.filter((subject) => subject.id !== response.data.id);
        return [...records, response.data].sort(
          (left, right) => left.semester - right.semester || left.code.localeCompare(right.code),
        );
      });
      setNotice({
        type: 'success',
        message: editingSubjectId ? 'Subject details updated.' : 'Subject created successfully.',
      });
      resetSubjectForm();
    } catch (error) {
      setNotice({ type: 'error', message: getErrorMessage(error) });
    } finally {
      setBusy(false);
    }
  };

  const editSubject = (subject) => {
    setEditingSubjectId(subject.id);
    setSubjectForm({
      code: subject.code,
      title: subject.title,
      credit_hours: String(subject.credit_hours),
      semester: String(subject.semester),
      description: subject.description || '',
    });
    setActiveTab('subjects');
    setNotice(null);
  };

  const toggleSubjectStatus = async (subject) => {
    const nextActive = !subject.is_active;
    if (!nextActive && !window.confirm(`Deactivate ${subject.code} — ${subject.title}?`)) return;
    setBusy(true);
    setNotice(null);
    try {
      const response = await api.put(`/subjects/${subject.id}`, { is_active: nextActive });
      setSubjects((current) => current.map((item) =>
        item.id === subject.id ? response.data : item,
      ));
      setNotice({
        type: 'success',
        message: `${subject.code} ${nextActive ? 'activated' : 'deactivated'}.`,
      });
    } catch (error) {
      setNotice({ type: 'error', message: getErrorMessage(error) });
    } finally {
      setBusy(false);
    }
  };

  const submitAllocation = async (event) => {
    event.preventDefault();
    if (!hasAcademicSession) {
      setNotice({ type: 'error', message: 'Choose the shared academic session before saving the allocation.' });
      return;
    }
    setBusy(true);
    setNotice(null);
    try {
      const response = await api.post('/subjects/allocate-faculty', {
        faculty_id: Number(allocationFacultyId),
        subject_id: Number(allocationSubjectId),
        academic_session: selectedAcademicSession.trim(),
        section: allocationSection,
      });
      setAllocations((current) => [
        response.data,
        ...current.filter((item) => item.id !== response.data.id),
      ]);
      setNotice({ type: 'success', message: 'Faculty allocation saved.' });
    } catch (error) {
      setNotice({ type: 'error', message: getErrorMessage(error) });
    } finally {
      setBusy(false);
    }
  };

  const removeAllocation = async (allocation) => {
    const facultyName = allocation.faculty?.user?.full_name || 'this faculty member';
    if (!window.confirm(`Remove ${facultyName}'s allocation for ${allocation.subject?.code} (${allocation.academic_session}, Section ${allocation.section})?`)) {
      return;
    }
    setBusy(true);
    setNotice(null);
    try {
      await api.delete(`/subjects/allocations/${allocation.id}`);
      setAllocations((current) => current.filter((item) => item.id !== allocation.id));
      setNotice({ type: 'success', message: 'Faculty allocation removed.' });
    } catch (error) {
      setNotice({ type: 'error', message: getErrorMessage(error) });
    } finally {
      setBusy(false);
    }
  };

  const submitEnrollment = async (event) => {
    event.preventDefault();
    if (!hasAcademicSession) {
      setNotice({ type: 'error', message: 'Choose the shared academic session before enrolling students.' });
      return;
    }
    if (selectedStudentIds.length === 0) {
      setNotice({ type: 'error', message: 'Select at least one student to enroll.' });
      return;
    }
    setBusy(true);
    setNotice(null);
    try {
      const response = await api.post('/subjects/enroll-students', {
        subject_id: Number(enrollmentSubjectId),
        academic_session: selectedAcademicSession.trim(),
        student_ids: selectedStudentIds,
      });
      setNotice({
        type: 'success',
        message: response.data.message || 'Student enrollments saved.',
      });
    } catch (error) {
      setNotice({ type: 'error', message: getErrorMessage(error) });
    } finally {
      setBusy(false);
    }
  };

  const toggleStudent = (studentId) => {
    setSelectedStudentIds((current) => current.includes(studentId)
      ? current.filter((id) => id !== studentId)
      : [...current, studentId]);
  };

  const selectAllStudents = (checked) => {
    setSelectedStudentIds(checked ? eligibleStudents.map((student) => student.id) : []);
  };

  const tabs = [
    { id: 'subjects', label: 'Subjects', icon: BookOpen },
    { id: 'allocations', label: 'Faculty allocations', icon: Users },
    ...(!isSuperAdmin
      ? [{ id: 'enrollment', label: 'Student enrollment', icon: GraduationCap }]
      : []),
  ];

  return (
    <section className="page-stack subject-management">
      <div className="subject-page-heading">
        <div>
          <p className="eyebrow">Academic administration</p>
          <h1 className="page-title">Subject management</h1>
          <p className="page-description">
            {isSuperAdmin
              ? 'Manage department curricula and allocate shared faculty across departments.'
              : 'Maintain your department curriculum, assign shared faculty, and enroll semester sections.'}
          </p>
        </div>
        <div className="subject-summary" aria-label="Subject overview">
          <span><strong>{subjects.length}</strong> subjects</span>
          <span><strong>{activeFaculty.length}</strong> active faculty</span>
        </div>
      </div>

      {notice && (
        <div className={`notice notice-${notice.type}`} role="status" aria-live="polite">
          {notice.type === 'error' ? <AlertCircle size={18} /> : <CheckCircle2 size={18} />}
          <span>{notice.message}</span>
        </div>
      )}

      <div className="panel academic-scope-panel">
        <div>
          <h2 className="section-title">Shared academic scope</h2>
          <p className="page-description">
            Select the semester and session once. Faculty allocations use this scope
            {isSuperAdmin ? '.' : ' and student enrollment uses this same scope.'}
          </p>
        </div>
        <div className="field-grid">
          {isSuperAdmin && (
            <label className="field-label" htmlFor="management-department">
              Department
              <select
                id="management-department"
                className="text-input"
                value={departmentId}
                onChange={(event) => setDepartmentId(event.target.value)}
              >
                {departments.map((department) => (
                  <option key={department.id} value={department.id}>{department.name} ({department.code})</option>
                ))}
              </select>
            </label>
          )}
          <label className="field-label" htmlFor="shared-semester">
            Semester
            <select
              id="shared-semester"
              className="text-input"
              value={selectedSemester}
              onChange={(event) => changeSemester(event.target.value)}
            >
              {SEMESTERS.map((semester) => (
                <option key={semester} value={semester}>Semester {semester}</option>
              ))}
            </select>
          </label>
          <label className="field-label" htmlFor="shared-academic-session">
            Academic session
            <AcademicSessionField
              id="shared-academic-session"
              value={selectedAcademicSession}
              onChange={changeAcademicSession}
            />
          </label>
        </div>
        <p className="form-hint">
          Current scope: {selectedSemester ? `Semester ${selectedSemester}` : 'Choose a semester'}
          {' · '}
          {selectedAcademicSession || 'Choose an academic session'}
        </p>
      </div>

      <nav className="subject-tabs" aria-label="Subject management sections">
        {tabs.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            type="button"
            className={`subject-tab ${activeTab === id ? 'subject-tab-active' : ''}`}
            aria-current={activeTab === id ? 'page' : undefined}
            onClick={() => changeTab(id)}
          >
            <Icon size={16} />
            {label}
          </button>
        ))}
      </nav>

      {loading ? (
        <div className="panel empty-state">Loading academic records…</div>
      ) : (
        <>
          {activeTab === 'subjects' && (
            <>
              <div className="panel">
                <div className="panel-heading">
                  <div>
                    <h2 className="section-title">{editingSubjectId ? 'Edit subject' : 'Create a subject'}</h2>
                    <p className="page-description">Add a course to the selected department's curriculum.</p>
                  </div>
                  {editingSubjectId && (
                    <button type="button" className="secondary-button" onClick={resetSubjectForm}>
                      Cancel editing
                    </button>
                  )}
                </div>
                <form className="form-stack subject-form" onSubmit={submitSubject}>
                  <div className="field-grid">
                    <label className="field-label" htmlFor="subject-code">
                      Course code
                      <input
                        id="subject-code"
                        className="text-input"
                        value={subjectForm.code}
                        onChange={(event) => setFormField('code', event.target.value)}
                        placeholder="CS-501"
                        maxLength={20}
                        required
                      />
                    </label>
                    <label className="field-label" htmlFor="subject-title">
                      Subject title
                      <input
                        id="subject-title"
                        className="text-input"
                        value={subjectForm.title}
                        onChange={(event) => setFormField('title', event.target.value)}
                        placeholder="Operating Systems"
                        maxLength={150}
                        required
                      />
                    </label>
                    <label className="field-label" htmlFor="subject-credits">
                      Credit hours
                      <input
                        id="subject-credits"
                        className="text-input"
                        type="number"
                        min="1"
                        max="6"
                        value={subjectForm.credit_hours}
                        onChange={(event) => setFormField('credit_hours', event.target.value)}
                        required
                      />
                    </label>
                    <label className="field-label" htmlFor="subject-semester">
                      Semester
                      <select
                        id="subject-semester"
                        className="text-input"
                        value={subjectForm.semester}
                        onChange={(event) => setFormField('semester', event.target.value)}
                        required
                      >
                        {Array.from({ length: 8 }, (_, index) => index + 1).map((semester) => (
                          <option key={semester} value={semester}>Semester {semester}</option>
                        ))}
                      </select>
                    </label>
                  </div>
                  <label className="field-label" htmlFor="subject-description">
                    Description <span className="optional-label">Optional</span>
                    <textarea
                      id="subject-description"
                      className="text-input textarea-input"
                      value={subjectForm.description}
                      onChange={(event) => setFormField('description', event.target.value)}
                      placeholder="Brief course outline or notes"
                      rows="3"
                    />
                  </label>
                  <div className="subject-form-actions">
                    <button type="submit" className="primary-button" disabled={busy}>
                      {busy ? 'Saving…' : editingSubjectId ? 'Save changes' : 'Create subject'}
                    </button>
                  </div>
                </form>
              </div>

              <div className="panel">
                <div className="panel-heading">
                  <div>
                    <h2 className="section-title">Curriculum subjects</h2>
                    <p className="page-description">Edit details or deactivate a course without removing its academic history.</p>
                  </div>
                  <span className="record-count">{visibleSubjects.length} shown</span>
                </div>
                <label className="field-label subject-search-label" htmlFor="subject-search">
                  Search by code, title, or semester
                  <input
                    id="subject-search"
                    className="text-input"
                    type="search"
                    value={subjectSearch}
                    onChange={(event) => setSubjectSearch(event.target.value)}
                    placeholder="e.g. CS-501"
                  />
                </label>
                <div className="table-wrap">
                  <table className="subject-table">
                    <thead>
                      <tr>
                        <th>Code</th>
                        <th>Title</th>
                        <th>Credit hours</th>
                        <th>Semester</th>
                        <th>Status</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {visibleSubjects.map((subject) => (
                        <tr key={subject.id}>
                          <td className="subject-code-cell">{subject.code}</td>
                          <td>{subject.title}</td>
                          <td>{subject.credit_hours}</td>
                          <td>{subject.semester}</td>
                          <td>
                            <span className={`status-pill ${subject.is_active ? 'status-active' : 'status-inactive'}`}>
                              {subject.is_active ? 'Active' : 'Inactive'}
                            </span>
                          </td>
                          <td>
                            <div className="row-actions">
                              <button
                                type="button"
                                className="text-button"
                                onClick={() => editSubject(subject)}
                                aria-label={`Edit ${subject.code}`}
                              >
                                <Pencil size={14} /> Edit
                              </button>
                              <button
                                type="button"
                                className="text-button"
                                disabled={busy}
                                onClick={() => toggleSubjectStatus(subject)}
                              >
                                {subject.is_active ? 'Deactivate' : 'Activate'}
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {visibleSubjects.length === 0 && (
                    <div className="empty-state">
                      {subjects.length ? 'No subjects match this search.' : 'No curriculum subjects have been created.'}
                    </div>
                  )}
                </div>
              </div>
            </>
          )}

          {activeTab === 'allocations' && (
            <>
              <div className="panel">
                <div className="panel-heading">
                  <div>
                    <h2 className="section-title">Allocate subject to faculty</h2>
                    <p className="page-description">Assign an active course to a faculty member using the shared semester and academic session above.</p>
                  </div>
                </div>
                <form className="form-stack" onSubmit={submitAllocation}>
                  <div className="field-grid">
                    <label className="field-label" htmlFor="allocation-subject">
                      Subject
                      <select
                        id="allocation-subject"
                        className="text-input"
                        value={allocationSubjectId}
                        onChange={(event) => setAllocationSubjectId(event.target.value)}
                        required
                      >
                        <option value="">Select a subject</option>
                        {scopedSubjects.map((subject) => (
                          <option key={subject.id} value={subject.id}>{subject.code} · {subject.title}</option>
                        ))}
                      </select>
                    </label>
                    <label className="field-label" htmlFor="allocation-faculty">
                      Faculty member
                      <select
                        id="allocation-faculty"
                        className="text-input"
                        value={allocationFacultyId}
                        onChange={(event) => setAllocationFacultyId(event.target.value)}
                        required
                      >
                        <option value="">Select faculty</option>
                        {activeFaculty.map((member) => (
                          <option key={member.id} value={member.id}>
                            {member.user?.full_name || `Faculty profile ${member.id}`}
                            {member.department?.name ? ` · ${member.department.name}` : ''}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="field-label" htmlFor="allocation-section">
                      Section
                      <select
                        id="allocation-section"
                        className="text-input"
                        value={allocationSection}
                        onChange={(event) => setAllocationSection(event.target.value)}
                      >
                        {SECTIONS.map((section) => <option key={section} value={section}>Section {section}</option>)}
                      </select>
                    </label>
                  </div>
                  <div className="subject-form-actions">
                    <button
                      type="submit"
                      className="primary-button"
                      disabled={busy || !scopedSubjects.length || !activeFaculty.length || !hasAcademicSession}
                    >
                      {busy ? 'Saving…' : 'Save allocation'}
                    </button>
                    {!activeFaculty.length && (
                      <span className="form-hint">
                        {isSuperAdmin
                          ? 'Create faculty accounts from Faculty management before allocating subjects.'
                          : 'No active faculty accounts are available in the shared directory yet.'}
                      </span>
                    )}
                  </div>
                </form>
              </div>

              <div className="panel">
                <div className="panel-heading">
                  <div>
                    <h2 className="section-title">Faculty teaching allocations</h2>
                    <p className="page-description">Current subject, instructor, academic session, and section assignments.</p>
                  </div>
                  <span className="record-count">{scopedAllocations.length} allocations in this scope</span>
                </div>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr><th>Subject</th><th>Faculty</th><th>Academic session</th><th>Section</th><th>Action</th></tr>
                    </thead>
                    <tbody>
                      {scopedAllocations.map((allocation) => (
                        <tr key={allocation.id}>
                          <td>
                            <span className="subject-code-cell">{allocation.subject?.code}</span>
                            <span className="table-secondary">{allocation.subject?.title}</span>
                          </td>
                          <td>{allocation.faculty?.user?.full_name || `Faculty profile ${allocation.faculty_id}`}</td>
                          <td>{allocation.academic_session}</td>
                          <td>{allocation.section}</td>
                          <td>
                            <button
                              type="button"
                              className="text-button"
                              disabled={busy}
                              onClick={() => removeAllocation(allocation)}
                            >
                              Remove / reassign
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {scopedAllocations.length === 0 && <div className="empty-state">No faculty allocations have been recorded for this semester and session.</div>}
                </div>
              </div>
            </>
          )}

          {activeTab === 'enrollment' && (
            <div className="panel">
              <div className="panel-heading">
                <div>
                  <h2 className="section-title">Enroll students in a subject</h2>
                  <p className="page-description">
                    Choose a course and section in the shared semester and academic session, then select students individually or all at once.
                  </p>
                </div>
              </div>
              <form className="form-stack enrollment-form" onSubmit={submitEnrollment}>
                <div className="field-grid">
                  <label className="field-label" htmlFor="enrollment-subject">
                    Subject
                    <select
                      id="enrollment-subject"
                      className="text-input"
                      value={enrollmentSubjectId}
                      onChange={(event) => {
                        setEnrollmentSubjectId(event.target.value);
                        loadStudents(event.target.value, enrollmentSection);
                      }}
                      required
                    >
                      <option value="">Select a subject</option>
                      {scopedSubjects.map((subject) => (
                        <option key={subject.id} value={subject.id}>
                          Semester {subject.semester} · {subject.code} · {subject.title}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="field-label" htmlFor="enrollment-section">
                    Student section
                    <select
                      id="enrollment-section"
                      className="text-input"
                      value={enrollmentSection}
                      onChange={(event) => {
                        setEnrollmentSection(event.target.value);
                        loadStudents(enrollmentSubjectId, event.target.value);
                      }}
                    >
                      {SECTIONS.map((section) => <option key={section} value={section}>Section {section}</option>)}
                    </select>
                  </label>
                </div>

                <div className="student-picker">
                  <div className="student-picker-heading">
                    <div>
                      <h3 className="section-title">Semester cohort</h3>
                      <p className="page-description">
                        {enrollmentSubject
                          ? `Semester ${enrollmentSubject.semester} · Section ${enrollmentSection}`
                          : 'Choose a subject to load eligible students.'}
                      </p>
                    </div>
                    <span className="record-count">
                      {studentsLoading ? 'Loading…' : `${eligibleStudents.length} students`}
                    </span>
                  </div>
                  {eligibleStudents.length > 0 && (
                    <label className="student-select-all">
                      <input
                        type="checkbox"
                        checked={selectedStudentIds.length === eligibleStudents.length}
                        onChange={(event) => selectAllStudents(event.target.checked)}
                      />
                      Select all students in this section
                    </label>
                  )}
                  <div className="student-list" aria-live="polite">
                    {studentsLoading ? (
                      <div className="empty-state">Loading students…</div>
                    ) : eligibleStudents.map((student) => (
                      <label key={student.id} className="student-option">
                        <input
                          type="checkbox"
                          checked={selectedStudentIds.includes(student.id)}
                          onChange={() => toggleStudent(student.id)}
                        />
                        <span className="student-option-details">
                          <strong>{student.user?.full_name || 'Student'}</strong>
                          <span>{student.roll_number} · {student.reg_number}</span>
                        </span>
                      </label>
                    ))}
                    {!studentsLoading && enrollmentSubject && eligibleStudents.length === 0 && (
                      <div className="empty-state">No active students found in this semester and section.</div>
                    )}
                  </div>
                </div>
                <div className="subject-form-actions">
                  <span className="form-hint">{selectedStudentIds.length} student(s) selected</span>
                  <button
                    type="submit"
                    className="primary-button"
                    disabled={busy || studentsLoading || selectedStudentIds.length === 0 || !hasAcademicSession}
                  >
                    {busy ? 'Saving…' : 'Save enrollments'}
                  </button>
                </div>
              </form>
            </div>
          )}
        </>
      )}
    </section>
  );
}
