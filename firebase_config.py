import firebase_admin
from firebase_admin import credentials, auth
import os

def initialize_firebase():
    """Initialize Firebase Admin SDK"""
    # Get the path to the service account key
    service_account_path = os.environ.get('FIREBASE_SERVICE_ACCOUNT_PATH')
    
    if service_account_path and os.path.exists(service_account_path):
        # Load from file
        cred = credentials.Certificate(service_account_path)
    else:
        # Try to load from environment variable (for platforms like Railway, Heroku)
        service_account_json = os.environ.get('FIREBASE_SERVICE_ACCOUNT_JSON')
        if service_account_json:
            import json
            service_account_info = json.loads(service_account_json)
            cred = credentials.Certificate(service_account_info)
        else:
            # For development only - create a dummy credential
            print("WARNING: Using default Firebase credentials for development")
            cred = credentials.ApplicationDefault()
    
    # Initialize Firebase app
    try:
        firebase_admin.get_app()
    except ValueError:
        firebase_admin.initialize_app(cred)
    
    return True