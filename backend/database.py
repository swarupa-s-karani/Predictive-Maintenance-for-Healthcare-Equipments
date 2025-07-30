# backend/database.py
import sqlite3
import os

def get_db():
    """
    Get database connection that works both locally and on Render
    """
    # Try different possible locations for the database
    possible_paths = [
        # On Render, try the source directory first
        "/opt/render/project/src/hospital_equipment_system.db",
        # Current directory (where the Python files are)
        os.path.join(os.path.dirname(__file__), "hospital_equipment_system.db"),
        # Parent directory
        os.path.join(os.path.dirname(__file__), "..", "hospital_equipment_system.db"),
        # Root of project
        "hospital_equipment_system.db"
    ]
    
    db_path = None
    for path in possible_paths:
        if os.path.exists(path):
            db_path = path
            break
    
    # If no existing database found, create in current directory
    if db_path is None:
        db_path = "hospital_equipment_system.db"
    
    print(f"Using database path: {os.path.abspath(db_path)}")
    return sqlite3.connect(db_path)