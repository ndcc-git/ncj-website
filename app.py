from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from flask_wtf.csrf import CSRFProtect
from pymongo import MongoClient
from datetime import datetime
import jwt
from functools import wraps
from bson.objectid import ObjectId
import pandas as pd
from io import BytesIO

from config import Config
from forms import RegistrationForm, AdminLoginForm, EmailForm
from utils.security import hash_password, verify_password, generate_csrf_token, verify_csrf_token
from utils.email_service import send_verification_email, send_bulk_emails
from utils.export_service import export_to_excel, export_to_csv

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
    
    # Get recent registrations
    recent_registrations = list(registrations_collection.find().sort('registration_date', -1).limit(10))
    
    # Get segment statistics
    segments = list(segments_collection.find({}))
    
    return render_template('admin/dashboard.html',
                         total_registrations=total_registrations,
                         verified_registrations=verified_registrations,
                         total_segments=total_segments,
                         recent_registrations=recent_registrations,
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
    """Export data page"""
    format_type = request.args.get('format', 'excel')
    segment_id = request.args.get('segment_id')
    
    query = {}
    if segment_id:
        query['segment_id'] = ObjectId(segment_id)
    
    registrations = list(registrations_collection.find(query))
    
    if format_type == 'csv':
        csv_data = export_to_csv(registrations)
        return csv_data
    else:
        excel_data = export_to_excel(registrations)
        return excel_data

@app.errorhandler(404)
def page_not_found(e):
    return render_template('errors/404.html'), 404

if __name__ == '__main__':
    # with app.app_context():
    #     init_db()
    app.run(debug=True, port=5000)