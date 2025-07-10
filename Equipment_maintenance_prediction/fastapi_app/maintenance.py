#maintenance.py
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import sqlite3

from fastapi_app.dependencies import get_current_user, require_role

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

from typing import Union

@router.post("/")
def add_log(
    data: Union[MaintenanceExtended, MaintenanceBase],
    user=Depends(get_current_user)
):
    conn = get_db()
    cursor = conn.cursor()

    # Detect model type based on role and validate
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
