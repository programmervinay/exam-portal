from datetime import datetime, date, time
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='student')  # 'admin', 'examiner', 'student'
    full_name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    examiner_profile = db.relationship('ExaminerProfile', back_populates='user', uselist=False, cascade='all, delete-orphan')
    slots = db.relationship('ExaminationSlot', back_populates='examiner', cascade='all, delete-orphan')
    bookings = db.relationship('Booking', foreign_keys='Booking.student_id', back_populates='student', cascade='all, delete-orphan')
    evaluations = db.relationship('Booking', foreign_keys='Booking.evaluated_by_id', back_populates='evaluator')
    notifications = db.relationship('NotificationLog', back_populates='user', cascade='all, delete-orphan')
    export_jobs = db.relationship('ExportJob', back_populates='user', cascade='all, delete-orphan')

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        data = {
            'id': self.id,
            'email': self.email,
            'role': self.role,
            'full_name': self.full_name,
            'phone': self.phone,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
        if self.role == 'examiner' and self.examiner_profile:
            data['examiner_profile'] = self.examiner_profile.to_dict()
        return data


class ExaminerProfile(db.Model):
    __tablename__ = 'examiner_profiles'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), unique=True, nullable=False)
    qualification = db.Column(db.String(100), default='M.Tech / Ph.D')
    department = db.Column(db.String(100), default='Computer Science')
    specialisation = db.Column(db.String(150), default='Software Engineering')
    experience_years = db.Column(db.Integer, default=5)
    approved_by_admin = db.Column(db.Boolean, default=True, nullable=False)

    user = db.relationship('User', back_populates='examiner_profile')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'qualification': self.qualification,
            'department': self.department,
            'specialisation': self.specialisation,
            'experience_years': self.experience_years,
            'approved_by_admin': self.approved_by_admin
        }


class Course(db.Model):
    __tablename__ = 'courses'

    id = db.Column(db.Integer, primary_key=True)
    course_code = db.Column(db.String(30), unique=True, nullable=False, index=True)
    course_name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    credits = db.Column(db.Integer, default=4, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    examinations = db.relationship('Examination', back_populates='course', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'course_code': self.course_code,
            'course_name': self.course_name,
            'description': self.description,
            'credits': self.credits,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'examinations_count': len(self.examinations) if self.examinations else 0
        }


class Examination(db.Model):
    __tablename__ = 'examinations'

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id', ondelete='CASCADE'), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    exam_type = db.Column(db.String(50), default='Viva Voce')  # 'Viva Voce', 'Practical Exam', 'Project Defense'
    total_marks = db.Column(db.Float, default=100.0, nullable=False)
    pass_marks = db.Column(db.Float, default=40.0, nullable=False)

    # Examination Timelines
    slot_creation_start = db.Column(db.DateTime, nullable=False)
    slot_creation_end = db.Column(db.DateTime, nullable=False)
    booking_start = db.Column(db.DateTime, nullable=False)
    booking_end = db.Column(db.DateTime, nullable=False)
    exam_start_date = db.Column(db.DateTime, nullable=False)
    exam_end_date = db.Column(db.DateTime, nullable=False)

    # Status: 'Draft', 'Slot Creation', 'Booking Open', 'Closed', 'Completed'
    status = db.Column(db.String(30), default='Draft', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    course = db.relationship('Course', back_populates='examinations')
    rubrics = db.relationship('ExaminationRubric', back_populates='examination', cascade='all, delete-orphan')
    slots = db.relationship('ExaminationSlot', back_populates='examination', cascade='all, delete-orphan')
    bookings = db.relationship('Booking', back_populates='examination', cascade='all, delete-orphan')

    def is_slot_creation_open(self) -> bool:
        now = datetime.utcnow()
        return self.status == 'Slot Creation' or (self.slot_creation_start <= now <= self.slot_creation_end and self.status not in ['Closed', 'Completed'])

    def is_booking_open(self) -> bool:
        now = datetime.utcnow()
        return self.status == 'Booking Open' or (self.booking_start <= now <= self.booking_end and self.status not in ['Closed', 'Completed'])

    def to_dict(self, include_rubrics=True, include_slots=False):
        data = {
            'id': self.id,
            'course_id': self.course_id,
            'course_code': self.course.course_code if self.course else None,
            'course_name': self.course.course_name if self.course else None,
            'title': self.title,
            'description': self.description,
            'exam_type': self.exam_type,
            'total_marks': self.total_marks,
            'pass_marks': self.pass_marks,
            'slot_creation_start': self.slot_creation_start.isoformat() if self.slot_creation_start else None,
            'slot_creation_end': self.slot_creation_end.isoformat() if self.slot_creation_end else None,
            'booking_start': self.booking_start.isoformat() if self.booking_start else None,
            'booking_end': self.booking_end.isoformat() if self.booking_end else None,
            'exam_start_date': self.exam_start_date.isoformat() if self.exam_start_date else None,
            'exam_end_date': self.exam_end_date.isoformat() if self.exam_end_date else None,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'slots_count': len(self.slots) if self.slots else 0,
            'bookings_count': len([b for b in self.bookings if b.status != 'Cancelled']) if self.bookings else 0
        }
        if include_rubrics and self.rubrics:
            data['rubrics'] = [r.to_dict() for r in self.rubrics]
        if include_slots and self.slots:
            data['slots'] = [s.to_dict() for s in self.slots]
        return data


class ExaminationRubric(db.Model):
    __tablename__ = 'examination_rubrics'

    id = db.Column(db.Integer, primary_key=True)
    examination_id = db.Column(db.Integer, db.ForeignKey('examinations.id', ondelete='CASCADE'), nullable=False)
    criterion_name = db.Column(db.String(150), nullable=False)
    max_marks = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text, nullable=True)

    # Relationships
    examination = db.relationship('Examination', back_populates='rubrics')
    scores = db.relationship('RubricScore', back_populates='rubric', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'examination_id': self.examination_id,
            'criterion_name': self.criterion_name,
            'max_marks': self.max_marks,
            'description': self.description
        }


class ExaminationSlot(db.Model):
    __tablename__ = 'examination_slots'

    id = db.Column(db.Integer, primary_key=True)
    examination_id = db.Column(db.Integer, db.ForeignKey('examinations.id', ondelete='CASCADE'), nullable=False)
    examiner_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    slot_date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    capacity = db.Column(db.Integer, default=5, nullable=False)
    booked_count = db.Column(db.Integer, default=0, nullable=False)
    venue_or_link = db.Column(db.String(255), default='Room 301 / Online Google Meet', nullable=False)
    # Status: 'Open', 'Full', 'Cancelled', 'Completed'
    status = db.Column(db.String(20), default='Open', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    examination = db.relationship('Examination', back_populates='slots')
    examiner = db.relationship('User', back_populates='slots')
    bookings = db.relationship('Booking', back_populates='slot', cascade='all, delete-orphan')

    def update_status(self):
        active_bookings = len([b for b in self.bookings if b.status != 'Cancelled'])
        self.booked_count = active_bookings
        if self.status != 'Cancelled':
            if self.booked_count >= self.capacity:
                self.status = 'Full'
            else:
                self.status = 'Open'

    def to_dict(self, include_bookings=False):
        data = {
            'id': self.id,
            'examination_id': self.examination_id,
            'examination_title': self.examination.title if self.examination else None,
            'course_code': self.examination.course.course_code if self.examination and self.examination.course else None,
            'examiner_id': self.examiner_id,
            'examiner_name': self.examiner.full_name if self.examiner else None,
            'examiner_email': self.examiner.email if self.examiner else None,
            'slot_date': self.slot_date.isoformat() if self.slot_date else None,
            'start_time': self.start_time.strftime('%H:%M') if self.start_time else None,
            'end_time': self.end_time.strftime('%H:%M') if self.end_time else None,
            'capacity': self.capacity,
            'booked_count': self.booked_count,
            'available_seats': max(0, self.capacity - self.booked_count),
            'venue_or_link': self.venue_or_link,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
        if include_bookings:
            data['bookings'] = [b.to_dict() for b in self.bookings if b.status != 'Cancelled']
        return data


class Booking(db.Model):
    __tablename__ = 'bookings'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    examination_slot_id = db.Column(db.Integer, db.ForeignKey('examination_slots.id', ondelete='CASCADE'), nullable=False)
    examination_id = db.Column(db.Integer, db.ForeignKey('examinations.id', ondelete='CASCADE'), nullable=False)
    booking_date = db.Column(db.DateTime, default=datetime.utcnow)
    # Status: 'Booked', 'Cancelled', 'Completed'
    status = db.Column(db.String(20), default='Booked', nullable=False)

    # Evaluation fields
    total_marks_obtained = db.Column(db.Float, nullable=True)
    is_passed = db.Column(db.Boolean, nullable=True)
    feedback_remarks = db.Column(db.Text, nullable=True)
    evaluated_by_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    evaluated_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    student = db.relationship('User', foreign_keys=[student_id], back_populates='bookings')
    evaluator = db.relationship('User', foreign_keys=[evaluated_by_id], back_populates='evaluations')
    slot = db.relationship('ExaminationSlot', back_populates='bookings')
    examination = db.relationship('Examination', back_populates='bookings')
    rubric_scores = db.relationship('RubricScore', back_populates='booking', cascade='all, delete-orphan')

    def to_dict(self, include_rubric_scores=True):
        data = {
            'id': self.id,
            'student_id': self.student_id,
            'student_name': self.student.full_name if self.student else None,
            'student_email': self.student.email if self.student else None,
            'examination_id': self.examination_id,
            'examination_title': self.examination.title if self.examination else None,
            'course_code': self.examination.course.course_code if self.examination and self.examination.course else None,
            'course_name': self.examination.course.course_name if self.examination and self.examination.course else None,
            'examination_slot_id': self.examination_slot_id,
            'slot_date': self.slot.slot_date.isoformat() if self.slot and self.slot.slot_date else None,
            'start_time': self.slot.start_time.strftime('%H:%M') if self.slot and self.slot.start_time else None,
            'end_time': self.slot.end_time.strftime('%H:%M') if self.slot and self.slot.end_time else None,
            'venue_or_link': self.slot.venue_or_link if self.slot else None,
            'examiner_name': self.slot.examiner.full_name if self.slot and self.slot.examiner else None,
            'examiner_id': self.slot.examiner_id if self.slot else None,
            'booking_date': self.booking_date.isoformat() if self.booking_date else None,
            'status': self.status,
            'total_marks_obtained': self.total_marks_obtained,
            'total_possible_marks': self.examination.total_marks if self.examination else None,
            'pass_marks': self.examination.pass_marks if self.examination else None,
            'is_passed': self.is_passed,
            'feedback_remarks': self.feedback_remarks,
            'evaluated_by_id': self.evaluated_by_id,
            'evaluated_by_name': self.evaluator.full_name if self.evaluator else None,
            'evaluated_at': self.evaluated_at.isoformat() if self.evaluated_at else None
        }
        if include_rubric_scores and self.rubric_scores:
            data['rubric_scores'] = [rs.to_dict() for rs in self.rubric_scores]
        return data


class RubricScore(db.Model):
    __tablename__ = 'rubric_scores'

    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.id', ondelete='CASCADE'), nullable=False)
    rubric_id = db.Column(db.Integer, db.ForeignKey('examination_rubrics.id', ondelete='CASCADE'), nullable=False)
    score_obtained = db.Column(db.Float, nullable=False)
    remarks = db.Column(db.Text, nullable=True)

    booking = db.relationship('Booking', back_populates='rubric_scores')
    rubric = db.relationship('ExaminationRubric', back_populates='scores')

    def to_dict(self):
        return {
            'id': self.id,
            'booking_id': self.booking_id,
            'rubric_id': self.rubric_id,
            'criterion_name': self.rubric.criterion_name if self.rubric else None,
            'max_marks': self.rubric.max_marks if self.rubric else None,
            'score_obtained': self.score_obtained,
            'remarks': self.remarks
        }


class ExportJob(db.Model):
    __tablename__ = 'export_jobs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    job_type = db.Column(db.String(50), nullable=False)  # 'csv_export', 'pdf_report'
    status = db.Column(db.String(20), default='PENDING', nullable=False)  # 'PENDING', 'PROCESSING', 'COMPLETED', 'FAILED'
    file_name = db.Column(db.String(255), nullable=True)
    file_path = db.Column(db.String(255), nullable=True)
    download_url = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship('User', back_populates='export_jobs')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'job_type': self.job_type,
            'status': self.status,
            'file_name': self.file_name,
            'download_url': self.download_url,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }


class NotificationLog(db.Model):
    __tablename__ = 'notification_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    message = db.Column(db.Text, nullable=False)
    channel = db.Column(db.String(30), default='Email', nullable=False)  # 'Email', 'GChat', 'SMS', 'Webhook'
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', back_populates='notifications')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'title': self.title,
            'message': self.message,
            'channel': self.channel,
            'is_read': self.is_read,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None
        }
