# utils/auth.py
import bcrypt
from typing import Optional
import streamlit as st
# Remove this line: from models import User

def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its hash"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def get_current_user() -> Optional[dict]:
    """Get current user from session state"""
    return st.session_state.get('user', None)

def is_authenticated() -> bool:
    """Check if user is authenticated"""
    return get_current_user() is not None

def login_user(user: dict):
    """Login user by storing in session state"""
    st.session_state['user'] = user

def logout_user():
    """Logout user by clearing session state"""
    if 'user' in st.session_state:
        del st.session_state['user']
    if 'current_ad' in st.session_state:
        del st.session_state['current_ad']