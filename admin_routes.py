from datetime import datetime
from flask import Blueprint, request, jsonify
from extensions import db, cache
from models import (
    User, ExaminerProfile, Course, Examination, ExaminationRubric,
    ExaminationSlot, Booking, RubricScore
)
from auth_routes import role_required

admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')

# -------------------------------------------------------------
# 1. Admin Dashboard Overview & Statistics
# -------------------------------------------------------------
@admin_bp.route('/stats', methods=['GET'])
@role_required('admin')
def get_dashboard_stats():
    """Returns system-wide metrics and aggregates for the Admin Dashboard."""
    total_courses = Course.query.count()
    total_examinations = Examination.query.count()
    total_examiners = User.query.filter_by(role='examiner').count()
    active_examiners = User.query.filter_by(role='examiner', is_active=True).count()
    total_students = User.query.filter_by(role='student').count()
    total_slots = ExaminationSlot.query.count()
    total_bookings = Booking.query.count()
    
    completed_bookings = Booking.query.filter_by(status='Completed').count()
    passed_bookings = Booking.query.filter_by(status='Completed', is_passed=True).count()
    failed_bookings = Booking.query.filter_by(status='Completed', is_passed=False).count()
    active_bookings = Booking.query.filter_by(status='Booked').count()

    # Breakdown by exam status
    exams_by_status = {
        'Draft': Examination.query.filter_by(status='Draft').count(),
        'Slot Creation': Examination.query.filter_by(status='Slot Creation').count(),
        'Booking Open': Examination.query.filter_by(status='Booking Open').count(),
        'Closed': Examination.query.filter_by(status='Closed').count(),
        'Completed': Examination.query.filter_by(status='Completed').count()
    }

    return jsonify({
        'success': True,
        'stats': {
            'total_courses': total_courses,
            'total_examinations': total_examinations,
            'total_examiners': total_examiners,
            'active_examiners': active_examiners,
            'total_students': total_students,
            'total_slots': total_slots,
            'total_bookings': total_bookings,
            'active_bookings': active_bookings,
            'completed_bookings': completed_bookings,
            'passed_bookings': passed_bookings,
            'failed_bookings': failed_bookings,
            'pass_rate': round((passed_bookings / completed_bookings * 100), 1) if completed_bookings > 0 else 0,
            'exams_by_status': exams_by_status
        }
    }), 200


# -------------------------------------------------------------
# 2. Course Management (CRUD)
# -------------------------------------------------------------
@admin_bp.route('/courses', methods=['GET'])
@role_required('admin')
def get_courses():
    query = request.args.get('q', '').strip()
    if query:
        courses = Course.query.filter(
            (Course.course_code.ilike(f'%{query}%')) | (Course.course_name.ilike(f'%{query}%'))
        ).order_by(Course.course_code).all()
    else:
        courses = Course.query.order_by(Course.course_code).all()
    return jsonify({'success': True, 'courses': [c.to_dict() for c in courses]}), 200


@admin_bp.route('/courses', methods=['POST'])
@role_required('admin')
def create_course():
    data = request.get_json() or {}
    code = data.get('course_code', '').strip().upper()
    name = data.get('course_name', '').strip()
    desc = data.get('description', '').strip()
    credits = int(data.get('credits', 4))

    if not code or not name:
        return jsonify({'success': False, 'message': 'Course code and name are required.'}), 400

    if Course.query.filter_by(course_code=code).first():
        return jsonify({'success': False, 'message': f'Course with code {code} already exists.'}), 409

    course = Course(course_code=code, course_name=name, description=desc, credits=credits)
    db.session.add(course)
    db.session.commit()
    cache.delete('public_courses')

    return jsonify({'success': True, 'message': 'Course created successfully.', 'course': course.to_dict()}), 201


@admin_bp.route('/courses/<int:course_id>', methods=['PUT'])
@role_required('admin')
def update_course(course_id):
    course = db.session.get(Course, course_id)
    if not course:
        return jsonify({'success': False, 'message': 'Course not found.'}), 404

    data = request.get_json() or {}
    if 'course_code' in data and data['course_code'].strip():
        code = data['course_code'].strip().upper()
        existing = Course.query.filter(Course.course_code == code, Course.id != course.id).first()
        if existing:
            return jsonify({'success': False, 'message': 'Course code already in use.'}), 409
        course.course_code = code

    if 'course_name' in data and data['course_name'].strip():
        course.course_name = data['course_name'].strip()
    if 'description' in data:
        course.description = data['description'].strip()
    if 'credits' in data:
        course.credits = int(data['credits'])

    db.session.commit()
    cache.delete('public_courses')
    return jsonify({'success': True, 'message': 'Course updated successfully.', 'course': course.to_dict()}), 200


@admin_bp.route('/courses/<int:course_id>', methods=['DELETE'])
@role_required('admin')
def delete_course(course_id):
    course = db.session.get(Course, course_id)
    if not course:
        return jsonify({'success': False, 'message': 'Course not found.'}), 404

    db.session.delete(course)
    db.session.commit()
    cache.delete('public_courses')
    return jsonify({'success': True, 'message': 'Course and associated examinations removed successfully.'}), 200


# -------------------------------------------------------------
# 3. Examination Management & Timelines
# -------------------------------------------------------------
@admin_bp.route('/examinations', methods=['GET'])
@role_required('admin')
def get_examinations():
    status = request.args.get('status', '').strip()
    query = request.args.get('q', '').strip()

    stmt = Examination.query
    if status:
        stmt = stmt.filter(Examination.status == status)
    if query:
        stmt = stmt.filter(Examination.title.ilike(f'%{query}%'))

    exams = stmt.order_by(Examination.created_at.desc()).all()
    return jsonify({'success': True, 'examinations': [e.to_dict(include_rubrics=True, include_slots=True) for e in exams]}), 200


@admin_bp.route('/examinations', methods=['POST'])
@role_required('admin')
def create_examination():
    data = request.get_json() or {}
    course_id = data.get('course_id')
    title = data.get('title', '').strip()
    description = data.get('description', '').strip()
    exam_type = data.get('exam_type', 'Viva Voce')
    total_marks = float(data.get('total_marks', 100.0))
    pass_marks = float(data.get('pass_marks', 40.0))
    status = data.get('status', 'Draft')

    if not course_id or not title:
        return jsonify({'success': False, 'message': 'Course ID and Examination Title are required.'}), 400

    course = db.session.get(Course, course_id)
    if not course:
        return jsonify({'success': False, 'message': 'Specified Course does not exist.'}), 404

    def parse_dt(dt_val, fallback):
        if not dt_val:
            return fallback
        try:
            return datetime.fromisoformat(dt_val.replace('Z', '+00:00')).replace(tzinfo=None)
        except Exception:
            return fallback

    now = datetime.utcnow()
    slot_creation_start = parse_dt(data.get('slot_creation_start'), now)
    slot_creation_end = parse_dt(data.get('slot_creation_end'), now + datetime.resolution * 86400 * 7)
    booking_start = parse_dt(data.get('booking_start'), now)
    booking_end = parse_dt(data.get('booking_end'), now + datetime.resolution * 86400 * 14)
    exam_start_date = parse_dt(data.get('exam_start_date'), now)
    exam_end_date = parse_dt(data.get('exam_end_date'), now + datetime.resolution * 86400 * 20)

    exam = Examination(
        course_id=course_id,
        title=title,
        description=description,
        exam_type=exam_type,
        total_marks=total_marks,
        pass_marks=pass_marks,
        slot_creation_start=slot_creation_start,
        slot_creation_end=slot_creation_end,
        booking_start=booking_start,
        booking_end=booking_end,
        exam_start_date=exam_start_date,
        exam_end_date=exam_end_date,
        status=status
    )
    db.session.add(exam)
    db.session.commit()

    # Optional default rubric if requested
    if data.get('default_rubrics'):
        for r in data.get('default_rubrics'):
            rubric = ExaminationRubric(
                examination_id=exam.id,
                criterion_name=r.get('criterion_name', 'General Assessment'),
                max_marks=float(r.get('max_marks', total_marks)),
                description=r.get('description', '')
            )
            db.session.add(rubric)
        db.session.commit()

    cache.delete('public_examinations')
    return jsonify({'success': True, 'message': 'Examination created successfully.', 'examination': exam.to_dict()}), 201


@admin_bp.route('/examinations/<int:exam_id>', methods=['PUT'])
@role_required('admin')
def update_examination(exam_id):
    exam = db.session.get(Examination, exam_id)
    if not exam:
        return jsonify({'success': False, 'message': 'Examination not found.'}), 404

    data = request.get_json() or {}
    if 'title' in data and data['title'].strip():
        exam.title = data['title'].strip()
    if 'description' in data:
        exam.description = data['description'].strip()
    if 'exam_type' in data:
        exam.exam_type = data['exam_type']
    if 'total_marks' in data:
        exam.total_marks = float(data['total_marks'])
    if 'pass_marks' in data:
        exam.pass_marks = float(data['pass_marks'])
    if 'status' in data and data['status'] in ['Draft', 'Slot Creation', 'Booking Open', 'Closed', 'Completed']:
        exam.status = data['status']

    def parse_dt(val):
        if not val:
            return None
        try:
            return datetime.fromisoformat(val.replace('Z', '+00:00')).replace(tzinfo=None)
        except Exception:
            return None

    for dt_field in ['slot_creation_start', 'slot_creation_end', 'booking_start', 'booking_end', 'exam_start_date', 'exam_end_date']:
        if dt_field in data and data[dt_field]:
            parsed = parse_dt(data[dt_field])
            if parsed:
                setattr(exam, dt_field, parsed)

    db.session.commit()
    cache.delete('public_examinations')
    cache.delete(f'exam_rubrics_{exam_id}')
    return jsonify({'success': True, 'message': 'Examination updated successfully.', 'examination': exam.to_dict()}), 200


@admin_bp.route('/examinations/<int:exam_id>/status', methods=['PATCH'])
@role_required('admin')
def change_exam_status(exam_id):
    """Allows Admin to toggle lifecycle phases: Draft, Slot Creation, Booking Open, Closed, Completed."""
    exam = db.session.get(Examination, exam_id)
    if not exam:
        return jsonify({'success': False, 'message': 'Examination not found.'}), 404

    data = request.get_json() or {}
    new_status = data.get('status')
    valid_statuses = ['Draft', 'Slot Creation', 'Booking Open', 'Closed', 'Completed']
    if new_status not in valid_statuses:
        return jsonify({'success': False, 'message': f'Invalid status. Allowed values: {valid_statuses}'}), 400

    exam.status = new_status
    db.session.commit()
    cache.delete('public_examinations')
    return jsonify({
        'success': True,
        'message': f'Examination status successfully transitioned to "{new_status}".',
        'examination': exam.to_dict()
    }), 200


@admin_bp.route('/examinations/<int:exam_id>', methods=['DELETE'])
@role_required('admin')
def delete_examination(exam_id):
    exam = db.session.get(Examination, exam_id)
    if not exam:
        return jsonify({'success': False, 'message': 'Examination not found.'}), 404

    db.session.delete(exam)
    db.session.commit()
    cache.delete('public_examinations')
    cache.delete(f'exam_rubrics_{exam_id}')
    return jsonify({'success': True, 'message': 'Examination and associated slots/rubrics deleted successfully.'}), 200


# -------------------------------------------------------------
# 4. Examination Rubric Management
# -------------------------------------------------------------
@admin_bp.route('/examinations/<int:exam_id>/rubrics', methods=['GET'])
@role_required('admin', 'examiner')
def get_examination_rubrics(exam_id):
    rubrics = ExaminationRubric.query.filter_by(examination_id=exam_id).all()
    return jsonify({'success': True, 'rubrics': [r.to_dict() for r in rubrics]}), 200


@admin_bp.route('/examinations/<int:exam_id>/rubrics', methods=['POST'])
@role_required('admin')
def add_rubric(exam_id):
    exam = db.session.get(Examination, exam_id)
    if not exam:
        return jsonify({'success': False, 'message': 'Examination not found.'}), 404

    data = request.get_json() or {}
    criterion_name = data.get('criterion_name', '').strip()
    max_marks = float(data.get('max_marks', 0.0))
    description = data.get('description', '').strip()

    if not criterion_name or max_marks <= 0:
        return jsonify({'success': False, 'message': 'Criterion name and positive max marks are required.'}), 400

    rubric = ExaminationRubric(
        examination_id=exam.id,
        criterion_name=criterion_name,
        max_marks=max_marks,
        description=description
    )
    db.session.add(rubric)
    db.session.commit()
    cache.delete(f'exam_rubrics_{exam_id}')
    return jsonify({'success': True, 'message': 'Rubric criterion added.', 'rubric': rubric.to_dict()}), 201


@admin_bp.route('/rubrics/<int:rubric_id>', methods=['PUT'])
@role_required('admin')
def update_rubric(rubric_id):
    rubric = db.session.get(ExaminationRubric, rubric_id)
    if not rubric:
        return jsonify({'success': False, 'message': 'Rubric not found.'}), 404

    data = request.get_json() or {}
    if 'criterion_name' in data and data['criterion_name'].strip():
        rubric.criterion_name = data['criterion_name'].strip()
    if 'max_marks' in data and float(data['max_marks']) > 0:
        rubric.max_marks = float(data['max_marks'])
    if 'description' in data:
        rubric.description = data['description'].strip()

    db.session.commit()
    cache.delete(f'exam_rubrics_{rubric.examination_id}')
    return jsonify({'success': True, 'message': 'Rubric updated.', 'rubric': rubric.to_dict()}), 200


@admin_bp.route('/rubrics/<int:rubric_id>', methods=['DELETE'])
@role_required('admin')
def delete_rubric(rubric_id):
    rubric = db.session.get(ExaminationRubric, rubric_id)
    if not rubric:
        return jsonify({'success': False, 'message': 'Rubric not found.'}), 404

    exam_id = rubric.examination_id
    db.session.delete(rubric)
    db.session.commit()
    cache.delete(f'exam_rubrics_{exam_id}')
    return jsonify({'success': True, 'message': 'Rubric deleted.'}), 200


# -------------------------------------------------------------
# 5. Examiner Management (Add, Approve, Deactivate)
# -------------------------------------------------------------
@admin_bp.route('/examiners', methods=['GET'])
@role_required('admin')
def list_examiners():
    query = request.args.get('q', '').strip()
    stmt = User.query.filter_by(role='examiner')
    if query:
        stmt = stmt.filter((User.full_name.ilike(f'%{query}%')) | (User.email.ilike(f'%{query}%')))
    examiners = stmt.order_by(User.full_name).all()
    return jsonify({'success': True, 'examiners': [e.to_dict() for e in examiners]}), 200


@admin_bp.route('/examiners', methods=['POST'])
@role_required('admin')
def create_examiner():
    """Admin creates examiner account and sets initial credentials."""
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    password = data.get('password', '').strip() or 'Examiner@123'
    full_name = data.get('full_name', '').strip()
    phone = data.get('phone', '').strip()
    
    qualification = data.get('qualification', 'Ph.D. / M.Tech')
    department = data.get('department', 'Computer Science & Engineering')
    specialisation = data.get('specialisation', 'Software Engineering')
    experience_years = int(data.get('experience_years', 5))
    approved = bool(data.get('approved', True))

    if not email or not full_name:
        return jsonify({'success': False, 'message': 'Email and Full Name are required.'}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({'success': False, 'message': 'An account with this email already exists.'}), 409

    examiner = User(email=email, full_name=full_name, phone=phone, role='examiner', is_active=True)
    examiner.set_password(password)
    db.session.add(examiner)
    db.session.commit()

    profile = ExaminerProfile(
        user_id=examiner.id,
        qualification=qualification,
        department=department,
        specialisation=specialisation,
        experience_years=experience_years,
        approved_by_admin=approved
    )
    db.session.add(profile)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'Examiner account created for {full_name}. Credentials sent via system mail.',
        'examiner': examiner.to_dict(),
        'default_password': password
    }), 201


@admin_bp.route('/examiners/<int:user_id>/toggle-status', methods=['PATCH'])
@role_required('admin')
def toggle_examiner_status(user_id):
    """Admin can activate, deactivate, or toggle approval for an examiner."""
    user = db.session.get(User, user_id)
    if not user or user.role != 'examiner':
        return jsonify({'success': False, 'message': 'Examiner not found.'}), 404

    data = request.get_json() or {}
    if 'is_active' in data:
        user.is_active = bool(data['is_active'])
    if 'approved' in data and user.examiner_profile:
        user.examiner_profile.approved_by_admin = bool(data['approved'])

    db.session.commit()
    return jsonify({
        'success': True,
        'message': 'Examiner status updated successfully.',
        'examiner': user.to_dict()
    }), 200


# -------------------------------------------------------------
# 6. Student Management & Overview
# -------------------------------------------------------------
@admin_bp.route('/students', methods=['GET'])
@role_required('admin')
def list_students():
    query = request.args.get('q', '').strip()
    stmt = User.query.filter_by(role='student')
    if query:
        stmt = stmt.filter((User.full_name.ilike(f'%{query}%')) | (User.email.ilike(f'%{query}%')))
    students = stmt.order_by(User.full_name).all()
    
    student_list = []
    for s in students:
        s_dict = s.to_dict()
        s_dict['total_bookings'] = len(s.bookings)
        s_dict['completed_exams'] = len([b for b in s.bookings if b.status == 'Completed'])
        student_list.append(s_dict)

    return jsonify({'success': True, 'students': student_list}), 200


# -------------------------------------------------------------
# 7. Slot Management & Examiner Reassignment (Admin Override)
# -------------------------------------------------------------
@admin_bp.route('/slots', methods=['GET'])
@role_required('admin')
def list_all_slots():
    """View all examination slots system-wide."""
    exam_id = request.args.get('examination_id')
    stmt = ExaminationSlot.query
    if exam_id:
        stmt = stmt.filter_by(examination_id=int(exam_id))
    slots = stmt.order_by(ExaminationSlot.slot_date.desc(), ExaminationSlot.start_time.asc()).all()
    return jsonify({'success': True, 'slots': [s.to_dict(include_bookings=True) for s in slots]}), 200


@admin_bp.route('/slots/<int:slot_id>/reassign-examiner', methods=['PUT'])
@role_required('admin')
def reassign_slot_examiner(slot_id):
    """
    Exceptional situation override:
    Change the assigned examiner for an entire slot and update pending booking evaluators.
    """
    slot = db.session.get(ExaminationSlot, slot_id)
    if not slot:
        return jsonify({'success': False, 'message': 'Slot not found.'}), 404

    data = request.get_json() or {}
    new_examiner_id = data.get('new_examiner_id')
    new_examiner = db.session.get(User, new_examiner_id)
    if not new_examiner or new_examiner.role != 'examiner':
        return jsonify({'success': False, 'message': 'Valid replacement examiner is required.'}), 400

    old_name = slot.examiner.full_name if slot.examiner else 'Unknown'
    slot.examiner_id = new_examiner.id
    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'Slot examiner successfully changed from {old_name} to {new_examiner.full_name}.',
        'slot': slot.to_dict()
    }), 200


# -------------------------------------------------------------
# 8. Booking Oversight & Admin Reschedule
# -------------------------------------------------------------
@admin_bp.route('/bookings', methods=['GET'])
@role_required('admin')
def list_all_bookings():
    """View and search all bookings across students, exams, and statuses."""
    query = request.args.get('q', '').strip()
    status = request.args.get('status', '').strip()
    exam_id = request.args.get('examination_id')

    stmt = Booking.query.join(User, Booking.student_id == User.id)
    if status:
        stmt = stmt.filter(Booking.status == status)
    if exam_id:
        stmt = stmt.filter(Booking.examination_id == int(exam_id))
    if query:
        stmt = stmt.filter((User.full_name.ilike(f'%{query}%')) | (User.email.ilike(f'%{query}%')))

    bookings = stmt.order_by(Booking.booking_date.desc()).all()
    return jsonify({'success': True, 'bookings': [b.to_dict() for b in bookings]}), 200


@admin_bp.route('/bookings/<int:booking_id>/reschedule', methods=['PUT'])
@role_required('admin')
def reschedule_booking(booking_id):
    """
    Admin override: Reschedule a student booking to a different slot.
    Updates slot capacities appropriately and checks destination validity.
    """
    booking = db.session.get(Booking, booking_id)
    if not booking:
        return jsonify({'success': False, 'message': 'Booking not found.'}), 404

    data = request.get_json() or {}
    new_slot_id = data.get('new_slot_id')
    target_slot = db.session.get(ExaminationSlot, new_slot_id)
    if not target_slot:
        return jsonify({'success': False, 'message': 'Destination examination slot not found.'}), 404

    if target_slot.examination_id != booking.examination_id:
        return jsonify({'success': False, 'message': 'Target slot belongs to a different examination.'}), 400

    if target_slot.id == booking.examination_slot_id:
        return jsonify({'success': False, 'message': 'Student is already booked in this slot.'}), 400

    # Check capacity
    target_slot.update_status()
    if target_slot.booked_count >= target_slot.capacity:
        return jsonify({'success': False, 'message': 'Selected target slot is already at full capacity.'}), 400

    # Old slot cleanup
    old_slot = booking.slot
    booking.examination_slot_id = target_slot.id
    db.session.commit()

    if old_slot:
        old_slot.update_status()
    target_slot.update_status()
    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'Booking for {booking.student.full_name} successfully rescheduled to {target_slot.slot_date} at {target_slot.start_time.strftime("%H:%M")}.',
        'booking': booking.to_dict()
    }), 200
