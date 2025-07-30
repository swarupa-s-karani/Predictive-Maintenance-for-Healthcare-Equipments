# backend/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from passlib.context import CryptContext
from jose import jwt
from datetime import datetime, timedelta
import sqlite3
from database import get_db
import os

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
router = APIRouter()

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

@router.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    conn = get_db()  # Use the shared function
    cursor = conn.cursor()
    
    # Also update the SELECT query to include personnel_id
    cursor.execute("""
        SELECT personnel_id, username, password, role 
        FROM personnel WHERE username = ?
    """, (form_data.username,))
    user = cursor.fetchone()
    conn.close()

    if not user or not verify_password(form_data.password, user[2]):  # password is now index 2
        raise HTTPException(status_code=401, detail="Invalid username or password")

    personnel_id = user[0]  # personnel_id
    username = user[1]      # username  
    role = user[3].lower().replace(" ", "")  # role is now index 3

    token = create_access_token({
        "sub": username, 
        "role": role,
        "personnel_id": personnel_id  # Add this to token
    })

    return {
        "access_token": token,
        "token_type": "bearer",
        "role": role,
        "personnel_id": personnel_id  # Return this to frontend
    }
