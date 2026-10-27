import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertCircle,
  BookOpenCheck,
  CalendarCheck,
  CheckCircle2,
  ClipboardList,
  FileText,
  GraduationCap,
  Save,
  Sparkles,
} from 'lucide-react';
import api, { getApiErrorMessage } from '../services/api';

const today = new Date().toISOString().slice(0, 10);
const TABS = [
  { id: 'attendance', label: 'Attendance', icon: CalendarCheck },
  { id: 'assignments', label: 'Assignments', icon: FileText },
  { id: 'quizzes', label: 'Quizzes', icon: ClipboardList },
  { id: 'marks', label: 'Mid-term & presentation', icon: GraduationCap },
  { id: 'results', label: 'Internal result', icon: Sparkles },
];

const identity = (subject) => `${subject.subject_id}:${subject.academic_session}:${subject.section}`;
const classParams = (subject) => ({
  academic_session: subject.academic_session,
  section: subject.section,
});

export default function FacultyAcademic() {
  const [subjects, setSubjects] = useState([]);
  const [selectedKey, setSelectedKey] = useState('');
  const [activeTab, setActiveTab] = useState('attendance');
  const [notice, setNotice] = useState(null);
  const [loadingSubjects, setLoadingSubjects] = useState(true);
  const [loadingData, setLoadingData] = useState(false);
  const [saving, setSaving] = useState(false);
  const [roster, setRoster] = useState([]);
  const [attendanceDate, setAttendanceDate] = useState(today);
  const [assignments, setAssignments] = useState([]);
  const [assignmentForm, setAssignmentForm] = useState({
    title: '',
    description: '',
    due_date: '',
  });
  const [selectedAssignmentId, setSelectedAssignmentId] = useState('');
  const [submissions, setSubmissions] = useState([]);
  const [submissionMarks, setSubmissionMarks] = useState({});
  const [quizzes, setQuizzes] = useState([]);
  const [quizForm, setQuizForm] = useState({
    title: '',
    description: '',
    quiz_date: today,
  });
  const [selectedQuizId, setSelectedQuizId] = useState('');
  const [quizMarks, setQuizMarks] = useState({});
  const [midTermMarks, setMidTermMarks] = useState({});
  const [presentationMarks, setPresentationMarks] = useState({});
  const [presentationTopics, setPresentationTopics] = useState({});
  const [results, setResults] = useState([]);

  const selectedSubject = useMemo(
    () => subjects.find((subject) => identity(subject) === selectedKey),
    [subjects, selectedKey],
  );
  const selectedQuiz = quizzes.find((quiz) => String(quiz.id) === selectedQuizId);

  useEffect(() => {
    let mounted = true;
    api.get('/subjects/my-subjects')
      .then((response) => {
        if (!mounted) return;
        const assignedSubjects = response.data
          .filter((subject) => subject.role === 'instructor')
          .sort((left, right) => (
            left.academic_session.localeCompare(right.academic_session)
            || left.semester - right.semester
            || left.code.localeCompare(right.code)
            || left.section.localeCompare(right.section)
          ));
        setSubjects(assignedSubjects);
        if (assignedSubjects.length) setSelectedKey(identity(assignedSubjects[0]));
      })
      .catch((error) => {
        if (mounted) setNotice({ type: 'error', message: getApiErrorMessage(error) });
      })
      .finally(() => {
        if (mounted) setLoadingSubjects(false);
      });
    return () => { mounted = false; };
  }, []);

  const loadAttendanceRoster = useCallback(async (subject, date = attendanceDate) => {
    const response = await api.get(`/attendance/subject/${subject.subject_id}/roster`, {
      params: { ...classParams(subject), attendance_date: date },
    });
    setRoster(response.data.map((student) => ({
      ...student,
      attendance_status: student.attendance_status || 'Present',
    })));
  }, [attendanceDate]);

  const loadMarksRoster = useCallback(async (subject) => {
    const [rosterResponse, midResponse, presentationResponse] = await Promise.all([
      api.get(`/attendance/subject/${subject.subject_id}/roster`, { params: classParams(subject) }),
      api.get(`/marks/mid-term/subject/${subject.subject_id}`, {
        params: { academic_session: subject.academic_session },
      }),
      api.get(`/marks/presentation/subject/${subject.subject_id}`, {
        params: { academic_session: subject.academic_session },
      }),
    ]);
    setRoster(rosterResponse.data);
    setMidTermMarks(Object.fromEntries(midResponse.data.map((item) => [
      item.student_id,
      String(item.obtained_marks),
    ])));
    setPresentationMarks(Object.fromEntries(presentationResponse.data.map((item) => [
      item.student_id,
      String(item.obtained_marks),
    ])));
    setPresentationTopics(Object.fromEntries(presentationResponse.data.map((item) => [
      item.student_id,
      item.topic || '',
    ])));
  }, []);

  const loadAssignments = useCallback(async (subject) => {
    const response = await api.get(`/assignments/subject/${subject.subject_id}`, {
      params: { academic_session: subject.academic_session },
    });
    setAssignments(response.data);
  }, []);

  const loadQuizzes = useCallback(async (subject) => {
    const response = await api.get(`/quizzes/subject/${subject.subject_id}`, {
      params: { academic_session: subject.academic_session },
    });
    setQuizzes(response.data);
  }, []);

  const loadResults = useCallback(async (subject) => {
    const response = await api.get(`/results/subject/${subject.subject_id}`, {
      params: classParams(subject),
    });
    setResults(response.data);
  }, []);

  useEffect(() => {
    if (!selectedSubject) return undefined;
    let mounted = true;
    const load = async () => {
      try {
        if (activeTab === 'attendance') await loadAttendanceRoster(selectedSubject);
        if (activeTab === 'assignments') await loadAssignments(selectedSubject);
        if (activeTab === 'quizzes') await loadQuizzes(selectedSubject);
        if (activeTab === 'marks') await loadMarksRoster(selectedSubject);
        if (activeTab === 'results') await loadResults(selectedSubject);
      } catch (error) {
        if (mounted) setNotice({ type: 'error', message: getApiErrorMessage(error) });
      } finally {
        if (mounted) setLoadingData(false);
      }
    };
    load();
    return () => { mounted = false; };
  }, [
    activeTab,
    selectedKey,
    selectedSubject,
    loadAttendanceRoster,
    loadAssignments,
    loadQuizzes,
    loadMarksRoster,
    loadResults,
  ]);

  const reloadActiveTab = async () => {
    if (!selectedSubject) return;
    setLoadingData(true);
    try {
      if (activeTab === 'attendance') await loadAttendanceRoster(selectedSubject);
      if (activeTab === 'assignments') await loadAssignments(selectedSubject);
      if (activeTab === 'quizzes') await loadQuizzes(selectedSubject);
      if (activeTab === 'marks') await loadMarksRoster(selectedSubject);
      if (activeTab === 'results') await loadResults(selectedSubject);
    } catch (error) {
      setNotice({ type: 'error', message: getApiErrorMessage(error) });
      return false;
    } finally {
      setLoadingData(false);
    }
    return true;
  };

  const runSave = async (action, successMessage) => {
    setSaving(true);
    setNotice(null);
    try {
      await action();
      if (await reloadActiveTab()) {
        setNotice({ type: 'success', message: successMessage });
      }
    } catch (error) {
      setNotice({ type: 'error', message: getApiErrorMessage(error) });
    } finally {
      setSaving(false);
    }
  };

  const submitAttendance = (event) => {
    event.preventDefault();
    runSave(async () => {
      await api.post('/attendance/bulk', {
        subject_id: selectedSubject.subject_id,
        academic_session: selectedSubject.academic_session,
        section: selectedSubject.section,
        date: attendanceDate,
        records: roster.map((student) => ({
          student_id: student.student_id,
          status: student.attendance_status,
        })),
      });
    }, `Attendance saved for ${roster.length} students.`);
  };

  const submitAssignment = (event) => {
    event.preventDefault();
    runSave(async () => {
      await api.post('/assignments/', {
        subject_id: selectedSubject.subject_id,
        academic_session: selectedSubject.academic_session,
        title: assignmentForm.title.trim(),
        description: assignmentForm.description.trim() || null,
        max_marks: 5,
        due_date: new Date(assignmentForm.due_date).toISOString(),
      });
      setAssignmentForm({ title: '', description: '', due_date: '' });
    }, 'Assignment created with a maximum of 5 marks.');
  };

  const openSubmissions = async (assignment) => {
    setSelectedAssignmentId(String(assignment.id));
    setNotice(null);
    try {
      const response = await api.get(`/assignments/${assignment.id}/submissions`);
      setSubmissions(response.data);
      setSubmissionMarks(Object.fromEntries(response.data
        .filter((submission) => submission.obtained_marks !== null)
        .map((submission) => [submission.id, String(submission.obtained_marks)])));
    } catch (error) {
      setNotice({ type: 'error', message: getApiErrorMessage(error) });
    }
  };

  const saveSubmissionGrade = (submissionId) => {
    const value = submissionMarks[submissionId];
    if (value === undefined || value === '') {
      setNotice({ type: 'error', message: 'Enter a mark from 0 to 5 before saving.' });
      return;
    }
    runSave(async () => {
      await api.post(`/assignments/submissions/${submissionId}/grade`, {
        obtained_marks: Number(value),
      });
      await openSubmissions(assignments.find((item) => String(item.id) === selectedAssignmentId));
    }, 'Assignment grade saved.');
  };

  const submitQuiz = (event) => {
    event.preventDefault();
    runSave(async () => {
      const response = await api.post('/quizzes/', {
        subject_id: selectedSubject.subject_id,
        academic_session: selectedSubject.academic_session,
        title: quizForm.title.trim(),
        description: quizForm.description.trim() || null,
        max_marks: 5,
        quiz_date: quizForm.quiz_date,
      });
      setQuizForm({ title: '', description: '', quiz_date: today });
      setSelectedQuizId(String(response.data.id));
    }, 'Quiz scheduled with a maximum of 5 marks.');
  };

  const openQuizMarks = async (quiz) => {
    setSelectedQuizId(String(quiz.id));
    setNotice(null);
    try {
      const [rosterResponse, marksResponse] = await Promise.all([
        api.get(`/attendance/subject/${selectedSubject.subject_id}/roster`, {
          params: classParams(selectedSubject),
        }),
        api.get(`/quizzes/${quiz.id}/marks`),
      ]);
      setRoster(rosterResponse.data);
      setQuizMarks(Object.fromEntries(marksResponse.data.map((item) => [
        item.student_id,
        String(item.obtained_marks),
      ])));
    } catch (error) {
      setNotice({ type: 'error', message: getApiErrorMessage(error) });
    }
  };

  const submitQuizMarks = (event) => {
    event.preventDefault();
    const marks = roster
      .filter((student) => quizMarks[student.student_id] !== undefined && quizMarks[student.student_id] !== '')
      .map((student) => ({
        student_id: student.student_id,
        obtained_marks: Number(quizMarks[student.student_id]),
      }));
    if (!marks.length) {
      setNotice({ type: 'error', message: 'Enter marks for at least one student.' });
      return;
    }
    runSave(async () => {
      await api.post(`/quizzes/${selectedQuizId}/marks/bulk`, { marks });
    }, `Quiz marks saved for ${marks.length} students.`);
  };

  const submitMarks = (event, kind) => {
    event.preventDefault();
    const source = kind === 'mid-term' ? midTermMarks : presentationMarks;
    const records = roster
      .filter((student) => source[student.student_id] !== undefined && source[student.student_id] !== '')
      .map((student) => ({
        student_id: student.student_id,
        obtained_marks: Number(source[student.student_id]),
        ...(kind === 'presentation' ? {
          topic: presentationTopics[student.student_id]?.trim() || null,
        } : {}),
      }));
    if (!records.length) {
      setNotice({ type: 'error', message: 'Enter marks for at least one student.' });
      return;
    }
    runSave(async () => {
      const endpoint = kind === 'mid-term' ? '/marks/mid-term/bulk' : '/marks/presentation/bulk';
      await api.post(endpoint, {
        subject_id: selectedSubject.subject_id,
        academic_session: selectedSubject.academic_session,
        records,
      });
    }, `${kind === 'mid-term' ? 'Mid-term' : 'Presentation'} marks saved for ${records.length} students.`);
  };

  const calculateResults = () => {
    runSave(async () => {
      const response = await api.post('/results/calculate', {
        subject_id: selectedSubject.subject_id,
        academic_session: selectedSubject.academic_session,
        section: selectedSubject.section,
      });
      setResults(response.data);
    }, 'Internal results calculated using the 40-mark formula.');
  };

  const updateAttendance = (studentId, status) => {
    setRoster((current) => current.map((student) =>
      student.student_id === studentId ? { ...student, attendance_status: status } : student,
    ));
  };

  const updateNumber = (setter, studentId, value) => {
    setter((current) => ({ ...current, [studentId]: value }));
  };

  const renderMarksTable = (kind) => {
    const isMidTerm = kind === 'mid-term';
    const values = isMidTerm ? midTermMarks : presentationMarks;
    const setter = isMidTerm ? setMidTermMarks : setPresentationMarks;
    const max = isMidTerm ? 20 : 5;
    return (
      <form className="faculty-tool-form" onSubmit={(event) => submitMarks(event, kind)}>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Student</th>
                <th>Roll number</th>
                {!isMidTerm && <th>Presentation topic</th>}
                <th>Marks / {max}</th>
              </tr>
            </thead>
            <tbody>
              {roster.map((student) => (
                <tr key={student.student_id}>
                  <td>{student.full_name}</td>
                  <td>{student.roll_number}</td>
                  {!isMidTerm && (
                    <td>
                      <input
                        className="text-input marks-input"
                        value={presentationTopics[student.student_id] || ''}
                        onChange={(event) => updateNumber(setPresentationTopics, student.student_id, event.target.value)}
                        maxLength="200"
                        aria-label={`Presentation topic for ${student.full_name}`}
                      />
                    </td>
                  )}
                  <td>
                    <input
                      className="text-input marks-input"
                      type="number"
                      min="0"
                      max={max}
                      step="0.5"
                      value={values[student.student_id] ?? ''}
                      onChange={(event) => updateNumber(setter, student.student_id, event.target.value)}
                      aria-label={`${kind} marks for ${student.full_name}`}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {roster.length === 0 && <div className="empty-state">No students are enrolled in this class for the selected session.</div>}
        </div>
        <div className="subject-form-actions">
          <span className="form-hint">Enter 0–{max} marks. Blank cells are left unchanged.</span>
          <button type="submit" className="primary-button" disabled={saving || !roster.length}>
            <Save size={15} /> {saving ? 'Saving…' : `Save ${isMidTerm ? 'mid-term' : 'presentation'} marks`}
          </button>
        </div>
      </form>
    );
  };

  return (
    <section className="page-stack faculty-academic-page">
      <div className="faculty-academic-heading">
        <div>
          <p className="eyebrow">Teaching workspace</p>
          <h1 className="page-title">Academic tools</h1>
          <p className="page-description">Daily attendance, assessment setup, marks entry, and internal result calculation for your allocated classes.</p>
        </div>
        <div className="faculty-class-select">
          <label className="field-label" htmlFor="faculty-class">
            Allocated subject / class
            <select
              id="faculty-class"
              className="text-input"
              value={selectedKey}
              onChange={(event) => {
                setSelectedKey(event.target.value);
                setSelectedAssignmentId('');
                setSelectedQuizId('');
                setLoadingData(true);
                setNotice(null);
              }}
              disabled={loadingSubjects || !subjects.length}
            >
              {subjects.map((subject) => (
                <option key={identity(subject)} value={identity(subject)}>
                  {subject.code} · {subject.title} · {subject.academic_session} · Section {subject.section}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>

      {notice && (
        <div className={`notice notice-${notice.type}`} role="status" aria-live="polite">
          {notice.type === 'error' ? <AlertCircle size={18} /> : <CheckCircle2 size={18} />}
          <span>{notice.message}</span>
        </div>
      )}

      {loadingSubjects ? (
        <div className="panel empty-state">Loading allocated subjects…</div>
      ) : subjects.length === 0 ? (
        <div className="panel faculty-no-allocations">
          <BookOpenCheck size={25} />
          <h2 className="section-title">No subjects allocated yet</h2>
          <p className="page-description">Ask the HOD or Super Admin to assign you a subject, academic session, and section.</p>
        </div>
      ) : (
        <>
          {selectedSubject && (
            <div className="faculty-class-summary">
              <span><strong>{selectedSubject.code}</strong> {selectedSubject.title}</span>
              <span>Semester {selectedSubject.semester}</span>
              <span>{selectedSubject.academic_session}</span>
              <span>Section {selectedSubject.section}</span>
            </div>
          )}
          <nav className="subject-tabs faculty-tool-tabs" aria-label="Faculty academic tools">
            {TABS.map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                type="button"
                className={`subject-tab ${activeTab === id ? 'subject-tab-active' : ''}`}
                aria-current={activeTab === id ? 'page' : undefined}
                onClick={() => { setLoadingData(true); setActiveTab(id); setNotice(null); }}
              >
                <Icon size={16} />
                {label}
              </button>
            ))}
          </nav>

          {loadingData ? (
            <div className="panel empty-state">Loading class records…</div>
          ) : (
            <>
              {activeTab === 'attendance' && selectedSubject && (
                <div className="panel">
                  <div className="panel-heading">
                    <div>
                      <h2 className="section-title">Class attendance</h2>
                      <p className="page-description">Attendance percentage is calculated from recorded lectures for this academic session.</p>
                    </div>
                  </div>
                  <form className="faculty-tool-form" onSubmit={submitAttendance}>
                    <label className="field-label attendance-date-field" htmlFor="attendance-date">
                      Class date
                      <input
                        id="attendance-date"
                        className="text-input"
                        type="date"
                        value={attendanceDate}
                        onChange={(event) => {
                          setLoadingData(true);
                          setAttendanceDate(event.target.value);
                        }}
                        required
                      />
                    </label>
                    <div className="table-wrap">
                      <table>
                        <thead>
                          <tr><th>Student</th><th>Roll number</th><th>Attendance</th><th>Present</th><th>Sessions</th><th>Percentage</th></tr>
                        </thead>
                        <tbody>
                          {roster.map((student) => (
                            <tr key={student.student_id}>
                              <td>{student.full_name}</td>
                              <td>{student.roll_number}</td>
                              <td>
                                <select
                                  className="text-input attendance-status-select"
                                  value={student.attendance_status}
                                  onChange={(event) => updateAttendance(student.student_id, event.target.value)}
                                  aria-label={`Attendance status for ${student.full_name}`}
                                >
                                  <option value="Present">Present</option>
                                  <option value="Absent">Absent</option>
                                  <option value="Leave">Leave</option>
                                </select>
                              </td>
                              <td>{student.present_count}</td>
                              <td>{student.total_lectures}</td>
                              <td>{student.attendance_percentage}%</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      {roster.length === 0 && <div className="empty-state">No enrolled students found for this subject, session, and section.</div>}
                    </div>
                    <div className="subject-form-actions">
                      <span className="form-hint">{roster.length} enrolled student(s)</span>
                      <button type="submit" className="primary-button" disabled={saving || !roster.length}>
                        <Save size={15} /> {saving ? 'Saving…' : 'Save attendance'}
                      </button>
                    </div>
                  </form>
                </div>
              )}

              {activeTab === 'assignments' && selectedSubject && (
                <div className="panel">
                  <div className="panel-heading">
                    <div>
                      <h2 className="section-title">Create assignment</h2>
                      <p className="page-description">Assignments contribute a combined maximum of 5 marks to the internal result.</p>
                    </div>
                  </div>
                  <form className="form-stack faculty-tool-form" onSubmit={submitAssignment}>
                    <div className="field-grid">
                      <label className="field-label" htmlFor="assignment-title">
                        Assignment title
                        <input
                          id="assignment-title"
                          className="text-input"
                          value={assignmentForm.title}
                          onChange={(event) => setAssignmentForm((current) => ({ ...current, title: event.target.value }))}
                          maxLength="180"
                          required
                        />
                      </label>
                      <label className="field-label" htmlFor="assignment-due-date">
                        Due date and time
                        <input
                          id="assignment-due-date"
                          className="text-input"
                          type="datetime-local"
                          value={assignmentForm.due_date}
                          onChange={(event) => setAssignmentForm((current) => ({ ...current, due_date: event.target.value }))}
                          required
                        />
                      </label>
                    </div>
                    <label className="field-label" htmlFor="assignment-description">
                      Instructions
                      <textarea
                        id="assignment-description"
                        className="text-input textarea-input"
                        rows="3"
                        value={assignmentForm.description}
                        onChange={(event) => setAssignmentForm((current) => ({ ...current, description: event.target.value }))}
                      />
                    </label>
                    <div className="subject-form-actions">
                      <span className="form-hint">Maximum marks: 5 (fixed)</span>
                      <button type="submit" className="primary-button" disabled={saving}>
                        <FileText size={15} /> {saving ? 'Creating…' : 'Create assignment'}
                      </button>
                    </div>
                  </form>

                  <div className="faculty-records-section">
                    <div className="panel-heading">
                      <h3 className="section-title">Assignments</h3>
                      <span className="record-count">{assignments.length} total</span>
                    </div>
                    {assignments.map((assignment) => (
                      <article key={assignment.id} className="academic-record-card">
                        <div>
                          <strong>{assignment.title}</strong>
                          <span>Due {new Date(assignment.due_date).toLocaleString()} · Max {assignment.max_marks} marks · {assignment.submissions_count || 0} submissions</span>
                        </div>
                        <button type="button" className="secondary-button" onClick={() => openSubmissions(assignment)}>
                          Review submissions
                        </button>
                      </article>
                    ))}
                    {assignments.length === 0 && <div className="empty-state">No assignments have been created for this subject and session.</div>}
                    {selectedAssignmentId && (
                      <div className="submission-review">
                        <h3 className="section-title">Submitted work</h3>
                        {submissions.map((submission) => (
                          <div className="submission-row" key={submission.id}>
                            <span>
                              <strong>{submission.student?.user?.full_name || 'Student'}</strong>
                              <small>{submission.student?.roll_number} · {submission.original_filename}</small>
                            </span>
                            <input
                              className="text-input marks-input"
                              type="number"
                              min="0"
                              max="5"
                              step="0.5"
                              value={submissionMarks[submission.id] ?? ''}
                              onChange={(event) => updateNumber(setSubmissionMarks, submission.id, event.target.value)}
                              aria-label={`Assignment marks for ${submission.student?.user?.full_name || 'student'}`}
                            />
                            <button type="button" className="secondary-button" disabled={saving} onClick={() => saveSubmissionGrade(submission.id)}>
                              Save grade
                            </button>
                          </div>
                        ))}
                        {submissions.length === 0 && <div className="empty-state">No submissions have been received for this assignment.</div>}
                      </div>
                    )}
                  </div>
                </div>
              )}

              {activeTab === 'quizzes' && selectedSubject && (
                <div className="panel">
                  <div className="panel-heading">
                    <div>
                      <h2 className="section-title">Create quiz</h2>
                      <p className="page-description">Enter quiz marks after the assessment; quiz marks contribute a combined maximum of 5.</p>
                    </div>
                  </div>
                  <form className="form-stack faculty-tool-form" onSubmit={submitQuiz}>
                    <div className="field-grid">
                      <label className="field-label" htmlFor="quiz-title">
                        Quiz title
                        <input
                          id="quiz-title"
                          className="text-input"
                          value={quizForm.title}
                          onChange={(event) => setQuizForm((current) => ({ ...current, title: event.target.value }))}
                          maxLength="180"
                          required
                        />
                      </label>
                      <label className="field-label" htmlFor="quiz-date">
                        Quiz date
                        <input
                          id="quiz-date"
                          className="text-input"
                          type="date"
                          value={quizForm.quiz_date}
                          onChange={(event) => setQuizForm((current) => ({ ...current, quiz_date: event.target.value }))}
                          required
                        />
                      </label>
                    </div>
                    <label className="field-label" htmlFor="quiz-description">
                      Notes
                      <textarea
                        id="quiz-description"
                        className="text-input textarea-input"
                        rows="2"
                        value={quizForm.description}
                        onChange={(event) => setQuizForm((current) => ({ ...current, description: event.target.value }))}
                      />
                    </label>
                    <div className="subject-form-actions">
                      <span className="form-hint">Maximum marks: 5 (fixed)</span>
                      <button type="submit" className="primary-button" disabled={saving}>
                        <ClipboardList size={15} /> {saving ? 'Creating…' : 'Create quiz'}
                      </button>
                    </div>
                  </form>
                  <div className="faculty-records-section">
                    <div className="panel-heading">
                      <h3 className="section-title">Quizzes</h3>
                      <span className="record-count">{quizzes.length} total</span>
                    </div>
                    {quizzes.map((quiz) => (
                      <article key={quiz.id} className="academic-record-card">
                        <div>
                          <strong>{quiz.title}</strong>
                          <span>{quiz.quiz_date} · Max {quiz.max_marks} marks</span>
                        </div>
                        <button type="button" className="secondary-button" onClick={() => openQuizMarks(quiz)}>
                          Enter marks
                        </button>
                      </article>
                    ))}
                    {quizzes.length === 0 && <div className="empty-state">No quizzes have been scheduled for this subject and session.</div>}
                    {selectedQuizId && selectedQuiz && (
                      <form className="quiz-marks-form" onSubmit={submitQuizMarks}>
                        <h3 className="section-title">Marks: {selectedQuiz.title} (out of 5)</h3>
                        <div className="table-wrap">
                          <table>
                            <thead><tr><th>Student</th><th>Roll number</th><th>Marks / 5</th></tr></thead>
                            <tbody>
                              {roster.map((student) => (
                                <tr key={student.student_id}>
                                  <td>{student.full_name}</td>
                                  <td>{student.roll_number}</td>
                                  <td>
                                    <input
                                      className="text-input marks-input"
                                      type="number"
                                      min="0"
                                      max="5"
                                      step="0.5"
                                      value={quizMarks[student.student_id] ?? ''}
                                      onChange={(event) => updateNumber(setQuizMarks, student.student_id, event.target.value)}
                                      aria-label={`Quiz marks for ${student.full_name}`}
                                    />
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                          {roster.length === 0 && <div className="empty-state">No enrolled students to assess.</div>}
                        </div>
                        <div className="subject-form-actions">
                          <span className="form-hint">Blank scores are left unchanged.</span>
                          <button type="submit" className="primary-button" disabled={saving || !roster.length}>
                            <Save size={15} /> {saving ? 'Saving…' : 'Save quiz marks'}
                          </button>
                        </div>
                      </form>
                    )}
                  </div>
                </div>
              )}

              {activeTab === 'marks' && selectedSubject && (
                <div className="page-stack">
                  <div className="panel">
                    <div className="panel-heading">
                      <div>
                        <h2 className="section-title">Mid-term examination</h2>
                        <p className="page-description">Marks are limited to 0–20. Blank rows are not changed.</p>
                      </div>
                    </div>
                    {renderMarksTable('mid-term')}
                  </div>
                  <div className="panel">
                    <div className="panel-heading">
                      <div>
                        <h2 className="section-title">Presentation</h2>
                        <p className="page-description">Marks are limited to 0–5. The topic is optional.</p>
                      </div>
                    </div>
                    {renderMarksTable('presentation')}
                  </div>
                </div>
              )}

              {activeTab === 'results' && selectedSubject && (
                <div className="panel">
                  <div className="panel-heading">
                    <div>
                      <h2 className="section-title">Internal result · 40 marks</h2>
                      <p className="page-description">Mid-term /20 + assignment /5 + quiz /5 + presentation /5 + attendance /5.</p>
                    </div>
                    <button type="button" className="primary-button" disabled={saving} onClick={calculateResults}>
                      <Sparkles size={15} /> {saving ? 'Calculating…' : 'Calculate / refresh results'}
                    </button>
                  </div>
                  <div className="table-wrap">
                    <table className="result-table">
                      <thead>
                        <tr>
                          <th>Student</th><th>Roll number</th><th>Mid /20</th><th>Assignments /5</th><th>Quizzes /5</th><th>Presentation /5</th><th>Attendance /5</th><th>Total /40</th>
                        </tr>
                      </thead>
                      <tbody>
                        {results.map((result) => (
                          <tr key={result.id}>
                            <td>{result.student?.user?.full_name || 'Student'}</td>
                            <td>{result.student?.roll_number || '—'}</td>
                            <td>{result.mid_paper_marks}</td>
                            <td>{result.assignment_marks}</td>
                            <td>{result.quiz_marks}</td>
                            <td>{result.presentation_marks}</td>
                            <td>
                              {result.attendance_marks}
                              <span className="table-secondary">{result.attendance_percentage}%</span>
                            </td>
                            <td className="result-total">{result.total_internal}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    {results.length === 0 && <div className="empty-state">Calculate the result to generate the award list for enrolled students.</div>}
                  </div>
                </div>
              )}
            </>
          )}
        </>
      )}
    </section>
  );
}
