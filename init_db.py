import os
from datetime import datetime, date, time, timedelta
from flask import Flask
from config import Config
from extensions import db
from models import (
    User, ExaminerProfile, Course, Examination, ExaminationRubric,
    ExaminationSlot, Booking, RubricScore, NotificationLog
)

def create_app_for_db():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    return app

def seed_database():
    app = create_app_for_db()
    with app.app_context():
        # Ensure directories exist
        os.makedirs(Config.EXPORTS_FOLDER, exist_ok=True)
        os.makedirs(Config.REPORTS_FOLDER, exist_ok=True)
        
        print("Creating all database tables...")
        db.create_all()

        # Check if admin already exists
        admin = User.query.filter_by(email='admin@portal.edu').first()
        if not admin:
            print("Creating predefined Admin user (admin@portal.edu)...")
            admin = User(
                email='admin@portal.edu',
                role='admin',
                full_name='System Administrator',
                phone='+91 9876543210',
                is_active=True
            )
            admin.set_password('Admin@123')
            db.session.add(admin)
        else:
            print("Admin user already exists.")

        # Seed sample Course if not present
        course1 = Course.query.filter_by(course_code='CS2006').first()
        if not course1:
            print("Seeding sample courses...")
            course1 = Course(
                course_code='CS2006',
                course_name='Modern Application Development II',
                description='Advanced web architecture, Flask, Vue.js, Celery, and Redis integration.',
                credits=4
            )
            course2 = Course(
                course_code='CS2001',
                course_name='Database Management Systems',
                description='Relational algebra, SQL, normal forms, transaction management, and indexing.',
                credits=4
            )
            course3 = Course(
                course_code='CS2002',
                course_name='Programming, Data Structures and Algorithms using Python',
                description='Core algorithmic concepts, data structures, and Python implementations.',
                credits=4
            )
            db.session.add_all([course1, course2, course3])
            db.session.commit()

        # Seed sample Examiners
        examiner1 = User.query.filter_by(email='examiner@portal.edu').first()
        if not examiner1:
            print("Seeding sample examiner (examiner@portal.edu)...")
            examiner1 = User(
                email='examiner@portal.edu',
                role='examiner',
                full_name='Dr. Arvind Sharma',
                phone='+91 9876543211',
                is_active=True
            )
            examiner1.set_password('Examiner@123')
            db.session.add(examiner1)
            db.session.commit()

            profile1 = ExaminerProfile(
                user_id=examiner1.id,
                qualification='Ph.D. in Computer Science',
                department='Department of Computer Science & Engineering',
                specialisation='Web Frameworks & Distributed Systems',
                experience_years=8,
                approved_by_admin=True
            )
            db.session.add(profile1)

        examiner2 = User.query.filter_by(email='examiner2@portal.edu').first()
        if not examiner2:
            print("Seeding second examiner (examiner2@portal.edu)...")
            examiner2 = User(
                email='examiner2@portal.edu',
                role='examiner',
                full_name='Prof. Priya Sundaram',
                phone='+91 9876543212',
                is_active=True
            )
            examiner2.set_password('Examiner@123')
            db.session.add(examiner2)
            db.session.commit()

            profile2 = ExaminerProfile(
                user_id=examiner2.id,
                qualification='M.Tech, Ph.D.',
                department='Data Sciences & Software Engineering',
                specialisation='Cloud Computing & Microservices',
                experience_years=6,
                approved_by_admin=True
            )
            db.session.add(profile2)

        # Seed sample Students
        student1 = User.query.filter_by(email='student@portal.edu').first()
        if not student1:
            print("Seeding sample student (student@portal.edu)...")
            student1 = User(
                email='student@portal.edu',
                role='student',
                full_name='Ananya Iyer',
                phone='+91 9876543220',
                is_active=True
            )
            student1.set_password('Student@123')
            db.session.add(student1)

        student2 = User.query.filter_by(email='student2@portal.edu').first()
        if not student2:
            print("Seeding second student (student2@portal.edu)...")
            student2 = User(
                email='student2@portal.edu',
                role='student',
                full_name='Rohan Deshmukh',
                phone='+91 9876543221',
                is_active=True
            )
            student2.set_password('Student@123')
            db.session.add(student2)

        db.session.commit()

        # Seed sample Examination if none exists
        exam = Examination.query.first()
        if not exam:
            print("Seeding sample examination with rubrics and slots...")
            course_cs = Course.query.filter_by(course_code='CS2006').first()
            now = datetime.utcnow()
            exam1 = Examination(
                course_id=course_cs.id,
                title='MAD-II Final Project Viva Voce',
                description='Comprehensive viva voce evaluating architecture, Celery async background processing, Redis caching, and responsive Vue.js frontend.',
                exam_type='Viva Voce',
                total_marks=100.0,
                pass_marks=40.0,
                slot_creation_start=now - timedelta(days=2),
                slot_creation_end=now + timedelta(days=5),
                booking_start=now - timedelta(days=1),
                booking_end=now + timedelta(days=10),
                exam_start_date=now + timedelta(days=2),
                exam_end_date=now + timedelta(days=15),
                status='Booking Open'
            )
            db.session.add(exam1)
            db.session.commit()

            # Rubrics for exam1
            rubrics = [
                ExaminationRubric(
                    examination_id=exam1.id,
                    criterion_name='Architecture & Code Cleanliness',
                    max_marks=25.0,
                    description='Modular architecture, adherence to MVC/REST principles, and proper code documentation.'
                ),
                ExaminationRubric(
                    examination_id=exam1.id,
                    criterion_name='Celery Background Jobs & Redis Caching',
                    max_marks=30.0,
                    description='Asynchronous task processing, beat scheduler, and effective cache invalidation policies.'
                ),
                ExaminationRubric(
                    examination_id=exam1.id,
                    criterion_name='Frontend Vue.js SPA & PWA Experience',
                    max_marks=25.0,
                    description='Component hierarchy, reactivity, Chart.js visual analytics, and PWA capabilities.'
                ),
                ExaminationRubric(
                    examination_id=exam1.id,
                    criterion_name='Viva Defense & Demonstration',
                    max_marks=20.0,
                    description='Ability to answer examiner questions, demonstrate code flows, and debug on the spot.'
                )
            ]
            db.session.add_all(rubrics)
            db.session.commit()

            # Examination Slots for examiner1
            today = date.today()
            slot1 = ExaminationSlot(
                examination_id=exam1.id,
                examiner_id=examiner1.id,
                slot_date=today + timedelta(days=3),
                start_time=time(10, 0),
                end_time=time(11, 0),
                capacity=3,
                booked_count=1,
                venue_or_link='https://meet.google.com/emp-mad2-viva',
                status='Open'
            )
            slot2 = ExaminationSlot(
                examination_id=exam1.id,
                examiner_id=examiner1.id,
                slot_date=today + timedelta(days=3),
                start_time=time(14, 0),
                end_time=time(15, 0),
                capacity=3,
                booked_count=0,
                venue_or_link='Lab 4, Computing Center / Google Meet',
                status='Open'
            )
            db.session.add_all([slot1, slot2])
            db.session.commit()

            # Sample Booking for student1
            booking1 = Booking(
                student_id=student1.id,
                examination_slot_id=slot1.id,
                examination_id=exam1.id,
                status='Booked'
            )
            db.session.add(booking1)
            db.session.commit()

            # Seed a sample completed exam to show analytics and history
            exam_past = Examination(
                course_id=course_cs.id,
                title='MAD-II Mid-Term Practical Evaluation',
                description='Mid-term evaluation for Vue frontend components and API design.',
                exam_type='Practical Exam',
                total_marks=50.0,
                pass_marks=20.0,
                slot_creation_start=now - timedelta(days=30),
                slot_creation_end=now - timedelta(days=25),
                booking_start=now - timedelta(days=24),
                booking_end=now - timedelta(days=20),
                exam_start_date=now - timedelta(days=19),
                exam_end_date=now - timedelta(days=15),
                status='Completed'
            )
            db.session.add(exam_past)
            db.session.commit()

            past_rubric = ExaminationRubric(
                examination_id=exam_past.id,
                criterion_name='Vue Components & Store Implementation',
                max_marks=50.0,
                description='Component structure, routing, and reactive data handling.'
            )
            db.session.add(past_rubric)
            db.session.commit()

            past_slot = ExaminationSlot(
                examination_id=exam_past.id,
                examiner_id=examiner1.id,
                slot_date=today - timedelta(days=18),
                start_time=time(11, 0),
                end_time=time(12, 0),
                capacity=2,
                booked_count=2,
                venue_or_link='Online Lab 2',
                status='Completed'
            )
            db.session.add(past_slot)
            db.session.commit()

            past_booking1 = Booking(
                student_id=student1.id,
                examination_slot_id=past_slot.id,
                examination_id=exam_past.id,
                booking_date=now - timedelta(days=22),
                status='Completed',
                total_marks_obtained=44.0,
                is_passed=True,
                feedback_remarks='Excellent demonstration. Good component decomposition and state management.',
                evaluated_by_id=examiner1.id,
                evaluated_at=now - timedelta(days=18)
            )
            past_booking2 = Booking(
                student_id=student2.id,
                examination_slot_id=past_slot.id,
                examination_id=exam_past.id,
                booking_date=now - timedelta(days=21),
                status='Completed',
                total_marks_obtained=38.0,
                is_passed=True,
                feedback_remarks='Good work. Consider adding more granular error boundaries.',
                evaluated_by_id=examiner1.id,
                evaluated_at=now - timedelta(days=18)
            )
            db.session.add_all([past_booking1, past_booking2])
            db.session.commit()

            # Rubric scores for past bookings
            db.session.add(RubricScore(booking_id=past_booking1.id, rubric_id=past_rubric.id, score_obtained=44.0, remarks='Solid implementation'))
            db.session.add(RubricScore(booking_id=past_booking2.id, rubric_id=past_rubric.id, score_obtained=38.0, remarks='Good effort'))
            db.session.commit()

        print("Database initialization and initial seeding complete!")

if __name__ == '__main__':
    seed_database()
