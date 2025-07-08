# backend/database.py
#from sqlalchemy import create_engine
#from sqlalchemy.orm import sessionmaker

# Set your own credentials here
#DATABASE_URL = "mysql+mysqlconnector://root:<MONA2003>@localhost/hospital_equipment"
#DATABASE_URL="sqlite:///./expense.db"

# Create engine
#engine = create_engine(DATABASE_URL)

# Create session factory
#SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Dependency to get DB session
#def get_db():
#    db = SessionLocal()
#    try:
#        yield db
#    finally:
#        db.close()

# backend/database.py: 
#from sqlalchemy import create_engine
#from sqlalchemy.orm import sessionmaker, declarative_base

# Replace with your MySQL user/pass/db
#DB_USER = "root"
#DB_PASSWORD = "MONA2003"
#DB_HOST = "localhost"
#DB_PORT = "3306"
#DB_NAME = "hospital_maintenance"

#SQLALCHEMY_DATABASE_URL = f"mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

#engine = create_engine(SQLALCHEMY_DATABASE_URL)
#SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

#Base = declarative_base()


# backend/database.py

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# SQLite DB path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SQLITE_PATH = os.path.join(BASE_DIR, '..', 'db', 'healthcare.db')
SQLALCHEMY_DATABASE_URL = f"sqlite:///{SQLITE_PATH}"

# SQLAlchemy setup
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
