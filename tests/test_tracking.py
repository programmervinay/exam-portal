import pytest
from datetime import datetime, timedelta, date, time
from config import Config
from app import create_app
from extensions import db
from models import User, Course, Examination, ExaminationRubric, ExaminationSlot, Booking, RubricScore

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    CACHE_TYPE = 'SimpleCache'

@pytest.fixture
def tracking_setup():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        now = datetime.utcnow()
        # Course & Exam
        course = Course(course_code='CS2006', course_name='MAD-II')
        db.session.add(course)
        db.session.commit()

        exam = Examination(
            course_id=course.id,
            title='MAD-II Final Evaluation',
            status='Completed',
            total_marks=100.0,
            pass_marks=40.0,
            slot_creation_start=now - timedelta(days=20),
            slot_creation_end=now - timedelta(days=15),
            booking_start=now - timedelta(days=14),
            booking_end=now - timedelta(days=10),
            exam_start_date=now - timedelta(days=9),
            exam_end_date=now - timedelta(days=5)
        )
        db.session.add(exam)
        db.session.commit()

        rubric = ExaminationRubric(examination_id=exam.id, criterion_name='Project Architecture', max_marks=100.0)
        db.session.add(rubric)

        # Users
        admin = User(email='admin_track@portal.edu', full_name='Admin Track', role='admin')
        admin.set_password('Pass@123')
        examiner = User(email='examiner_track@portal.edu', full_name='Dr. Track', role='examiner')
        examiner.set_password('Pass@123')
        student = User(email='student_track@portal.edu', full_name='Student Track', role='student')
        student.set_password('Pass@123')
        db.session.add_all([admin, examiner, student])
        db.session.commit()

        slot = ExaminationSlot(
            examination_id=exam.id,
            examiner_id=examiner.id,
            slot_date=date.today() - timedelta(days=7),
            start_time=time(10, 0),
            end_time=time(11, 0),
            capacity=5,
            booked_count=1,
            status='Completed'
        )
        db.session.add(slot)
        db.session.commit()

        booking = Booking(
            student_id=student.id,
            examination_slot_id=slot.id,
            examination_id=exam.id,
            status='Completed',
            total_marks_obtained=88.0,
            is_passed=True,
            feedback_remarks='Outstanding project architecture and comprehensive testing.',
            evaluated_by_id=examiner.id,
            evaluated_at=now - timedelta(days=7)
        )
        db.session.add(booking)
        db.session.commit()

        db.session.add(RubricScore(booking_id=booking.id, rubric_id=rubric.id, score_obtained=88.0, remarks='High quality'))
        db.session.commit()

        client = app.test_client()
        admin_token = client.post('/api/auth/login', json={'email': 'admin_track@portal.edu', 'password': 'Pass@123'}).get_json()['token']
        student_token = client.post('/api/auth/login', json={'email': 'student_track@portal.edu', 'password': 'Pass@123'}).get_json()['token']

        yield client, admin_token, student_token, student.id
        db.drop_all()

def test_student_history_and_feedback(tracking_setup):
    client, _, student_token, _ = tracking_setup
    res = client.get('/api/student/results', headers={'Authorization': f'Bearer {student_token}'})
    assert res.status_code == 200
    results = res.get_json()['results']
    assert len(results) == 1
    assert results[0]['total_marks_obtained'] == 88.0
    assert results[0]['is_passed'] is True
    assert 'Outstanding' in results[0]['feedback_remarks']
    assert len(results[0]['rubric_scores']) == 1

def test_admin_view_all_history(tracking_setup):
    client, admin_token, _, _ = tracking_setup
    res = client.get('/api/admin/bookings?status=Completed', headers={'Authorization': f'Bearer {admin_token}'})
    assert res.status_code == 200
    bookings = res.get_json()['bookings']
    assert len(bookings) >= 1
    assert bookings[0]['status'] == 'Completed'
