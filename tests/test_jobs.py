import os
import pytest
from datetime import datetime, timedelta, date, time
from config import Config
from app import create_app
from extensions import db
from models import User, Course, Examination, ExaminationSlot, Booking, ExportJob, NotificationLog

from celery_worker import celery

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    CACHE_TYPE = 'SimpleCache'

@pytest.fixture
def jobs_test_setup():
    celery.conf.task_always_eager = True
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        now = datetime.utcnow()
        # Admin
        admin = User(email='admin_job@portal.edu', full_name='Admin Job', role='admin')
        admin.set_password('Admin@123')
        # Student
        student = User(email='student_job@portal.edu', full_name='Student Job', role='student')
        student.set_password('Student@123')
        # Examiner
        examiner = User(email='examiner_job@portal.edu', full_name='Dr. Job', role='examiner')
        examiner.set_password('Examiner@123')
        db.session.add_all([admin, student, examiner])
        db.session.commit()

        # Course & Exam
        course = Course(course_code='CS9001', course_name='Distributed Cloud')
        db.session.add(course)
        db.session.commit()

        exam = Examination(
            course_id=course.id,
            title='Cloud Exam',
            status='Completed',
            slot_creation_start=now - timedelta(days=5),
            slot_creation_end=now - timedelta(days=4),
            booking_start=now - timedelta(days=3),
            booking_end=now - timedelta(days=2),
            exam_start_date=now - timedelta(days=1),
            exam_end_date=now
        )
        db.session.add(exam)
        db.session.commit()

        slot = ExaminationSlot(
            examination_id=exam.id,
            examiner_id=examiner.id,
            slot_date=date.today() + timedelta(days=1),
            start_time=time(10, 0),
            end_time=time(11, 0),
            capacity=2,
            booked_count=1,
            venue_or_link='Online Meet'
        )
        db.session.add(slot)
        db.session.commit()

        booking = Booking(
            student_id=student.id,
            examination_slot_id=slot.id,
            examination_id=exam.id,
            status='Booked'
        )
        db.session.add(booking)
        db.session.commit()

        client = app.test_client()
        s_token = client.post('/api/auth/login', json={'email': 'student_job@portal.edu', 'password': 'Student@123'}).get_json()['token']
        a_token = client.post('/api/auth/login', json={'email': 'admin_job@portal.edu', 'password': 'Admin@123'}).get_json()['token']

        yield client, s_token, a_token, student.id, admin.id
        db.drop_all()

def test_csv_export_endpoint(jobs_test_setup):
    client, s_token, _, _, _ = jobs_test_setup
    res = client.post('/api/jobs/export-csv', headers={'Authorization': f'Bearer {s_token}'})
    assert res.status_code == 202
    data = res.get_json()
    assert data['success'] is True
    assert 'job' in data

    # Verify export job created and listed
    res_list = client.get('/api/jobs/exports', headers={'Authorization': f'Bearer {s_token}'})
    assert res_list.status_code == 200
    jobs = res_list.get_json()['export_jobs']
    assert len(jobs) >= 1

def test_monthly_admin_report_generation(jobs_test_setup):
    client, _, a_token, _, _ = jobs_test_setup
    res = client.post('/api/jobs/generate-report', headers={'Authorization': f'Bearer {a_token}'})
    assert res.status_code in [200, 202]

def test_daily_reminders_trigger(jobs_test_setup):
    client, _, a_token, _, _ = jobs_test_setup
    res = client.post('/api/jobs/trigger-daily-reminders', headers={'Authorization': f'Bearer {a_token}'})
    assert res.status_code == 200
    assert res.get_json()['success'] is True
