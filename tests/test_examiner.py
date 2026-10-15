import pytest
from datetime import datetime, timedelta, date, time
from config import Config
from app import create_app
from extensions import db
from models import User, Course, Examination, ExaminationRubric, ExaminationSlot, Booking

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    CACHE_TYPE = 'SimpleCache'

@pytest.fixture
def examiner_test_setup():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        now = datetime.utcnow()
        # Create Course & Exam
        course = Course(course_code='CS101', course_name='Intro to Python')
        db.session.add(course)
        db.session.commit()

        exam = Examination(
            course_id=course.id,
            title='Python Viva',
            status='Slot Creation',
            total_marks=100.0,
            pass_marks=40.0,
            slot_creation_start=now - timedelta(days=1),
            slot_creation_end=now + timedelta(days=5),
            booking_start=now + timedelta(days=6),
            booking_end=now + timedelta(days=10),
            exam_start_date=now + timedelta(days=11),
            exam_end_date=now + timedelta(days=15)
        )
        db.session.add(exam)
        db.session.commit()

        # Rubrics
        r1 = ExaminationRubric(examination_id=exam.id, criterion_name='Syntax', max_marks=50.0)
        r2 = ExaminationRubric(examination_id=exam.id, criterion_name='Logic', max_marks=50.0)
        db.session.add_all([r1, r2])

        # Examiner 1 & Examiner 2
        ex1 = User(email='ex1@portal.edu', full_name='Dr. One', role='examiner')
        ex1.set_password('Ex1@123')
        ex2 = User(email='ex2@portal.edu', full_name='Dr. Two', role='examiner')
        ex2.set_password('Ex2@123')

        # Student
        student = User(email='student@portal.edu', full_name='Student One', role='student')
        student.set_password('Student@123')

        db.session.add_all([ex1, ex2, student])
        db.session.commit()

        client = app.test_client()
        token1 = client.post('/api/auth/login', json={'email': 'ex1@portal.edu', 'password': 'Ex1@123'}).get_json()['token']
        token2 = client.post('/api/auth/login', json={'email': 'ex2@portal.edu', 'password': 'Ex2@123'}).get_json()['token']

        yield client, token1, token2, exam.id, r1.id, r2.id, student.id
        db.drop_all()

def test_examiner_slot_creation(examiner_test_setup):
    client, token1, _, exam_id, _, _, _ = examiner_test_setup
    res = client.post('/api/examiner/slots', json={
        'examination_id': exam_id,
        'slot_date': str(date.today() + timedelta(days=2)),
        'start_time': '10:00',
        'end_time': '11:00',
        'capacity': 4,
        'venue_or_link': 'Room 101'
    }, headers={'Authorization': f'Bearer {token1}'})
    assert res.status_code == 201
    assert res.get_json()['success'] is True
    assert res.get_json()['slot']['capacity'] == 4

def test_examiner_rubric_evaluation(examiner_test_setup):
    client, token1, token2, exam_id, r1_id, r2_id, student_id = examiner_test_setup

    # Create slot for examiner 1
    slot_res = client.post('/api/examiner/slots', json={
        'examination_id': exam_id,
        'slot_date': str(date.today() + timedelta(days=2)),
        'start_time': '11:00',
        'end_time': '12:00',
        'capacity': 2
    }, headers={'Authorization': f'Bearer {token1}'})
    slot_id = slot_res.get_json()['slot']['id']

    # Book student into this slot directly
    with client.application.app_context():
        booking = Booking(student_id=student_id, examination_slot_id=slot_id, examination_id=exam_id, status='Booked')
        db.session.add(booking)
        db.session.commit()
        booking_id = booking.id

    # Examiner 2 cannot evaluate student in Examiner 1's slot
    unauth_eval = client.post(f'/api/examiner/bookings/{booking_id}/evaluate', json={
        'rubric_scores': [{'rubric_id': r1_id, 'score': 45}, {'rubric_id': r2_id, 'score': 40}],
        'feedback_remarks': 'Great test'
    }, headers={'Authorization': f'Bearer {token2}'})
    assert unauth_eval.status_code == 403

    # Examiner 1 evaluates successfully
    auth_eval = client.post(f'/api/examiner/bookings/{booking_id}/evaluate', json={
        'rubric_scores': [{'rubric_id': r1_id, 'score': 45}, {'rubric_id': r2_id, 'score': 40}],
        'feedback_remarks': 'Excellent command over syntax and logic'
    }, headers={'Authorization': f'Bearer {token1}'})
    assert auth_eval.status_code == 200
    res_data = auth_eval.get_json()
    assert res_data['success'] is True
    assert res_data['booking']['total_marks_obtained'] == 85.0
    assert res_data['booking']['is_passed'] is True
    assert res_data['booking']['status'] == 'Completed'
