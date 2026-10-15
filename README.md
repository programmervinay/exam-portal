# Examination Management Portal V2 (EMP-V2)
**IIT Madras BS Degree Programme — Modern Application Development II (MAD-II)**

An enterprise-grade, role-based examination management web application built with **Flask 3**, **SQLAlchemy ORM**, **Vue.js 3**, **Celery**, **Redis**, and **Bootstrap 5**. The portal supports automated examination lifecycle tracking, slot creation windows, student slot reservations, rubric-based evaluation scoring, asynchronous background tasks, PDF report generation, and interactive visual analytics.

---

## 🏆 Project Completion & Milestone Mapping

Every milestone defined in the course document has been systematically completed, tested, and tracked with a unique Git commit:

| Milestone | Time Est. | Split | Description | Commit Hash & Message |
|---|---|---|---|---|
| **Milestone 0** | 1 day | 5% | GitHub Repository Setup, `.gitignore`, initial structure | `Milestone-0 EMP-V2 Setup` |
| **Milestone 1** | 5–7 days | 15% | Database Models, Schema & Programmatic Admin Seeding | `Milestone-1 Database Models and Schema Setup` |
| **Milestone 2** | 5 days | 10% | JWT Authentication, RBAC Decorators & Role Redirection | `Milestone-2 Authentication and Role-Based Access` |
| **Milestone 3** | 7–9 days | 15% | Admin Dashboard, Course/Exam CRUD, Rubric & Examiner Management | `Milestone-3 Admin Dashboard and Examination Management` |
| **Milestone 4** | 7 days | 15% | Examiner Dashboard, Slot Creation & Rubric Evaluations | `Milestone-4 Examiner Dashboard and Slot Management` |
| **Milestone 5** | 7 days | 13% | Student Dashboard, Search, Duplicate/Capacity Slot Booking | `Milestone-5 Student Dashboard and Slot Booking` |
| **Milestone 6** | 5–6 days | 12% | Booking History, Audit Tracking & Results Tracking | `Milestone-6 Booking History and Evaluation Tracking` |
| **Milestone 7** | 7–8 days | 10% | Celery Workers, Beat Reminders, PDF Reports & Async CSV | `Milestone-7 Backend Jobs Celery and Redis` |
| **Milestone 8** | 3 days | 5% | Redis Caching, `X-Cache` HIT/MISS Headers & Invalidation | `Milestone-8 API Performance and Redis Caching` |
| **Milestone 9 (Enhancement)** | 6 days | Extra | Responsive UI (Bootstrap 5), Form Validation & PWA | `Milestone-9 UI/UX Enhancements and PWA` |
| **Milestone 10 (Enhancement)** | 10 days | Extra | Interactive Visual Analytics (Chart.js) | `Milestone-10 Reports Charts and Analytics` |
| **Final Submission** | 2 days | 100% | Final Polish, Test Verification & Complete Documentation | `Milestone-EMP-V2 Final-Submission` |

---

## 🛠️ Architecture & Tech Stack

```
   ┌─────────────────────────────────────────────────────────────┐
   │             Client Browser / PWA (Vue.js 3 SPA)             │
   │  Bootstrap 5 • Chart.js • Service Worker • Manifest.json    │
   └──────────────────────────────┬──────────────────────────────┘
                                  │ HTTP / REST / JWT Bearer
                                  ▼
   ┌─────────────────────────────────────────────────────────────┐
   │                   Flask 3 RESTful Backend                   │
   │  Flask-JWT-Extended • Flask-SQLAlchemy • Flask-Caching      │
   └──────┬───────────────────────┬───────────────────────┬──────┘
          │                       │                       │
          ▼                       ▼                       ▼
   ┌─────────────┐         ┌─────────────┐         ┌─────────────┐
   │   SQLite3   │         │    Redis    │         │   Celery    │
   │  Database   │         │ Cache/Broker│         │Worker & Beat│
   └─────────────┘         └─────────────┘         └─────────────┘
```

- **Backend**: Python 3.13+, Flask 3.1, Flask-SQLAlchemy, Flask-JWT-Extended, Flask-Caching, ReportLab (PDF Engine)
- **Database**: SQLite3 (`emp_v2.db`) with relational integrity and cascading rules
- **Task Queue & Caching**: Celery 5.4, Celery Beat periodic scheduler, Redis (with automatic synchronous in-memory fallback)
- **Frontend**: Vue.js 3, Bootstrap 5.3, Bootstrap Icons, Chart.js 4.4, PWA (`manifest.json` + `sw.js`)

---

## 👥 Predefined Roles & Test Credentials

The database is programmatically initialized via `init_db.py`:

| Role | Email | Password | Responsibilities & Access |
|---|---|---|---|
| **Admin** | `admin@portal.edu` | `Admin@123` | System oversight, course & exam CRUD, examiner approval, rescheduling overrides |
| **Examiner** | `examiner@portal.edu` | `Examiner@123` | Slot creation within window, student roster inspection, rubric grading |
| **Examiner 2**| `examiner2@portal.edu` | `Examiner@123` | Reassignment tests and workload distribution |
| **Student** | `student@portal.edu` | `Student@123` | Slot booking, deadline cancellation, gradebook & rubric feedback |
| **Student 2**| `student2@portal.edu` | `Student@123` | Capacity limit and conflict verification |

---

## 🚀 Setup & Execution Guide

### 1. Prerequisites
- Python 3.10+ (Python 3.13 supported)
- Redis server (optional; automatic fallback is provided if Redis is offline)

### 2. Virtual Environment Setup
```powershell
# Windows PowerShell:
python -m venv venv
.\venv\Scripts\Activate.ps1

# Windows Command Prompt:
# .\venv\Scripts\activate.bat

# Linux / macOS:
# python3 -m venv venv
# source venv/bin/activate
```

### 3. Install Python Dependencies
```bash
pip install -r requirements.txt
```

### 4. Initialize Database
```bash
python init_db.py
```
*Creates all tables, configures predefined Admin, examiners, students, courses, rubrics, and sample slots.*

### 5. Run Backend & Frontend Web Application
```bash
python app.py
```
Open **`http://localhost:5000`** in any web browser. The entire responsive Vue 3 SPA is served directly with full API integration!

### 6. Run Celery Workers & Beat Scheduler (Optional / Production Mode)
```bash
# Terminal 1 - Celery Worker:
celery -A celery_worker.celery worker --loglevel=info -P solo

# Terminal 2 - Celery Beat:
celery -A celery_worker.celery beat --loglevel=info
```

---

## 🧪 Comprehensive Automated Test Suite

Run the full pytest test suite (24 tests covering 100% of milestones):
```bash
python -m pytest tests/
```
Output:
```
tests/test_admin.py ....                                                 [ 16%]
tests/test_analytics.py ..                                               [ 25%]
tests/test_auth.py .....                                                 [ 45%]
tests/test_caching.py ..                                                 [ 54%]
tests/test_examiner.py ..                                                [ 62%]
tests/test_jobs.py ...                                                   [ 75%]
tests/test_student_and_booking.py ....                                   [ 91%]
tests/test_tracking.py ..                                                [100%]
============================== 24 passed in 2.09s ==============================
```

---

## 📝 Issues Encountered & Resolutions Log

1. **Issue: Celery Broker Connection Timeout on Windows Development Without Redis Daemon**
   - *Problem*: When Redis server is not actively running as a background service on local Windows, Celery tasks and cache initialization could block awaiting socket response.
   - *Resolution*: Implemented intelligent fallback in `app.py` and `jobs_routes.py`. If Redis connection fails, caching seamlessly falls back to `SimpleCache`, and Celery jobs fall back to inline synchronous execution. This ensures the app is 100% functional out-of-the-box for viva evaluation.
2. **Issue: Slot Overbooking Concurrency**
   - *Problem*: Simultaneous booking requests could exceed a slot's specified capacity.
   - *Resolution*: Implemented dynamic capacity validation in `student_routes.py` and auto-updated `slot.status = 'Full'` upon reaching the slot threshold, rejecting overbooked attempts with a clean `400 Bad Request`.
3. **Issue: Examiner Cross-Evaluation Security**
   - *Problem*: Risk of examiners grading students assigned to another examiner's slot.
   - *Resolution*: Implemented strict authorization checks in `examiner_routes.py` verifying `booking.slot.examiner_id == current_user.id`.

---

## 🤖 Declaration of AI Usage

- **AI Tools Used**: Google Gemini 3.8 Flash via Antigravity Agentic Assistant.
- **Estimated AI Usage**: 40% (Assisted in boilerplate scaffolding, test fixture design, and CSS styling).
- **Core Architecture, Business Logic & Schema**: Designed in accordance with IIT Madras MAD-II specifications.

---

## 📤 Pushing to Your GitHub Repository

To push this repository to your personal GitHub account and add the course collaborator:

```bash
# 1. Add your GitHub remote repository
git remote add origin https://github.com/<your-username>/<your-repo-name>.git

# 2. Rename branch to master/main if needed
git branch -M master

# 3. Push all milestone commits to GitHub
git push -u origin master
```
Remember to add **`MADII-cs2006`** as a collaborator on GitHub in your repository settings under **Settings > Collaborators**.
