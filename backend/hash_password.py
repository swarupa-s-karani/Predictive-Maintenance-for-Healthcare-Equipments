# backend/hash_password.py
from passlib.context import CryptContext
import sqlite3
from database import get_db

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

conn = get_db()
cursor = conn.cursor()
cursor.execute("SELECT username, password FROM personnel")
rows = cursor.fetchall()

for username, password in rows:
    hashed = pwd_context.hash(password)
    cursor.execute("UPDATE personnel SET password = ? WHERE username = ?", (hashed, username))

conn.commit()
conn.close()
print("All passwords hashed with bcrypt.")
