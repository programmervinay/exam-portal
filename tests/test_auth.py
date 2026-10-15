import pytest
from config import Config
from app import create_app
from extensions import db
from models import User

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    CACHE_TYPE = 'SimpleCache'

@pytest.fixture
def client():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        # Create predefined admin
        admin = User(email='admin@portal.edu', full_name='Admin', role='admin')
        admin.set_password('Admin@123')
        # Create predefined examiner
        examiner = User(email='examiner@portal.edu', full_name='Dr. Examiner', role='examiner')
        examiner.set_password('Examiner@123')
        db.session.add_all([admin, examiner])
        db.session.commit()
        yield app.test_client()
        db.drop_all()

def test_student_registration_success(client):
    res = client.post('/api/auth/register', json={
        'email': 'newstudent@portal.edu',
        'password': 'password123',
        'full_name': 'New Student',
        'phone': '1234567890'
    })
    assert res.status_code == 201
    data = res.get_json()
    assert data['success'] is True
    assert 'token' in data
    assert data['user']['role'] == 'student'

def test_prevent_admin_or_examiner_public_registration(client):
    res = client.post('/api/auth/register', json={
        'email': 'fakeadmin@portal.edu',
        'password': 'password123',
        'full_name': 'Hacker Admin',
        'role': 'admin'
    })
    assert res.status_code == 400
    data = res.get_json()
    assert data['success'] is False

def test_admin_predefined_login(client):
    res = client.post('/api/auth/login', json={
        'email': 'admin@portal.edu',
        'password': 'Admin@123'
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert data['user']['role'] == 'admin'
    assert data['redirect_route'] == '/admin/dashboard'
    assert 'token' in data

def test_examiner_login(client):
    res = client.post('/api/auth/login', json={
        'email': 'examiner@portal.edu',
        'password': 'Examiner@123'
    })
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert data['user']['role'] == 'examiner'
    assert data['redirect_route'] == '/examiner/dashboard'

def test_invalid_login(client):
    res = client.post('/api/auth/login', json={
        'email': 'admin@portal.edu',
        'password': 'WrongPassword'
    })
    assert res.status_code == 401
    data = res.get_json()
    assert data['success'] is False
