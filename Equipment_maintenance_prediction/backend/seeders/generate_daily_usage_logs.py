import pandas as pd
import numpy as np
from datetime import datetime
import random
import os

# Paths
DATA_DIR = "../data"
EQUIPMENT_FILE = os.path.join(DATA_DIR, "equipment_metadata.csv")
USAGE_LOG_FILE = os.path.join(DATA_DIR, "usage_logs.csv")

# Load existing equipment
equipment_df = pd.read_csv(EQUIPMENT_FILE)
equipment_ids = equipment_df['equipment_id'].tolist()

# Today's date
today = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Function to generate random usage data for one equipment
def generate_log(equipment_id):
    usage_hours = round(np.random.uniform(1, 8), 2)
    patients_served = np.random.randint(1, 20)
    workload_level = round(np.random.uniform(5, 30), 1)
    avg_cpu_temp = round(np.random.uniform(40, 60), 1)
    temp_C = round(np.random.uniform(45, 65), 1)
    error_count = np.random.poisson(1)
    cumulative_usage = round(np.random.uniform(1000, 2000), 1)
    days_since_service = np.random.randint(1, 300)
    power_consumption_kwh = round(np.random.uniform(1, 10), 2)
    ambient_temp_C = round(np.random.uniform(25, 35), 1)
    humidity_percent = round(np.random.uniform(30, 90), 1)

    return {
        "equipment_id": equipment_id,
        "timestamp": today,
        "usage_hours": usage_hours,
        "patients_served": patients_served,
        "workload_level": workload_level,
        "avg_cpu_temp": avg_cpu_temp,
        "temp_C": temp_C,
        "error_count": error_count,
        "cumulative_usage": cumulative_usage,
        "days_since_service": days_since_service,
        "power_consumption_kwh": power_consumption_kwh,
        "ambient_temp_C": ambient_temp_C,
        "humidity_percent": humidity_percent
    }

# Generate daily logs
daily_logs = [generate_log(eid) for eid in equipment_ids]
df_logs = pd.DataFrame(daily_logs)

# Append to CSV
if os.path.exists(USAGE_LOG_FILE):
    df_logs.to_csv(USAGE_LOG_FILE, mode='a', index=False, header=False)
else:
    df_logs.to_csv(USAGE_LOG_FILE, index=False)

print(f"✅ Daily usage logs generated for {len(equipment_ids)} equipments on {today}")
