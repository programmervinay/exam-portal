from datetime import datetime, date
from flask import Blueprint, request, jsonify
from extensions import db, cache
from models import (
    User, Course, Examination, ExaminationSlot, Booking, RubricScore
)
from auth_routes import role_required, get_current_user

student_bp = Blueprint('student', __name__, url_prefix='/api/student')

# -------------------------------------------------------------
# 1. Student Dashboard Overview & Statistics
# -------------------------------------------------------------
@student_bp.route('/dashboard', methods=['GET'])
@role_required('student')
def get_student_dashboard():
    """
    Returns student dashboard metrics:
    - Active upcoming examination bookings
    - Completed examinations count
    - Passed examinations count
    - Upcoming schedule list
    - Recent results
    """
    student = get_current_user()
    bookings = Booking.query.filter_by(student_id=student.id).all()

    active_bookings = [b for b in bookings if b.status == 'Booked']
    completed_bookings = [b for b in bookings if b.status == 'Completed']
    passed_bookings = [b for b in completed_bookings if b.is_passed]

    # Upcoming examinations sorted by date
    upcoming = sorted(
        active_bookings,
        key=lambda b: (b.slot.slot_date, b.slot.start_time) if b.slot else (date.max, None)
    )

    return jsonify({
        'success': True,
        'student': student.to_dict(),
        'dashboard': {
            'upcoming_bookings_count': len(active_bookings),
            'completed_exams_count': len(completed_bookings),
            'passed_exams_count': len(passed_bookings),
            'upcoming_schedule': [b.to_dict() for b in upcoming[:5]],
            'recent_results': [b.to_dict(include_rubric_scores=True) for b in completed_bookings[:5]]
        }
    }), 200


# -------------------------------------------------------------
# 2. Browse & Search Available Examinations
# -------------------------------------------------------------
@student_bp.route('/examinations', methods=['GET'])
@role_required('student')
def list_available_examinations():
    """
    View, search, and filter available examinations.
    Identifies whether the student is already booked for each examination.
    """
    student = get_current_user()
    query = request.args.get('q', '').strip()
    course_id = request.args.get('course_id')

    stmt = Examination.query.filter(Examination.status.in_(['Booking Open', 'Slot Creation', 'Completed', 'Closed']))
    if course_id:
        stmt = stmt.filter_by(course_id=int(course_id))
    if query:
        stmt = stmt.filter(Examination.title.ilike(f'%{query}%'))

    exams = stmt.order_by(Examination.exam_start_date.asc()).all()
    user_bookings = {b.examination_id: b for b in student.bookings if b.status != 'Cancelled'}

    results = []
    for exam in exams:
        item = exam.to_dict(include_rubrics=True)
        user_booking = user_bookings.get(exam.id)
        item['is_booked_by_user'] = user_booking is not None
        item['user_booking_id'] = user_booking.id if user_booking else None
        item['user_booking_status'] = user_booking.status if user_booking else None
        item['booking_open'] = exam.is_booking_open()
        results.append(item)

    return jsonify({'success': True, 'examinations': results}), 200


# -------------------------------------------------------------
# 3. View Available Slots for an Examination
# -------------------------------------------------------------
@student_bp.route('/examinations/<int:exam_id>/slots', methods=['GET'])
@role_required('student')
def list_examination_slots(exam_id):
    """
    View available examination slots for booking.
    Displays slot timings, examiner name, venue/link, and available capacity.
    """
    exam = db.session.get(Examination, exam_id)
    if not exam:
        return jsonify({'success': False, 'message': 'Examination not found.'}), 404

    slots = ExaminationSlot.query.filter_by(examination_id=exam.id).order_by(
        ExaminationSlot.slot_date.asc(), ExaminationSlot.start_time.asc()
    ).all()

    # Refresh status & counts dynamically
    slot_data = []
    for s in slots:
        s.update_status()
        d = s.to_dict()
        slot_data.append(d)

    return jsonify({
        'success': True,
        'examination': exam.to_dict(),
        'is_booking_open': exam.is_booking_open(),
        'slots': slot_data
    }), 200


# -------------------------------------------------------------
# 4. Slot Booking (Strict Duplicate, Timing & Capacity Checks)
# -------------------------------------------------------------
@student_bp.route('/bookings', methods=['POST'])
@role_required('student')
def book_slot():
    """
    Book an examination slot with complete verification:
    1. Prevent booking when student slot booking is closed.
    2. Prevent duplicate bookings for the same examination.
    3. Prevent overbooking beyond available slot capacity.
    4. Automatically update slot status to 'Full' when capacity reached.
    """
    student = get_current_user()
    data = request.get_json() or {}
    slot_id = data.get('slot_id')

    if not slot_id:
        return jsonify({'success': False, 'message': 'Slot ID is required.'}), 400

    slot = db.session.get(ExaminationSlot, slot_id)
    if not slot:
        return jsonify({'success': False, 'message': 'Selected examination slot does not exist.'}), 404

    exam = slot.examination
    if not exam:
        return jsonify({'success': False, 'message': 'Associated examination not found.'}), 404

    # 1. Booking window check: Prevent booking when slot booking is closed
    if not exam.is_booking_open():
        return jsonify({
            'success': False,
            'message': f'Booking is closed for this examination. Status is "{exam.status}". Booking window: {exam.booking_start} to {exam.booking_end}.'
        }), 400

    # 2. Prevent duplicate booking for the same examination
    existing_booking = Booking.query.filter(
        Booking.student_id == student.id,
        Booking.examination_id == exam.id,
        Booking.status != 'Cancelled'
    ).first()

    if existing_booking:
        return jsonify({
            'success': False,
            'message': f'Duplicate booking prevented: You already have a confirmed slot ({existing_booking.slot.slot_date} {existing_booking.slot.start_time.strftime("%H:%M")}) for this examination.'
        }), 400

    # 3. Prevent overbooking beyond capacity
    slot.update_status()
    if slot.booked_count >= slot.capacity or slot.status == 'Full':
        return jsonify({
            'success': False,
            'message': 'This examination slot has reached its maximum capacity. Please choose another slot.'
        }), 400

    # Create Booking
    booking = Booking(
        student_id=student.id,
        examination_slot_id=slot.id,
        examination_id=exam.id,
        status='Booked',
        booking_date=datetime.utcnow()
    )
    db.session.add(booking)
    db.session.commit()

    # Update slot count and status
    slot.update_status()
    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'Slot booked successfully for {exam.title} on {slot.slot_date} at {slot.start_time.strftime("%H:%M")}.',
        'booking': booking.to_dict()
    }), 201


# -------------------------------------------------------------
# 5. Cancel Booking (With Deadline Verification)
# -------------------------------------------------------------
@student_bp.route('/bookings/<int:booking_id>/cancel', methods=['POST'])
@role_required('student')
def cancel_booking(booking_id):
    """
    Cancel booking before the booking deadline.
    Releases capacity back to the slot.
    """
    student = get_current_user()
    booking = db.session.get(Booking, booking_id)
    if not booking:
        return jsonify({'success': False, 'message': 'Booking not found.'}), 404

    # Privacy / ownership check
    if booking.student_id != student.id:
        return jsonify({'success': False, 'message': 'Access denied: You cannot cancel another student’s booking.'}), 403

    if booking.status == 'Cancelled':
        return jsonify({'success': False, 'message': 'This booking has already been cancelled.'}), 400

    if booking.status == 'Completed':
        return jsonify({'success': False, 'message': 'Cannot cancel an examination that has already been evaluated.'}), 400

    exam = booking.examination
    now = datetime.utcnow()

    # Deadline check: Cannot cancel if booking deadline has passed or exam is closed
    if now > exam.booking_end or exam.status in ['Closed', 'Completed']:
        return jsonify({
            'success': False,
            'message': f'Cancellation deadline exceeded. The booking window closed on {exam.booking_end}.'
        }), 400

    slot = booking.slot
    booking.status = 'Cancelled'
    db.session.commit()

    # Re-evaluate slot capacity
    if slot:
        slot.update_status()
        db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Examination booking cancelled successfully. The slot has been released.',
        'booking': booking.to_dict()
    }), 200


# -------------------------------------------------------------
# 6. Booking History & Upcoming Schedule
# -------------------------------------------------------------
@student_bp.route('/bookings', methods=['GET'])
@role_required('student')
def list_student_bookings():
    """
    Maintain and view complete examination and booking history per student.
    Students view only their own records.
    """
    student = get_current_user()
    status = request.args.get('status', '').strip()

    stmt = Booking.query.filter_by(student_id=student.id)
    if status:
        stmt = stmt.filter_by(status=status)

    bookings = stmt.order_by(Booking.booking_date.desc()).all()
    return jsonify({'success': True, 'bookings': [b.to_dict() for b in bookings]}), 200


# -------------------------------------------------------------
# 7. Examination Results & Evaluation Feedback Tracking
# -------------------------------------------------------------
@student_bp.route('/results', methods=['GET'])
@role_required('student')
def get_student_results():
    """
    View published results, marks breakdown by rubric, and evaluation feedback.
    Maintains complete academic progress per student.
    """
    student = get_current_user()
    completed_bookings = Booking.query.filter_by(
        student_id=student.id,
        status='Completed'
    ).order_by(Booking.evaluated_at.desc()).all()

    return jsonify({
        'success': True,
        'results': [b.to_dict(include_rubric_scores=True) for b in completed_bookings]
    }), 200
