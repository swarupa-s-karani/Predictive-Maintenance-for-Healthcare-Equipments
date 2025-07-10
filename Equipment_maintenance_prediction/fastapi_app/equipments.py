#equipments.py
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional
from fastapi.responses import JSONResponse
import matplotlib.pyplot as plt
import sqlite3, io, base64
import pandas as pd

from fastapi_app.dependencies import get_current_user, require_role
from pydantic import BaseModel

router = APIRouter()

def get_db():
    return sqlite3.connect("hospital_equipment_system.db")

# Pydantic model
class EquipmentIn(BaseModel):
    equipment_id: str
    type: str
    manufacturer: str
    location: str
    criticality: str
    installation_date: str

@router.get("/")
def list_equipments(type: Optional[str] = Query(None), location: Optional[str] = Query(None), user=Depends(get_current_user)):
    conn = get_db()
    cursor = conn.cursor()

    query = "SELECT * FROM equipment WHERE 1=1"
    params = []
    if type:
        query += " AND type = ?"
        params.append(type)
    if location:
        query += " AND location = ?"
        params.append(location)

    if user["role"] == "technician":
        query += " AND equipment_id IN (SELECT DISTINCT equipment_id FROM maintenance_logs WHERE status = 'Scheduled')"

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return {"equipments": rows}

@router.get("/{equipment_id}")
def get_equipment(equipment_id: str, user=Depends(get_current_user)):
    conn = get_db()
    cursor = conn.cursor()

    if user["role"] == "technician":
        cursor.execute("SELECT COUNT(*) FROM maintenance_logs WHERE equipment_id = ? AND status = 'Scheduled'", (equipment_id,))
        if cursor.fetchone()[0] == 0:
            raise HTTPException(status_code=403, detail="Not authorized for this equipment")

    cursor.execute("SELECT * FROM equipment WHERE equipment_id = ?", (equipment_id,))
    row = cursor.fetchone()

    df = pd.read_sql_query("SELECT * FROM usage_logs WHERE equipment_id = ? ORDER BY timestamp", conn, params=(equipment_id,))
    if df.empty:
        conn.close()
        return {"equipment": row, "trend_plot": None}

    df["timestamp"] = pd.to_datetime(df["timestamp"])
    plt.figure(figsize=(6, 3))
    plt.plot(df["timestamp"], df["error_count"], label="Error Count")
    plt.plot(df["timestamp"], df["avg_cpu_temp"], label="CPU Temp")
    plt.legend()
    plt.title(f"Trends - {equipment_id}")
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png")
    plt.close()
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode("utf-8")
    conn.close()
    return {"equipment": row, "trend_plot": f"data:image/png;base64,{img_base64}"}

@router.post("/", dependencies=[Depends(require_role("admin"))])
def add_equipment(data: EquipmentIn, user=Depends(get_current_user)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO equipment (equipment_id, type, manufacturer, location, criticality, installation_date)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        data.equipment_id, data.type, data.manufacturer,
        data.location, data.criticality, data.installation_date
    ))
    conn.commit()
    conn.close()
    return {"message": "Equipment added"}

@router.put("/{equipment_id}", dependencies=[Depends(require_role("admin"))])
def update_equipment(equipment_id: str, data: EquipmentIn, user=Depends(get_current_user)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE equipment SET type = ?, manufacturer = ?, location = ?, criticality = ?, installation_date = ?
        WHERE equipment_id = ?
    """, (
        data.type, data.manufacturer, data.location,
        data.criticality, data.installation_date, equipment_id
    ))
    conn.commit()
    conn.close()
    return {"message": "Equipment updated"}

@router.delete("/{equipment_id}", dependencies=[Depends(require_role("admin"))])
def delete_equipment(equipment_id: str, user=Depends(get_current_user)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM equipment WHERE equipment_id = ?", (equipment_id,))
    conn.commit()
    conn.close()
    return {"message": "Equipment deleted"}
