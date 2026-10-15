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
def booking_test_setup():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        now = datetime.utcnow()
        # Create course & exam
        course = Course(course_code='CS5001', course_name='Distributed Systems')
        db.session.add(course)
        db.session.commit()

        # Open exam for booking
        exam_open = Examination(
            course_id=course.id,
            title='Distributed Systems Viva',
            status='Booking Open',
            total_marks=100.0,
            pass_marks=40.0,
            slot_creation_start=now - timedelta(days=10),
            slot_creation_end=now - timedelta(days=5),
            booking_start=now - timedelta(days=4),
            booking_end=now + timedelta(days=5),
            exam_start_date=now + timedelta(days=6),
            exam_end_date=now + timedelta(days=10)
        )

        # Closed exam
        exam_closed = Examination(
            course_id=course.id,
            title='Old Exam',
            status='Closed',
            total_marks=100.0,
            pass_marks=40.0,
            slot_creation_start=now - timedelta(days=20),
            slot_creation_end=now - timedelta(days=15),
            booking_start=now - timedelta(days=14),
            booking_end=now - timedelta(days=10),
            exam_start_date=now - timedelta(days=9),
            exam_end_date=now - timedelta(days=5)
        )
        db.session.add_all([exam_open, exam_closed])
        db.session.commit()

        # Examiner & Slots
        examiner = User(email='ex_test@portal.edu', full_name='Dr. Test', role='examiner')
        examiner.set_password('Ex@123')
        db.session.add(examiner)
        db.session.commit()

        # Slot with capacity 1
        slot1 = ExaminationSlot(
            examination_id=exam_open.id,
            examiner_id=examiner.id,
            slot_date=date.today() + timedelta(days=7),
            start_time=time(10, 0),
            end_time=time(11, 0),
            capacity=1,
            booked_count=0,
            status='Open'
        )
        # Slot for closed exam
        slot_closed = ExaminationSlot(
            examination_id=exam_closed.id,
            examiner_id=examiner.id,
            slot_date=date.today() - timedelta(days=6),
            start_time=time(10, 0),
            end_time=time(11, 0),
            capacity=2,
            booked_count=0,
            status='Open'
        )
        db.session.add_all([slot1, slot_closed])
        db.session.commit()

        # Two students
        s1 = User(email='student1@portal.edu', full_name='Student One', role='student')
        s1.set_password('Student@123')
        s2 = User(email='student2@portal.edu', full_name='Student Two', role='student')
        s2.set_password('Student@123')
        db.session.add_all([s1, s2])
        db.session.commit()

        client = app.test_client()
        t1 = client.post('/api/auth/login', json={'email': 'student1@portal.edu', 'password': 'Student@123'}).get_json()['token']
        t2 = client.post('/api/auth/login', json={'email': 'student2@portal.edu', 'password': 'Student@123'}).get_json()['token']

        yield client, t1, t2, slot1.id, slot_closed.id
        db.drop_all()

def test_successful_booking_and_capacity_closure(booking_test_setup):
    client, t1, t2, slot1_id, _ = booking_test_setup
    
    # Student 1 books slot 1
    res1 = client.post('/api/student/bookings', json={'slot_id': slot1_id}, headers={'Authorization': f'Bearer {t1}'})
    assert res1.status_code == 201
    assert res1.get_json()['success'] is True

    # Slot 1 had capacity 1, so now it is full. Student 2 tries to book it -> must be rejected
    res2 = client.post('/api/student/bookings', json={'slot_id': slot1_id}, headers={'Authorization': f'Bearer {t2}'})
    assert res2.status_code == 400
    assert 'maximum capacity' in res2.get_json()['message']

def test_prevent_duplicate_booking(booking_test_setup):
    client, t1, _, slot1_id, _ = booking_test_setup

    # Student 1 books slot 1
    res1 = client.post('/api/student/bookings', json={'slot_id': slot1_id}, headers={'Authorization': f'Bearer {t1}'})
    assert res1.status_code == 201

    # Student 1 tries to book the same exam again -> duplicate booking error
    res_dup = client.post('/api/student/bookings', json={'slot_id': slot1_id}, headers={'Authorization': f'Bearer {t1}'})
    assert res_dup.status_code == 400
    assert 'Duplicate booking' in res_dup.get_json()['message']

def test_prevent_booking_closed_exam(booking_test_setup):
    client, t1, _, _, slot_closed_id = booking_test_setup

    res = client.post('/api/student/bookings', json={'slot_id': slot_closed_id}, headers={'Authorization': f'Bearer {t1}'})
    assert res.status_code == 400
    assert 'Booking is closed' in res.get_json()['message']

def test_cancel_booking_restores_capacity(booking_test_setup):
    client, t1, t2, slot1_id, _ = booking_test_setup

    # Student 1 books
    res1 = client.post('/api/student/bookings', json={'slot_id': slot1_id}, headers={'Authorization': f'Bearer {t1}'})
    booking_id = res1.get_json()['booking']['id']

    # Student 1 cancels
    res_cancel = client.post(f'/api/student/bookings/{booking_id}/cancel', headers={'Authorization': f'Bearer {t1}'})
    assert res_cancel.status_code == 200
    assert res_cancel.get_json()['success'] is True

    # Now Student 2 can book because capacity was freed
    res2 = client.post('/api/student/bookings', json={'slot_id': slot1_id}, headers={'Authorization': f'Bearer {t2}'})
    assert res2.status_code == 201
    assert res2.get_json()['success'] is True
