from flask import Blueprint, jsonify
from extensions import db
from models import Examination, Booking, User, Course
from auth_routes import role_required

analytics_bp = Blueprint('analytics', __name__, url_prefix='/api/analytics')

@analytics_bp.route('/overview', methods=['GET'])
@role_required('admin', 'examiner')
def get_analytics_overview():
    """
    Returns aggregated metrics tailored for Chart.js visual charts:
    1. Pass / Fail distribution
    2. Examination participation trends
    3. Examiner evaluation workload
    4. Average score per examination
    """
    # 1. Pass / Fail counts
    passed_count = Booking.query.filter_by(status='Completed', is_passed=True).count()
    failed_count = Booking.query.filter_by(status='Completed', is_passed=False).count()
    pending_count = Booking.query.filter_by(status='Booked').count()

    pass_fail_chart = {
        'labels': ['Passed Candidates', 'Failed Candidates', 'Pending Evaluations'],
        'datasets': [{
            'label': 'Student Count',
            'data': [passed_count, failed_count, pending_count],
            'backgroundColor': ['#198754', '#dc3545', '#ffc107']
        }]
    }

    # 2. Examination Participation by Exam Title
    exams = Examination.query.all()
    exam_labels = []
    booked_data = []
    completed_data = []
    avg_scores = []

    for exam in exams:
        exam_labels.append(exam.title[:20] + ('...' if len(exam.title) > 20 else ''))
        active_b = len([b for b in exam.bookings if b.status != 'Cancelled'])
        comp_b = len([b for b in exam.bookings if b.status == 'Completed'])
        booked_data.append(active_b)
        completed_data.append(comp_b)
        
        scores = [b.total_marks_obtained for b in exam.bookings if b.status == 'Completed' and b.total_marks_obtained is not None]
        avg = round(sum(scores) / len(scores), 1) if scores else 0.0
        avg_scores.append(avg)

    participation_chart = {
        'labels': exam_labels,
        'datasets': [
            {
                'label': 'Total Booked',
                'data': booked_data,
                'backgroundColor': '#0d6efd'
            },
            {
                'label': 'Completed',
                'data': completed_data,
                'backgroundColor': '#20c997'
            }
        ]
    }

    performance_chart = {
        'labels': exam_labels,
        'datasets': [{
            'label': 'Average Score Obtained',
            'data': avg_scores,
            'borderColor': '#6f42c1',
            'backgroundColor': 'rgba(111, 66, 193, 0.2)',
            'fill': True
        }]
    }

    # 3. Examiner Workload
    examiners = User.query.filter_by(role='examiner').all()
    examiner_names = []
    eval_counts = []
    for ex in examiners:
        examiner_names.append(ex.full_name)
        count = Booking.query.filter_by(evaluated_by_id=ex.id).count()
        eval_counts.append(count)

    examiner_chart = {
        'labels': examiner_names,
        'datasets': [{
            'label': 'Completed Evaluations',
            'data': eval_counts,
            'backgroundColor': '#fd7e14'
        }]
    }

    return jsonify({
        'success': True,
        'analytics': {
            'pass_fail': pass_fail_chart,
            'participation': participation_chart,
            'performance': performance_chart,
            'examiner_workload': examiner_chart,
            'summary': {
                'total_exams': len(exams),
                'total_evaluations': passed_count + failed_count,
                'pass_percentage': round((passed_count / (passed_count + failed_count) * 100), 1) if (passed_count + failed_count) > 0 else 0
            }
        }
    }), 200
