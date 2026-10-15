import pytest
from datetime import datetime
from config import Config
from app import create_app
from extensions import db
from models import User, Course, Examination, ExaminationSlot, Booking

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    CACHE_TYPE = 'SimpleCache'

@pytest.fixture
def analytics_setup():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        # Admin
        admin = User(email='admin_an@portal.edu', full_name='Admin Analytics', role='admin')
        admin.set_password('Admin@123')
        # Student
        student = User(email='student_an@portal.edu', full_name='Student Analytics', role='student')
        student.set_password('Student@123')
        # Examiner
        examiner = User(email='examiner_an@portal.edu', full_name='Dr. Analytics', role='examiner')
        examiner.set_password('Examiner@123')
        db.session.add_all([admin, student, examiner])
        db.session.commit()

        client = app.test_client()
        admin_token = client.post('/api/auth/login', json={'email': 'admin_an@portal.edu', 'password': 'Admin@123'}).get_json()['token']
        student_token = client.post('/api/auth/login', json={'email': 'student_an@portal.edu', 'password': 'Student@123'}).get_json()['token']

        yield client, admin_token, student_token
        db.drop_all()

def test_analytics_overview_admin_success(analytics_setup):
    client, admin_token, _ = analytics_setup
    res = client.get('/api/analytics/overview', headers={'Authorization': f'Bearer {admin_token}'})
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert 'pass_fail' in data['analytics']
    assert 'participation' in data['analytics']
    assert 'performance' in data['analytics']
    assert 'examiner_workload' in data['analytics']

def test_analytics_forbidden_for_student(analytics_setup):
    client, _, student_token = analytics_setup
    res = client.get('/api/analytics/overview', headers={'Authorization': f'Bearer {student_token}'})
    assert res.status_code == 403
