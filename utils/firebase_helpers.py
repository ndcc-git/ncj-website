import firebase_admin
from firebase_admin import auth
from firebase_admin import exceptions as firebase_exceptions
import requests
import json
from flask import current_app
import os
from .email_service import send_email

def firebase_create_user(email, password, display_name=None):
    """Create a new user in Firebase Authentication using REST API"""
    api_key = os.environ.get('FIREBASE_API_KEY')
    
    if not api_key:
        raise Exception('Firebase API key not configured')
    
    # Firebase REST API endpoint for signup
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={api_key}"
    
    payload = {
        "email": email,
        "password": password,
        "returnSecureToken": True
    }
    
    if display_name:
        payload["displayName"] = display_name
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        data = response.json()
        
        if response.status_code == 200:
            # Create a simple object with uid attribute
            class FirebaseUser:
                def __init__(self, data):
                    self.uid = data.get('localId')
                    self.email = data.get('email')
                    self.display_name = data.get('displayName')
                    self.id_token = data.get('idToken')
                    self.refresh_token = data.get('refreshToken')
                    
                def __getattr__(self, name):
                    return None
                    
            return FirebaseUser(data)
        else:
            error_message = data.get('error', {}).get('message', 'Unknown error')
            
            if 'EMAIL_EXISTS' in error_message:
                raise Exception('Email already registered')
            elif 'WEAK_PASSWORD' in error_message:
                raise Exception('Password is too weak (should be at least 6 characters)')
            elif 'INVALID_EMAIL' in error_message:
                raise Exception('Invalid email format')
            else:
                raise Exception(f'Firebase error: {error_message}')
                
    except requests.exceptions.Timeout:
        raise Exception('Connection timeout. Please try again.')
    except requests.exceptions.ConnectionError:
        raise Exception('Network error. Please check your connection.')
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
    """Send password reset email using Firebase REST API"""
    api_key = os.environ.get('FIREBASE_API_KEY')
    
    if not api_key:
        raise Exception('Firebase API key not configured')
    
    # Firebase REST API endpoint for password reset
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key={api_key}"
    
    payload = {
        "requestType": "PASSWORD_RESET",
        "email": email
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        data = response.json()
        
        if response.status_code == 200:
            # Firebase sends the email automatically
            # The response contains the email that was sent to
            email_sent_to = data.get('email')
            
            subject = "Password Reset Link for 10th NCJ"
            body = f"""

            We received a request to reset your password.

            A password reset email has been sent to {email_sent_to}. 
            Please check your inbox (and spam folder) for instructions.

            If you did not request this, please ignore this email.

            Regards,
            Notre Dame Cultural Club

            """
            
            # Send a confirmation email (optional - you can remove this if Firebase already sends one)
            send_email(email, subject=subject, body=body, is_html=False)
            
            return data.get('email')
        else:
            error_message = data.get('error', {}).get('message', 'Unknown error')
            
            if 'EMAIL_NOT_FOUND' in error_message:
                raise Exception('No account found with this email address')
            elif 'INVALID_EMAIL' in error_message:
                raise Exception('Invalid email format')
            else:
                raise Exception(f'Firebase error: {error_message}')
                
    except requests.exceptions.Timeout:
        raise Exception('Connection timeout. Please try again.')
    except requests.exceptions.ConnectionError:
        raise Exception('Network error. Please check your connection.')
    except Exception as e:
        raise Exception(f'Error sending password reset: {str(e)}')

def firebase_verify_token(id_token):
    """Verify Firebase ID token using REST API (no project ID required)"""
    if not id_token:
        return None
    
    api_key = os.environ.get('FIREBASE_API_KEY')
    
    if not api_key:
        print("FIREBASE_API_KEY not configured")
        return None
    
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:lookup?key={api_key}"
    
    payload = {
        "idToken": id_token
    }
    
    try:
        response = requests.post(url, json=payload, timeout=5)
        data = response.json()
        
        if response.status_code == 200:
            users = data.get('users', [])
            if users:
                return users[0]  # Return user info
        return None
    except Exception as e:
        print(f"Token verification error: {e}")
        return None

def firebase_update_user(uid, display_name=None, email=None, phone_number=None):
    """Update Firebase user profile using REST API"""
    api_key = os.environ.get('FIREBASE_API_KEY')
    id_token = None  # You'll need to pass this or get it from session
    
    # You need an ID token to update user profile via REST API
    # This function requires the user's current ID token
    if not id_token:
        raise Exception('User must be authenticated to update profile')
    
    if not api_key:
        raise Exception('Firebase API key not configured')
    
    # Firebase REST API endpoint for updating profile
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:update?key={api_key}"
    
    payload = {
        "idToken": id_token,
        "returnSecureToken": True
    }
    
    if display_name:
        payload["displayName"] = display_name
    
    if email:
        payload["email"] = email
    
    if phone_number:
        payload["phoneNumber"] = phone_number
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        data = response.json()
        
        if response.status_code == 200:
            # Create a user object to match Admin SDK style
            class FirebaseUser:
                def __init__(self, data):
                    self.uid = data.get('localId')
                    self.email = data.get('email')
                    self.display_name = data.get('displayName')
                    self.phone_number = data.get('phoneNumber')
                    self.id_token = data.get('idToken')
                    self.refresh_token = data.get('refreshToken')
                    
            return FirebaseUser(data)
        else:
            error_message = data.get('error', {}).get('message', 'Unknown error')
            raise Exception(f'Error updating user: {error_message}')
                
    except requests.exceptions.Timeout:
        raise Exception('Connection timeout. Please try again.')
    except requests.exceptions.ConnectionError:
        raise Exception('Network error. Please check your connection.')
    except Exception as e:
        raise Exception(f'Error updating user: {str(e)}')

def firebase_change_password(uid, new_password):
    """Change user password in Firebase using REST API"""
    from flask import session  # Import here to avoid circular imports
    
    api_key = os.environ.get('FIREBASE_API_KEY')
    id_token = session.get('firebase_token')  # Get token from session
    
    if not api_key:
        raise Exception('Firebase API key not configured')
    
    if not id_token:
        raise Exception('User must be authenticated to change password')
    
    # Firebase REST API endpoint for updating password
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:update?key={api_key}"
    
    payload = {
        "idToken": id_token,
        "password": new_password,
        "returnSecureToken": True
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        data = response.json()
        
        if response.status_code == 200:
            # Update session with new tokens
            session['firebase_token'] = data.get('idToken')
            if data.get('refreshToken'):
                session['refresh_token'] = data.get('refreshToken')
            
            # Return user info
            return {
                'uid': data.get('localId'),
                'email': data.get('email'),
                'display_name': data.get('displayName')
            }
        else:
            error_message = data.get('error', {}).get('message', 'Unknown error')
            
            if 'WEAK_PASSWORD' in error_message:
                raise Exception('Password is too weak (should be at least 6 characters)')
            else:
                raise Exception(f'Error changing password: {error_message}')
                
    except requests.exceptions.Timeout:
        raise Exception('Connection timeout. Please try again.')
    except requests.exceptions.ConnectionError:
        raise Exception('Network error. Please check your connection.')
    except Exception as e:
        raise Exception(f'Error changing password: {str(e)}')

def firebase_delete_user(uid):
    """Delete user from Firebase Authentication using REST API"""
    from flask import session  # Import here to avoid circular imports
    
    api_key = os.environ.get('FIREBASE_API_KEY')
    id_token = session.get('firebase_token')  # Get token from session
    
    if not api_key:
        raise Exception('Firebase API key not configured')
    
    if not id_token:
        raise Exception('User must be authenticated to delete account')
    
    # Firebase REST API endpoint for deleting account
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:delete?key={api_key}"
    
    payload = {
        "idToken": id_token
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        data = response.json()
        
        if response.status_code == 200:
            # Clear session
            session.clear()
            return True
        else:
            error_message = data.get('error', {}).get('message', 'Unknown error')
            
            if 'INVALID_ID_TOKEN' in error_message:
                raise Exception('Session expired. Please login again.')
            elif 'USER_NOT_FOUND' in error_message:
                raise Exception('User not found')
            else:
                raise Exception(f'Error deleting user: {error_message}')
                
    except requests.exceptions.Timeout:
        raise Exception('Connection timeout. Please try again.')
    except requests.exceptions.ConnectionError:
        raise Exception('Network error. Please check your connection.')
    except Exception as e:
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