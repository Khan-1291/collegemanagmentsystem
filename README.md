# GPGCM College Management System

Phase 1 for the Computer Science Department at Government Post Graduate College Mardan.

The system supports department-scoped administration. Computer Science remains the seeded/legacy default department, while Super Admin can add departments and assign their HODs.

## Project structure

- `backend/` — FastAPI API, SQLAlchemy models, Alembic migrations, authentication and academic services.
- `frontend/` — React/Vite application. The browser reads and writes college records through the backend API; it contains no sample student or academic records.
- `docker-compose.yml` — production-style local stack with PostgreSQL, FastAPI, and Nginx-served React.

## Deployment with Docker (recommended)

Docker Compose runs PostgreSQL, the FastAPI backend, and the frontend behind Nginx. The browser uses the same-origin `/api/v1` path; Nginx proxies API and profile-image requests to the backend. PostgreSQL and uploaded files persist in named Docker volumes.

1. Install Docker Engine and the Docker Compose plugin (or Docker Desktop).
2. From the project root, create the local, ignored environment file:

   ```powershell
   Copy-Item .env.example .env
   ```

3. Generate and set `SECRET_KEY` to the output of `python -c "import secrets; print(secrets.token_urlsafe(48))"`. Generate a separate long `POSTGRES_PASSWORD` with `python -c "import secrets; print(secrets.token_urlsafe(32))"` and place both values in `.env`. Do not use the example file's blank values or commit `.env`.
4. For email, set `RESEND_API_KEY`, a verified `RESEND_FROM_EMAIL`, and the user-facing `FRONTEND_BASE_URL`. Email is optional.
5. Build and start the services:

   ```powershell
   docker compose up --build -d
   docker compose ps
   ```

6. Open `http://localhost/`. Docker starts the API after PostgreSQL is healthy, bootstraps an empty database, runs `alembic upgrade head`, and then starts FastAPI. Initial startup can take a few minutes while images build. Logs are available with `docker compose logs -f backend frontend db`.
7. Create the first administrator as described in [First Super Admin](#first-super-admin).

Set `APP_PORT` in `.env` to publish a different host port. The frontend image defaults to `VITE_API_BASE_URL=/api/v1`; retain this relative URL when deploying behind the included Nginx proxy. Set `BACKEND_CORS_ORIGINS` only if a separately hosted frontend needs cross-origin access; for the same-origin Compose setup the default empty list is appropriate.

### Database initialization and migrations

There is no historical baseline Alembic revision in this project. On an empty database, the backend's `app.db_bootstrap` creates the initial schema from the SQLAlchemy models, seeds the real Computer Science department, and stamps the current Alembic head. On a database containing existing application tables, it leaves the schema untouched and runs `alembic upgrade head` to apply outstanding revisions. The API itself no longer creates tables at application startup. Review and back up an existing database before deploying; do not point a new deployment at a live database until its schema and migration state have been checked.

To apply migrations manually after updating the application image:

```powershell
docker compose exec backend alembic upgrade head
```

For local development without Docker, initialize a brand-new local DB once from `backend/` with `python -m app.db_bootstrap`, then run `alembic upgrade head`. Existing local databases should use `alembic upgrade head` without bootstrapping.

## Running without Docker (development)

1. Install PostgreSQL locally, create an application database/user, or use SQLite for development.
2. From the project root, copy `backend/.env.example` to `backend/.env`, set `DATABASE_URL` and a unique `SECRET_KEY` (at least 32 characters), and set exact `BACKEND_CORS_ORIGINS`.
3. In `backend/`, create/activate a Python virtual environment, install `pip install -r requirements.txt`, and initialize a new database using `python -m app.db_bootstrap`. Use `alembic upgrade head` for later schema updates.
4. Start the backend from `backend/` with `uvicorn app.main:app --host 0.0.0.0 --port 8000`. The API docs are at `http://localhost:8000/docs`.
5. In `frontend/`, run `npm ci`, then `npm run dev`. For direct browser/API development set `VITE_API_BASE_URL=http://localhost:8000/api/v1` in `frontend/.env.local` (or use the existing hostname-based default).

The UI defaults to Light mode. The theme choice is saved in this browser.

### Environment variables

The root `.env.example` is the Compose deployment template. Copy it to `.env`; Compose refuses to start until `POSTGRES_PASSWORD` and `SECRET_KEY` are set.

| Variable | Required | Purpose |
|---|---|---|
| `POSTGRES_DB` | No | PostgreSQL database name (default `gpgcm`). |
| `POSTGRES_USER` | No | PostgreSQL application user (default `gpgcm`). |
| `POSTGRES_PASSWORD` | Yes | Database password. Use a generated URL-safe password so Compose can place it safely in the backend connection URL. |
| `DATABASE_URL` | Docker: generated; non-Docker: yes | SQLAlchemy database connection string. Compose builds it from the PostgreSQL settings; set it directly in `backend/.env` for non-Docker use. |
| `SECRET_KEY` | Yes | Unique signing key of at least 32 characters; never reuse or commit it. |
| `APP_PORT` | No | Host port for the Nginx frontend (default `80`). |
| `VITE_API_BASE_URL` | No | Frontend API base URL baked into the image (default `/api/v1` behind Nginx). |
| `BACKEND_CORS_ORIGINS` | No | JSON array of trusted browser origins; same-origin Nginx deployment uses `[]`. |
| `FRONTEND_BASE_URL` | No | Public frontend URL included in email links. |
| `RESEND_API_KEY` | No | Resend API key; leave empty to disable email delivery. |
| `RESEND_FROM_EMAIL` | No | Sender address verified in Resend for production. |

`DATABASE_URL` is assembled for the backend from the Compose PostgreSQL settings. For a non-Docker backend, set `DATABASE_URL` directly in `backend/.env`; use a SQLAlchemy PostgreSQL URL and URL-encode reserved characters in credentials. The backend also supports `UPLOAD_DIR`, `PROFILE_UPLOAD_DIR`, `ACTIVITY_UPLOAD_DIR`, `MAX_PROFILE_IMAGE_SIZE_MB`, `MAX_ACTIVITY_ATTACHMENT_SIZE_MB`, `MAX_FILE_SIZE_MB`, and `ACCESS_TOKEN_EXPIRE_MINUTES`; defaults are defined in `backend/app/config.py`.

## First Super Admin

No administrator is seeded by default. After the backend is healthy and its database is initialized, run the following once. The command prompts for a password without echoing it; use 12–72 UTF-8 bytes (usually 12–72 ASCII characters) and store it in the college password manager. Passwords longer than bcrypt's 72-byte limit are rejected before hashing.

```powershell
docker compose exec backend python -m app.create_super_admin --email admin@gpgcm.edu.pk --full-name "GPGCM Super Admin"
```

Without Docker, run from `backend/` after configuring its environment:

```powershell
python -m app.create_super_admin --email admin@gpgcm.edu.pk --full-name "GPGCM Super Admin"
```

The command rejects an email already in use and does not accept the password as a command-line argument.

## College Edge PC deployment

- Prefer a supported 64-bit Ubuntu Server LTS PC with Docker Engine and Compose, a fixed LAN IP or college DNS name, SSD storage, and a UPS. Docker Desktop on a supported Windows PC can be used for a pilot, but a managed Linux host is preferable for an always-on deployment.
- Set `.env` secrets and `APP_PORT` for the college network. Keep PostgreSQL unexposed; Compose publishes only the Nginx frontend. Restrict inbound firewall access to the college LAN and use HTTPS through a managed reverse proxy if users connect beyond a trusted LAN.
- Start at boot with Docker's `restart: unless-stopped`; verify `docker compose ps` reports all services healthy after reboot.
- Configure an off-PC backup schedule. Back up PostgreSQL with `pg_dump` and separately archive `uploads_data` and `private_uploads_data`; periodically test restoring all three. Named Docker volumes are persistent across container replacement but are not backups.
- Check free disk space, update images deliberately, and retain previous database/upload backups before upgrades. Don't expose `/docs` or the Edge PC directly to the public internet.

## AWS deployment notes

The images can run on ECS/Fargate or EC2. For production, replace the bundled PostgreSQL container with Amazon RDS for PostgreSQL; put database credentials, `SECRET_KEY`, and Resend credentials in AWS Secrets Manager/SSM, and terminate TLS at an Application Load Balancer. Store profile images and attachments in S3 (private attachments must remain private and use authenticated access or short-lived signed URLs), rather than relying on container-local storage. Push versioned images to ECR, run the migration/bootstrap task once as a release step, and then roll out the API/frontend. Configure RDS backups, S3 lifecycle policies, CloudWatch logs/alarms, VPC security groups, and health checks. Avoid running multiple API replicas with local uploads; the in-process email background tasks also do not provide durable retries.

## Push the cleaned project to GitHub

Create an empty private GitHub repository, set up GitHub authentication, then run these commands from the project root in PowerShell. Replace the remote URL with the repository you created. Review the staged list and confirm that `.env`, databases, virtual environments, `node_modules`, uploads, and build output are not included before committing.

```powershell
git init -b main
git add .
git status --short
git diff --cached --stat
git commit -m "Prepare GPGCM CMS for Docker deployment"
git remote add origin https://github.com/ORGANIZATION/gpgcm-cms.git
git push -u origin main
```

If this directory is already a Git repository, do not run `git init`; review its status and existing remote first.

## Email notifications (Resend)

1. Create an API key in the Resend dashboard at `https://resend.com/api-keys`.
2. For Docker, add `RESEND_API_KEY=re_...` to the root `.env`; without Docker, add it to `backend/.env` (or set it as a backend environment secret). Do not commit the key.
3. Set `RESEND_FROM_EMAIL` to a sender address verified for your Resend account. `onboarding@resend.dev` is only suitable for Resend's limited test mode; production requires a verified sending domain.
4. Set `FRONTEND_BASE_URL` to the sign-in URL students and faculty can reach.

Email delivery runs as FastAPI background work after a successful database commit; a provider failure does not undo the saved academic record. With no API key, messages are skipped and the backend logs a warning. Delivery tasks run in-process, so production deployments requiring retries/delivery guarantees should move notifications to a durable task queue.

Currently configured email events:

- A new assignment or quiz is created: notify active students enrolled in its subject and academic session.
- Assignment, quiz, mid-term, or presentation marks are entered/updated: notify the affected active student.
- Internal results are calculated and when HOD/Super Admin finalizes them: notify each affected active student.
- Student or faculty account is created individually or by CSV import: send a welcome email with the account email and initial password.
- A student/faculty account is deactivated: notify its account email.
- Attendance notifications are not currently enabled.

Welcome messages contain the initial password provided during registration/import. Send account CSV files and initial credentials only through approved secure channels; ask users to change their initial password after signing in.

## Department activities

All signed-in roles can open **Department activities** from the sidebar, publish a title, text, category, and optional PDF/image attachment, and browse or filter the newest-first feed. Students may delete only their own posts; Faculty, HOD, and Super Admin can delete any post. Attachments are stored outside the public static-upload directory and are served through an authenticated download route. Supported attachment types are PDF, PNG, JPG/JPEG, GIF, and WEBP, up to 10 MB.

Apply the activities schema with `cd backend` then `alembic upgrade head` before running the API against an existing database. To test the page, start the API and frontend, sign in with any active account, select **Department activities**, create a post in each category, optionally attach an allowed file, filter the feed, and verify that a student cannot delete another user's post while Faculty/HOD/Admin can. Check that a saved attachment downloads while signed in and returns unauthorized when signed out.

## Profile images and activity comments

Users can upload or replace their profile image in **My Profile**. The API accepts PNG, JPG/JPEG, GIF, and WEBP images up to 5 MB and stores them in `uploads/profiles/`; uploaded images are served by the existing `/uploads` static mount. The interface shows initials when no image has been uploaded.

Every activity post includes its comments. Any signed-in user can comment; users can delete their own comments, while Faculty, HOD, and Super Admin can delete any comment. Comments are shown oldest-first within each post; the feed itself remains newest-first.

For an existing database, apply the schema from `backend/` with `alembic upgrade head`. The new migration adds `users.profile_image_url` and the `activity_comments` table. New endpoints:

- `POST /api/v1/auth/me/profile-image` — authenticated multipart upload using the `image` field.
- `GET /api/v1/activities/{activity_id}/comments` — list comments on a post.
- `POST /api/v1/activities/{activity_id}/comments` — create a comment with a JSON `content` field.
- `DELETE /api/v1/activities/{activity_id}/comments/{comment_id}` — delete an owned comment or a comment as staff.
- `GET /api/v1/activities/` also returns each author's profile image and comments with commenter details.

To test the complete flow, migrate the database, sign in as a user, upload a profile image from **My Profile**, then open **Department activities** and create a post/comment. Confirm the image is shown in the navbar, sidebar, profile, post, and comment. Sign in as another student to comment and confirm they cannot delete the first student's comment; then verify staff can moderate it. Also try a non-image upload and an image larger than 5 MB to confirm validation.

For testing from another device on the network, start the backend with `uvicorn app.main:app --host 0.0.0.0 --reload` and Vite with `npm run dev -- --host 0.0.0.0`. Set `BACKEND_CORS_ORIGINS` in the backend environment to a JSON list containing the exact frontend origin, such as `["http://192.168.1.20:5173"]`. If the backend is not on the frontend's hostname, set `VITE_API_BASE_URL` to its reachable URL. Browser messages for requests with no response show the configured API address and mention backend reachability/CORS. The `/health` endpoint is at `http://127.0.0.1:8000/health` (not under `/api/v1`).

## Account enrollment

HODs can register students for their own department from **Enroll students**, or upload a CSV. Super Admin creates faculty accounts from **Faculty management** and selects each faculty member's primary department. Required fields include an initial password (at least six characters); use a secure transfer method for CSV files and remove them safely after enrollment.

Imports are limited to UTF-8 CSV, 2 MB, and 500 records. All rows are validated before saving. Invalid rows, duplicate email addresses, student roll numbers, or student registration numbers prevent the entire file from being imported. Accounts and their linked profiles are created together.

## Multi-department administration

Run `alembic upgrade head` from `backend/` when deploying this version. The migration assigns existing unassigned student and faculty profiles to Computer Science, maps existing HOD profiles to their departments, and makes student/faculty department ownership required without changing their academic records.

Super Admin can open **Departments** to create a department. The form can also create its HOD account in the same transaction by supplying the HOD's name, email, initial password, designation, and qualification. The HOD profile is created in that department and a welcome email is queued. Alternatively, enroll faculty into the department and choose that faculty member as HOD from the department card.

Department API endpoints (Super Admin only for create/assign; `GET` returns all departments to Super Admin and only the signed-in user's department to other roles):

- `GET /api/v1/departments/` — list accessible departments.
- `POST /api/v1/departments/` — create a department, optionally including `hod_full_name`, `hod_email`, `hod_password`, `hod_designation`, and `hod_qualification`.
- `PATCH /api/v1/departments/{department_id}/hod` — assign an existing faculty user with JSON `{"faculty_user_id": 123}`. The faculty profile must already belong to the target department.

Student and subject list endpoints scope HOD results to their assigned department. Super Admin can filter these endpoints with `department_id`; the faculty directory returns all active and inactive faculty to Super Admin and HOD so HODs can allocate any active faculty member. HOD student enrollment, student management, subject creation, and faculty allocation are checked against the HOD's department on the server. Faculty profile `department_id` remains the required primary affiliation for existing data, while `FacultySubject` allocations determine teaching access and may link a faculty member to subjects in any department. No migration is required for cross-department teaching because the existing allocation relationship already supports it.

There is intentionally no database demo seeder. Do not run unreviewed sample-data scripts against a real college database.

## Subject management

Super Admin and HOD accounts can open **Subjects** to create and edit courses, activate/deactivate subjects, and allocate global faculty by academic session and section. HODs can additionally enroll selected students or an entire semester section; Super Admin enrollment controls are not shown or permitted by the API. Select the semester and academic session once in **Shared academic scope**; allocation and enrollment use the same session, and their subject choices are filtered to the selected semester. Enrollment candidates are matched to the subject semester and selected section; the academic session is recorded separately from the student's admission cohort.

The page uses these authenticated API routes:

- `GET /api/v1/subjects/` and `POST /api/v1/subjects/` — list and create curriculum subjects.
- `PUT /api/v1/subjects/{subject_id}` — update or activate/deactivate a subject (added for this feature).
- `GET /api/v1/faculty/` and `GET /api/v1/students/?semester={semester}&section={section}` — populate allocation and enrollment choices.
- `POST /api/v1/subjects/allocate-faculty` — save a faculty, subject, session, and section allocation.
- `GET /api/v1/subjects/allocations` — list faculty allocations (added for this feature; restricted to Super Admin and HOD).
- `POST /api/v1/subjects/enroll-students` — enroll selected student profile IDs in a subject and academic session.

To test cross-department teaching, sign in as a department HOD, select a subject in their department, and allocate an active faculty member whose primary affiliation is another department. Verify the home department is shown next to the faculty name and the allocation is saved. Sign in as that faculty member and confirm the subject appears in **Academic tools**. To test student enrollment, use the HOD account, select the subject/session/section, choose students (or select all), and save. Super Admin can also allocate faculty but cannot enroll students through this page or API. The backend must be running and student/faculty accounts must already exist.

## Faculty academic workflow

Faculty can open **Academic tools** to work only with subject/session/section allocations assigned to their account. The workspace supports session-specific attendance (including present/absent/leave and attendance percentages), assignment setup and submission grading, quiz setup and marks entry, mid-term and presentation marks, and internal result calculation.

Attendance now stores its academic session. Apply `alembic upgrade head` to an existing database before recording attendance with this version. The migration backfills a session for prior attendance only when the student's subject enrollment identifies exactly one session; ambiguous historical records remain unassigned and are excluded from session-specific totals. New databases get the updated attendance schema from the model metadata.

Faculty workflows use the existing `GET /api/v1/subjects/my-subjects`, attendance, assignments, quizzes, marks, and results APIs. Added endpoints:

- `DELETE /api/v1/subjects/allocations/{allocation_id}` — remove an allocation before assigning the class to another faculty member (Super Admin/HOD only).
- `GET /api/v1/attendance/subject/{subject_id}/roster?academic_session={session}&section={section}` — list enrolled students, daily attendance, and session percentage.
- `GET /api/v1/assignments/{assignment_id}/submissions` — list submissions for faculty grading.
- `GET /api/v1/quizzes/{quiz_id}/marks` — load existing quiz scores before editing them.

Faculty access to attendance, assignment, quiz, mark, and result operations is checked against subject/session/section allocations on the backend, not just hidden in the UI.

To test the workflow, sign in as Super Admin or HOD, allocate a subject to a faculty member for an academic session and section, then enroll active students in that subject/session/section. Sign in as the allocated faculty member and open **Academic tools**. Choose the allocated class, mark and save attendance for a date, create an assignment and quiz, grade at least one assignment submission and enter quiz marks, then enter mid-term and presentation marks. Select **Internal result** and calculate; the page shows Mid-term (20) + Assignment (5) + Quiz (5) + Presentation (5) + Attendance (5), totaling at most 40. Try the same class as a faculty member without an allocation and verify the backend rejects access.

Students can open **My academics** from their sidebar to see attendance per enrolled subject, assignment due/submission/grade status, scheduled quizzes and available quiz marks, mid-term/presentation marks, and calculated internal results. They can submit an allowed assignment file before its due date from that page. Assignment and quiz lists are restricted to subjects and sessions in which the student is actively enrolled.

## Profile settings and account status

Every signed-in role can open **My Profile** to update their name, email, and phone, and change their password after confirming the current password. Students may also update guardian name and phone; their roll number, registration number, admission session, semester, and program remain read-only. Faculty may update qualification, specialization, office room, and joining date; designation and department remain read-only. Institutional profile fields are only available when that user has a linked profile.

Super Admin can open **User management** to list and activate/deactivate student and global faculty accounts. HODs can manage student accounts in their department only; faculty account management is reserved for Super Admin. Deactivation disables login and authenticated API access while retaining the account, profile, and academic records.

- `GET /api/v1/auth/me` — retrieve the current user's profile (existing endpoint).
- `PUT /api/v1/auth/me` — update permitted self-service profile fields.
- `PUT /api/v1/auth/me/password` — change password with current-password verification.
- `PATCH /api/v1/users/{user_id}/status` — activate/deactivate student and faculty accounts (Super Admin/HOD only).
- The user-management lists use existing `GET /api/v1/students/` and `GET /api/v1/faculty/` endpoints.

To test profile settings, sign in as each role, open **My Profile**, update allowed contact/profile fields, save, and verify the values after refreshing. Try changing a student's academic identifiers or a faculty member's designation/department through an API request; the self-update endpoint rejects these fields. Change the password using the correct current password, then verify the new password works and the old one does not.

To test activation status, sign in as Super Admin or HOD, open **User management**, deactivate a student or faculty account, and verify login with that account is rejected. Activate the same account again and verify sign-in succeeds. Confirm its profile and academic records remain present. Attempts by other roles or attempts to toggle an HOD/Super Admin account are rejected.

## Remaining deployment work

This codebase is not yet ready to expose to real classes. Complete and verify these items in a controlled deployment:

1. **Secure configuration:** supply unique production values through a secret manager/environment, rotate signing keys that may have been used elsewhere, and use TLS. The included reverse-proxy deployment is same-origin; restrict any additional CORS origins to exact trusted frontends.
2. **Database lifecycle:** this repository has no historical baseline Alembic revision. Empty deployments initialize from the current model metadata and stamp the current migration head; later changes use Alembic. Review this bootstrap/migration flow and back up any existing database before upgrading.
3. **Initial privileged access:** create the first Super Admin through the interactive bootstrap command, store the credential in the college password manager, and verify sign-in. No default administrator is seeded.
4. **Credential lifecycle:** establish a secure password reset/first-login process, password policy, account recovery, and a secure way to distribute initial credentials; the current system has no reset workflow.
5. **Role and privacy review:** verify each endpoint's authorization against actual institutional policy, especially access to student lists, marks, attendance, and uploaded work. Review audit trails for account and academic-record changes.
6. **Academic workflows:** validate course allocations, class/section enrollments, attendance, marks, result finalization, and award-list calculations with the department and AWKUM before use.
7. **Operational controls:** the Compose setup provides Nginx, API/database health checks, persistent named volumes, and container restart policies. Still configure HTTPS, monitoring and structured logs without credentials, external/off-PC backups, and a tested incident/restore plan.
8. **Acceptance and security testing:** add automated API and UI tests for all roles, registration/import validation and rollback, access control, and production migration/deployment. Perform a security review before loading live student data.

Existing database contents are not deleted by this code cleanup. If a local or shared database was already seeded, review and remove only confirmed test records using a separate, backed-up data-cleanup procedure.
