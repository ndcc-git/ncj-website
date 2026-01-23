import json
import os
import random
import string
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from flask_wtf.csrf import CSRFProtect
from pymongo import MongoClient
from datetime import datetime, timedelta
import jwt
from functools import wraps
from bson.objectid import ObjectId
from bson import json_util
import pandas as pd
from io import BytesIO
from werkzeug.utils import secure_filename
from config import Config
from forms import RegistrationForm, AdminLoginForm, EmailForm, CARegistrationForm, ContactForm
from utils.security import hash_password, verify_password, generate_csrf_token, verify_csrf_token
from utils.email_service import send_verification_email, send_bulk_emails, send_ca_approval_email
from utils.export_service import export_ca_to_csv, export_to_excel, export_to_csv

app = Flask(__name__)
app.config.from_object(Config)

# Initialize CSRF protection
csrf = CSRFProtect(app)

# MongoDB connection
client = MongoClient(app.config['MONGO_URI'])
db = client.festival_db

# Collections
users_collection = db.users
registrations_collection = db.registrations
segments_collection = db.segments
ca_collection = db.ca_registrations

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



def init_db():
    """Initialize database with sample data if empty"""
    if segments_collection.count_documents({}) == 0:
        sample_segments = [
            {
                'name': 'Robotics Competition',
                'price': 500,
                'type': 'Competition',
                'categories': ['P', 'S', 'HS', 'A'],
                'max_participants': 50,
                'current_participants': 0
            },
            {
                'name': 'Programming Contest',
                'price': 300,
                'type': 'Competition',
                'categories': ['S', 'HS', 'A'],
                'max_participants': 100,
                'current_participants': 0
            },
            {
                'name': 'Science Fair',
                'price': 200,
                'type': 'Exhibition',
                'categories': ['P', 'S'],
                'max_participants': 80,
                'current_participants': 0
            },
            {
                'name': 'Cultural Night',
                'price': 100,
                'type': 'Performance',
                'categories': ['HS', 'A'],
                'max_participants': 200,
                'current_participants': 0
            }
        ]
        segments_collection.insert_many(sample_segments)
    
    # Create admin user if not exists
    if users_collection.count_documents({'role': 'admin'}) == 0:
        admin_user = {
            'email': 'admin@festival.com',
            'password': hash_password('admin123'),
            'full_name': 'System Administrator',
            'role': 'admin',
            'created_at': datetime.utcnow()
        }
        users_collection.insert_one(admin_user)

    db.ca_registrations.create_index([('email', 1)], unique=False)
    db.ca_registrations.create_index([('ca_code', 1)], unique=True)

def admin_required(f):
    """Decorator to require admin authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = session.get('admin_token')
        
        if not token:
            return redirect(url_for('admin_login'))
        
        try:
            payload = jwt.decode(token, app.config['JWT_SECRET_KEY'], algorithms=['HS256'])
            if payload['role'] != 'admin':
                flash('Admin access required', 'error')
                return redirect(url_for('admin_login'))
        except jwt.ExpiredSignatureError:
            flash('Session expired. Please login again.', 'error')
            return redirect(url_for('admin_login'))
        except jwt.InvalidTokenError:
            flash('Invalid token. Please login again.', 'error')
            return redirect(url_for('admin_login'))
        
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    """Home page"""
    segments = list(segments_collection.find({}, {'_id': 1, 'name': 1, 'price': 1, 'type': 1}))
    return render_template('index.html', segments=segments)

@app.route('/ca-register', methods=['GET', 'POST'])
def ca_register():
    """CA Registration page"""
    form = CARegistrationForm()
    
    if form.validate_on_submit():
        # Check if email already registered as CA
        existing_ca = db.ca_registrations.find_one({'email': form.email.data})
        if existing_ca:
            flash('This email is already registered as a CA', 'error')
            return redirect(url_for('ca_register'))
        
        # Generate CA code
        ca_code = generate_ca_code(form.full_name.data)
        
        # Handle profile picture upload
        profile_pic_filename = None
        if form.profile_picture.data:
            file = form.profile_picture.data
            filename = secure_filename(file.filename)
            # Create unique filename with CA code
            file_ext = os.path.splitext(filename)[1]
            profile_pic_filename = f"ca_{ca_code}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}{file_ext}"
            
            # Save file (in production, use cloud storage)
            upload_folder = os.path.join(app.root_path, 'static', 'uploads', 'ca_profiles')
            os.makedirs(upload_folder, exist_ok=True)
            file_path = os.path.join(upload_folder, profile_pic_filename)
            file.save(file_path)
        
        # Create CA registration
        ca_data = {
            'full_name': form.full_name.data,
            'institution': form.institution.data,
            'class': form.class_info.data,
            'phone': form.phone.data,
            'email': form.email.data,
            'why_ca': form.why_ca.data,
            'profile_picture': profile_pic_filename,
            'ca_code': ca_code,
            'status': 'pending',  # pending, approved, rejected
            'registration_date': datetime.utcnow(),
            'ip_address': request.remote_addr,
            'user_agent': request.user_agent.string
        }
        
        # Insert into database
        result = db.ca_registrations.insert_one(ca_data)
        
        # Store in session for auto-fill
        session['last_ca_registration'] = {
            'full_name': form.full_name.data,
            'email': form.email.data,
            'phone': form.phone.data,
            'institution': form.institution.data
        }
        
        return redirect(url_for('ca_registration_success', ca_id=str(result.inserted_id)))
    
    # Pre-fill form with session data if available
    if 'last_ca_registration' in session:
        form.full_name.data = session['last_ca_registration']['full_name']
        form.email.data = session['last_ca_registration']['email']
        form.phone.data = session['last_ca_registration']['phone']
        form.institution.data = session['last_ca_registration']['institution']
    
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
def register():
    """Registration form for participants"""
    form = RegistrationForm()
    
    # Get segments for dropdown
    segments = list(segments_collection.find({}, {'_id': 1, 'name': 1, 'price': 1, 'categories': 1}))
    form.segment.choices = [(str(seg['_id']), f"{seg['name']} - ${seg['price']}") for seg in segments]
    
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
        
        # Check for duplicate registration (same email for same segment)
        existing = registrations_collection.find_one({
            'email': form.email.data,
            'segment_id': ObjectId(form.segment.data),
            'verified': True
        })
        
        if existing:
            flash('You have already registered for this segment', 'error')
            return redirect(url_for('register'))
        
        # Create registration
        registration_data = {
            'full_name': form.full_name.data,
            'email': form.email.data,
            'institution': form.institution.data,
            'segment_id': ObjectId(form.segment.data),
            'segment_name': segment['name'],
            'category': form.category.data,
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
        
        # Store in session for auto-fill
        session['last_registration'] = {
            'full_name': form.full_name.data,
            'email': form.email.data
        }
        
        return redirect(url_for('registration_success', registration_id=str(result.inserted_id)))
    
    # Pre-fill form with session data if available
    if 'last_registration' in session:
        form.full_name.data = session['last_registration']['full_name']
        form.email.data = session['last_registration']['email']
    
    return render_template('register.html', form=form, segments=segments)

@app.route('/registration-success/<registration_id>')
def registration_success(registration_id):
    """Success page after registration"""
    registration = registrations_collection.find_one({'_id': ObjectId(registration_id)})
    if not registration:
        flash('Registration not found', 'error')
        return redirect(url_for('index'))
    
    return render_template('success.html', registration=registration)


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


# ========== ADMIN ROUTES ==========

# Add CA management to admin dashboard
@app.route('/admin/ca-registrations')
@admin_required
def admin_ca_registrations():
    """View and manage CA registrations"""
    status_filter = request.args.get('status', 'all')
    
    query = {}
    if status_filter != 'all':
        query['status'] = status_filter
    
    ca_registrations = list(db.ca_registrations.find(query).sort('registration_date', -1))
    
    return render_template('admin/ca_registrations.html',
                         ca_registrations=ca_registrations,
                         status_filter=status_filter)

@app.route('/admin/update-ca-status/<ca_id>', methods=['POST'])
@admin_required
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


@app.route('/api/ca-details/<ca_id>')
@admin_required
def api_ca_details(ca_id):
    """API endpoint to get CA details"""
    try:
        ca = db.ca_registrations.find_one({'_id': ObjectId(ca_id)})
        if ca:
            # Convert ObjectId to string for JSON serialization
            ca['_id'] = str(ca['_id'])
            return jsonify({'success': True, 'ca': ca})
        return jsonify({'success': False, 'message': 'CA not found'}), 404
    except:
        return jsonify({'success': False, 'message': 'Invalid CA ID'}), 400


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

# Add bulk update endpoint
@app.route('/admin/update-message-status/bulk', methods=['POST'])
@admin_required
def bulk_update_message_status():
    """Bulk update message status"""
    status = request.json.get('status')
    message_ids = request.json.get('message_ids', [])
    
    if not message_ids or status not in ['unread', 'read', 'replied']:
        return jsonify({'success': False, 'message': 'Invalid request'}), 400
    
    try:
        object_ids = [ObjectId(msg_id) for msg_id in message_ids]
        
        result = db.contact_messages.update_many(
            {'_id': {'$in': object_ids}},
            {'$set': {'status': status}}
        )
        
        return jsonify({'success': True, 'modified': result.modified_count})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500



@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Admin login page"""
    if 'admin_token' in session:
        return redirect(url_for('admin_dashboard'))
    
    form = AdminLoginForm()
    
    if form.validate_on_submit():
        admin_user = users_collection.find_one({'email': form.email.data, 'role': 'admin'})
        
        if admin_user and verify_password(admin_user['password'], form.password.data):
            # Generate JWT token
            token_payload = {
                'email': admin_user['email'],
                'role': 'admin',
                'exp': datetime.utcnow() + app.config['JWT_ACCESS_TOKEN_EXPIRES']
            }
            token = jwt.encode(token_payload, app.config['JWT_SECRET_KEY'], algorithm='HS256')
            
            session['admin_token'] = token
            flash('Logged in successfully', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid email or password', 'error')
    
    return render_template('admin/login.html', form=form)

@app.route('/admin/logout')
def admin_logout():
    """Admin logout"""
    session.pop('admin_token', None)
    flash('Logged out successfully', 'success')
    return redirect(url_for('admin_login'))

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    """Admin dashboard overview"""
    # Get statistics
    total_registrations = registrations_collection.count_documents({})
    verified_registrations = registrations_collection.count_documents({'verified': True})
    total_segments = segments_collection.count_documents({})
    
    # Get contact message statistics
    contact_messages_count = db.contact_messages.count_documents({'archived': False})
    unread_contact_messages = db.contact_messages.count_documents({
        'status': 'unread',
        'archived': False
    })
    
    # Get recent registrations
    recent_registrations = list(registrations_collection.find().sort('registration_date', -1).limit(10))
    
    # Get recent contact messages
    recent_messages = list(db.contact_messages.find({'archived': False})
                          .sort('submitted_at', -1).limit(5))
    
    # Get segment statistics
    segments = list(segments_collection.find({}))
    segments = json.loads(json_util.dumps(list(segments)))

    return render_template('admin/dashboard.html',
                         total_registrations=total_registrations,
                         verified_registrations=verified_registrations,
                         contact_messages_count=contact_messages_count,
                         unread_contact_messages=unread_contact_messages,
                         recent_registrations=recent_registrations,
                         recent_messages=recent_messages,
                         segments=segments)

@app.route('/admin/registrations')
@admin_required
def admin_registrations():
    """View and manage registrations"""
    segment_id = request.args.get('segment_id')
    verified_filter = request.args.get('verified')
    
    query = {}
    
    if segment_id:
        query['segment_id'] = ObjectId(segment_id)
    
    if verified_filter == 'true':
        query['verified'] = True
    elif verified_filter == 'false':
        query['verified'] = False
    
    registrations = list(registrations_collection.find(query).sort('registration_date', -1))
    segments = list(segments_collection.find({}))
    
    return render_template('admin/registrations.html',
                         registrations=registrations,
                         segments=segments,
                         segment_id=segment_id,
                         verified_filter=verified_filter)

@app.route('/admin/verify-registration/<registration_id>', methods=['POST'])
@admin_required
def verify_registration(registration_id):
    """Verify a single registration"""
    try:
        registrations_collection.update_one(
            {'_id': ObjectId(registration_id)},
            {'$set': {'verified': True, 'verified_at': datetime.utcnow()}}
        )
        
        # Get registration to send email
        registration = registrations_collection.find_one({'_id': ObjectId(registration_id)})
        if registration:
            send_verification_email(registration)
        
        return jsonify({'success': True})
    except:
        return jsonify({'success': False}), 500

@app.route('/admin/bulk-verify', methods=['POST'])
@admin_required
def bulk_verify():
    """Bulk verify registrations"""
    registration_ids = request.json.get('registration_ids', [])
    
    if not registration_ids:
        return jsonify({'success': False, 'message': 'No registrations selected'}), 400
    
    try:
        object_ids = [ObjectId(rid) for rid in registration_ids]
        
        # Update all selected registrations
        result = registrations_collection.update_many(
            {'_id': {'$in': object_ids}},
            {'$set': {'verified': True, 'verified_at': datetime.utcnow()}}
        )
        
        # Send emails to verified registrations
        verified_registrations = list(registrations_collection.find({'_id': {'$in': object_ids}}))
        send_bulk_emails(verified_registrations)
        
        return jsonify({'success': True, 'verified_count': result.modified_count})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/admin/contact-messages')
@admin_required
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

@app.route('/admin/update-message-status/<message_id>', methods=['POST'])
@admin_required
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

@app.route('/admin/delete-message/<message_id>', methods=['DELETE'])
@admin_required
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

# Add to init_db function
def init_db():
    """Initialize database with sample data if empty"""
    # ... existing init_db code ...
    
    # Ensure contact messages collection has indexes
    db.contact_messages.create_index([('email', 1)])
    db.contact_messages.create_index([('submitted_at', -1)])
    db.contact_messages.create_index([('status', 1)])
    db.contact_messages.create_index([('archived', 1)])


@app.route('/admin/analytics')
@admin_required
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
    daily_stats = list(registrations_collection.aggregate(pipeline))
    
    # Category distribution
    category_pipeline = [
        {'$group': {'_id': '$category', 'count': {'$sum': 1}}},
        {'$sort': {'count': -1}}
    ]
    category_stats = list(registrations_collection.aggregate(category_pipeline))
    
    # Segment distribution
    segment_pipeline = [
        {'$group': {'_id': '$segment_name', 'count': {'$sum': 1}}},
        {'$sort': {'count': -1}}
    ]
    segment_stats = list(registrations_collection.aggregate(segment_pipeline))

    ca_pipeline = [
        {'$group': {'_id': '$ca_ref', 'count': {'$sum': 1}}},
        {'$sort': {'count': -1}}
    ]
    ca_stats = list(registrations_collection.aggregate(ca_pipeline))
    
    return render_template('admin/analytics.html',
                         daily_stats=daily_stats,
                         category_stats=category_stats,
                         segment_stats=segment_stats,
                         ca_stats=ca_stats)

@app.route('/admin/email', methods=['GET', 'POST'])
@admin_required
def admin_email():
    """Email management page"""
    form = EmailForm()
    
    if form.validate_on_submit():
        query = {}
        
        if form.segment.data:
            query['segment_id'] = ObjectId(form.segment.data)
        
        if form.category.data:
            query['category'] = form.category.data
        
        if form.verified_only.data:
            query['verified'] = True
        
        recipients = list(registrations_collection.find(query, {'email': 1, 'full_name': 1}))
        
        # Send email
        email_list = [r['email'] for r in recipients]
        success = send_bulk_emails(recipients, form.subject.data, form.message.data)
        
        if success:
            flash(f'Email sent to {len(email_list)} recipients', 'success')
        else:
            flash('Failed to send email', 'error')
        
        return redirect(url_for('admin_email'))
    
    segments = list(segments_collection.find({}))
    
    return render_template('admin/email.html', form=form, segments=segments)

@app.route('/admin/export')
@admin_required
def admin_export():
    segments = list(segments_collection.find({}))
    return render_template(
        'admin/export.html',
        segments=segments
    )

@app.route('/admin/reg-export')
@admin_required
def admin_reg_export():
    format_type = request.args.get('format', 'csv')
    verified = request.args.get('verified')  # "true", "false", or None
    segment_id = request.args.get('segment_id')

    query = {}

    if segment_id:
        query['segment_id'] = ObjectId(segment_id)

    if verified in ('true', 'false'):
        query['verified'] = True if verified == 'true' else False

    registrations = list(registrations_collection.find(query))

    if format_type == 'csv':
        return export_to_csv(registrations)
    else:
        return export_to_excel(registrations)


@app.route('/admin/ca-export')
@admin_required
def admin_ca_export():
    """Export data page"""
    format_type = request.args.get('format', 'csv')
    status = request.args.get('status')
    
    query = {}
    if status:
        query['status'] = status
    
    ca_data = list(ca_collection.find(query))

    if format_type == 'csv':
        csv_data = export_ca_to_csv(ca_data)
        return csv_data
    else:
        excel_data = export_to_excel(ca_data)
        return excel_data

@app.errorhandler(404)
def page_not_found(e):
    return render_template('errors/404.html'), 404

if __name__ == '__main__':
    # with app.app_context():
    #     init_db()
    app.run(debug=True, port=5000)