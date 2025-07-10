#predict.py
from fastapi import APIRouter, Depends
from fastapi_app.dependencies import get_current_user
import numpy as np
import pandas as pd
import sqlite3
import joblib
from tensorflow.keras.models import load_model
import os

router = APIRouter()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
lstm_model = load_model(os.path.join(BASE_DIR, "..", "saved_models", "lstm_model.h5"))
lgbm_model = joblib.load(os.path.join(BASE_DIR, "..", "saved_models", "lgbm_model.pkl"))
scaler = joblib.load(os.path.join(BASE_DIR, "..", "saved_models", "scaler.pkl"))

@router.post("/", summary="Predict maintenance for all equipment")
def predict_maintenance(user=Depends(get_current_user)):
    conn = sqlite3.connect("hospital_equipment_system.db")
    query = """
    SELECT equipment_id, timestamp, usage_hours, patients_served, workload_level, avg_cpu_temp, error_count
    FROM usage_logs
    ORDER BY equipment_id, timestamp DESC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values(["equipment_id", "timestamp"], ascending=[True, False])
    features = ["usage_hours", "patients_served", "workload_level", "avg_cpu_temp", "error_count"]

    equipment_ids = df["equipment_id"].unique()
    sequences = []
    equipment_map = []

    for eq_id in equipment_ids:
        eq_data = df[df["equipment_id"] == eq_id]
        if len(eq_data) >= 5:
            recent_logs = eq_data.head(5).sort_values("timestamp")
            X_scaled = scaler.transform(recent_logs[features])
            sequences.append(X_scaled)
            equipment_map.append(eq_id)

    if not sequences:
        return {"message": "Not enough data for any equipment."}

    X_seq = np.array(sequences)
    X_flat = X_seq.reshape(X_seq.shape[0], -1)

    lstm_probs = lstm_model.predict(X_seq).flatten()
    lgbm_probs = lgbm_model.predict_proba(X_flat)[:, 1]
    ensemble_probs = (lstm_probs + lgbm_probs) / 2
    ensemble_preds = (ensemble_probs > 0.4).astype(int)

    results = []
    for eid, pred, prob in zip(equipment_map, ensemble_preds, ensemble_probs):
        results.append({
            "equipment_id": eid,
            "maintenance_needed": int(pred),
            "confidence_score": round(float(prob), 4)
        })

    return {"predictions": results}

