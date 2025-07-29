#backend/predict.py
from fastapi import APIRouter, Depends
from fastapi_app.dependencies import get_current_user
import numpy as np
import pandas as pd
import sqlite3
import joblib
from tensorflow.keras.models import load_model
import os
from datetime import datetime, timedelta

router = APIRouter()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
lstm_model = load_model(os.path.join(BASE_DIR, "..", "saved_models", "lstm_model.h5"))
lgbm_model = joblib.load(os.path.join(BASE_DIR, "..", "saved_models", "lgbm_model.pkl"))
scaler = joblib.load(os.path.join(BASE_DIR, "..", "saved_models", "scaler.pkl"))

def should_skip_prediction_update(equipment_id, cursor):
    """
    Check if equipment had recent maintenance completion and should not be overridden
    """
    # Check if maintenance was completed in the last 24 hours
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    cursor.execute("""
        SELECT maintenance_id FROM maintenance_logs 
        WHERE equipment_id = ? 
        AND status = 'Completed' 
        AND (completion_status = 'Confirmed' OR completion_status = 'Approved')
        AND date >= ?
        ORDER BY date DESC 
        LIMIT 1
    """, (equipment_id, yesterday))
    
    recent_maintenance = cursor.fetchone()
    
    if recent_maintenance:
        print(f"Skipping prediction update for {equipment_id} - recent maintenance completed")
        return True
    
    # Also check if the failure_predictions table was manually reset recently
    cursor.execute("""
        SELECT prediction_date, failure_probability FROM failure_predictions 
        WHERE equipment_id = ? 
        AND failure_probability = 0.1 
        AND needs_maintenance_10_days = 0
        ORDER BY prediction_date DESC 
        LIMIT 1
    """, (equipment_id,))
    
    recent_reset = cursor.fetchone()
    if recent_reset:
        reset_date = datetime.strptime(recent_reset[0], '%Y-%m-%d')
        if (datetime.now() - reset_date).days < 1:  # Reset within last 24 hours
            print(f"Skipping prediction update for {equipment_id} - recently reset after maintenance")
            return True
    
    return False

@router.post("/", summary="Predict maintenance for all equipment")
def predict_maintenance(user=Depends(get_current_user)):
    conn = sqlite3.connect("hospital_equipment_system.db")
    cursor = conn.cursor()

    # Create table if it doesn't exist
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS failure_predictions (
        prediction_id INTEGER PRIMARY KEY AUTOINCREMENT,
        equipment_id TEXT,
        prediction_date TEXT,
        needs_maintenance_10_days INTEGER,
        failure_probability REAL
    )
    """)

    query = """
    SELECT equipment_id, timestamp, usage_hours, patients_served, workload_level, avg_cpu_temp, error_count
    FROM usage_logs
    ORDER BY equipment_id, timestamp DESC
    """
    df = pd.read_sql_query(query, conn)
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

    today = pd.Timestamp.today().strftime('%Y-%m-%d')
    results = []
    skipped_count = 0

    for eid, pred, prob in zip(equipment_map, ensemble_preds, ensemble_probs):
        # Check if we should skip updating this equipment's prediction
        if should_skip_prediction_update(eid, cursor):
            skipped_count += 1
            # Get current values for reporting
            cursor.execute("""
                SELECT needs_maintenance_10_days, failure_probability 
                FROM failure_predictions 
                WHERE equipment_id = ?
            """, (eid,))
            current = cursor.fetchone()
            if current:
                results.append({
                    "equipment_id": eid,
                    "maintenance_needed": current[0],
                    "confidence_score": round(float(current[1]), 4),
                    "status": "preserved_post_maintenance"
                })
            continue
        
        # Delete existing prediction for the equipment if any (overwrite behavior)
        cursor.execute("DELETE FROM failure_predictions WHERE equipment_id = ?", (eid,))
        
        # Insert new prediction
        cursor.execute("""
            INSERT INTO failure_predictions (equipment_id, prediction_date, needs_maintenance_10_days, failure_probability)
            VALUES (?, ?, ?, ?)
        """, (eid, today, int(pred), float(round(prob, 4))))

        results.append({
            "equipment_id": eid,
            "maintenance_needed": int(pred),
            "confidence_score": round(float(prob), 4),
            "status": "updated"
        })

    conn.commit()
    conn.close()
    
    return {
        "predictions": results,
        "summary": {
            "total_equipment": len(equipment_map),
            "updated": len(equipment_map) - skipped_count,
            "preserved_post_maintenance": skipped_count
        }
    }

@router.post("/force-update", summary="Force predict maintenance for all equipment (override post-maintenance resets)")
def force_predict_maintenance(user=Depends(get_current_user)):
    """
    Force update all predictions, ignoring recent maintenance completions.
    Use this only when you want to override post-maintenance resets.
    """
    conn = sqlite3.connect("hospital_equipment_system.db")
    cursor = conn.cursor()

    # Create table if it doesn't exist
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS failure_predictions (
        prediction_id INTEGER PRIMARY KEY AUTOINCREMENT,
        equipment_id TEXT,
        prediction_date TEXT,
        needs_maintenance_10_days INTEGER,
        failure_probability REAL
    )
    """)

    query = """
    SELECT equipment_id, timestamp, usage_hours, patients_served, workload_level, avg_cpu_temp, error_count
    FROM usage_logs
    ORDER BY equipment_id, timestamp DESC
    """
    df = pd.read_sql_query(query, conn)
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

    today = pd.Timestamp.today().strftime('%Y-%m-%d')
    results = []

    for eid, pred, prob in zip(equipment_map, ensemble_preds, ensemble_probs):
        # Force delete and insert (original behavior)
        cursor.execute("DELETE FROM failure_predictions WHERE equipment_id = ?", (eid,))
        
        cursor.execute("""
            INSERT INTO failure_predictions (equipment_id, prediction_date, needs_maintenance_10_days, failure_probability)
            VALUES (?, ?, ?, ?)
        """, (eid, today, int(pred), float(round(prob, 4))))

        results.append({
            "equipment_id": eid,
            "maintenance_needed": int(pred),
            "confidence_score": round(float(prob), 4)
        })

    conn.commit()
    conn.close()
    return {"predictions": results, "note": "All predictions force updated, overriding post-maintenance resets"}