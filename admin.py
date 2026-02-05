from datetime import datetime
from functools import wraps
import json
from bson import ObjectId, json_util
from bson.errors import InvalidId
from flask import Blueprint
from flask import render_template, request, jsonify, redirect, url_for, flash, session, current_app
import jwt
from pymongo import MongoClient
from forms import AdminLoginForm, AdminUserForm
from utils.email_service import send_bulk_emails, send_ca_approval_email, send_verification_email
from utils.export_service import export_ca_to_csv, export_to_csv, export_to_excel
from utils.security import hash_password, verify_password
from extensions import db


# Create a blueprint instance
admin_bp = Blueprint('admin', __name__)

def admin_required(f):
    """Decorator to require admin authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = session.get('admin_token')
        
        if not token:
            return redirect(url_for('admin.admin_login'))
        
        try:
            payload = jwt.decode(token, current_app.config['JWT_SECRET_KEY'], algorithms=['HS256'])
            if payload['role'] != 'admin':
                flash('Admin access required', 'error')
                return redirect(url_for('admin.admin_login'))
            
            # Store admin email in session for reference
            session['admin_email'] = payload['email']
            
        except jwt.ExpiredSignatureError:
            flash('Session expired. Please login again.', 'error')
            return redirect(url_for('admin.admin_login'))
        except jwt.InvalidTokenError:
            flash('Invalid token. Please login again.', 'error')
            return redirect(url_for('admin.admin_login'))
        
        return f(*args, **kwargs)
    return decorated_function


def role_required(*allowed_roles):
    """Decorator to require specific role(s)"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            token = session.get('admin_token')
            
            if not token:
                flash('Authentication required', 'error')
                return redirect(url_for('admin.admin_login'))
            
            try:
                payload = jwt.decode(token, current_app.config['JWT_SECRET_KEY'], algorithms=['HS256'])
                user_role = payload.get('role')
                
                if user_role not in allowed_roles:
                    flash('Insufficient permissions', 'error')
                    return redirect(url_for('admin.admin_dashboard'))
                
                # Store user info in session
                session['admin_role'] = user_role
                session['admin_email'] = payload.get('email')
                
            except jwt.ExpiredSignatureError:
                flash('Session expired. Please login again.', 'error')
                return redirect(url_for('admin.admin_login'))
            except jwt.InvalidTokenError:
                flash('Invalid token. Please login again.', 'error')
                return redirect(url_for('admin.admin_login'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def has_permission(permission):
    """Check if current user has specific permission"""
    if 'admin_role' not in session:
        return False
    
    user_role = session['admin_role']
    
    # Admin has all permissions
    if user_role == 'admin':
        return True
    
    # Get user from database to check permissions
    user = db.users.find_one({'email': session['admin_email']})
    if not user:
        return False
    
    # Check if user has the permission
    permissions = user.get('permissions', [])
    return permission in permissions or '*' in permissions


# Update admin_required to use role_required
def admin_required(f):
    """Decorator to require admin authentication (for backward compatibility)"""
    return role_required('admin', 'executive', 'organizer', 'moderator')(f)


@admin_bp.route('/login', methods=['GET', 'POST'])
def admin_login():
    """Admin login page"""
    if 'admin_token' in session:
        return redirect(url_for('admin.admin_dashboard'))
    
    form = AdminLoginForm()
    
    if form.validate_on_submit():
        user = db.users.find_one({'email': form.email.data})

        if user and verify_password(user['password'], form.password.data):
            # Check if account is active
            if not user.get('active', True):
                flash('Your account has been deactivated. Please contact an admin.', 'error')
                return redirect(url_for('admin.admin_login'))
            
            # Update last login
            db.users.update_one(
                {'_id': user['_id']},
                {'$set': {'last_login': datetime.utcnow()}}
            )
            
            # Generate JWT token with role
            token_payload = {
                'email': user['email'],
                'role': user.get('role', 'moderator'),
                'exp': datetime.utcnow() + current_app.config['JWT_ACCESS_TOKEN_EXPIRES']
            }
            token = jwt.encode(token_payload, current_app.config['JWT_SECRET_KEY'], algorithm='HS256')
            
            session['admin_token'] = token
            session['admin_role'] = user.get('role', 'moderator')
            session['admin_email'] = user['email']
            
            flash(f'Logged in successfully as {user.get("role", "moderator").title()}', 'success')
            return redirect(url_for('admin.admin_dashboard'))
        else:
            flash('Invalid email or password', 'error')
    
    return render_template('admin/login.html', form=form)

@admin_bp.route('/logout')
def admin_logout():
    """Admin logout"""
    session.pop('admin_token', None)
    flash('Logged out successfully', 'success')
    return redirect(url_for('admin.admin_login'))

@admin_bp.route('/dashboard')
@role_required('admin', 'executive', 'organizer', 'moderator')
def admin_dashboard():
    """Admin dashboard overview"""
    # Get statistics
    total_registrations = db.registrations.count_documents({})
    verified_registrations = db.registrations.count_documents({'verified': True})
    total_segments = db.segments.count_documents({})
    
    # Get contact message statistics
    contact_messages_count = db.contact_messages.count_documents({'archived': False})
    unread_contact_messages = db.contact_messages.count_documents({
        'status': 'unread',
        'archived': False
    })
    
    # Get recent registrations
    recent_registrations = list(db.registrations.find().sort('registration_date', -1).limit(10))
    
    # Get recent contact messages
    recent_messages = list(db.contact_messages.find({'archived': False})
                          .sort('submitted_at', -1).limit(5))
    
    # Get segment statistics
    segments = list(db.segments.find({}))
    segments = json.loads(json_util.dumps(list(segments)))

    return render_template('admin/dashboard.html',
                         total_registrations=total_registrations,
                         verified_registrations=verified_registrations,
                         contact_messages_count=contact_messages_count,
                         unread_contact_messages=unread_contact_messages,
                         recent_registrations=recent_registrations,
                         recent_messages=recent_messages,
                         segments=segments)


@admin_bp.route('/analytics')
@role_required('admin', 'executive', 'organizer', 'moderator')
def admin_analytics():
    """Analytics dashboard"""
    # Registration statistics by day
    pipeline = [
        {
            '$group': {
                '_id': {'$dateToString': {'format': '%Y-%m-%d', 'date': '$registration_date'}},
                'count': {'$sum': 1}
            }
        },
        {'$sort': {'_id': 1}}
    ]
    daily_stats = list(db.registrations.aggregate(pipeline))
    
    # Category distribution
    category_pipeline = [
        {'$group': {'_id': '$category', 'count': {'$sum': 1}}},
        {'$sort': {'count': -1}}
    ]
    category_stats = list(db.registrations.aggregate(category_pipeline))
    
    # Segment distribution
    segment_pipeline = [
        {'$group': {'_id': '$segment_name', 'count': {'$sum': 1}}},
        {'$sort': {'count': -1}}
    ]
    segment_stats = list(db.registrations.aggregate(segment_pipeline))

    ca_pipeline = [
        {'$group': {'_id': '$ca_ref', 'count': {'$sum': 1}}},
        {'$sort': {'count': -1}}
    ]
    ca_stats = list(db.registrations.aggregate(ca_pipeline))
    
    return render_template('admin/analytics.html',
                         daily_stats=daily_stats,
                         category_stats=category_stats,
                         segment_stats=segment_stats,
                         ca_stats=ca_stats)


####  Contact Message Routes

@admin_bp.route('/contact-messages')
@role_required('admin', 'executive', 'organizer', 'moderator')
def admin_contact_messages():
    """View and manage contact messages"""
    status_filter = request.args.get('status', 'all')
    archived_filter = request.args.get('archived', 'false') == 'true'
    
    query = {'archived': archived_filter}
    
    if status_filter != 'all':
        query['status'] = status_filter
    
    # Get messages sorted by newest first
    contact_messages = list(db.contact_messages.find(query).sort('submitted_at', -1))
    
    # Get statistics
    unread_count = db.contact_messages.count_documents({'status': 'unread', 'archived': False})
    total_messages = db.contact_messages.count_documents({'archived': False})
    
    return render_template('admin/contact_messages.html',
                         contact_messages=contact_messages,
                         status_filter=status_filter,
                         archived_filter=archived_filter,
                         unread_count=unread_count,
                         total_messages=total_messages)

@admin_bp.route('/update-message-status/<message_id>', methods=['POST'])
@role_required('admin', 'executive')
def update_message_status(message_id):
    """Update contact message status"""
    status = request.json.get('status')
    archived = request.json.get('archived')
    
    if status not in ['unread', 'read', 'replied', None]:
        return jsonify({'success': False, 'message': 'Invalid status'}), 400
    
    update_data = {}
    if status is not None:
        update_data['status'] = status
    
    if archived is not None:
        update_data['archived'] = archived
    
    try:
        result = db.contact_messages.update_one(
            {'_id': ObjectId(message_id)},
            {'$set': update_data}
        )
        
        return jsonify({'success': True, 'modified': result.modified_count})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@admin_bp.route('/delete-message/<message_id>', methods=['DELETE'])
@role_required('admin', 'executive')
def delete_message(message_id):
    """Delete a contact message"""
    try:
        result = db.contact_messages.delete_one({'_id': ObjectId(message_id)})
        
        if result.deleted_count > 0:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'message': 'Message not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

#### Registration Routes

@admin_bp.route('/registrations')
@role_required('admin', 'executive', 'organizer', 'moderator')
def admin_registrations():
    """View and manage registrations"""
    segment_id = request.args.get('segment_id')
    verified_filter = request.args.get('verified')
    search = request.args.get('search')

    query = {}

    # Normal filters
    if segment_id:
        query['segment_id'] = ObjectId(segment_id)

    if verified_filter == 'true':
        query['verified'] = True
    elif verified_filter == 'false':
        query['verified'] = False

    # Search filter (same input for _id or other fields)
    if search:
        search = search.strip()
        or_conditions = [
            {"full_name": {"$regex": search, "$options": "i"}},
            {"email": {"$regex": search, "$options": "i"}},
            {"bkash_number": {"$regex": search, "$options": "i"}},
            {"transaction_id": {"$regex": search, "$options": "i"}},
        ]

        # Try adding _id search if valid ObjectId
        try:
            or_conditions.append({"_id": ObjectId(search)})
        except InvalidId:
            pass

        query["$or"] = or_conditions

    registrations = list(
        db.registrations.find(query).sort('registration_date', -1)
    )
    segments = list(db.segments.find({}))

    return render_template(
        'admin/registrations.html',
        registrations=registrations,
        segments=segments,
        segment_id=segment_id,
        verified_filter=verified_filter,
        search=search
    )


@admin_bp.route('/verify-registration/<registration_id>', methods=['POST'])
@role_required('admin', 'executive')  # Only admin/executive can verify
def verify_registration(registration_id):
    """Verify a single registration"""
    try:
        db.registrations.update_one(
            {'_id': ObjectId(registration_id)},
            {'$set': {'verified': True, 'verified_at': datetime.utcnow()}}
        )
        
        # Get registration to send email
        registration = db.registrations.find_one({'_id': ObjectId(registration_id)})
        if registration:
            send_verification_email(registration)
        
        return jsonify({'success': True})
    except:
        return jsonify({'success': False}), 500

@admin_bp.route('/bulk-verify', methods=['POST'])
@role_required('admin', 'executive')
def bulk_verify():
    """Bulk verify registrations"""
    registration_ids = request.json.get('registration_ids', [])
    
    if not registration_ids:
        return jsonify({'success': False, 'message': 'No registrations selected'}), 400
    
    try:
        object_ids = [ObjectId(rid) for rid in registration_ids]
        
        # Update all selected registrations
        result = db.registrations.update_many(
            {'_id': {'$in': object_ids}},
            {'$set': {'verified': True, 'verified_at': datetime.utcnow()}}
        )
        
        # Send emails to verified registrations
        verified_registrations = list(db.registrations.find({'_id': {'$in': object_ids}}))
        send_bulk_emails(verified_registrations)
        
        return jsonify({'success': True, 'verified_count': result.modified_count})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


### CA Registration Routes
@admin_bp.route('/ca-registrations')
@role_required('admin', 'executive', 'organizer', 'moderator')
def admin_ca_registrations():
    """View and manage CA registrations"""
    status_filter = request.args.get('status', 'all')
    search = request.args.get('search')

    query = {}

    # Status filter
    if status_filter != 'all':
        query['status'] = status_filter

    # Search filter (same input for _id or other fields)
    if search:
        search = search.strip()
        or_conditions = [
            {"full_name": {"$regex": search, "$options": "i"}},
            {"email": {"$regex": search, "$options": "i"}},
            {"phone": {"$regex": search, "$options": "i"}},
            {"institution": {"$regex": search, "$options": "i"}},
            {"ca_code": {"$regex": search, "$options": "i"}},
        ]

        # If valid ObjectId, also search by _id
        try:
            or_conditions.append({"_id": ObjectId(search)})
        except InvalidId:
            pass

        query["$or"] = or_conditions

    ca_registrations = list(
        db.ca_registrations.find(query).sort('registration_date', -1)
    )

    return render_template(
        'admin/ca_registrations.html',
        ca_registrations=ca_registrations,
        status_filter=status_filter,
        search=search
    )

@admin_bp.route('/update-ca-status/<ca_id>', methods=['POST'])
@role_required('admin', 'executive')  # Only admin/executive can approve/reject
def update_ca_status(ca_id):
    """Update CA status (approve/reject)"""
    status = request.json.get('status')
    
    if status not in ['approved', 'rejected', 'pending']:
        return jsonify({'success': False, 'message': 'Invalid status'}), 400
    
    try:
        result = db.ca_registrations.update_one(
            {'_id': ObjectId(ca_id)},
            {'$set': {'status': status, 'status_updated_at': datetime.utcnow()}}
        )
        
        if status == 'approved':
            # Send approval email
            ca = db.ca_registrations.find_one({'_id': ObjectId(ca_id)})
            if ca:
                send_ca_approval_email(ca)
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@admin_bp.route('/export')
@role_required('admin', 'executive', 'organizer', 'moderator')
def admin_export():
    segments = list(db.segments.find({}))
    return render_template(
        'admin/export.html',
        segments=segments
    )

@admin_bp.route('/reg-export')
@role_required('admin', 'executive', 'organizer', 'moderator')
def admin_reg_export():
    format_type = request.args.get('format', 'csv')
    verified = request.args.get('verified')  # "true", "false", or None
    segment_id = request.args.get('segment_id')

    query = {}

    if segment_id:
        query['segment_id'] = ObjectId(segment_id)

    if verified in ('true', 'false'):
        query['verified'] = True if verified == 'true' else False

    registrations = list(db.registrations.find(query))

    if format_type == 'csv':
        return export_to_csv(registrations)
    else:
        return export_to_excel(registrations)


@admin_bp.route('/ca-export')
@role_required('admin', 'executive', 'organizer', 'moderator')
def admin_ca_export():
    """Export data page"""
    format_type = request.args.get('format', 'csv')
    status = request.args.get('status')
    
    query = {}
    if status:
        query['status'] = status
    
    ca_data = list(db.ca_registrations.find(query))

    if format_type == 'csv':
        csv_data = export_ca_to_csv(ca_data)
        return csv_data
    else:
        excel_data = export_to_excel(ca_data)
        return excel_data

# Replace both admin_users and add_admin_user routes with this combined route:
@admin_bp.route('/users', methods=['GET', 'POST'])
@role_required('admin', 'executive')  # Only admin and executive can manage users
def admin_users():
    """View all admin users and add new ones"""
    form = AdminUserForm()
    
    # Handle form submission for adding new user
    if form.validate_on_submit():
        # Check if email already exists
        existing_user = db.users.find_one({'email': form.email.data})
        if existing_user:
            flash('Email already registered', 'error')
            return redirect(url_for('admin.admin_users'))
        
        # Check if current user can create this role
        current_user_role = session.get('admin_role')
        target_role = form.role.data
        
        # Only admin can create other admins
        if target_role == 'admin' and current_user_role != 'admin':
            flash('Only admin can create other admin users', 'error')
            return redirect(url_for('admin.admin_users'))
        
        # Create new user with default permissions
        new_user = {
            'name': form.name.data,
            'email': form.email.data,
            'password': hash_password(form.password.data),
            'role': target_role,
            'permissions': get_default_permissions(target_role),
            'created_at': datetime.utcnow(),
            'created_by': session.get('admin_email', 'system'),
            'active': True,
            'last_login': None
        }
        
        # Insert into database
        db.users.insert_one(new_user)
        
        flash(f'{target_role.title()} user {form.email.data} added successfully', 'success')
        return redirect(url_for('admin.admin_users'))
    
    # Get all users for display (filter based on current user's role)
    current_user_role = session.get('admin_role')
    
    if current_user_role == 'admin':
        # Admin can see all users
        admin_users_list = list(db.users.find().sort('created_at', -1))
    else:
        # Others can only see non-admin users
        admin_users_list = list(db.users.find({'role': {'$ne': 'admin'}}).sort('created_at', -1))
    
    return render_template('admin/users.html', 
                         form=form, 
                         admin_users=admin_users_list,
                         current_user_role=current_user_role)
# Remove the add_admin_user route entirely

# Keep the other admin user management routes (delete, reset password)
@admin_bp.route('/users/<user_id>/reset-password', methods=['POST'])
@role_required('admin', 'executive')
def reset_admin_password(user_id):
    """Reset admin user password"""
    try:
        new_password = request.json.get('new_password')
        
        if not new_password or len(new_password) < 6:
            return jsonify({'success': False, 'message': 'Password must be at least 6 characters'}), 400
        
        user = db.users.find_one({'_id': ObjectId(user_id), 'role': 'admin'})
        
        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 404
        
        # Update password
        db.users.update_one(
            {'_id': ObjectId(user_id)},
            {'$set': {
                'password': hash_password(new_password),
                'updated_at': datetime.utcnow(),
                'password_changed_at': datetime.utcnow()
            }}
        )
        
        return jsonify({'success': True, 'message': 'Password reset successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# Update delete user route with role checks
@admin_bp.route('/users/<user_id>/delete', methods=['DELETE'])
@role_required('admin', 'executive')
def delete_admin_user(user_id):
    """Delete admin user"""
    try:
        user = db.users.find_one({'_id': ObjectId(user_id)})
        
        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 404
        
        current_user_role = session.get('admin_role')
        current_user_email = session.get('admin_email')
        
        # Prevent deleting own account
        if user['email'] == current_user_email:
            return jsonify({'success': False, 'message': 'Cannot delete your own account'}), 400
        
        # Check permissions based on roles
        if user['role'] == 'admin':
            # Only admin can delete other admins
            if current_user_role != 'admin':
                return jsonify({'success': False, 'message': 'Only admin can delete admin users'}), 403
        else:
            # Executive can delete non-admin users
            if current_user_role not in ['admin', 'executive']:
                return jsonify({'success': False, 'message': 'Insufficient permissions'}), 403
        
        # Delete user
        result = db.users.delete_one({'_id': ObjectId(user_id)})
        
        if result.deleted_count > 0:
            return jsonify({'success': True, 'message': 'User deleted successfully'})
        else:
            return jsonify({'success': False, 'message': 'Failed to delete user'}), 500
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500