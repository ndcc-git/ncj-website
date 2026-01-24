import json
import os
import random
import string
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session, blueprints
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
from forms import RegistrationForm, AdminLoginForm, CARegistrationForm, ContactForm, AdminUserForm
from utils.security import hash_password, verify_password, generate_csrf_token, verify_csrf_token
from utils.email_service import send_verification_email, send_bulk_emails, send_ca_approval_email
from utils.export_service import export_ca_to_csv, export_to_excel, export_to_csv
import extensions

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
    db.contact_messages.create_index([('email', 1)])
    db.contact_messages.create_index([('submitted_at', -1)])
    db.contact_messages.create_index([('status', 1)])
    db.contact_messages.create_index([('archived', 1)])




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
    segments = list(segments_collection.find({}, {'_id': 1, 'name': 1, 'price': 1, 'categories': 1, 'type': 1}))
    form.segment.choices = [(str(seg['_id']), f"{seg['name']} - ${seg['price']}") for seg in segments]
    
    if form.validate_on_submit():
        # Generate CSRF token for this submission
        csrf_token = generate_csrf_token()
        
        # Fetch selected segment
        segment = segments_collection.find_one({'_id': ObjectId(form.segment.data)})
        if not segment:
            flash('Selected segment not found', 'error')
            return redirect(url_for('register'))
        
        # Check if segment has capacity
        if segment.get('current_participants', 0) >= segment.get('max_participants', float('inf')):
            flash('This segment is full', 'error')
            return redirect(url_for('register'))
        
        # Check for duplicate registration
        existing = registrations_collection.find_one({
            'email': form.email.data,
            'segment_id': ObjectId(form.segment.data),
            'verified': True
        })
        if existing:
            flash('You have already registered for this segment', 'error')
            return redirect(url_for('register'))
        
        # ✅ Conditional category validation
        if segment.get('categories') and not form.category.data:
            form.category.errors.append("Category is required for this segment.")
            return render_template('register.html', form=form, segments=segments)
        
        # ✅ Conditional submission link validation
        if segment.get('type') == "submission" and not form.submission_link.data:
            form.submission_link.errors.append("Submission link is required for this segment.")
            return render_template('register.html', form=form, segments=segments)
        
        # Create registration
        registration_data = {
            'full_name': form.full_name.data,
            'email': form.email.data,
            'institution': form.institution.data,
            'segment_id': ObjectId(form.segment.data),
            'segment_name': segment['name'],
            'category': form.category.data if segment.get('categories') else None,
            'submission_link': form.submission_link.data if segment.get('type') == "submission" else None,
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




@app.errorhandler(404)
def page_not_found(e):
    return render_template('errors/404.html'), 404

if __name__ == '__main__':
    # with app.app_context():
    #     init_db()
    app.run(debug=True, port=5000)