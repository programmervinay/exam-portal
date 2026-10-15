import os
from flask import Blueprint, request, jsonify, send_from_directory
from extensions import db
from config import Config
from models import ExportJob, NotificationLog, User
from auth_routes import role_required, get_current_user

jobs_bp = Blueprint('jobs', __name__, url_prefix='/api/jobs')

@jobs_bp.route('/export-csv', methods=['POST'])
@role_required('student', 'admin', 'examiner')
def trigger_csv_export():
    """
    User-triggered CSV export for exam/result history.
    Triggers batch jobs asynchronously (via Celery or synchronous fallback if broker unavailable)
    and notifies user once export is complete.
    """
    user = get_current_user()
    job_type = 'student_results_csv' if user.role == 'student' else 'admin_all_examinations_csv'

    export_job = ExportJob(
        user_id=user.id,
        job_type=job_type,
        status='PENDING'
    )
    db.session.add(export_job)
    db.session.commit()

    # Try triggering via Celery worker
    celery_dispatched = False
    try:
        from tasks import export_student_results_csv_task, export_admin_examinations_csv_task
        if user.role == 'student':
            export_student_results_csv_task.delay(user.id, export_job.id)
        else:
            export_admin_examinations_csv_task.delay(user.id, export_job.id)
        celery_dispatched = True
    except Exception as e:
        # Fallback for local environments without running Celery/Redis daemon
        print(f"[Celery Note: Redis/Celery worker offline, executing task inline]: {e}")
        from tasks import export_student_results_csv_task, export_admin_examinations_csv_task
        if user.role == 'student':
            export_student_results_csv_task(user.id, export_job.id)
        else:
            export_admin_examinations_csv_task(user.id, export_job.id)

    db.session.refresh(export_job)
    return jsonify({
        'success': True,
        'message': 'CSV export job initiated asynchronously. You will receive an in-app notification when ready.',
        'job': export_job.to_dict(),
        'async_mode': celery_dispatched
    }), 202


@jobs_bp.route('/exports', methods=['GET'])
@role_required('student', 'admin', 'examiner')
def list_user_exports():
    """List recent CSV export jobs requested by the authenticated user."""
    user = get_current_user()
    jobs = ExportJob.query.filter_by(user_id=user.id).order_by(ExportJob.created_at.desc()).all()
    return jsonify({'success': True, 'export_jobs': [j.to_dict() for j in jobs]}), 200


@jobs_bp.route('/exports/download/<filename>', methods=['GET'])
def download_export_file(filename):
    """Securely download generated CSV file."""
    # Prevent directory traversal attacks
    safe_filename = os.path.basename(filename)
    return send_from_directory(Config.EXPORTS_FOLDER, safe_filename, as_attachment=True)


@jobs_bp.route('/generate-report', methods=['POST'])
@role_required('admin')
def trigger_monthly_report():
    """
    Trigger generation of the monthly examination report for Admin (HTML and PDF).
    Includes:
    - Number of exams conducted
    - Number of participants
    - Number of examiners involved
    """
    try:
        from tasks import generate_monthly_admin_report_task
        try:
            task_result = generate_monthly_admin_report_task.delay()
            return jsonify({
                'success': True,
                'message': 'Monthly examination report task dispatched to Celery worker.',
                'task_id': str(task_result.id)
            }), 202
        except Exception:
            # Fallback to direct synchronous execution
            result = generate_monthly_admin_report_task()
            return jsonify({
                'success': True,
                'message': 'Monthly examination report generated successfully.',
                'result': result
            }), 200
    except Exception as e:
        return jsonify({'success': False, 'message': f'Failed to generate report: {str(e)}'}), 500


@jobs_bp.route('/reports/download/<filename>', methods=['GET'])
def download_report_file(filename):
    """Download generated HTML/PDF monthly report."""
    safe_filename = os.path.basename(filename)
    return send_from_directory(Config.REPORTS_FOLDER, safe_filename, as_attachment=True)


@jobs_bp.route('/trigger-daily-reminders', methods=['POST'])
@role_required('admin')
def trigger_daily_reminders():
    """Manual trigger endpoint for daily examination reminders."""
    try:
        from tasks import send_daily_reminders
        try:
            task = send_daily_reminders.delay()
            return jsonify({'success': True, 'message': 'Daily reminders job queued.', 'task_id': str(task.id)}), 200
        except Exception:
            result = send_daily_reminders()
            return jsonify({'success': True, 'message': 'Daily reminders executed directly.', 'result': result}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@jobs_bp.route('/notifications', methods=['GET'])
@role_required('student', 'examiner', 'admin')
def get_user_notifications():
    """Retrieve notifications sent to the current user (e.g. reminders, export completion)."""
    user = get_current_user()
    notifs = NotificationLog.query.filter_by(user_id=user.id).order_by(NotificationLog.sent_at.desc()).all()
    return jsonify({'success': True, 'notifications': [n.to_dict() for n in notifs]}), 200


@jobs_bp.route('/notifications/<int:notif_id>/read', methods=['PATCH'])
@role_required('student', 'examiner', 'admin')
def mark_notification_read(notif_id):
    """Mark a notification as read."""
    user = get_current_user()
    notif = db.session.get(NotificationLog, notif_id)
    if not notif or notif.user_id != user.id:
        return jsonify({'success': False, 'message': 'Notification not found.'}), 404

    notif.is_read = True
    db.session.commit()
    return jsonify({'success': True, 'message': 'Notification marked as read.'}), 200
