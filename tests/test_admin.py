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
def client_and_tokens():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        # Create Admin
        admin = User(email='admin@portal.edu', full_name='Admin User', role='admin')
        admin.set_password('Admin@123')
        # Create Examiner
        examiner = User(email='examiner@portal.edu', full_name='Examiner User', role='examiner')
        examiner.set_password('Examiner@123')
        # Create Student
        student = User(email='student@portal.edu', full_name='Student User', role='student')
        student.set_password('Student@123')
        db.session.add_all([admin, examiner, student])
        db.session.commit()

        client = app.test_client()

        # Login admin
        res_adm = client.post('/api/auth/login', json={'email': 'admin@portal.edu', 'password': 'Admin@123'})
        admin_token = res_adm.get_json()['token']

        # Login student
        res_stu = client.post('/api/auth/login', json={'email': 'student@portal.edu', 'password': 'Student@123'})
        student_token = res_stu.get_json()['token']

        yield client, admin_token, student_token
        db.drop_all()

def test_admin_dashboard_stats(client_and_tokens):
    client, admin_token, student_token = client_and_tokens
    res = client.get('/api/admin/stats', headers={'Authorization': f'Bearer {admin_token}'})
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert 'total_courses' in data['stats']
    assert 'total_examinations' in data['stats']

def test_student_cannot_access_admin_stats(client_and_tokens):
    client, admin_token, student_token = client_and_tokens
    res = client.get('/api/admin/stats', headers={'Authorization': f'Bearer {student_token}'})
    assert res.status_code == 403

def test_admin_course_crud(client_and_tokens):
    client, admin_token, _ = client_and_tokens
    headers = {'Authorization': f'Bearer {admin_token}'}

    # Create Course
    res = client.post('/api/admin/courses', json={
        'course_code': 'CS9999',
        'course_name': 'Cloud Native Architectures',
        'description': 'Distributed cloud microservices',
        'credits': 4
    }, headers=headers)
    assert res.status_code == 201
    course_id = res.get_json()['course']['id']

    # Update Course
    res_up = client.put(f'/api/admin/courses/{course_id}', json={
        'course_name': 'Cloud Native Architectures Advanced'
    }, headers=headers)
    assert res_up.status_code == 200
    assert res_up.get_json()['course']['course_name'] == 'Cloud Native Architectures Advanced'

    # List Courses
    res_list = client.get('/api/admin/courses', headers=headers)
    assert res_list.status_code == 200
    assert any(c['course_code'] == 'CS9999' for c in res_list.get_json()['courses'])

def test_admin_examination_and_rubrics(client_and_tokens):
    client, admin_token, _ = client_and_tokens
    headers = {'Authorization': f'Bearer {admin_token}'}

    # First create course
    c_res = client.post('/api/admin/courses', json={'course_code': 'CS8001', 'course_name': 'Test Course'}, headers=headers)
    c_id = c_res.get_json()['course']['id']

    # Create Exam
    e_res = client.post('/api/admin/examinations', json={
        'course_id': c_id,
        'title': 'Midterm Viva',
        'total_marks': 100,
        'pass_marks': 40,
        'status': 'Slot Creation'
    }, headers=headers)
    assert e_res.status_code == 201
    exam_id = e_res.get_json()['examination']['id']

    # Add Rubric
    r_res = client.post(f'/api/admin/examinations/{exam_id}/rubrics', json={
        'criterion_name': 'Code Quality',
        'max_marks': 50,
        'description': 'Clean, documented code'
    }, headers=headers)
    assert r_res.status_code == 201
    rubric_id = r_res.get_json()['rubric']['id']

    # Update Status
    s_res = client.patch(f'/api/admin/examinations/{exam_id}/status', json={'status': 'Booking Open'}, headers=headers)
    assert s_res.status_code == 200
    assert s_res.get_json()['examination']['status'] == 'Booking Open'
