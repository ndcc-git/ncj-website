import firebase_admin
from firebase_admin import auth
from firebase_admin import exceptions as firebase_exceptions
import requests
import json
from flask import current_app
import os

def firebase_create_user(email, password, display_name=None):
    """Create a new user in Firebase Authentication"""
    try:
        user = auth.create_user(
            email=email,
            password=password,
            display_name=display_name,
            email_verified=False
        )
        return user
    except firebase_exceptions.FirebaseError as e:
        error_message = str(e)
        if 'EMAIL_EXISTS' in error_message:
            raise Exception('Email already registered')
        elif 'WEAK_PASSWORD' in error_message:
            raise Exception('Password is too weak')
        else:
            raise Exception(f'Firebase error: {error_message}')
    except Exception as e:
        raise Exception(f'Error creating user: {str(e)}')

def firebase_login_user(email, password):
    """Login user with email and password using Firebase REST API"""
    # Firebase REST API endpoint for email/password authentication
    api_key = os.environ.get('FIREBASE_API_KEY')
    
    if not api_key:
        raise Exception('Firebase API key not configured')
    
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}"
    
    payload = {
        "email": email,
        "password": password,
        "returnSecureToken": True
    }
    
    try:
        response = requests.post(url, json=payload)
        data = response.json()
        
        if response.status_code == 200:
            return data
        else:
            error_message = data.get('error', {}).get('message', 'Login failed')
            if 'INVALID_LOGIN_CREDENTIALS' in error_message:
                raise Exception('Invalid email or password')
            elif 'USER_DISABLED' in error_message:
                raise Exception('Account has been disabled')
            elif 'TOO_MANY_ATTEMPTS_TRY_LATER' in error_message:
                raise Exception('Too many attempts. Try again later')
            else:
                raise Exception(f'Login failed: {error_message}')
    except Exception as e:
        raise Exception(f'Network error: {str(e)}')

def firebase_send_password_reset(email):
    """Send password reset email"""
    try:
        link = auth.generate_password_reset_link(email)
        
        # You can customize the email template in Firebase Console
        # For now, we'll return the reset link
        return link
    except firebase_exceptions.FirebaseError as e:
        error_message = str(e)
        if 'USER_NOT_FOUND' in error_message:
            raise Exception('No account found with this email')
        else:
            raise Exception(f'Error sending reset email: {error_message}')

def firebase_verify_token(id_token):
    """Verify Firebase ID token"""
    try:
        decoded_token = auth.verify_id_token(id_token)
        return decoded_token
    except firebase_exceptions.FirebaseError:
        return None

def firebase_update_user(uid, display_name=None, email=None, phone_number=None):
    """Update Firebase user profile"""
    try:
        update_params = {}
        if display_name:
            update_params['display_name'] = display_name
        if email:
            update_params['email'] = email
        if phone_number:
            update_params['phone_number'] = phone_number
        
        if update_params:
            user = auth.update_user(uid, **update_params)
            return user
        return None
    except firebase_exceptions.FirebaseError as e:
        raise Exception(f'Error updating user: {str(e)}')

def firebase_change_password(uid, new_password):
    """Change user password in Firebase"""
    try:
        user = auth.update_user(uid, password=new_password)
        return user
    except firebase_exceptions.FirebaseError as e:
        error_message = str(e)
        if 'WEAK_PASSWORD' in error_message:
            raise Exception('Password is too weak')
        else:
            raise Exception(f'Error changing password: {error_message}')

def firebase_delete_user(uid):
    """Delete user from Firebase Authentication"""
    try:
        auth.delete_user(uid)
        return True
    except firebase_exceptions.FirebaseError as e:
        raise Exception(f'Error deleting user: {str(e)}')

def firebase_get_user(uid):
    """Get user information from Firebase"""
    try:
        user = auth.get_user(uid)
        return user
    except firebase_exceptions.FirebaseError:
        return None

def firebase_send_email_verification(id_token):
    """Send email verification using Firebase REST API"""
    api_key = os.environ.get('FIREBASE_API_KEY')
    
    if not api_key:
        raise Exception('Firebase API key not configured')
    
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key={api_key}"
    
    payload = {
        "requestType": "VERIFY_EMAIL",
        "idToken": id_token
    }
    
    try:
        response = requests.post(url, json=payload)
        data = response.json()
        
        if response.status_code == 200:
            return data
        else:
            error_message = data.get('error', {}).get('message', 'Failed to send verification email')
            raise Exception(f'Failed to send verification email: {error_message}')
    except Exception as e:
        raise Exception(f'Network error: {str(e)}')
    

def refresh_firebase_token(refresh_token):
    """Refresh Firebase ID token"""
    api_key = os.environ.get('FIREBASE_API_KEY')
    
    if not api_key:
        return None
    
    url = f"https://securetoken.googleapis.com/v1/token?key={api_key}"
    
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token
    }
    
    try:
        response = requests.post(url, json=payload)
        data = response.json()
        
        if response.status_code == 200:
            return {
                'id_token': data.get('id_token'),
                'refresh_token': data.get('refresh_token'),
                'expires_in': data.get('expires_in')
            }
        else:
            return None
    except:
        return None
    
def firebase_get_user_info(id_token):
    """Get user information from Firebase using ID token"""
    api_key = os.environ.get('FIREBASE_API_KEY')
    
    if not api_key:
        raise Exception('Firebase API key not configured')
    
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:lookup?key={api_key}"
    
    payload = {
        "idToken": id_token
    }
    
    try:
        response = requests.post(url, json=payload)
        data = response.json()
        
        if response.status_code == 200:
            users = data.get('users', [])
            if users:
                return users[0]
        return None
    except Exception as e:
        raise Exception(f'Error getting user info: {str(e)}')