import pytest
from config import Config
from app import create_app
from extensions import db, cache
from models import Course, Examination, ExaminationRubric
from cache_routes import invalidate_all_public_cache

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    CACHE_TYPE = 'SimpleCache'

@pytest.fixture
def cache_client():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        course = Course(course_code='CS3001', course_name='Algorithms')
        db.session.add(course)
        db.session.commit()
        cache.clear()
        yield app.test_client()
        cache.clear()
        db.drop_all()

def test_cache_miss_then_hit(cache_client):
    # First request: should be Cache MISS
    res1 = cache_client.get('/api/public/courses')
    assert res1.status_code == 200
    assert res1.headers.get('X-Cache') == 'MISS'
    data1 = res1.get_json()
    assert data1['source'] == 'database'
    assert len(data1['courses']) == 1

    # Second request: should be Cache HIT
    res2 = cache_client.get('/api/public/courses')
    assert res2.status_code == 200
    assert res2.headers.get('X-Cache') == 'HIT'
    data2 = res2.get_json()
    assert data2['source'] == 'cache'

def test_cache_invalidation(cache_client):
    # Prime cache
    res1 = cache_client.get('/api/public/courses')
    assert res1.headers.get('X-Cache') == 'MISS'

    # Invalidate
    invalidate_all_public_cache()

    # Next request should be MISS again
    res3 = cache_client.get('/api/public/courses')
    assert res3.headers.get('X-Cache') == 'MISS'
