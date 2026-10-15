from functools import wraps
from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    create_access_token, jwt_required, get_jwt_identity, get_jwt
)
from extensions import db
from models import User

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

def role_required(*allowed_roles):
    """
    Decorator to enforce Role-Based Access Control (RBAC).
    Verifies that the JWT identity corresponds to an active user with one of the allowed roles.
    """
    def decorator(fn):
        @wraps(fn)
        @jwt_required()
        def wrapper(*args, **kwargs):
            user_id = get_jwt_identity()
            user = db.session.get(User, int(user_id))
            if not user or not user.is_active:
                return jsonify({'success': False, 'message': 'Account is inactive or not found.'}), 403
            
            if user.role not in allowed_roles:
                return jsonify({
                    'success': False,
                    'message': f'Access forbidden: Role "{user.role}" does not have permission for this resource.'
                }), 403
            
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def get_current_user():
    """Helper to retrieve current User instance from JWT identity."""
    user_id = get_jwt_identity()
    if not user_id:
        return None
    return db.session.get(User, int(user_id))


@auth_bp.route('/register', methods=['POST'])
def register():
    """
    Student self-registration endpoint.
    Public registration is strictly restricted to students.
    Admin and Examiner accounts cannot be created via public registration.
    """
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    full_name = data.get('full_name', '').strip()
    phone = data.get('phone', '').strip()
    requested_role = data.get('role', 'student').strip().lower()

    if requested_role in ['admin', 'examiner']:
        return jsonify({
            'success': False,
            'message': 'Public registration is only permitted for Students. Examiner and Admin accounts are restricted.'
        }), 400

    if not email or not password or not full_name:
        return jsonify({
            'success': False,
            'message': 'Email, password, and full name are required.'
        }), 400

    if len(password) < 6:
        return jsonify({
            'success': False,
            'message': 'Password must be at least 6 characters long.'
        }), 400

    if User.query.filter_by(email=email).first():
        return jsonify({
            'success': False,
            'message': 'An account with this email address already exists.'
        }), 409

    new_student = User(
        email=email,
        full_name=full_name,
        phone=phone,
        role='student',
        is_active=True
    )
    new_student.set_password(password)
    db.session.add(new_student)
    db.session.commit()

    # Generate JWT token for immediate access
    access_token = create_access_token(
        identity=str(new_student.id),
        additional_claims={'role': new_student.role, 'email': new_student.email}
    )

    return jsonify({
        'success': True,
        'message': 'Student registration successful!',
        'token': access_token,
        'user': new_student.to_dict(),
        'redirect_route': '/student/dashboard'
    }), 201


@auth_bp.route('/login', methods=['POST'])
def login():
    """
    Unified login endpoint for Admin, Examiner, and Student roles.
    Validates credentials, checks approval/active status, and returns JWT token
    with role-based redirect target.
    """
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({'success': False, 'message': 'Email and password are required.'}), 400

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({'success': False, 'message': 'Invalid email address or password.'}), 401

    if not user.is_active:
        return jsonify({'success': False, 'message': 'This account has been deactivated. Contact the administrator.'}), 403

    # Examiner approval check
    if user.role == 'examiner':
        if user.examiner_profile and not user.examiner_profile.approved_by_admin:
            return jsonify({
                'success': False,
                'message': 'Your examiner account is awaiting administrator approval.'
            }), 403

    # Determine role-specific dashboard route
    redirect_map = {
        'admin': '/admin/dashboard',
        'examiner': '/examiner/dashboard',
        'student': '/student/dashboard'
    }
    dashboard_route = redirect_map.get(user.role, '/student/dashboard')

    access_token = create_access_token(
        identity=str(user.id),
        additional_claims={'role': user.role, 'email': user.email}
    )

    return jsonify({
        'success': True,
        'message': f'Welcome back, {user.full_name}!',
        'token': access_token,
        'user': user.to_dict(),
        'redirect_route': dashboard_route
    }), 200


@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_profile():
    """Returns the authenticated user's profile and active role."""
    user = get_current_user()
    if not user:
        return jsonify({'success': False, 'message': 'User session not found.'}), 404
    return jsonify({
        'success': True,
        'user': user.to_dict()
    }), 200


@auth_bp.route('/profile', methods=['PUT'])
@jwt_required()
def update_profile():
    """Allows authenticated user to update their profile information and password."""
    user = get_current_user()
    if not user:
        return jsonify({'success': False, 'message': 'User session not found.'}), 404

    data = request.get_json() or {}
    if 'full_name' in data and data['full_name'].strip():
        user.full_name = data['full_name'].strip()
    if 'phone' in data:
        user.phone = data['phone'].strip()
    
    # Password update
    if data.get('new_password'):
        if len(data['new_password']) < 6:
            return jsonify({'success': False, 'message': 'New password must be at least 6 characters.'}), 400
        current_password = data.get('current_password')
        if not current_password or not user.check_password(current_password):
            return jsonify({'success': False, 'message': 'Current password verification failed.'}), 400
        user.set_password(data['new_password'])

    # If examiner profile updates
    if user.role == 'examiner' and user.examiner_profile:
        if 'qualification' in data:
            user.examiner_profile.qualification = data['qualification'].strip()
        if 'department' in data:
            user.examiner_profile.department = data['department'].strip()
        if 'specialisation' in data:
            user.examiner_profile.specialisation = data['specialisation'].strip()
        if 'experience_years' in data:
            user.examiner_profile.experience_years = int(data['experience_years'])

    db.session.commit()
    return jsonify({
        'success': True,
        'message': 'Profile updated successfully.',
        'user': user.to_dict()
    }), 200
