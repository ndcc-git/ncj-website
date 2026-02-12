from functools import wraps
import os
import random
import string
import uuid
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session, blueprints
from flask_wtf.csrf import CSRFProtect
import jwt
from pymongo import MongoClient
from datetime import datetime, timedelta
from bson.objectid import ObjectId
import requests
from werkzeug.utils import secure_filename
from config import Config
from forms import ChangePasswordForm, ForgotPasswordForm, ProfileUpdateForm, RegistrationForm, CARegistrationForm, ContactForm, UserLoginForm, UserSignupForm
from utils.security import hash_password, generate_csrf_token
import extensions
from firebase_config import initialize_firebase
from utils.firebase_helpers import firebase_get_user_info, firebase_verify_token
from utils.firebase_helpers import (
    firebase_create_user, 
    firebase_login_user, 
    firebase_send_password_reset,
    firebase_update_user,
    firebase_change_password,
    firebase_send_email_verification
)
import uuid
import re

app = Flask(__name__)
app.config.from_object(Config)

extensions.client = MongoClient(app.config['MONGO_URI'])
extensions.db = extensions.client.festival_db

from admin import admin_bp, admin_required
app.register_blueprint(admin_bp, url_prefix='/admin')

# Initialize CSRF protection
csrf = CSRFProtect(app)

db = extensions.client.festival_db
# Collections
users_collection = db.users
registrations_collection = db.registrations
segments_collection = db.segments
ca_collection = db.ca_registrations

initialize_firebase()


def generate_ca_code(full_name):
    """Generate unique 4-letter CA code from name"""
    # Get initials from name
    initials = ''.join([word[0].upper() for word in full_name.split() if word])
    
    # If initials are less than 4 letters, add random letters
    if len(initials) >= 4:
        code = initials[:4]
    else:
        # Add random letters to make 4 characters
        random_chars = ''.join(random.choices(string.ascii_uppercase, k=4-len(initials)))
        code = initials + random_chars
    
    # Check if code already exists, if yes, add number
    existing_ca = db.ca_registrations.find_one({'ca_code': code})
    counter = 1
    original_code = code
    
    while existing_ca:
        if counter < 10:
            code = f"{original_code[:3]}{counter}"
        else:
            code = f"{original_code[:2]}{counter:02d}"
        existing_ca = db.ca_registrations.find_one({'ca_code': code})
        counter += 1
    
    return code

def get_default_permissions(role):
    """Get default permissions based on role"""
    permissions = {
        'admin': ['*'],  # All permissions
        'executive': [
            'view_dashboard',
            'manage_registrations',
            'verify_registrations',
            'manage_ca',
            'approve_ca',
            'view_analytics',
            'send_emails',
            'export_data',
            'view_contact_messages',
            'manage_admin_users',
            'view_segments'
        ],
        'organizer': [
            'view_dashboard',
            'view_registrations',
            'view_ca',
            'view_analytics',
            'view_contact_messages',
            'export_data',
            'view_segments'
        ],
        'moderator': [
            'view_dashboard',
            'view_registrations',
            'view_ca',
            'export_data',
            'view_segments'
        ]
    }
    return permissions.get(role, [])

def login_required(f):
    """Decorator to require user login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page', 'error')
            return redirect(url_for('user_login', next=request.url))
        
        # Check if we have a refresh token and token is expired
        if 'refresh_token' in session:
            try:
                # Try to verify current token
                decoded_token = firebase_verify_token(session['firebase_token'])
                if not decoded_token:
                    # Token expired, try to refresh it
                    from utils.firebase_helpers import refresh_firebase_token
                    new_tokens = refresh_firebase_token(session['refresh_token'])
                    if new_tokens:
                        session['firebase_token'] = new_tokens.get('id_token')
                        session['refresh_token'] = new_tokens.get('refresh_token')
                    else:
                        # Refresh failed, clear session
                        session.clear()
                        flash('Session expired. Please login again.', 'error')
                        return redirect(url_for('user_login'))
            except:
                # Token verification failed
                session.clear()
                flash('Session expired. Please login again.', 'error')
                return redirect(url_for('user_login'))
        
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
                payload = jwt.decode(token, app.config['JWT_SECRET_KEY'], algorithms=['HS256'])
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


def email_verified_required(f):
    """Decorator to require verified email"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        
        if not user:
            flash('Please login to access this page', 'error')
            return redirect(url_for('user_login', next=request.url))
        
        # Check if email is verified
        if not user.get('email_verified', False):
            flash('❌ Please verify your email address before accessing this feature. '
                  'Check your inbox for the verification email or go to your profile to resend it.', 'error')
            return redirect(url_for('user_profile'))
        
        return f(*args, **kwargs)
    return decorated_function

def get_current_user():
    """Get current user from session"""
    if 'user_id' not in session:
        return None
    
    user = db.users.find_one({'_id': ObjectId(session['user_id'])})
    return user

def init_db():
    """Initialize database with sample data if empty"""
    
    if db.settings.count_documents({'name': 'system_settings'}) == 0:
        system_settings = {
            'name': 'system_settings',
            'registration_enabled': True,
            'ca_registration_enabled': True,
            'contact_form_enabled': True,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }
        db.settings.insert_one(system_settings)

    # Create admin user if not exists
    if users_collection.count_documents({'role': 'admin'}) == 0:
        admin_user = {
            'email': 'admin@festival.com',
            'password': hash_password('admin123'),
            'name': 'System Administrator',
            'role': 'admin',
            'created_at': datetime.utcnow(),
            'created_by': 'system',
            'active': True,
            'last_login': None,
            'permissions': ['*']  # All permissions
        }
        users_collection.insert_one(admin_user)

    # Create sample users with different roles
    sample_roles = ['executive', 'organizer', 'moderator']

    """Initialize database with sample data if empty"""
    # Initialize Firebase
    initialize_firebase()
    
    # Ensure collections exist and have indexes
    collections = {
        'users': [
            [('email', 1), {'unique': True}],
            [('firebase_uid', 1), {'unique': True}],
            [('created_at', -1)],
            [('institution', 1)],
            [('mobile', 1)]
        ],
        'registrations': [
            [('user_id', 1)],
            [('email', 1)],
            [('segment_id', 1)],
            [('registration_date', -1)],
            [('verified', 1)],
            [('transaction_id', 1), {'unique': True, 'sparse': True}]
        ],
        'ca_registrations': [
            [('user_id', 1)],
            [('email', 1)],
            [('ca_code', 1), {'unique': True}],
            [('registration_date', -1)],
            [('status', 1)]
        ],
        'segments': [
            [('name', 1)],
            [('type', 1)],
            [('price', 1)]
        ],
        'contact_messages': [
            [('email', 1)],
            [('submitted_at', -1)],
            [('status', 1)]
        ]
    }
    
    for collection_name, indexes in collections.items():
        collection = db[collection_name]
        for index_spec in indexes:
            try:
                collection.create_index(index_spec[0], **index_spec[1] if len(index_spec) > 1 else {})
            except:
                pass

    users_collection.create_index([('email', 1)], unique=True)
    users_collection.create_index([('role', 1)])
    users_collection.create_index([('active', 1)])
    users_collection.create_index([('created_at', -1)])

    db.ca_registrations.create_index([('email', 1)], unique=False)
    db.ca_registrations.create_index([('ca_code', 1)], unique=True)
    db.contact_messages.create_index([('email', 1)])
    db.contact_messages.create_index([('submitted_at', -1)])
    db.contact_messages.create_index([('status', 1)])
    db.contact_messages.create_index([('archived', 1)])


ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png'}
MAX_FILE_SIZE = 2 * 1024 * 1024

@app.route('/registration-closed')
def registration_closed():
    """Registration closed page"""
    return render_template('registration_closed.html')

@app.route('/ca-registration-closed')
def ca_registration_closed():
    """CA registration closed page"""
    return render_template('ca_registration_closed.html')

@app.route('/')
def index():
    """Home page"""
    segments = list(segments_collection.find({}, {'_id': 1, 'name': 1, 'price': 1, 'type': 1}))
    return render_template('index.html', segments=segments)


# User Authentication Routes
@app.route('/signup', methods=['GET', 'POST'])
def user_signup():
    """User signup page"""
    if 'user_id' in session:
        return redirect(url_for('user_profile'))
    
    form = UserSignupForm()
    
    if form.validate_on_submit():
        try:
            # 1. Create user in Firebase Authentication
            firebase_user = firebase_create_user(
                email=form.email.data,
                password=form.password.data,
                display_name=form.full_name.data
            )
            
            # 2. Create user document in MongoDB
            user_data = {
                'firebase_uid': firebase_user.uid,
                'full_name': form.full_name.data,
                'address': form.address.data,
                'email': form.email.data,
                'mobile': form.mobile.data,
                'institution': form.institution.data,
                'class_level': form.class_level.data,
                'facebook_link': form.facebook_link.data,
                'email_verified': False,
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow(),
                'last_login': None,
                'status': 'active',
                'registrations': [],  # Array of registration IDs
                'ca_applications': []  # Array of CA application IDs
            }
            
            result = db.users.insert_one(user_data)
            user_id = str(result.inserted_id)
            
            # 3. Login user immediately
            login_data = firebase_login_user(form.email.data, form.password.data)
            
            # 4. Store user session
            session['user_id'] = user_id
            session['firebase_uid'] = firebase_user.uid
            session['firebase_token'] = login_data.get('idToken')
            session['user_email'] = form.email.data
            session['user_name'] = form.full_name.data
            
            # 5. Send email verification
            try:
                firebase_send_email_verification(login_data.get('idToken'))
                flash('Verification email sent. Please check your inbox.', 'info')
            except:
                pass  # Verification email sending is optional
            
            flash('Account created successfully!', 'success')
            return redirect(url_for('user_profile'))
            
        except Exception as e:
            flash(str(e), 'error')
    
    return render_template('user/signup.html', form=form)


def check_and_update_email_verification(id_token):
    """Check if user's email is verified and update MongoDB"""
    try:
        user_info = firebase_get_user_info(id_token)
        print(user_info)
        if user_info:
            email = user_info.get('email')
            email_verified = user_info.get('emailVerified', False)
            
            if email and email_verified:
                # Update MongoDB
                db.users.update_one(
                    {'email': email},
                    {'$set': {'email_verified': True}}
                )
                return True
        return False
    except Exception as e:
        print(f"Error checking email verification: {str(e)}")
        return False

@app.route('/login', methods=['GET', 'POST'])
def user_login():
    """User login page"""
    # Clear any existing session first
    if 'user_id' in session:
        session.clear()
    
    form = UserLoginForm()
    
    if form.validate_on_submit():
        try:
            # 1. Login with Firebase
            login_data = firebase_login_user(form.email.data, form.password.data)
            id_token = login_data.get('idToken')
            
            # 2. Get user from MongoDB
            user = db.users.find_one({'email': form.email.data})
            
            if not user:
                flash('Account not found. Please sign up first.', 'error')
                return redirect(url_for('user_signup'))
            
            # 3. Check and update email verification status
            is_verified = check_and_update_email_verification(id_token)
            
            if is_verified and not user.get('email_verified', False):
                db.users.update_one(
                    {'_id': user['_id']},
                    {'$set': {'email_verified': True}}
                )
                user['email_verified'] = True
            elif not is_verified:
                # Update verification status from Firebase
                db.users.update_one(
                    {'_id': user['_id']},
                    {'$set': {'email_verified': False}}
                )
                user['email_verified'] = False
            
            # 4. Update last login
            db.users.update_one(
                {'_id': user['_id']},
                {'$set': {'last_login': datetime.utcnow()}}
            )
            
            # 5. Store user session
            session['user_id'] = str(user['_id'])
            session['firebase_uid'] = user['firebase_uid']
            session['firebase_token'] = id_token
            session['refresh_token'] = login_data.get('refreshToken')
            session['user_email'] = user['email']
            session['user_name'] = user['full_name']
            session['email_verified'] = user.get('email_verified', False)
            
            # 6. Set session expiration based on "Remember Me"
            if form.remember.data:
                # Remember for 30 days
                session.permanent = True
                app.permanent_session_lifetime = timedelta(days=30)
                # Also set a cookie flag
                response = redirect(url_for('user_profile'))
                response.set_cookie('remember_me', 'true', max_age=30*24*60*60)
                return response
            else:
                # Browser session only
                session.permanent = False
            
            flash('Logged in successfully!', 'success')
            
            # 7. Show verification reminder if not verified
            if not user.get('email_verified', False):
                flash('Please verify your email address to access all features.', 'warning')
            
            # Redirect to previous page or profile
            next_page = request.args.get('next')
            return redirect(next_page or url_for('user_profile'))
            
        except Exception as e:
            flash(str(e), 'error')
    
    return render_template('user/login.html', form=form)



@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Forgot password page"""
    form = ForgotPasswordForm()
    
    if form.validate_on_submit():
        try:
            reset_link = firebase_send_password_reset(form.email.data)
            
            # In production, Firebase sends the email automatically
            # We can log the reset link for debugging
            app.logger.info(f'Password reset link: {reset_link}')
            
            flash('Password reset email sent. Check your inbox.', 'success')
            return redirect(url_for('user_login'))
            
        except Exception as e:
            flash(str(e), 'error')
    
    return render_template('user/forgot_password.html', form=form)

@app.route('/logout')
def user_logout():
    """User logout"""
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('index'))

@app.route('/profile')
@login_required
def user_profile():
    """User profile page"""
    user = get_current_user()
    
    if not user:
        session.clear()
        return redirect(url_for('user_login'))
    
    # Get user's registrations
    user_registrations = list(db.registrations.find(
        {'user_id': user['_id']}
    ).sort('registration_date', -1))
    
    # Get user's CA applications
    ca_applications = list(db.ca_registrations.find(
        {'user_id': user['_id']}
    ).sort('registration_date', -1))
    
    return render_template('user/profile.html', 
                         user=user,
                         registrations=user_registrations,
                         ca_applications=ca_applications)

@app.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    """Edit profile page"""
    user = get_current_user()
    
    if not user:
        return redirect(url_for('user_login'))
    
    form = ProfileUpdateForm()
    
    # Pre-fill form with current data
    if request.method == 'GET':
        form.full_name.data = user.get('full_name', '')
        form.address.data = user.get('address', '')
        form.mobile.data = user.get('mobile', '')
        form.institution.data = user.get('institution', '')
        form.class_level.data = user.get('class_level', '')
        form.facebook_link.data = user.get('facebook_link', '')
    
    if form.validate_on_submit():
        try:

            # Update user in MongoDB
            update_data = {
                'full_name': form.full_name.data,
                'address': form.address.data,
                'mobile': form.mobile.data,
                'institution': form.institution.data,
                'class_level': form.class_level.data,
                'facebook_link': form.facebook_link.data,
                'updated_at': datetime.utcnow()
            }
                    
            db.users.update_one(
                {'_id': user['_id']},
                {'$set': update_data}
            )
            
            # Update Firebase display name
            try:
                firebase_update_user(
                    uid=user['firebase_uid'],
                    display_name=form.full_name.data
                )
            except:
                pass  # Firebase update is optional
            
            flash('Profile updated successfully!', 'success')
            return redirect(url_for('user_profile'))
            
        except Exception as e:
            flash(f'Error updating profile: {str(e)}', 'error')
    
    return render_template('user/edit_profile.html', form=form, user=user)

@app.route('/profile/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Change password page"""
    user = get_current_user()
    
    if not user:
        return redirect(url_for('user_login'))
    
    form = ChangePasswordForm()
    
    if form.validate_on_submit():
        try:
            # Verify current password
            try:
                login_data = firebase_login_user(user['email'], form.current_password.data)
            except Exception as e:
                flash('Current password is incorrect', 'error')
                return render_template('user/change_password.html', form=form)
            
            # Validate new password strength
            if len(form.new_password.data) < 8:
                flash('New password must be at least 8 characters', 'error')
                return render_template('user/change_password.html', form=form)
            
            if not re.search(r"[A-Z]", form.new_password.data):
                flash('New password must contain at least one uppercase letter', 'error')
                return render_template('user/change_password.html', form=form)
            
            if not re.search(r"[a-z]", form.new_password.data):
                flash('New password must contain at least one lowercase letter', 'error')
                return render_template('user/change_password.html', form=form)
            
            if not re.search(r"[0-9]", form.new_password.data):
                flash('New password must contain at least one number', 'error')
                return render_template('user/change_password.html', form=form)
            
            # Check if new password is same as old
            if form.current_password.data == form.new_password.data:
                flash('New password must be different from current password', 'error')
                return render_template('user/change_password.html', form=form)
            
            # Change password in Firebase
            firebase_change_password(user['firebase_uid'], form.new_password.data)
            
            # Update password changed timestamp in MongoDB
            db.users.update_one(
                {'_id': user['_id']},
                {'$set': {
                    'password_changed_at': datetime.utcnow(),
                    'updated_at': datetime.utcnow()
                }}
            )
            
            # Send confirmation email
            try:
                from utils.email_service import send_password_changed_email
                send_password_changed_email(
                    user['email'],
                    user['full_name']
                )
            except:
                pass  # Email sending is optional
            
            flash('Password changed successfully!', 'success')
            return redirect(url_for('user_profile'))
            
        except Exception as e:
            flash(str(e), 'error')
    
    return render_template('user/change_password.html', form=form)



@app.route('/verify-email')
@login_required
def verify_email():
    """Send email verification"""
    user = get_current_user()
    
    if not user:
        return redirect(url_for('user_login'))
    
    try:
        firebase_send_email_verification(session.get('firebase_token'))
        flash('Verification email sent. Please check your inbox.', 'success')
    except Exception as e:
        flash(f'Error sending verification: {str(e)}', 'error')
    
    return redirect(url_for('user_profile'))


@app.route('/ca-register', methods=['GET', 'POST'])
@login_required
@email_verified_required
def ca_register():
    """CA Registration page"""
    user = get_current_user()
    
    if not user:
        return redirect(url_for('user_login'))
    
    # Check if CA registration is enabled
    settings = db.settings.find_one({'name': 'system_settings'})
    if not settings or not settings.get('ca_registration_enabled', True):
        flash('CA registration is currently closed.', 'error')
        return redirect(url_for('ca_registration_closed'))
    
    # Check if user has already applied for CA
    existing_ca = db.ca_registrations.find_one({'user_id': user['_id']})
    if existing_ca:
        flash('You have already applied to be a Campus Ambassador. '
              'You cannot apply again.', 'error')
        return redirect(url_for('ca_registration_success', ca_id=str(existing_ca['_id'])))
    
    # Check if email already registered as CA (additional check)
    existing_ca_email = db.ca_registrations.find_one({'email': user['email']})
    if existing_ca_email:
        flash('This email is already registered as a CA', 'error')
        return redirect(url_for('ca_registration_success', ca_id=str(existing_ca_email['_id'])))
    
    form = CARegistrationForm()
    
    # File upload configurations
    UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads', 'ca_profiles')
    
    # Ensure upload directory exists
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    
    # Helper function to validate file
    def allowed_file(filename):
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
    
    def validate_file_size(file):
        file.seek(0, 2)  # Seek to end
        file_size = file.tell()
        file.seek(0)  # Reset to beginning
        return file_size <= MAX_FILE_SIZE
    
    # Pre-fill form with user data
    if request.method == 'GET':
        form.full_name.data = user.get('full_name', '')
        form.email.data = user.get('email', '')
        form.phone.data = user.get('mobile', '')
        form.institution.data = user.get('institution', '')
        form.class_info.data = user.get('class_level', '')
    
    if form.validate_on_submit():
        # Generate CA code
        ca_code = generate_ca_code(form.full_name.data)
        
        # Handle profile picture upload from form
        profile_pic_filename = None
        
        if form.profile_picture.data:
            file = form.profile_picture.data
            
            # Check if file has a name
            if file.filename == '':
                flash('Profile picture is required', 'error')
                return redirect(url_for('ca_register'))
            
            # Validate file extension
            if not allowed_file(file.filename):
                flash('Only JPG, JPEG, and PNG files are allowed', 'error')
                return redirect(url_for('ca_register'))
            
            # Validate file size
            if not validate_file_size(file):
                flash(f'File size exceeds {MAX_FILE_SIZE // (1024*1024)}MB limit', 'error')
                return redirect(url_for('ca_register'))
            
            # Secure the filename
            original_filename = secure_filename(file.filename)
            
            # Extract file extension
            file_ext = original_filename.rsplit('.', 1)[1].lower() if '.' in original_filename else 'jpg'
            
            # Generate unique filename with UUID and timestamp
            unique_id = uuid.uuid4().hex[:8]
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            profile_pic_filename = f"ca_{ca_code}_{timestamp}_{unique_id}.{file_ext}"
            
            # Build safe file path
            safe_filename = secure_filename(profile_pic_filename)
            file_path = os.path.join(UPLOAD_FOLDER, safe_filename)
            
            # Ensure we're not writing outside the upload directory
            upload_root = os.path.abspath(UPLOAD_FOLDER)
            file_abs_path = os.path.abspath(file_path)
            
            if not file_abs_path.startswith(upload_root):
                flash('Invalid file path', 'error')
                return redirect(url_for('ca_register'))
            
            try:
                # Save the file
                file.save(file_path)
                
                # Verify the saved file is an actual image
                try:
                    from PIL import Image
                    with Image.open(file_path) as img:
                        img.verify()
                        
                        # Resize image if too large
                        max_dimension = 800
                        with Image.open(file_path) as img_resize:
                            if img_resize.width > max_dimension or img_resize.height > max_dimension:
                                img_resize.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
                                img_resize.save(file_path, optimize=True, quality=85)
                except ImportError:
                    # PIL not installed, skip verification
                    pass
                except Exception as e:
                    # Invalid image file, delete it
                    os.remove(file_path)
                    flash('Invalid image file. Please upload a valid image.', 'error')
                    return redirect(url_for('ca_register'))
                    
            except Exception as e:
                app.logger.error(f'File upload error: {str(e)}')
                flash('Error uploading file. Please try again.', 'error')
                return redirect(url_for('ca_register'))
        else:
            flash('Profile picture is required', 'error')
            return redirect(url_for('ca_register'))
        
        # Create CA registration
        ca_data = {
            'user_id': user['_id'],
            'firebase_uid': user['firebase_uid'],
            'full_name': form.full_name.data,
            'institution': form.institution.data,
            'class': form.class_info.data,
            'phone': form.phone.data,
            'email': form.email.data,
            'why_ca': form.why_ca.data,
            'profile_picture': profile_pic_filename,
            'ca_code': ca_code,
            'status': 'pending',
            'registration_date': datetime.utcnow(),
            'ip_address': request.remote_addr,
            'user_agent': request.user_agent.string,
            'user_email_verified': True
        }
        
        # Insert into database
        result = db.ca_registrations.insert_one(ca_data)
        
        # Add CA application ID to user's applications array
        db.users.update_one(
            {'_id': user['_id']},
            {'$push': {'ca_applications': result.inserted_id}}
        )
        
        flash('CA application submitted successfully!', 'success')
        return redirect(url_for('ca_registration_success', ca_id=str(result.inserted_id)))
    
    return render_template('ca_register.html', form=form)


@app.route('/ca-registration-success/<ca_id>')
def ca_registration_success(ca_id):
    """CA Registration success page"""
    ca_registration = db.ca_registrations.find_one({'_id': ObjectId(ca_id)})
    if not ca_registration:
        flash('CA registration not found', 'error')
        return redirect(url_for('index'))
    
    return render_template('ca_success.html', ca_registration=ca_registration)

@app.route('/register', methods=['GET', 'POST'])
@login_required
@email_verified_required
def register():
    """Registration form for participants"""
    user = get_current_user()
    
    if not user:
        return redirect(url_for('user_login'))
    
    settings = db.settings.find_one({'name': 'system_settings'})
    if not settings or not settings.get('registration_enabled', True):
        flash('❌ Event registration is currently closed.', 'error')
        return redirect(url_for('registration_closed'))

    form = RegistrationForm()
    
    # Get segments for dropdown
    segments = list(segments_collection.find({}, {'_id': 1, 'name': 1, 'price': 1, 'categories': 1}))
    form.segment.choices = [(str(seg['_id']), f"{seg['name']} - ${seg['price']}") for seg in segments]
    
    # Get segment_id from query parameter
    segment_id = request.args.get('segment_id')
    
    # Pre-fill form with user data
    if request.method == 'GET':
        form.full_name.data = user.get('full_name', '')
        form.email.data = user.get('email', '')
        form.institution.data = user.get('institution', '')
    
    if form.validate_on_submit():
        # Generate CSRF token for this submission
        csrf_token = generate_csrf_token()
        
        # Check if segment exists and has capacity
        segment = segments_collection.find_one({'_id': ObjectId(form.segment.data)})
        if not segment:
            flash('Selected segment not found', 'error')
            return redirect(url_for('register'))
        
        if segment.get('current_participants', 0) >= segment.get('max_participants', float('inf')):
            flash('This segment is full', 'error')
            return redirect(url_for('register'))
        
        # Check for duplicate registration (same user for same segment)
        existing = registrations_collection.find_one({
            'user_id': user['_id'],
            'segment_id': ObjectId(form.segment.data)
        })
        
        if existing:
            flash('You have already registered for this segment', 'error')
            return redirect(url_for('register'))
        
        # Conditional category validation
        if segment.get('categories') and not form.category.data:
            form.category.errors.append("Category is required for this segment.")
            return render_template('register.html', form=form, segments=segments)
        
        # Conditional submission link validation
        if segment.get('type') == "Submission" and not form.submission_link.data:
            form.submission_link.errors.append("Submission link is required for this segment.")
            return render_template('register.html', form=form, segments=segments)

        # Create registration
        registration_data = {
            'user_id': user['_id'],
            'firebase_uid': user['firebase_uid'],
            'full_name': form.full_name.data,
            'email': form.email.data,
            'institution': form.institution.data,
            'segment_id': ObjectId(form.segment.data),
            'segment_name': segment['name'],
            'category': form.category.data if segment.get('categories') else None,
            'submission_link': form.submission_link.data if segment.get('type') == "Submission" else None,
            'ca_ref': form.ca_ref.data,
            'bkash_number': form.bkash_number.data,
            'transaction_id': form.transaction_id.data,
            'verified': False,
            'registration_date': datetime.utcnow(),
            'csrf_token': csrf_token,
            'ip_address': request.remote_addr,
            'user_agent': request.user_agent.string
        }
        
        # Insert registration
        result = registrations_collection.insert_one(registration_data)
        
        # Update segment participant count
        segments_collection.update_one(
            {'_id': ObjectId(form.segment.data)},
            {'$inc': {'current_participants': 1}}
        )
        
        # Add registration ID to user's registrations array
        db.users.update_one(
            {'_id': user['_id']},
            {'$push': {'registrations': result.inserted_id}}
        )
        
        return redirect(url_for('registration_success', registration_id=str(result.inserted_id)))
    
    # Pre-select segment if segment_id is provided and valid
    if segment_id:
        try:
            ObjectId(segment_id)
            segment_exists = any(str(seg['_id']) == segment_id for seg in segments)
            if segment_exists:
                form.segment.data = segment_id
                return render_template('register.html', 
                                     form=form, 
                                     segments=segments,
                                     preselected_segment_id=segment_id)
        except:
            pass
    
    return render_template('register.html', form=form, segments=segments)


@app.route('/registration-success/<registration_id>')
def registration_success(registration_id):
    """Success page after registration"""
    registration = registrations_collection.find_one({'_id': ObjectId(registration_id)})
    if not registration:
        flash('Registration not found', 'error')
        return redirect(url_for('index'))
    
    return render_template('success.html', registration=registration)

@app.route('/gallery', methods=['GET'])
def gallery():
    return {"Hello": "adawd"}

@app.route('/about', methods=['GET'])
def about():
    return {"Hello": "adawd"}

@app.route('/events', methods=['GET'])
def events():
    return {"Hello": "adawd"}



@app.route('/contact', methods=['GET', 'POST'])
def contact():
    """Contact form page"""
    form = ContactForm()
    
    if form.validate_on_submit():
        # Check for spam/duplicate submissions
        recent_submission = db.contact_messages.find_one({
            'email': form.email.data,
            'submitted_at': {'$gte': datetime.utcnow() - timedelta(hours=1)}
        })
        
        if recent_submission:
            flash('You have already submitted a message recently. Please wait before submitting again.', 'warning')
            return redirect(url_for('contact'))
        
        # Create contact message
        contact_data = {
            'name': form.name.data,
            'institution': form.institution.data,
            'email': form.email.data,
            'message': form.message.data,
            'submitted_at': datetime.utcnow(),
            'ip_address': request.remote_addr,
            'user_agent': request.user_agent.string,
            'status': 'unread',  # unread, read, replied
            'archived': False
        }
        
        # Insert into database
        db.contact_messages.insert_one(contact_data)
        
        flash('Your message has been sent successfully! We will get back to you soon.', 'success')
        
        # Store in session for auto-fill
        session['last_contact'] = {
            'name': form.name.data,
            'email': form.email.data,
            'institution': form.institution.data
        }
        
        return redirect(url_for('contact_success'))
    
    # Pre-fill form with session data if available
    if 'last_contact' in session:
        form.name.data = session['last_contact']['name']
        form.email.data = session['last_contact']['email']
        form.institution.data = session['last_contact']['institution']
    
    return render_template('contact.html', form=form)

@app.route('/contact-success')
def contact_success():
    """Contact form success page"""
    return render_template('contact_success.html')


# ========== API ROUTES ==========

@app.route('/api/segments/<segment_id>/categories')
def get_segment_categories(segment_id):
    """API endpoint to get categories for a segment"""
    try:
        segment = segments_collection.find_one({'_id': ObjectId(segment_id)})
        if segment:
            return jsonify({'categories': segment.get('categories', [])})
        return jsonify({'categories': []})
    except:
        return jsonify({'categories': []})
    
@app.route('/api/segments/<segment_id>/type')
def get_segment_type(segment_id):
    """API endpoint to get categories for a segment"""
    try:
        segment = segments_collection.find_one({'_id': ObjectId(segment_id)})
        if segment:
            return jsonify({'type': segment.get('type', '')})
        return jsonify({'type': ''})
    except:
        return jsonify({'type': ''})


@app.route('/api/ca-details/<ca_id>')
@admin_required
def api_ca_details(ca_id):
    """API endpoint to get CA details"""
    try:
        ca = db.ca_registrations.find_one({'_id': ObjectId(ca_id)})
        if ca:
            # Convert ObjectId to string for JSON serialization
            ca['_id'] = str(ca['_id'])
            ca['user_id'] = str(ca['user_id'])
            return jsonify({'success': True, 'ca': ca})
        return jsonify({'success': False, 'message': 'CA not found'}), 404
    except:
        return jsonify({'success': False, 'message': f'Invalid CA ID'}), 400


@app.route('/api/message-details/<message_id>')
@admin_required
def api_message_details(message_id):
    """API endpoint to get message details"""
    try:
        message = db.contact_messages.find_one({'_id': ObjectId(message_id)})
        if message:
            # Convert ObjectId to string for JSON serialization
            message['_id'] = str(message['_id'])
            # Convert datetime to string
            if 'submitted_at' in message and isinstance(message['submitted_at'], datetime):
                message['submitted_at'] = message['submitted_at'].isoformat()
            return jsonify({'success': True, 'message': message})
        return jsonify({'success': False, 'message': 'Message not found'}), 404
    except:
        return jsonify({'success': False, 'message': 'Invalid message ID'}), 400

@app.route('/api/toggle-setting', methods=['POST'])
@admin_required
def toggle_setting():
    """API endpoint to toggle settings"""
    data = request.json
    setting_name = data.get('setting_name')
    new_value = data.get('value')
    
    if setting_name not in ['registration_enabled', 'ca_registration_enabled']:
        return jsonify({'success': False, 'message': 'Invalid setting'}), 400
    
    update_data = {
        setting_name: new_value,
        'updated_at': datetime.utcnow()
    }
    
    # Update or insert settings
    db.settings.update_one(
        {'name': 'system_settings'},
        {'$set': update_data},
        upsert=True
    )
    
    return jsonify({'success': True, setting_name: new_value})


@app.route('/api/scan-user/<user_id>')
@role_required('admin', 'executive', 'organizer', 'moderator')
def get_user_by_scan(user_id):
    """Get user details by scanned ID"""
    try:
        # Validate ObjectId
        try:
            obj_id = ObjectId(user_id)
        except:
            return jsonify({'success': False, 'message': 'Invalid QR code format'})
        
        # Step 1: Try to find user
        user = db.users.find_one({'_id': obj_id})
        
        # Step 2: If not user, try to find registration and get its user
        if not user:
            registration = db.registrations.find_one({'_id': obj_id})
            if registration:
                user = db.users.find_one({'_id': registration.get('user_id')})
        
        # Step 3: If still no user, try to find CA application and get its user
        if not user:
            ca_application = db.ca_registrations.find_one({'_id': obj_id})
            if ca_application:
                user = db.users.find_one({'_id': ca_application.get('user_id')})
        
        # Step 4: If still no user, return error
        if not user:
            return jsonify({'success': False, 'message': 'User not found'})
        
        # Get all registrations for this user
        user_registrations = list(db.registrations.find(
            {'user_id': user['_id']}
        ).sort('registration_date', -1))
        
        # Get all CA applications for this user
        user_ca_applications = list(db.ca_registrations.find(
            {'user_id': user['_id']}
        ).sort('registration_date', -1))
        
        # Build response
        response_data = {
            'success': True,
            'user': {
                'id': str(user['_id']),
                'name': user.get('full_name', user.get('name', '')),
                'present': user.get('present', False),
                'email': user.get('email', ''),
                'mobile': user.get('mobile', ''),
                'institution': user.get('institution', ''),
                'profile_picture': user.get('profile_picture'),
                'class_level': user.get('class_level', ''),
                'email_verified': user.get('email_verified', False),
                'facebook_link': user.get('facebook_link', ''),
                'address': user.get('address', ''),
                'created_at': user.get('created_at')
            },
            'registrations': [
                {
                    'id': str(reg['_id']),
                    'segment': reg.get('segment_name', ''),
                    'category': reg.get('category', ''),
                    'verified': reg.get('verified', False),
                    'present': reg.get('present', False),
                    'present_at': reg.get('present_at'),
                    'date': reg.get('registration_date'),
                    'transaction_id': reg.get('transaction_id', ''),
                    'bkash_number': reg.get('bkash_number', '')
                }
                for reg in user_registrations
            ],
            'ca_applications': [
                {
                    'id': str(ca['_id']),
                    'ca_code': ca.get('ca_code', ''),
                    'status': ca.get('status', 'pending'),
                    'phone': ca.get('phone', ''),
                    'why_ca': ca.get('why_ca', ''),
                    'class': ca.get('class', ''),
                    'date': ca.get('registration_date'),
                    'profile_picture': ca.get('profile_picture')
                }
                for ca in user_ca_applications
            ]
        }
        
        # Add current registration if this scan was for a registration
        registration = db.registrations.find_one({'_id': obj_id})
        if registration and str(registration.get('user_id')) == str(user['_id']):
            response_data['current_registration'] = {
                'id': str(registration['_id']),
                'segment': registration.get('segment_name', ''),
                'category': registration.get('category', ''),
                'verified': registration.get('verified', False),
                'present': registration.get('present', False),
                'present_at': registration.get('present_at'),
                'date': registration.get('registration_date'),
                'transaction_id': registration.get('transaction_id', ''),
                'bkash_number': registration.get('bkash_number', '')
            }
        
        # Add current CA application if this scan was for a CA application
        ca_application = db.ca_registrations.find_one({'_id': obj_id})
        if ca_application and str(ca_application.get('user_id')) == str(user['_id']):
            response_data['current_ca_application'] = {
                'id': str(ca_application['_id']),
                'ca_code': ca_application.get('ca_code', ''),
                'status': ca_application.get('status', 'pending'),
                'phone': ca_application.get('phone', ''),
                'why_ca': ca_application.get('why_ca', ''),
                'class': ca_application.get('class', ''),
                'date': ca_application.get('registration_date'),
                'profile_picture': ca_application.get('profile_picture')
            }
        
        return jsonify(response_data)
        
    except Exception as e:
        print(f"Scan error: {str(e)}")
        return jsonify({'success': False, 'message': 'Error processing scan'})

@app.route('/api/mark-present/<user_id>', methods=['POST'])
@role_required('admin', 'executive', 'organizer', 'moderator')
def mark_present(user_id):
    """Mark a registration as present"""
    try:
        # Validate CSRF token
        csrf_token = request.headers.get('X-CSRFToken')
        if not csrf_token:
            return jsonify({'success': False, 'message': 'CSRF token missing'}), 403
        
        result = db.users.update_one(
            {'_id': ObjectId(user_id)},
            {'$set': {
                'present': True,
                'present_at': datetime.utcnow()
            }}
        )
        
        if result.modified_count > 0:
            return jsonify({'success': True, 'message': 'Marked as present'})
        else:
            return jsonify({'success': False, 'message': 'Registration not found'})
            
    except Exception as e:
        return jsonify({'success': False, 'message': 'Error marking present'})

@app.errorhandler(404)
def page_not_found(e):
    return render_template('errors/404.html'), 404

if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(debug=True, port=5000)