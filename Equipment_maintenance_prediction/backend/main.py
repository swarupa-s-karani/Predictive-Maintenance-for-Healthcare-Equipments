# backend/main.py
#from fastapi import FastAPI, UploadFile, File
#from fastapi.middleware.cors import CORSMiddleware
#from backend.predict import predict_equipment_maintenance
#from typing import Dict

#app = FastAPI(
#    title="Hospital Equipment Maintenance Predictor",
#    description="Predicts whether hospital equipment needs maintenance using ML models",
#    version="1.0.0"
#)

# Enable CORS (for React frontend)
#app.add_middleware(
#    CORSMiddleware,
#    allow_origins=["*"],  # Use specific origins in production
#    allow_credentials=True,
#    allow_methods=["*"],
#    allow_headers=["*"],
#)

#@app.get("/")
#def root():
#    return {"message": "Equipment Maintenance Prediction API is running."}

#@app.post("/predict")
#def predict(input_data: Dict):
#    prediction = predict_equipment_maintenance(input_data)
#    return prediction

# backend/main.py:
from fastapi import FastAPI, UploadFile, File, Depends
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict
from sqlalchemy.orm import Session

from backend.predict import predict_equipment_maintenance
from backend.database import SessionLocal

app = FastAPI(
    title="Hospital Equipment Maintenance Predictor",
    description="Predicts whether hospital equipment needs maintenance using ML models",
    version="1.0.0"
)

# Enable CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change to specific origin in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency for DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Default route
@app.get("/")
def root():
    return {"message": "Equipment Maintenance Prediction API is running."}

# Test DB connection
@app.get("/test-db")
def test_db_connection(db: Session = Depends(get_db)):
    return {"message": "Database connected!"}

# Prediction endpoint
@app.post("/predict")
def predict(input_data: Dict):
    prediction = predict_equipment_maintenance(input_data)
    return prediction

