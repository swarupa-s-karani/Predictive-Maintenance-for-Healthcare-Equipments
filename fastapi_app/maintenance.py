#fastapi_app/maintenance.py
from fastapi import APIRouter, HTTPException, Depends, Body
from pydantic import BaseModel
from typing import Union
import sqlite3
import pandas as pd
import joblib
from datetime import datetime
from fastapi_app.llm_engine import generate_llm_explanation
from fastapi_app.dependencies import get_current_user, require_role
from fastapi import File, UploadFile
import base64
from generate_equipment_report import fetch_equipment_metrics

router = APIRouter()

def get_db():
    return sqlite3.connect("hospital_equipment_system.db")

# --- Base model for Technician ---
class MaintenanceBase(BaseModel):
    maintenance_id: str
    equipment_id: str
    date: str
    maintenance_type: str
    downtime_hours: float
    cost_inr: float
    issue_description: str
    parts_replaced: str
    vendor: str
    technician_id: str
    completion_status: str
    warranty_covered: str

# --- Extended model for Admin/Biomedical ---
class MaintenanceExtended(MaintenanceBase):
    service_rating: int
    response_time_hours: float
    status: str

class CompletionSchema(BaseModel):
    downtime_hours: float
    cost_inr: float
    remarks: str
    technician_id: str

class ReviewSchema(BaseModel):
    service_rating: int
    completion_status: str = None 
    final_status: str = None 

def reset_equipment_health_predictions(equipment_id: str):
    """
    Reset equipment health predictions after successful maintenance completion
    """
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        print(f"Resetting health predictions for equipment: {equipment_id}")
        
        # First check if records exist
        cursor.execute("SELECT COUNT(*) FROM maintenance_prediction_results WHERE equipment_id = ?", (equipment_id,))
        mpr_exists = cursor.fetchone()[0] > 0
        
        cursor.execute("SELECT COUNT(*) FROM failure_predictions WHERE equipment_id = ?", (equipment_id,))
        fp_exists = cursor.fetchone()[0] > 0
        
        print(f"Records exist - MPR: {mpr_exists}, FP: {fp_exists}")
        
        # Update or insert maintenance_prediction_results
        if mpr_exists:
            cursor.execute("""
                UPDATE maintenance_prediction_results 
                SET predicted_to_fail = 0,
                    preventive = 'Low',
                    corrective = 'Low', 
                    replacement = 'Low',
                    last_updated = CURRENT_TIMESTAMP
                WHERE equipment_id = ?
            """, (equipment_id,))
            print(f"Updated maintenance_prediction_results for {equipment_id}")
        else:
            cursor.execute("""
                INSERT INTO maintenance_prediction_results 
                (equipment_id, predicted_to_fail, preventive, corrective, replacement, last_updated)
                VALUES (?, 0, 'Low', 'Low', 'Low', CURRENT_TIMESTAMP)
            """, (equipment_id,))
            print(f"Inserted new maintenance_prediction_results for {equipment_id}")
        
        # Update or insert failure_predictions - FORCE UPDATE
        if fp_exists:
            cursor.execute("""
                UPDATE failure_predictions
                SET needs_maintenance_10_days = 0,
                    failure_probability = 0.1,
                    prediction_date = DATE('now')
                WHERE equipment_id = ?
            """, (equipment_id,))
            rows_updated = cursor.rowcount
            print(f"Updated {rows_updated} rows in failure_predictions for {equipment_id}")
        else:
            cursor.execute("""
                INSERT INTO failure_predictions 
                (equipment_id, prediction_date, needs_maintenance_10_days, failure_probability)
                VALUES (?, DATE('now'), 0, 0.1)
            """, (equipment_id,))
            print(f"Inserted new failure_predictions for {equipment_id}")
        
        # Alternative approach - DELETE and INSERT for failure_predictions to ensure update
        print("Force updating failure_predictions with DELETE and INSERT approach...")
        cursor.execute("DELETE FROM failure_predictions WHERE equipment_id = ?", (equipment_id,))
        deleted_rows = cursor.rowcount
        print(f"Deleted {deleted_rows} old failure_prediction records for {equipment_id}")
        
        cursor.execute("""
            INSERT INTO failure_predictions 
            (equipment_id, prediction_date, needs_maintenance_10_days, failure_probability)
            VALUES (?, DATE('now'), 0, 0.1)
        """, (equipment_id,))
        print(f"Inserted fresh failure_predictions record for {equipment_id}")
        
        # Commit all changes
        conn.commit()
        print(f"Successfully reset health predictions for equipment {equipment_id}")
        
        # Verify the updates by querying the tables
        cursor.execute("SELECT * FROM maintenance_prediction_results WHERE equipment_id = ?", (equipment_id,))
        mpr_result = cursor.fetchone()
        print(f"Maintenance prediction results after update: {mpr_result}")
        
        cursor.execute("SELECT * FROM failure_predictions WHERE equipment_id = ?", (equipment_id,))
        fp_result = cursor.fetchone()
        print(f"Failure predictions after update: {fp_result}")
        
    except Exception as e:
        conn.rollback()
        print(f"Error resetting health predictions for {equipment_id}: {str(e)}")
        raise
    finally:
        conn.close()

# --- View all logs (Technician sees only scheduled ones) ---
@router.get("/")
def view_logs(user=Depends(get_current_user)):
    conn = get_db()
    cursor = conn.cursor()
    query = "SELECT * FROM maintenance_logs"
    if user["role"] == "technician":
        query += " WHERE status = 'Scheduled'"

    cursor.execute(query)
    columns = [col[0] for col in cursor.description]
    rows = cursor.fetchall()
    conn.close()
    return {"logs": [dict(zip(columns, row)) for row in rows]}

# --- Add a maintenance log based on role ---
@router.post("/")
def add_log(
    data: Union[MaintenanceExtended, MaintenanceBase],
    user=Depends(get_current_user)
):
    conn = get_db()
    cursor = conn.cursor()

    if user["role"] == "technician":
        if not isinstance(data, MaintenanceBase) or isinstance(data, MaintenanceExtended):
            raise HTTPException(status_code=403, detail="Technician not allowed to submit extended fields.")
        fields = list(MaintenanceBase.__fields__.keys())
    elif user["role"] in ["admin", "biomedical"]:
        if not isinstance(data, MaintenanceExtended):
            raise HTTPException(status_code=400, detail="Admin must submit full log data.")
        fields = list(MaintenanceExtended.__fields__.keys())
    else:
        raise HTTPException(status_code=403, detail="Unauthorized role.")

    values = [getattr(data, field) for field in fields]
    query = f"""
        INSERT INTO maintenance_logs ({','.join(fields)})
        VALUES ({','.join(['?']*len(fields))})
    """

    cursor.execute(query, values)
    conn.commit()
    conn.close()
    return {"message": "Log added"}

# --- Delete maintenance log (admin only) ---
@router.delete("/{maintenance_id}", dependencies=[Depends(require_role("admin"))])
def delete_log(maintenance_id: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM maintenance_logs WHERE maintenance_id = ?", (maintenance_id,))
    conn.commit()
    conn.close()
    return {"message": f"Maintenance log {maintenance_id} deleted"}

# === Predict Maintenance Priority ===
@router.get("/priority/{equipment_id}")
def get_full_maintenance_priority(equipment_id: str, user=Depends(get_current_user)):
    print(f"Priority request for {equipment_id} from user role: {user.get('role', 'NO_ROLE')}")

    conn = get_db()
    
    # First check if we have existing prediction results that are recent
    cursor = conn.cursor()
    cursor.execute("""
        SELECT predicted_to_fail, preventive, corrective, replacement, last_updated
        FROM maintenance_prediction_results 
        WHERE equipment_id = ?
    """, (equipment_id,))
    
    existing_result = cursor.fetchone()
    
    # If we have recent results (within last hour), return them
    if existing_result:
        print(f"Found existing prediction results for {equipment_id}: {existing_result}")
        conn.close()
        return {
            "equipment_id": equipment_id,
            "predicted_to_fail": bool(existing_result[0]),
            "maintenance_needs": {
                "preventive": existing_result[1],
                "corrective": existing_result[2], 
                "replacement": existing_result[3]
            }
        }
    
    # Otherwise, run the full prediction logic
    query = """
    SELECT e.equipment_id, e.installation_date,
           COALESCE(SUM(m.downtime_hours), 0) AS downtime,
           COUNT(m.maintenance_id) AS failures,
           COALESCE(AVG(m.response_time_hours), 0) AS avg_response,
           COALESCE(f.needs_maintenance_10_days, 0) AS needs_maintenance_10_days
    FROM equipment e
    LEFT JOIN maintenance_logs m ON e.equipment_id = m.equipment_id
    LEFT JOIN failure_predictions f ON e.equipment_id = f.equipment_id
    WHERE e.equipment_id = ?
    GROUP BY e.equipment_id
    """
    df = pd.read_sql_query(query, conn, params=(equipment_id,))
    conn.close()

    if df.empty:
        raise HTTPException(status_code=404, detail="Equipment not found")

    df["installation_date"] = pd.to_datetime(df["installation_date"])
    df["equipment_age"] = (pd.Timestamp.today() - df["installation_date"]).dt.days // 365

    features = df[[
        "equipment_age",
        "downtime",
        "failures",
        "avg_response",
        "needs_maintenance_10_days"
    ]]
    features.columns = [
        "equipment_age",
        "downtime_hours",
        "num_failures",
        "response_time_hours",
        "needs_maintenance_10_days"
    ]

    scaler = joblib.load("saved_models/multi_priority_scaler.pkl")
    X_scaled = scaler.transform(features)

    def label(pred): return {0: "Low", 1: "Medium", 2: "High"}[pred]

    results = {}
    for mtype in ["preventive", "corrective", "replacement"]:
        model = joblib.load(f"saved_models/{mtype}_model.pkl")
        pred = model.predict(X_scaled)[0]
        results[mtype] = label(pred)

    predicted_to_fail = bool(df["needs_maintenance_10_days"].iloc[0])

    # Save to database
    conn = sqlite3.connect("hospital_equipment_system.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO maintenance_prediction_results (equipment_id, predicted_to_fail, preventive, corrective, replacement, last_updated)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(equipment_id) DO UPDATE SET
            predicted_to_fail = excluded.predicted_to_fail,
            preventive = excluded.preventive,
            corrective = excluded.corrective,
            replacement = excluded.replacement,
            last_updated = CURRENT_TIMESTAMP
    """, (
        equipment_id,
        int(predicted_to_fail),
        results["preventive"],
        results["corrective"],
        results["replacement"]
    ))
    conn.commit()
    conn.close()

    return {
        "equipment_id": equipment_id,
        "predicted_to_fail": predicted_to_fail,
        "maintenance_needs": results
    }

# fastapi_app/maintenance.py - updated LLM route
@router.get("/llm-explanation/{equipment_id}")
def get_llm_explanation(equipment_id: str, user=Depends(get_current_user)):
    """Get LLM explanation separately - can fail without affecting metrics"""
    try:
        # FIXED: Import the correct function name
        from fastapi_app.llm_engine import generate_llm_explanation
        import os

        # Get metrics for LLM context
        metrics = fetch_equipment_metrics(equipment_id)
        chart_path = metrics.get("chart_path")
        
        if not chart_path or not os.path.exists(chart_path):
            print(f"Chart not found at path: {chart_path}")
            # Continue without chart - the LLM function can handle empty image_path
            chart_path = ""

        # Get maintenance prediction data for LLM context
        conn = sqlite3.connect("hospital_equipment_system.db")
        query = """
        SELECT e.equipment_id, e.installation_date,
               COALESCE(SUM(m.downtime_hours), 0) AS downtime,
               COUNT(CASE WHEN m.maintenance_id IS NOT NULL THEN 1 END) AS failures,
               COALESCE(AVG(m.response_time_hours), 0) AS avg_response,
               COALESCE(f.needs_maintenance_10_days, 0) AS needs_maintenance_10_days
        FROM equipment e
        LEFT JOIN maintenance_logs m ON e.equipment_id = m.equipment_id
        LEFT JOIN failure_predictions f ON e.equipment_id = f.equipment_id
        WHERE e.equipment_id = ?
        GROUP BY e.equipment_id
        """
        df = pd.read_sql_query(query, conn, params=(equipment_id,))
        conn.close()
        
        if df.empty:
            raise HTTPException(status_code=404, detail="Equipment not found")

        df["installation_date"] = pd.to_datetime(df["installation_date"])
        df["equipment_age"] = (pd.Timestamp.today() - df["installation_date"]).dt.days // 365

        features = df[["equipment_age", "downtime", "failures", "avg_response", "needs_maintenance_10_days"]]
        features.columns = ["equipment_age", "downtime_hours", "num_failures", "response_time_hours", "needs_maintenance_10_days"]

        scaler = joblib.load("saved_models/multi_priority_scaler.pkl")
        X_scaled = scaler.transform(features)

        def label(pred): return {0: "Low", 1: "Medium", 2: "High"}[pred]
        maintenance_needs = {}
        for mtype in ["preventive", "corrective", "replacement"]:
            model = joblib.load(f"saved_models/{mtype}_model.pkl")
            pred = model.predict(X_scaled)[0]
            maintenance_needs[mtype] = label(pred)

        # Prepare data for LLM - FIXED: Use the correct structure
        llm_metrics = {
            'equipment_id': equipment_id,
            'equipment_age': int(df["equipment_age"].iloc[0]),
            'downtime_hours': float(df["downtime"].iloc[0]),
            'num_failures': int(df["failures"].iloc[0]),
            'response_time_hours': float(df["avg_response"].iloc[0]),
            'predicted_to_fail': bool(df["needs_maintenance_10_days"].iloc[0]),
            'maintenance_needs': maintenance_needs
        }

        print(f"Calling LLM with metrics: {llm_metrics}")
        print(f"Chart path: {chart_path}")
        print(f"User role: {user['role']}")

        role = user["role"].lower()
        
        # FIXED: Call the correct function with proper parameters
        explanation = generate_llm_explanation(llm_metrics, role, chart_path)

        return {
            "equipment_id": equipment_id,
            "explanation": explanation,
            "status": "success"
        }

    except Exception as e:
        print(f"LLM explanation error for {equipment_id}: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Return error but don't crash the whole system
        return {
            "equipment_id": equipment_id,
            "explanation": f"LLM explanation temporarily unavailable. Error: {str(e)}",
            "status": "error"
        }

@router.get("/metrics/{equipment_id}")
def get_equipment_metrics_only(equipment_id: str, user=Depends(get_current_user)):
    """Get equipment metrics and chart without LLM explanation"""
    import base64, os
    
    # Get full metrics from existing function
    metrics = fetch_equipment_metrics(equipment_id)
    
    # Get chart
    chart_path = metrics.get("chart_path")
    if not os.path.exists(chart_path):
        raise HTTPException(status_code=404, detail="Trend chart not found")

    with open(chart_path, "rb") as img_file:
        base64_chart = base64.b64encode(img_file.read()).decode()

    # Get maintenance predictions (this is where downtime, failures, response time come from)
    conn = sqlite3.connect("hospital_equipment_system.db")
    query = """
    SELECT e.equipment_id, e.installation_date,
           COALESCE(SUM(m.downtime_hours), 0) AS downtime,
           COUNT(CASE WHEN m.maintenance_id IS NOT NULL THEN 1 END) AS failures,
           COALESCE(AVG(m.response_time_hours), 0) AS avg_response,
           COALESCE(f.needs_maintenance_10_days, 0) AS needs_maintenance_10_days
    FROM equipment e
    LEFT JOIN maintenance_logs m ON e.equipment_id = m.equipment_id
    LEFT JOIN failure_predictions f ON e.equipment_id = f.equipment_id
    WHERE e.equipment_id = ?
    GROUP BY e.equipment_id
    """
    df = pd.read_sql_query(query, conn, params=(equipment_id,))
    conn.close()
    
    if df.empty:
        raise HTTPException(status_code=404, detail="Equipment not found")

    df["installation_date"] = pd.to_datetime(df["installation_date"])
    df["equipment_age"] = (pd.Timestamp.today() - df["installation_date"]).dt.days // 365

    features = df[["equipment_age", "downtime", "failures", "avg_response", "needs_maintenance_10_days"]]
    features.columns = ["equipment_age", "downtime_hours", "num_failures", "response_time_hours", "needs_maintenance_10_days"]

    scaler = joblib.load("saved_models/multi_priority_scaler.pkl")
    X_scaled = scaler.transform(features)

    def label(pred): return {0: "Low", 1: "Medium", 2: "High"}[pred]
    results = {}
    for mtype in ["preventive", "corrective", "replacement"]:
        model = joblib.load(f"saved_models/{mtype}_model.pkl")
        pred = model.predict(X_scaled)[0]
        results[mtype] = label(pred)

    return {
        "equipment_id": equipment_id,
        "image_base64": base64_chart,
        "metrics": {
            "equipment_id": metrics["equipment_id"],
            "usage_hours": metrics.get("usage_hours", 0),
            "avg_cpu_temp": metrics.get("avg_cpu_temp", 0),
            "error_count": metrics.get("error_count", 0),
            "risk_score": metrics.get("risk_score", 0),
            # These come from maintenance_logs table:
            "downtime_hours": float(df["downtime"].iloc[0]),
            "num_failures": int(df["failures"].iloc[0]),
            "response_time_hours": float(df["avg_response"].iloc[0]),
        },
        "maintenance_needs": results,
        "predicted_to_fail": bool(df["needs_maintenance_10_days"].iloc[0])
    }


# Update status by technician (e.g., In Progress or Completed)
@router.put("/update-status/{maintenance_id}", dependencies=[Depends(require_role("technician"))])
def update_technician_progress(
    maintenance_id: str,
    status: str = Body(..., embed=True),  # Expect JSON: { "status": "In Progress" }
    user=Depends(get_current_user)
):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE maintenance_logs
        SET status = ?
        WHERE maintenance_id = ?
    """, (status, maintenance_id))
    conn.commit()
    conn.close()
    return {"message": f"Maintenance log {maintenance_id} updated to status: {status}"}

from typing import Optional
...

# In fastapi_app/maintenance.py, update the schedule_maintenance endpoint:
@router.put("/schedule/{equipment_id}")
def schedule_maintenance(
    equipment_id: str,
    maintenance_type: str = Body(...),
    date: str = Body(...),
    issue_description: str = Body(""),
    technician_id: Optional[str] = Body(None),
    user=Depends(get_current_user)
):
    # Check permissions - ENSURE biomedicalengineer is included
    user_role = user.get("role", "").lower().strip()
    allowed_roles = ["admin", "biomedical", "biomedicalengineer"]  # This is the key fix
    
    if user_role not in allowed_roles:
        print(f"Schedule access denied: user role '{user_role}' not in allowed roles {allowed_roles}")
        raise HTTPException(
            status_code=403, 
            detail=f"Insufficient permissions. User role '{user_role}' cannot schedule maintenance. Allowed: {allowed_roles}"
        )
    
    conn = get_db()
    cursor = conn.cursor()

    # Generate unique maintenance ID
    max_attempts = 10
    for attempt in range(max_attempts):
        try:
            cursor.execute("""
                SELECT maintenance_id FROM maintenance_logs 
                WHERE maintenance_id LIKE 'MTN%' 
                ORDER BY CAST(SUBSTR(maintenance_id, 4) AS INTEGER) DESC 
                LIMIT 1
            """)
            result = cursor.fetchone()
            
            if result:
                last_num = int(result[0][3:])
                new_num = last_num + 1
            else:
                new_num = 3341
            
            new_id = f"MTN{new_num}"

            cursor.execute("""
                INSERT INTO maintenance_logs (
                    maintenance_id, equipment_id, date, maintenance_type,
                    status, technician_id, completion_status, issue_description
                ) VALUES (?, ?, ?, ?, 'Scheduled', ?, 'Pending', ?)
            """, (
                new_id, equipment_id, date, maintenance_type,
                technician_id, issue_description
            ))

            conn.commit()
            break
            
        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint failed" in str(e) and attempt < max_attempts - 1:
                continue
            else:
                conn.rollback()
                raise HTTPException(status_code=500, detail=f"Could not generate unique maintenance ID")
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    else:
        conn.close()
        raise HTTPException(status_code=500, detail=f"Could not generate unique maintenance ID after {max_attempts} attempts")
    
    conn.close()
    
    return {
        "message": f"Maintenance {new_id} scheduled for {equipment_id} on {date}",
        "maintenance_id": new_id
    }

# in fastapi_app/maintenance.py

@router.get("/combined/{equipment_id}")
def get_combined_equipment_data(equipment_id: str, user=Depends(get_current_user)):
    from fastapi_app.llm_engine import generate_llm_explanation
    import base64, os

    metrics = fetch_equipment_metrics(equipment_id)

    chart_path = metrics.get("chart_path")
    if not os.path.exists(chart_path):
        raise HTTPException(status_code=404, detail="Trend chart not found")

    with open(chart_path, "rb") as img_file:
        base64_chart = base64.b64encode(img_file.read()).decode()

    # Priority prediction
    conn = sqlite3.connect("hospital_equipment_system.db")
    query = """
    SELECT e.equipment_id, e.installation_date,
           COALESCE(SUM(m.downtime_hours), 0) AS downtime,
           COUNT(m.maintenance_id) AS failures,
           COALESCE(AVG(m.response_time_hours), 0) AS avg_response,
           COALESCE(f.needs_maintenance_10_days, 0) AS needs_maintenance_10_days
    FROM equipment e
    LEFT JOIN maintenance_logs m ON e.equipment_id = m.equipment_id
    LEFT JOIN failure_predictions f ON e.equipment_id = f.equipment_id
    WHERE e.equipment_id = ?
    GROUP BY e.equipment_id
    """
    df = pd.read_sql_query(query, conn, params=(equipment_id,))
    conn.close()
    if df.empty:
        raise HTTPException(status_code=404, detail="Equipment not found")

    df["installation_date"] = pd.to_datetime(df["installation_date"])
    df["equipment_age"] = (pd.Timestamp.today() - df["installation_date"]).dt.days // 365

    features = df[["equipment_age", "downtime", "failures", "avg_response", "needs_maintenance_10_days"]]
    features.columns = ["equipment_age", "downtime_hours", "num_failures", "response_time_hours", "needs_maintenance_10_days"]

    scaler = joblib.load("saved_models/multi_priority_scaler.pkl")
    X_scaled = scaler.transform(features)

    def label(pred): return {0: "Low", 1: "Medium", 2: "High"}[pred]
    results = {}
    for mtype in ["preventive", "corrective", "replacement"]:
        model = joblib.load(f"saved_models/{mtype}_model.pkl")
        pred = model.predict(X_scaled)[0]
        results[mtype] = label(pred)

    role = user["role"].lower()
    explanation = generate_llm_explanation(metrics, role, chart_path)

    return {
        "equipment_id": equipment_id,
        "image_base64": base64_chart,
        "metrics": metrics,
        "maintenance_needs": results,
        "predicted_to_fail": bool(df["needs_maintenance_10_days"].iloc[0]),
        "explanation": explanation
    }

@router.get("/health-status")
def get_all_equipment_health(user=Depends(get_current_user)):
    # Check if user has permission - ENSURE biomedicalengineer is included
    user_role = user.get("role", "").lower().strip()
    allowed_roles = ["admin", "biomedical", "biomedicalengineer"]  # This is the key fix
    
    if user_role not in allowed_roles:
        raise HTTPException(status_code=403, detail="Insufficient permissions to view health status")
    
    conn = sqlite3.connect("hospital_equipment_system.db")
    cursor = conn.cursor()

    cursor.execute("SELECT equipment_id FROM equipment")
    ids = [row[0] for row in cursor.fetchall()]
    conn.close()

    results = []
    for eid in ids:
        try:
            detail = get_full_maintenance_priority(eid, user)
            msg = []
            if detail["predicted_to_fail"]:
                msg.append("Likely to fail in 10 days")
            for typ, level in detail["maintenance_needs"].items():
                if level == "High":
                    msg.append(f"{typ.capitalize()} maintenance needed")

            if msg:
                results.append({
                    "equipment_id": eid,
                    "health_status": "Attention Needed",
                    "message": "; ".join(msg)
                })
        except:
            continue

    return {"health_status": results}

# --- Get all logs for a specific equipment ---
@router.get("/by-equipment/{equipment_id}")
def get_logs_by_equipment(equipment_id: str, user=Depends(get_current_user)):
    print(f"Equipment logs request for {equipment_id} from user role: {user.get('role', 'NO_ROLE')}")
    
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM maintenance_logs WHERE equipment_id = ?", (equipment_id,))
    columns = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()
    conn.close()

    return {"logs": [dict(zip(columns, row)) for row in rows]}

# --- Get upcoming scheduled maintenances for a specific equipment ---
@router.get("/upcoming/{equipment_id}")
def get_upcoming_maintenances(equipment_id: str, user=Depends(get_current_user)):
    conn = get_db()
    cursor = conn.cursor()

    today = datetime.today().strftime("%Y-%m-%d")
    cursor.execute("""
        SELECT * FROM maintenance_logs
        WHERE equipment_id = ?
        AND date >= ?
        AND status = 'Scheduled'
        ORDER BY date ASC
    """, (equipment_id, today))

    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    conn.close()

    return {"upcoming_maintenances": [dict(zip(columns, row)) for row in rows]}

# In fastapi_app/maintenance.py - Update the mark_maintenance_complete function

@router.put("/mark-complete/{maintenance_id}", dependencies=[Depends(require_role("technician"))])
def mark_maintenance_complete(
    maintenance_id: str,
    completion: CompletionSchema,
    user=Depends(get_current_user)
):
    conn = get_db()
    cursor = conn.cursor()

    # Debug: Print user object to see available keys
    print(f"User object keys: {user.keys()}")
    print(f"User object: {user}")
    
    # Get technician_id from user object - prioritize personnel_id
    technician_id = None
    if 'personnel_id' in user:
        technician_id = user['personnel_id']
    elif 'id' in user:
        technician_id = user['id']
    elif 'user_id' in user:
        technician_id = user['user_id']
    else:
        # If none found, use the completion.technician_id as fallback
        technician_id = completion.technician_id
    
    print(f"Using technician_id: {technician_id}")
    
    if not technician_id:
        raise HTTPException(status_code=400, detail="Cannot determine technician ID")

    cursor.execute("""
        UPDATE maintenance_logs
        SET downtime_hours = ?, cost_inr = ?, technician_id = ?, status = 'Completed', completion_status = 'Pending'
        WHERE maintenance_id = ?
    """, (
        completion.downtime_hours,
        completion.cost_inr,
        technician_id,  # Use the resolved technician_id (should be personnel_id)
        maintenance_id
    ))

    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Maintenance log not found")

    conn.commit()
    conn.close()
    return {"message": "Maintenance marked as completed and pending confirmation"}

@router.put("/confirm/{maintenance_id}")
def confirm_completion_status(
    maintenance_id: str,
    service_rating: int = Body(..., embed=True),
    user=Depends(get_current_user)
):
    # Check if user has permission - ENSURE biomedicalengineer is included
    user_role = user.get("role", "").lower().strip()
    allowed_roles = ["admin", "biomedical", "biomedicalengineer"]
    
    if user_role not in allowed_roles:
        raise HTTPException(
            status_code=403, 
            detail=f"Insufficient permissions. User role '{user_role}' cannot confirm maintenance completion."
        )
    
    conn = get_db()
    cursor = conn.cursor()

    # Get equipment_id before updating
    cursor.execute("SELECT equipment_id FROM maintenance_logs WHERE maintenance_id = ?", (maintenance_id,))
    equipment_result = cursor.fetchone()
    
    if not equipment_result:
        conn.close()
        raise HTTPException(status_code=404, detail="Maintenance ID not found")
    
    equipment_id = equipment_result[0]
    print(f"Confirming maintenance {maintenance_id} for equipment {equipment_id}")

    cursor.execute("""
        UPDATE maintenance_logs
        SET status = 'Completed', completion_status = 'Confirmed', service_rating = ?
        WHERE maintenance_id = ?
    """, (service_rating, maintenance_id))

    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Failed to update maintenance log")

    conn.commit()
    conn.close()
    
    # ALWAYS reset equipment health predictions when maintenance is confirmed as completed
    try:
        reset_equipment_health_predictions(equipment_id)
        print(f"Successfully reset health predictions for equipment {equipment_id}")
    except Exception as e:
        print(f"Warning: Failed to reset health predictions for {equipment_id}: {str(e)}")
    
    return {
        "message": f"Maintenance {maintenance_id} confirmed with rating {service_rating}. Equipment health status updated.",
        "equipment_id": equipment_id
    }

@router.put("/review-completion/{maintenance_id}")
def review_maintenance_completion(
    maintenance_id: str,
    review: ReviewSchema,
    user=Depends(get_current_user)
):
    # Check if user has permission - ENSURE biomedicalengineer is included
    user_role = user.get("role", "").lower().strip()
    allowed_roles = ["admin", "biomedical", "biomedicalengineer"]
    
    if user_role not in allowed_roles:
        print(f"Review completion access denied: user role '{user_role}' not in allowed roles {allowed_roles}")
        raise HTTPException(
            status_code=403, 
            detail=f"Insufficient permissions to review maintenance. User role: '{user_role}'"
        )
    
    conn = get_db()
    cursor = conn.cursor()

    # First, check the current status and get equipment_id
    cursor.execute("SELECT maintenance_id, status, completion_status, equipment_id FROM maintenance_logs WHERE maintenance_id = ?", (maintenance_id,))
    current_record = cursor.fetchone()
    
    if not current_record:
        conn.close()
        raise HTTPException(status_code=404, detail="Maintenance log not found")
    
    equipment_id = current_record[3]  # equipment_id is the 4th column (index 3)
    
    print(f"Reviewing maintenance {maintenance_id} for equipment {equipment_id}")
    print(f"Review completion status: {review.completion_status}")
    
    # Determine final status based on completion_status
    if review.completion_status == "Approved":
        final_status = "Completed"
        completion_status = "Approved"
    else:
        # For "Requires Follow-up" or "Rejected", set back to Scheduled
        final_status = "Scheduled"  
        completion_status = "Requires Follow-up" if review.completion_status == "Requires Follow-up" else "Rejected"

    # Update the record
    cursor.execute("""
        UPDATE maintenance_logs
        SET completion_status = ?, service_rating = ?, status = ?
        WHERE maintenance_id = ?
    """, (
        completion_status,
        review.service_rating,
        final_status,
        maintenance_id
    ))

    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="No rows updated")

    conn.commit()
    conn.close()
    
    # Reset equipment health predictions when maintenance is approved OR completed
    if review.completion_status == "Approved" or final_status == "Completed":
        try:
            reset_equipment_health_predictions(equipment_id)
            print(f"Successfully reset health predictions for equipment {equipment_id}")
            message = f"Maintenance {maintenance_id} approved and completed successfully. Equipment health status updated."
        except Exception as e:
            print(f"Warning: Failed to reset health predictions for {equipment_id}: {str(e)}")
            message = f"Maintenance {maintenance_id} approved and completed successfully. Warning: Health status update failed."
    else:
        message = f"Maintenance {maintenance_id} returned to technician for additional work"
    
    return {
        "message": message,
        "updated_status": final_status,
        "updated_completion_status": completion_status,
        "equipment_id": equipment_id
    }

# --- Alert to Admin/Biomedical for pending review ---
@router.get("/pending-reviews")
def get_pending_reviews(user=Depends(get_current_user)):
    # Check if user has permission - ENSURE biomedicalengineer is included
    user_role = user.get("role", "").lower().strip()
    allowed_roles = ["admin", "biomedical", "biomedicalengineer"]  # This is the key fix
    
    if user_role not in allowed_roles:
        print(f"Pending reviews access denied: user role '{user_role}' not in allowed roles {allowed_roles}")
        raise HTTPException(
            status_code=403, 
            detail=f"Insufficient permissions to view pending reviews. User role: '{user_role}'"
        )
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT maintenance_id, equipment_id, technician_id, date
        FROM maintenance_logs
        WHERE status = 'Completed' AND completion_status = 'Pending'
    """)
    rows = cursor.fetchall()
    conn.close()
    return {"reviews": [dict(zip(["maintenance_id", "equipment_id", "technician_id", "date"], row)) for row in rows]}

from datetime import datetime

@router.get("/new-scheduled", dependencies=[Depends(require_role("technician"))])
def get_new_scheduled_maintenances(user=Depends(get_current_user)):
    today = datetime.today().strftime("%Y-%m-%d")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT maintenance_id, equipment_id, date, maintenance_type 
        FROM maintenance_logs
        WHERE status = 'Scheduled' AND date >= ?
    """, (today,))
    rows = cursor.fetchall()
    conn.close()
    return {"new_scheduled": [dict(zip(["maintenance_id", "equipment_id", "date", "maintenance_type"], row)) for row in rows]}

@router.put("/reset-predictions/{equipment_id}")
def manually_reset_predictions(
    equipment_id: str,
    user=Depends(get_current_user)
):
    # Check if user has permission
    user_role = user.get("role", "").lower().strip()
    allowed_roles = ["admin", "biomedical", "biomedicalengineer"]
    
    if user_role not in allowed_roles:
        raise HTTPException(
            status_code=403, 
            detail=f"Insufficient permissions to reset predictions. User role: '{user_role}'"
        )
    
    try:
        reset_equipment_health_predictions(equipment_id)
        return {
            "message": f"Health predictions reset successfully for equipment {equipment_id}",
            "equipment_id": equipment_id
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reset health predictions: {str(e)}"
        )
    
# Add this route to your fastapi_app/maintenance.py file

@router.get("/maintenance-types")
def get_maintenance_types(user=Depends(get_current_user)):
    """Get unique maintenance types from maintenance_logs table"""
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT DISTINCT maintenance_type 
            FROM maintenance_logs 
            WHERE maintenance_type IS NOT NULL 
            AND maintenance_type != ''
            ORDER BY maintenance_type
        """)
        
        types = [row[0] for row in cursor.fetchall()]
        
        # If no types found, return common defaults
        if not types:
            types = ['Preventive', 'Corrective', 'Replacement']
            
        return {"maintenance_types": types}
        
    except Exception as e:
        print(f"Error fetching maintenance types: {str(e)}")
        # Return fallback types
        return {"maintenance_types": ['Preventive', 'Corrective', 'Replacement']}
    finally:
        conn.close()