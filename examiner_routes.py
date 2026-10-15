from datetime import datetime, date, time
from flask import Blueprint, request, jsonify
from extensions import db
from models import (
    User, Examination, ExaminationRubric, ExaminationSlot, Booking, RubricScore
)
from auth_routes import role_required, get_current_user

examiner_bp = Blueprint('examiner', __name__, url_prefix='/api/examiner')

# -------------------------------------------------------------
# 1. Examiner Dashboard Overview & Statistics
# -------------------------------------------------------------
@examiner_bp.route('/dashboard', methods=['GET'])
@role_required('examiner')
def get_examiner_dashboard():
    """
    Returns examiner's summary metrics:
    - Assigned examinations
    - Created slots
    - Number of students booked
    - Pending evaluations
    - Completed evaluations
    """
    examiner = get_current_user()
    slots = ExaminationSlot.query.filter_by(examiner_id=examiner.id).all()
    slot_ids = [s.id for s in slots]

    bookings = Booking.query.filter(Booking.examination_slot_id.in_(slot_ids)).all() if slot_ids else []
    active_bookings = [b for b in bookings if b.status != 'Cancelled']
    pending_evaluations = [b for b in active_bookings if b.status == 'Booked']
    completed_evaluations = [b for b in active_bookings if b.status == 'Completed']

    # Unique examinations where this examiner has slots or active examinations
    assigned_exam_ids = list(set([s.examination_id for s in slots]))
    assigned_exams = Examination.query.filter(Examination.id.in_(assigned_exam_ids)).all() if assigned_exam_ids else []

    return jsonify({
        'success': True,
        'examiner': examiner.to_dict(),
        'dashboard': {
            'total_assigned_exams': len(assigned_exams),
            'total_created_slots': len(slots),
            'total_students_booked': len(active_bookings),
            'pending_evaluations_count': len(pending_evaluations),
            'completed_evaluations_count': len(completed_evaluations),
            'recent_slots': [s.to_dict() for s in slots[:5]],
            'pending_list': [b.to_dict() for b in pending_evaluations[:5]]
        }
    }), 200


# -------------------------------------------------------------
# 2. View Assigned & Available Examinations
# -------------------------------------------------------------
@examiner_bp.route('/examinations', methods=['GET'])
@role_required('examiner')
def get_examiner_examinations():
    """Lists examinations available for slot creation and evaluations."""
    exams = Examination.query.filter(Examination.status != 'Draft').order_by(Examination.created_at.desc()).all()
    examiner = get_current_user()

    results = []
    for exam in exams:
        item = exam.to_dict(include_rubrics=True)
        examiner_slots = [s for s in exam.slots if s.examiner_id == examiner.id]
        item['examiner_slots_count'] = len(examiner_slots)
        item['examiner_booked_count'] = sum(s.booked_count for s in examiner_slots)
        item['can_create_slots'] = exam.is_slot_creation_open()
        results.append(item)

    return jsonify({'success': True, 'examinations': results}), 200


# -------------------------------------------------------------
# 3. Examination Slot Management (Creation, Update, Removal)
# -------------------------------------------------------------
@examiner_bp.route('/slots', methods=['GET'])
@role_required('examiner')
def list_examiner_slots():
    """Lists only slots created by the current authenticated examiner."""
    examiner = get_current_user()
    slots = ExaminationSlot.query.filter_by(examiner_id=examiner.id).order_by(
        ExaminationSlot.slot_date.desc(), ExaminationSlot.start_time.asc()
    ).all()
    return jsonify({'success': True, 'slots': [s.to_dict(include_bookings=True) for s in slots]}), 200


@examiner_bp.route('/slots', methods=['POST'])
@role_required('examiner')
def create_examiner_slot():
    """
    Create examination slots ONLY during the slot creation period.
    Enforces window checks and validates times and venue.
    """
    examiner = get_current_user()
    data = request.get_json() or {}

    exam_id = data.get('examination_id')
    slot_date_str = data.get('slot_date')
    start_time_str = data.get('start_time')
    end_time_str = data.get('end_time')
    capacity = int(data.get('capacity', 5))
    venue_or_link = data.get('venue_or_link', '').strip() or 'Online Google Meet'

    if not exam_id or not slot_date_str or not start_time_str or not end_time_str:
        return jsonify({'success': False, 'message': 'Examination ID, Date, Start Time, and End Time are required.'}), 400

    exam = db.session.get(Examination, exam_id)
    if not exam:
        return jsonify({'success': False, 'message': 'Examination not found.'}), 404

    # Verification: Allow slot creation only during slot creation period
    if not exam.is_slot_creation_open():
        return jsonify({
            'success': False,
            'message': f'Slot creation is closed for this examination. Current phase is "{exam.status}". Slot creation window: {exam.slot_creation_start} to {exam.slot_creation_end}.'
        }), 403

    try:
        parsed_date = date.fromisoformat(slot_date_str)
        t_parts_s = [int(x) for x in start_time_str.split(':')[:2]]
        t_parts_e = [int(x) for x in end_time_str.split(':')[:2]]
        parsed_start = time(t_parts_s[0], t_parts_s[1])
        parsed_end = time(t_parts_e[0], t_parts_e[1])
    except Exception as e:
        return jsonify({'success': False, 'message': f'Invalid date or time format. ({e})'}), 400

    if parsed_start >= parsed_end:
        return jsonify({'success': False, 'message': 'Slot start time must be before end time.'}), 400

    if capacity < 1:
        return jsonify({'success': False, 'message': 'Capacity must be at least 1 student.'}), 400

    new_slot = ExaminationSlot(
        examination_id=exam.id,
        examiner_id=examiner.id,
        slot_date=parsed_date,
        start_time=parsed_start,
        end_time=parsed_end,
        capacity=capacity,
        booked_count=0,
        venue_or_link=venue_or_link,
        status='Open'
    )
    db.session.add(new_slot)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Examination slot created successfully.',
        'slot': new_slot.to_dict()
    }), 201


@examiner_bp.route('/slots/<int:slot_id>', methods=['PUT'])
@role_required('examiner')
def update_examiner_slot(slot_id):
    """
    Update examination slot BEFORE student booking starts.
    Only the assigned examiner can update their own slots.
    """
    examiner = get_current_user()
    slot = db.session.get(ExaminationSlot, slot_id)
    if not slot:
        return jsonify({'success': False, 'message': 'Slot not found.'}), 404

    # Ownership check
    if slot.examiner_id != examiner.id:
        return jsonify({'success': False, 'message': 'You are not authorized to modify slots assigned to another examiner.'}), 403

    # Booking restriction: cannot update if student bookings have started
    slot.update_status()
    if slot.booked_count > 0:
        return jsonify({
            'success': False,
            'message': f'Cannot modify slot because {slot.booked_count} student(s) have already booked this slot.'
        }), 400

    data = request.get_json() or {}
    if 'slot_date' in data:
        try:
            slot.slot_date = date.fromisoformat(data['slot_date'])
        except Exception:
            return jsonify({'success': False, 'message': 'Invalid date format.'}), 400

    if 'start_time' in data:
        t_parts = [int(x) for x in data['start_time'].split(':')[:2]]
        slot.start_time = time(t_parts[0], t_parts[1])

    if 'end_time' in data:
        t_parts = [int(x) for x in data['end_time'].split(':')[:2]]
        slot.end_time = time(t_parts[0], t_parts[1])

    if 'capacity' in data and int(data['capacity']) >= 1:
        slot.capacity = int(data['capacity'])

    if 'venue_or_link' in data:
        slot.venue_or_link = data['venue_or_link'].strip()

    db.session.commit()
    return jsonify({'success': True, 'message': 'Slot updated successfully.', 'slot': slot.to_dict()}), 200


@examiner_bp.route('/slots/<int:slot_id>', methods=['DELETE'])
@role_required('examiner')
def remove_examiner_slot(slot_id):
    """
    Remove examination slot BEFORE student booking starts.
    Only the assigned examiner can delete their own slots.
    """
    examiner = get_current_user()
    slot = db.session.get(ExaminationSlot, slot_id)
    if not slot:
        return jsonify({'success': False, 'message': 'Slot not found.'}), 404

    if slot.examiner_id != examiner.id:
        return jsonify({'success': False, 'message': 'You are not authorized to remove slots assigned to another examiner.'}), 403

    slot.update_status()
    if slot.booked_count > 0:
        return jsonify({
            'success': False,
            'message': f'Cannot remove slot because {slot.booked_count} student(s) have already booked it.'
        }), 400

    db.session.delete(slot)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Examination slot removed successfully.'}), 200


# -------------------------------------------------------------
# 4. Student Evaluation & Rubric-based Scoring
# -------------------------------------------------------------
@examiner_bp.route('/slots/<int:slot_id>/students', methods=['GET'])
@role_required('examiner')
def get_slot_students(slot_id):
    """
    View students booked for the examiner's slot along with evaluation rubrics.
    Ensures only the assigned examiner can access this roster.
    """
    examiner = get_current_user()
    slot = db.session.get(ExaminationSlot, slot_id)
    if not slot:
        return jsonify({'success': False, 'message': 'Slot not found.'}), 404

    if slot.examiner_id != examiner.id:
        return jsonify({'success': False, 'message': 'Access denied: You are not the assigned examiner for this slot.'}), 403

    bookings = Booking.query.filter(
        Booking.examination_slot_id == slot.id,
        Booking.status != 'Cancelled'
    ).all()

    rubrics = ExaminationRubric.query.filter_by(examination_id=slot.examination_id).all()

    return jsonify({
        'success': True,
        'slot': slot.to_dict(),
        'students': [b.to_dict(include_rubric_scores=True) for b in bookings],
        'rubrics': [r.to_dict() for r in rubrics]
    }), 200


@examiner_bp.route('/bookings/<int:booking_id>/evaluate', methods=['POST'])
@role_required('examiner')
def evaluate_student(booking_id):
    """
    Evaluate student using examination rubrics, submit marks and remarks.
    Ensures ONLY the assigned examiner can evaluate students booked into their slots.
    """
    examiner = get_current_user()
    booking = db.session.get(Booking, booking_id)
    if not booking:
        return jsonify({'success': False, 'message': 'Booking not found.'}), 404

    # Crucial security check: Ensure only assigned examiner evaluates
    if booking.slot.examiner_id != examiner.id:
        return jsonify({
            'success': False,
            'message': 'Access forbidden: Only the assigned examiner can evaluate students booked into this slot.'
        }), 403

    data = request.get_json() or {}
    scores_data = data.get('rubric_scores', [])
    feedback_remarks = data.get('feedback_remarks', '').strip()

    if not scores_data:
        return jsonify({'success': False, 'message': 'Rubric scores are required for evaluation.'}), 400

    exam = booking.examination
    rubrics_by_id = {r.id: r for r in exam.rubrics}

    # Remove any existing rubric scores for idempotency
    RubricScore.query.filter_by(booking_id=booking.id).delete()

    total_marks_obtained = 0.0
    for item in scores_data:
        rubric_id = item.get('rubric_id')
        score = float(item.get('score', 0.0))
        remarks = item.get('remarks', '').strip()

        rubric = rubrics_by_id.get(rubric_id)
        if not rubric:
            return jsonify({'success': False, 'message': f'Invalid rubric ID {rubric_id} for this examination.'}), 400

        if score < 0 or score > rubric.max_marks:
            return jsonify({
                'success': False,
                'message': f'Score for "{rubric.criterion_name}" must be between 0 and {rubric.max_marks}. (Received: {score})'
            }), 400

        total_marks_obtained += score
        rubric_score = RubricScore(
            booking_id=booking.id,
            rubric_id=rubric.id,
            score_obtained=score,
            remarks=remarks
        )
        db.session.add(rubric_score)

    # Update Booking record
    booking.total_marks_obtained = round(total_marks_obtained, 2)
    booking.is_passed = total_marks_obtained >= exam.pass_marks
    booking.feedback_remarks = feedback_remarks
    booking.evaluated_by_id = examiner.id
    booking.evaluated_at = datetime.utcnow()
    booking.status = 'Completed'

    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'Evaluation submitted successfully for {booking.student.full_name}. Result: {"PASS" if booking.is_passed else "FAIL"} ({booking.total_marks_obtained}/{exam.total_marks}).',
        'booking': booking.to_dict(include_rubric_scores=True)
    }), 200
