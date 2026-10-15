import time
from flask import Blueprint, jsonify, make_response
from extensions import db, cache
from models import Course, Examination, ExaminationRubric, ExaminationSlot, Booking, User

cache_bp = Blueprint('public_cached', __name__, url_prefix='/api/public')

# Invalidation helper functions
def invalidate_all_public_cache():
    cache.delete('public_landing_stats')
    cache.delete('public_courses_catalog')
    cache.delete('public_active_examinations')

def invalidate_exam_rubrics_cache(exam_id):
    cache.delete(f'public_rubrics_exam_{exam_id}')
    cache.delete('public_active_examinations')
    cache.delete('public_landing_stats')


@cache_bp.route('/landing-stats', methods=['GET'])
def get_landing_stats():
    """
    Cached landing page overview stats.
    Optimized for high-concurrency public visits.
    Cached for 120 seconds with X-Cache HIT/MISS indicators.
    """
    cache_key = 'public_landing_stats'
    cached_data = cache.get(cache_key)

    if cached_data is not None:
        response = make_response(jsonify({'success': True, 'source': 'cache', 'data': cached_data}))
        response.headers['X-Cache'] = 'HIT'
        return response, 200

    # Fresh computation
    start_t = time.time()
    total_courses = Course.query.count()
    open_exams = Examination.query.filter(Examination.status.in_(['Booking Open', 'Slot Creation'])).count()
    total_slots = ExaminationSlot.query.count()
    total_students = User.query.filter_by(role='student').count()
    total_examiners = User.query.filter_by(role='examiner', is_active=True).count()
    completed_evaluations = Booking.query.filter_by(status='Completed').count()

    stats_data = {
        'total_courses': total_courses,
        'open_examinations': open_exams,
        'total_slots': total_slots,
        'total_students': total_students,
        'active_examiners': total_examiners,
        'completed_evaluations': completed_evaluations,
        'computed_in_ms': round((time.time() - start_t) * 1000, 2)
    }

    cache.set(cache_key, stats_data, timeout=120)

    response = make_response(jsonify({'success': True, 'source': 'database', 'data': stats_data}))
    response.headers['X-Cache'] = 'MISS'
    return response, 200


@cache_bp.route('/courses', methods=['GET'])
def get_cached_courses():
    """
    Cached courses catalog.
    Cache expires every 300 seconds or upon course updates.
    """
    cache_key = 'public_courses_catalog'
    cached = cache.get(cache_key)
    if cached is not None:
        resp = make_response(jsonify({'success': True, 'source': 'cache', 'courses': cached}))
        resp.headers['X-Cache'] = 'HIT'
        return resp, 200

    courses = Course.query.order_by(Course.course_code).all()
    data = [c.to_dict() for c in courses]
    cache.set(cache_key, data, timeout=300)

    resp = make_response(jsonify({'success': True, 'source': 'database', 'courses': data}))
    resp.headers['X-Cache'] = 'MISS'
    return resp, 200


@cache_bp.route('/examinations', methods=['GET'])
def get_cached_examinations():
    """
    Cached active examinations list.
    """
    cache_key = 'public_active_examinations'
    cached = cache.get(cache_key)
    if cached is not None:
        resp = make_response(jsonify({'success': True, 'source': 'cache', 'examinations': cached}))
        resp.headers['X-Cache'] = 'HIT'
        return resp, 200

    exams = Examination.query.filter(Examination.status != 'Draft').order_by(Examination.exam_start_date.asc()).all()
    data = [e.to_dict(include_rubrics=True, include_slots=True) for e in exams]
    cache.set(cache_key, data, timeout=180)

    resp = make_response(jsonify({'success': True, 'source': 'database', 'examinations': data}))
    resp.headers['X-Cache'] = 'MISS'
    return resp, 200


@cache_bp.route('/examinations/<int:exam_id>/rubrics', methods=['GET'])
def get_cached_exam_rubrics(exam_id):
    """
    Cached examination rubrics with granular invalidation.
    """
    cache_key = f'public_rubrics_exam_{exam_id}'
    cached = cache.get(cache_key)
    if cached is not None:
        resp = make_response(jsonify({'success': True, 'source': 'cache', 'rubrics': cached}))
        resp.headers['X-Cache'] = 'HIT'
        return resp, 200

    rubrics = ExaminationRubric.query.filter_by(examination_id=exam_id).all()
    data = [r.to_dict() for r in rubrics]
    cache.set(cache_key, data, timeout=300)

    resp = make_response(jsonify({'success': True, 'source': 'database', 'rubrics': data}))
    resp.headers['X-Cache'] = 'MISS'
    return resp, 200
