# database/seed_data.py

import sqlite3
import pandas as pd
import os

# Move up one level from /database to /project-root
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# Then go into backend/
BACKEND_DIR = os.path.join(PROJECT_ROOT, 'backend')
DB_DIR = os.path.join(BACKEND_DIR, 'db')
DATA_DIR = os.path.join(BACKEND_DIR, 'data')
DB_PATH = os.path.join(DB_DIR, 'healthcare.db')

# Ensure db folder exists
os.makedirs(DB_DIR, exist_ok=True)

# Connect to SQLite
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# CSV-to-table mapping
csv_table_map = {
    "equipment_metadata.csv": "equipment_metadata",
    "personnel_operators.csv": "personnel_operators",
    "equipment_assignments.csv": "equipment_assignments",
    "failure_labels.csv": "failure_labels",
    "maintenance_logs.csv": "maintenance_logs",
    "usage_logs.csv": "usage_logs"
}

# Load and insert
for file, table in csv_table_map.items():
    file_path = os.path.join(DATA_DIR, file)
    if os.path.exists(file_path):
        print(f"Inserting data into: {table}")
        df = pd.read_csv(file_path)
        df.to_sql(table, conn, if_exists='append', index=False)
    else:
        print(f"⚠️ File not found: {file_path}")

conn.commit()
conn.close()
print("✅ Database seeding completed.")
