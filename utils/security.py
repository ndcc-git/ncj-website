import bcrypt
import secrets
import hashlib
from datetime import datetime

def hash_password(password):
    """Hash a password using bcrypt"""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_password(hashed_password, password):
    """Verify a password against its hash"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))

def generate_csrf_token():
    """Generate a CSRF token"""
    return secrets.token_hex(32)

def verify_csrf_token(token, stored_token):
    """Verify CSRF token"""
    return token == stored_token

def generate_session_token():
    """Generate a session token"""
    return secrets.token_urlsafe(32)

def hash_data(data):
    """Create a hash of data"""
    return hashlib.sha256(data.encode()).hexdigest()