import os
import csv
from datetime import datetime, date, timedelta
from celery_worker import celery
from extensions import db
from config import Config
from models import (
    User, Course, Examination, ExaminationSlot, Booking, RubricScore,
    ExportJob, NotificationLog
)

# Lazy app context helper for Celery workers
def get_flask_app():
    from app import create_app
    return create_app()

@celery.task(name='tasks.send_daily_reminders')
def send_daily_reminders():
    """
    Daily reminder job for upcoming examinations (Email / GChat / SMS / Webhook).
    Scans for examinations happening within the next 48 hours and dispatches notifications
    to both students and assigned examiners.
    """
    app = get_flask_app()
    with app.app_context():
        today = date.today()
        upcoming_window = today + timedelta(days=2)

        upcoming_slots = ExaminationSlot.query.filter(
            ExaminationSlot.slot_date >= today,
            ExaminationSlot.slot_date <= upcoming_window,
            ExaminationSlot.status != 'Cancelled'
        ).all()

        reminders_sent = 0
        for slot in upcoming_slots:
            exam = slot.examination
            examiner = slot.examiner

            # Notify examiner
            examiner_msg = (
                f"Reminder: You have an upcoming examination session for '{exam.title}' "
                f"scheduled on {slot.slot_date} from {slot.start_time.strftime('%H:%M')} to {slot.end_time.strftime('%H:%M')}. "
                f"Venue/Link: {slot.venue_or_link}. Total booked students: {slot.booked_count}."
            )
            examiner_notif = NotificationLog(
                user_id=examiner.id,
                title=f"Upcoming Exam Session: {exam.title}",
                message=examiner_msg,
                channel='Email / Webhook'
            )
            db.session.add(examiner_notif)
            reminders_sent += 1

            # Notify each booked student
            for booking in slot.bookings:
                if booking.status == 'Booked':
                    student = booking.student
                    student_msg = (
                        f"Dear {student.full_name}, this is a reminder that your examination for '{exam.title}' "
                        f"is scheduled on {slot.slot_date} at {slot.start_time.strftime('%H:%M')}. "
                        f"Examiner: {examiner.full_name}. Venue/Link: {slot.venue_or_link}. Please be on time."
                    )
                    student_notif = NotificationLog(
                        user_id=student.id,
                        title=f"Exam Reminder: {exam.title}",
                        message=student_msg,
                        channel='Email / SMS'
                    )
                    db.session.add(student_notif)
                    reminders_sent += 1

        db.session.commit()
        print(f"[Celery Daily Reminders] Dispatched {reminders_sent} reminder notifications.")
        return {'status': 'SUCCESS', 'reminders_sent': reminders_sent}


@celery.task(name='tasks.generate_monthly_admin_report_task')
def generate_monthly_admin_report_task():
    """
    Monthly examination report for Admin (HTML and PDF).
    Report includes:
    - Number of exams conducted
    - Number of participants
    - Number of examiners involved
    - Pass/fail statistics and summary
    """
    app = get_flask_app()
    with app.app_context():
        os.makedirs(Config.REPORTS_FOLDER, exist_ok=True)
        now = datetime.utcnow()
        month_str = now.strftime('%B %Y')
        timestamp = now.strftime('%Y%m%d_%H%M%S')

        # Compute Metrics
        exams_conducted = Examination.query.filter(Examination.status.in_(['Completed', 'Closed'])).all()
        exam_ids = [e.id for e in exams_conducted]

        completed_bookings = Booking.query.filter(Booking.status == 'Completed').all()
        total_participants = len(completed_bookings)
        passed_count = len([b for b in completed_bookings if b.is_passed])
        failed_count = total_participants - passed_count
        pass_rate = round((passed_count / total_participants * 100), 1) if total_participants > 0 else 0.0

        examiners_involved_ids = set()
        for b in completed_bookings:
            if b.evaluated_by_id:
                examiners_involved_ids.add(b.evaluated_by_id)
        examiners_count = len(examiners_involved_ids)

        # 1. Generate HTML Report
        html_filename = f"monthly_report_{timestamp}.html"
        html_path = os.path.join(Config.REPORTS_FOLDER, html_filename)

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Monthly Examination Report - {month_str}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; color: #212529; background-color: #f8f9fa; }}
        .header {{ text-align: center; border-bottom: 2px solid #0d6efd; padding-bottom: 15px; margin-bottom: 30px; }}
        .header h1 {{ margin: 0; color: #0d6efd; }}
        .card {{ background: white; border-radius: 8px; padding: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }}
        .grid {{ display: flex; gap: 20px; justify-content: space-around; }}
        .stat-box {{ text-align: center; padding: 15px; border-radius: 6px; background: #e7f1ff; flex: 1; }}
        .stat-value {{ font-size: 28px; font-weight: bold; color: #0d6efd; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th, td {{ border: 1px solid #dee2e6; padding: 10px; text-align: left; }}
        th {{ background-color: #f1f3f5; }}
        .pass {{ color: green; font-weight: bold; }}
        .fail {{ color: red; font-weight: bold; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Examination Management Portal V2</h1>
        <h2>Monthly Administration & Performance Report</h2>
        <p>Reporting Period: <strong>{month_str}</strong> | Generated on: {now.strftime('%d %B %Y, %H:%M UTC')}</p>
    </div>

    <div class="card">
        <h3>Executive Summary</h3>
        <div class="grid">
            <div class="stat-box">
                <div class="stat-value">{len(exams_conducted)}</div>
                <div>Exams Conducted</div>
            </div>
            <div class="stat-box">
                <div class="stat-value">{total_participants}</div>
                <div>Total Participants</div>
            </div>
            <div class="stat-box">
                <div class="stat-value">{examiners_count}</div>
                <div>Examiners Involved</div>
            </div>
            <div class="stat-box">
                <div class="stat-value">{pass_rate}%</div>
                <div>Overall Pass Rate</div>
            </div>
        </div>
    </div>

    <div class="card">
        <h3>Examinations Summary</h3>
        <table>
            <thead>
                <tr>
                    <th>Course Code</th>
                    <th>Examination Title</th>
                    <th>Type</th>
                    <th>Max Marks</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
                {''.join(f"<tr><td>{e.course.course_code if e.course else '-'}</td><td>{e.title}</td><td>{e.exam_type}</td><td>{e.total_marks}</td><td>{e.status}</td></tr>" for e in exams_conducted) if exams_conducted else "<tr><td colspan='5'>No completed examinations in this period.</td></tr>"}
            </tbody>
        </table>
    </div>

    <div class="card">
        <h3>Recent Evaluated Participants</h3>
        <table>
            <thead>
                <tr>
                    <th>Student Name</th>
                    <th>Exam</th>
                    <th>Marks</th>
                    <th>Result</th>
                    <th>Evaluator</th>
                </tr>
            </thead>
            <tbody>
                {''.join(f"<tr><td>{b.student.full_name}</td><td>{b.examination.title}</td><td>{b.total_marks_obtained}</td><td class='{'pass' if b.is_passed else 'fail'}'>{'PASS' if b.is_passed else 'FAIL'}</td><td>{b.evaluator.full_name if b.evaluator else '-'}</td></tr>" for b in completed_bookings[:15]) if completed_bookings else "<tr><td colspan='5'>No student records available.</td></tr>"}
            </tbody>
        </table>
    </div>
</body>
</html>"""

        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        # 2. Generate PDF Report using ReportLab
        pdf_filename = f"monthly_report_{timestamp}.pdf"
        pdf_path = os.path.join(Config.REPORTS_FOLDER, pdf_filename)

        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib import colors

            doc = SimpleDocTemplate(pdf_path, pagesize=letter)
            styles = getSampleStyleSheet()
            story = []

            title_style = ParagraphStyle(
                'ReportTitle',
                parent=styles['Heading1'],
                fontSize=20,
                textColor=colors.HexColor('#0d6efd'),
                alignment=1,
                spaceAfter=10
            )
            story.append(Paragraph("Examination Management Portal V2", title_style))
            story.append(Paragraph(f"Monthly Administration Report - {month_str}", styles['Heading2']))
            story.append(Paragraph(f"Generated at: {now.strftime('%d %B %Y %H:%M UTC')}", styles['Normal']))
            story.append(Spacer(1, 15))

            # Summary Table
            summary_data = [
                ['Metric', 'Value'],
                ['Examinations Conducted', str(len(exams_conducted))],
                ['Total Participants (Students)', str(total_participants)],
                ['Active Examiners Involved', str(examiners_count)],
                ['Passed Candidates', str(passed_count)],
                ['Failed Candidates', str(failed_count)],
                ['Overall Pass Rate', f"{pass_rate}%"]
            ]
            t = Table(summary_data, colWidths=[250, 150])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0d6efd')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
            ]))
            story.append(t)
            story.append(Spacer(1, 20))

            doc.build(story)
        except Exception as e:
            print(f"ReportLab PDF generation note: {e}")

        # Send Notification to Admin
        admin = User.query.filter_by(role='admin').first()
        if admin:
            notif = NotificationLog(
                user_id=admin.id,
                title="Monthly Examination Report Ready",
                message=f"The Monthly Administration Report for {month_str} has been generated. Exams: {len(exams_conducted)}, Participants: {total_participants}, Examiners: {examiners_count}.",
                channel='In-App / Email'
            )
            db.session.add(notif)
            db.session.commit()

        return {
            'status': 'SUCCESS',
            'html_report': html_filename,
            'pdf_report': pdf_filename,
            'metrics': {
                'exams_conducted': len(exams_conducted),
                'total_participants': total_participants,
                'examiners_involved': examiners_count,
                'pass_rate': pass_rate
            }
        }


@celery.task(name='tasks.export_student_results_csv_task')
def export_student_results_csv_task(user_id, export_job_id):
    """
    User-triggered CSV export for student's examination & results history.
    Executes asynchronously and notifies user once export is complete.
    """
    app = get_flask_app()
    with app.app_context():
        job = db.session.get(ExportJob, export_job_id)
        if not job:
            return {'status': 'FAILED', 'reason': 'ExportJob record not found'}

        job.status = 'PROCESSING'
        db.session.commit()

        os.makedirs(Config.EXPORTS_FOLDER, exist_ok=True)
        filename = f"student_results_user_{user_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
        file_path = os.path.join(Config.EXPORTS_FOLDER, filename)

        bookings = Booking.query.filter_by(student_id=user_id).order_by(Booking.booking_date.desc()).all()

        with open(file_path, mode='w', newline='', encoding='utf-8') as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow([
                'Booking ID', 'Course Code', 'Course Name', 'Examination Title',
                'Exam Type', 'Slot Date', 'Slot Time', 'Examiner Name',
                'Status', 'Total Marks Obtained', 'Max Marks', 'Pass Marks',
                'Result Status', 'Feedback Remarks', 'Evaluated At'
            ])

            for b in bookings:
                slot = b.slot
                exam = b.examination
                course = exam.course if exam else None
                writer.writerow([
                    b.id,
                    course.course_code if course else 'N/A',
                    course.course_name if course else 'N/A',
                    exam.title if exam else 'N/A',
                    exam.exam_type if exam else 'N/A',
                    slot.slot_date if slot else 'N/A',
                    f"{slot.start_time.strftime('%H:%M')} - {slot.end_time.strftime('%H:%M')}" if slot else 'N/A',
                    slot.examiner.full_name if slot and slot.examiner else 'N/A',
                    b.status,
                    b.total_marks_obtained if b.total_marks_obtained is not None else 'N/A',
                    exam.total_marks if exam else 'N/A',
                    exam.pass_marks if exam else 'N/A',
                    'PASS' if b.is_passed else ('FAIL' if b.is_passed is False else 'PENDING'),
                    b.feedback_remarks or 'None',
                    b.evaluated_at.strftime('%Y-%m-%d %H:%M') if b.evaluated_at else 'N/A'
                ])

        job.status = 'COMPLETED'
        job.file_name = filename
        job.file_path = file_path
        job.download_url = f"/api/jobs/exports/download/{filename}"
        job.completed_at = datetime.utcnow()

        # Send notification to student
        notif = NotificationLog(
            user_id=user_id,
            title="CSV Export Complete",
            message=f"Your examination history CSV export '{filename}' is ready for download.",
            channel='System'
        )
        db.session.add(notif)
        db.session.commit()

        return {'status': 'SUCCESS', 'file_name': filename, 'download_url': job.download_url}


@celery.task(name='tasks.export_admin_examinations_csv_task')
def export_admin_examinations_csv_task(user_id, export_job_id):
    """
    Admin-triggered CSV export for all examinations, enrollments, and performance.
    Executes asynchronously and updates job status.
    """
    app = get_flask_app()
    with app.app_context():
        job = db.session.get(ExportJob, export_job_id)
        if not job:
            return {'status': 'FAILED', 'reason': 'ExportJob not found'}

        job.status = 'PROCESSING'
        db.session.commit()

        os.makedirs(Config.EXPORTS_FOLDER, exist_ok=True)
        filename = f"admin_all_examinations_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
        file_path = os.path.join(Config.EXPORTS_FOLDER, filename)

        bookings = Booking.query.order_by(Booking.booking_date.desc()).all()

        with open(file_path, mode='w', newline='', encoding='utf-8') as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow([
                'Booking ID', 'Student ID', 'Student Name', 'Student Email',
                'Course Code', 'Examination Title', 'Slot Date', 'Examiner Name',
                'Status', 'Marks Obtained', 'Max Marks', 'Pass Status', 'Evaluated At'
            ])

            for b in bookings:
                exam = b.examination
                course = exam.course if exam else None
                slot = b.slot
                writer.writerow([
                    b.id,
                    b.student_id,
                    b.student.full_name if b.student else 'N/A',
                    b.student.email if b.student else 'N/A',
                    course.course_code if course else 'N/A',
                    exam.title if exam else 'N/A',
                    slot.slot_date if slot else 'N/A',
                    slot.examiner.full_name if slot and slot.examiner else 'N/A',
                    b.status,
                    b.total_marks_obtained if b.total_marks_obtained is not None else 'N/A',
                    exam.total_marks if exam else 'N/A',
                    'PASS' if b.is_passed else ('FAIL' if b.is_passed is False else 'PENDING'),
                    b.evaluated_at.strftime('%Y-%m-%d %H:%M') if b.evaluated_at else 'N/A'
                ])

        job.status = 'COMPLETED'
        job.file_name = filename
        job.file_path = file_path
        job.download_url = f"/api/jobs/exports/download/{filename}"
        job.completed_at = datetime.utcnow()

        notif = NotificationLog(
            user_id=user_id,
            title="Admin CSV Export Ready",
            message=f"All examinations report '{filename}' has been generated.",
            channel='System'
        )
        db.session.add(notif)
        db.session.commit()

        return {'status': 'SUCCESS', 'file_name': filename, 'download_url': job.download_url}
