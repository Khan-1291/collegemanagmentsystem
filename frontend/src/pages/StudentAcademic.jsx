import { useCallback, useEffect, useMemo, useState } from 'react';
import { AlertCircle, CalendarCheck, CheckCircle2, Clock3, FileUp, GraduationCap, RefreshCw } from 'lucide-react';
import api, { getApiErrorMessage } from '../services/api';

const initialData = {
  subjects: [],
  attendance: [],
  assignments: [],
  submissions: [],
  quizzes: [],
  quizMarks: [],
  marks: [],
  results: [],
};

const formatDate = (value) => (value ? new Date(value).toLocaleString() : '—');

const fetchStudentAcademicRecords = async () => {
  const [
    subjectsResponse,
    attendanceResponse,
    submissionsResponse,
    quizMarksResponse,
    marksResponse,
    resultsResponse,
  ] = await Promise.all([
    api.get('/subjects/my-subjects'),
    api.get('/attendance/my-attendance'),
    api.get('/assignments/my-submissions'),
    api.get('/quizzes/my-marks'),
    api.get('/marks/my-marks'),
    api.get('/results/my-results'),
  ]);
  const subjects = subjectsResponse.data.filter(
    (subject) => subject.role === 'student' && subject.status === 'enrolled',
  );
  const courseWork = await Promise.all(subjects.map(async (subject) => {
    const params = { academic_session: subject.academic_session };
    const [assignmentsResponse, quizzesResponse] = await Promise.all([
      api.get(`/assignments/subject/${subject.subject_id}`, { params }),
      api.get(`/quizzes/subject/${subject.subject_id}`, { params }),
    ]);
    return {
      assignments: assignmentsResponse.data,
      quizzes: quizzesResponse.data,
    };
  }));

  return {
    subjects,
    attendance: attendanceResponse.data.subjects || [],
    assignments: courseWork.flatMap((course) => course.assignments),
    submissions: submissionsResponse.data,
    quizzes: courseWork.flatMap((course) => course.quizzes),
    quizMarks: quizMarksResponse.data,
    marks: marksResponse.data.subjects || [],
    results: resultsResponse.data,
  };
};

export default function StudentAcademic() {
  const [data, setData] = useState(initialData);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState(null);
  const [selectedFiles, setSelectedFiles] = useState({});
  const [submittingAssignment, setSubmittingAssignment] = useState(null);

  useEffect(() => {
    let active = true;
    fetchStudentAcademicRecords()
      .then((records) => {
        if (active) setData(records);
      })
      .catch((requestError) => {
        if (active) setError(getApiErrorMessage(requestError));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, []);

  const refreshRecords = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      setData(await fetchStudentAcademicRecords());
    } catch (requestError) {
      setError(getApiErrorMessage(requestError));
    } finally {
      setLoading(false);
    }
  }, []);

  const submissionByAssignment = useMemo(
    () => new Map(data.submissions.map((submission) => [submission.assignment_id, submission])),
    [data.submissions],
  );
  const quizMarkById = useMemo(
    () => new Map(data.quizMarks.map((mark) => [mark.quiz_id, mark])),
    [data.quizMarks],
  );
  const pendingAssignments = data.assignments.filter(
    (assignment) => !submissionByAssignment.has(assignment.id),
  ).length;
  const attendancePercentage = useMemo(() => {
    const lectureCount = data.attendance.reduce((total, item) => total + item.total_lectures, 0);
    const presentCount = data.attendance.reduce((total, item) => total + item.present_count, 0);
    return lectureCount ? Math.round((presentCount / lectureCount) * 100) : 0;
  }, [data.attendance]);

  const submitAssignment = async (event, assignment) => {
    event.preventDefault();
    const file = selectedFiles[assignment.id];
    if (!file) {
      setNotice({ type: 'error', message: 'Choose a file before submitting the assignment.' });
      return;
    }

    setSubmittingAssignment(assignment.id);
    setNotice(null);
    const formData = new FormData();
    formData.append('file', file);
    try {
      await api.post(`/assignments/${assignment.id}/submit`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setSelectedFiles((current) => {
        const next = { ...current };
        delete next[assignment.id];
        return next;
      });
      await refreshRecords();
      setNotice({ type: 'success', message: `“${assignment.title}” was submitted successfully.` });
    } catch (requestError) {
      setNotice({ type: 'error', message: getApiErrorMessage(requestError) });
    } finally {
      setSubmittingAssignment(null);
    }
  };

  return (
    <section className="page-stack">
      <div className="page-heading-row">
        <div>
          <p className="eyebrow">Student learning</p>
          <h1 className="page-title">My academics</h1>
          <p className="page-description">Check your attendance, assignment deadlines and submissions, quiz marks, and internal results.</p>
        </div>
        <button type="button" className="secondary-button" onClick={refreshRecords} disabled={loading}>
          <RefreshCw size={16} className={loading ? 'spin' : ''} /> Refresh
        </button>
      </div>

      {notice && (
        <div className={`notice notice-${notice.type}`} role="status" aria-live="polite">
          {notice.type === 'error' ? <AlertCircle size={18} /> : <CheckCircle2 size={18} />}
          <span>{notice.message}</span>
        </div>
      )}
      {error && <div className="notice notice-error" role="alert"><AlertCircle size={18} />{error}</div>}

      {loading ? <div className="panel empty-state">Loading your academic records…</div> : (
        <>
          <div className="stat-grid student-academic-stats">
            <article className="stat-card"><GraduationCap size={20} /><span>Enrolled subjects</span><strong>{data.subjects.length}</strong></article>
            <article className="stat-card"><CalendarCheck size={20} /><span>Overall attendance</span><strong>{attendancePercentage}%</strong></article>
            <article className="stat-card"><Clock3 size={20} /><span>Pending assignments</span><strong>{pendingAssignments}</strong></article>
          </div>

          <div className="panel">
            <div className="panel-heading">
              <div>
                <h2 className="section-title">Attendance</h2>
                <p className="page-description">Attendance recorded by your instructors for each enrolled subject.</p>
              </div>
            </div>
            {data.attendance.length ? (
              <div className="table-wrap">
                <table>
                  <thead><tr><th>Subject</th><th>Session</th><th>Present</th><th>Absent</th><th>Leave</th><th>Attendance</th><th>Recent classes</th></tr></thead>
                  <tbody>
                    {data.attendance.map((item) => (
                      <tr key={`${item.subject_id}:${item.academic_session}`}>
                        <td>{item.subject_code} · {item.subject_title}</td>
                        <td>{item.academic_session}</td>
                        <td>{item.present_count}/{item.total_lectures}</td>
                        <td>{item.absent_count}</td>
                        <td>{item.leave_count}</td>
                        <td>{item.attendance_percentage}%</td>
                        <td>{item.recent_records?.slice(0, 3).map((record) => `${record.date}: ${record.status}`).join(' · ') || 'No attendance entered'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : <div className="empty-state">No attendance records are available yet.</div>}
          </div>

          <div className="panel">
            <div className="panel-heading">
              <div>
                <h2 className="section-title">Assignments</h2>
                <p className="page-description">Submit a file before the due date. Your status and grade will appear here.</p>
              </div>
            </div>
            {data.assignments.length ? (
              <div className="student-coursework-list">
                {data.assignments.map((assignment) => {
                  const submission = submissionByAssignment.get(assignment.id);
                  const statusLabel = submission
                    ? submission.obtained_marks === null ? 'Submitted · awaiting grade' : `Graded · ${submission.obtained_marks}/${assignment.max_marks}`
                    : 'Pending';
                  return (
                    <article className="student-coursework-card" key={assignment.id}>
                      <div className="student-coursework-details">
                        <strong>{assignment.title}</strong>
                        <span>{data.subjects.find((subject) => subject.subject_id === assignment.subject_id && subject.academic_session === assignment.academic_session)?.code || 'Subject'} · Due {formatDate(assignment.due_date)}</span>
                        {submission && <span>Submitted {formatDate(submission.submitted_at)} · {submission.original_filename}</span>}
                        {submission?.feedback && <span>Faculty feedback: {submission.feedback}</span>}
                      </div>
                      <div className={`student-status ${submission ? 'student-status-complete' : ''}`}>
                        {statusLabel}
                      </div>
                      {!submission && (
                        <form className="student-submit-form" onSubmit={(event) => submitAssignment(event, assignment)}>
                          <input
                            className="file-input"
                            type="file"
                            accept=".pdf,.docx,.zip,.png,.jpg,.txt,.py,.cpp,.java"
                            required
                            onChange={(event) => setSelectedFiles((current) => ({
                              ...current,
                              [assignment.id]: event.target.files?.[0],
                            }))}
                            aria-label={`Choose file for ${assignment.title}`}
                          />
                          <button className="primary-button" type="submit" disabled={submittingAssignment === assignment.id}>
                            <FileUp size={15} />
                            {submittingAssignment === assignment.id ? 'Submitting…' : 'Submit assignment'}
                          </button>
                        </form>
                      )}
                    </article>
                  );
                })}
              </div>
            ) : <div className="empty-state">No assignments are available for your enrolled subjects.</div>}
          </div>

          <div className="panel">
            <div className="panel-heading">
              <div>
                <h2 className="section-title">Quizzes</h2>
                <p className="page-description">Scheduled quizzes appear here; marks update after your instructor enters them.</p>
              </div>
            </div>
            {data.quizzes.length ? (
              <div className="table-wrap">
                <table>
                  <thead><tr><th>Quiz</th><th>Subject</th><th>Date</th><th>Marks</th><th>Status</th></tr></thead>
                  <tbody>
                    {data.quizzes.map((quiz) => {
                      const mark = quizMarkById.get(quiz.id);
                      return (
                        <tr key={quiz.id}>
                          <td>{quiz.title}</td>
                          <td>{data.subjects.find((subject) => subject.subject_id === quiz.subject_id && subject.academic_session === quiz.academic_session)?.code || 'Subject'}</td>
                          <td>{formatDate(quiz.quiz_date)}</td>
                          <td>{mark ? `${mark.obtained_marks}/${quiz.max_marks}` : '—'}</td>
                          <td>{mark ? 'Marks available' : 'Marks pending'}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : <div className="empty-state">No quizzes are scheduled for your enrolled subjects.</div>}
          </div>

          <div className="panel">
            <div className="panel-heading">
              <div>
                <h2 className="section-title">Marks and internal results</h2>
                <p className="page-description">Results appear after your instructor records marks and calculates the internal award.</p>
              </div>
            </div>
            {data.results.length ? (
              <div className="table-wrap">
                <table>
                  <thead><tr><th>Subject</th><th>Session</th><th>Mid-term /20</th><th>Assignment /5</th><th>Quiz /5</th><th>Presentation /5</th><th>Attendance /5</th><th>Total /40</th></tr></thead>
                  <tbody>
                    {data.results.map((result) => (
                      <tr key={result.id}>
                        <td>{result.subject?.code || `Subject ${result.subject_id}`}</td>
                        <td>{result.academic_session}</td>
                        <td>{result.mid_paper_marks}</td>
                        <td>{result.assignment_marks}</td>
                        <td>{result.quiz_marks}</td>
                        <td>{result.presentation_marks}</td>
                        <td>{result.attendance_marks}</td>
                        <td><strong className="result-total">{result.total_internal}</strong></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : data.marks.length ? (
              <div className="table-wrap">
                <table>
                  <thead><tr><th>Subject</th><th>Session</th><th>Mid-term /20</th><th>Presentation /5</th></tr></thead>
                  <tbody>
                    {data.marks.map((item) => (
                      <tr key={`${item.subject_id}:${item.academic_session}`}>
                        <td>{item.subject_code} · {item.subject_title}</td>
                        <td>{item.academic_session}</td>
                        <td>{item.mid_term?.obtained ?? 'Pending'}</td>
                        <td>{item.presentation?.obtained ?? 'Pending'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : <div className="empty-state">Marks have not been published yet.</div>}
          </div>
        </>
      )}
    </section>
  );
}
