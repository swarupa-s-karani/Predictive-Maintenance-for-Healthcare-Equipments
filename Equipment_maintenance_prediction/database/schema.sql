-- backend/database/schema.sql

-- Drop tables if they exist (in reverse dependency order)
DROP TABLE IF EXISTS usage_logs;
DROP TABLE IF EXISTS maintenance_logs;
DROP TABLE IF EXISTS failure_labels;
DROP TABLE IF EXISTS equipment_assignments;
DROP TABLE IF EXISTS personnel_operators;
DROP TABLE IF EXISTS equipment_metadata;

-- Table: equipment_metadata
CREATE TABLE IF NOT EXISTS equipment_metadata (
    equipment_id TEXT PRIMARY KEY,
    equipment_code TEXT,
    type TEXT,
    manufacturer TEXT,
    location TEXT,
    criticality TEXT,
    installation_date TEXT,
    last_service_date TEXT,
    age_days INTEGER,
    days_since_installation INTEGER,
    model TEXT,
    serial_number TEXT,
    warranty_status TEXT,
    purchase_cost_inr REAL,
    vendor TEXT,
    floor TEXT,
    room TEXT
);

-- Table: personnel_operators
CREATE TABLE IF NOT EXISTS personnel_operators (
    personnel_id TEXT PRIMARY KEY,
    employee_id TEXT,
    name TEXT,
    gender TEXT,
    role TEXT,
    department TEXT,
    experience_years REAL,
    shift TEXT,
    phone TEXT,
    email TEXT,
    certifications TEXT,
    salary_inr REAL,
    joining_date TEXT,
    status TEXT,
    supervisor TEXT,
    emergency_contact TEXT,
    address TEXT
);

-- Table: equipment_assignments
CREATE TABLE IF NOT EXISTS equipment_assignments (
    assignment_id TEXT PRIMARY KEY,
    equipment_id TEXT,
    personnel_id TEXT,
    assignment_date TEXT,
    proficiency_level TEXT,
    primary_operator TEXT,
    training_completed TEXT,
    last_training_date TEXT,
    access_level TEXT,
    performance_rating REAL,
    FOREIGN KEY (equipment_id) REFERENCES equipment_metadata(equipment_id),
    FOREIGN KEY (personnel_id) REFERENCES personnel_operators(personnel_id)
);

-- Table: failure_labels
CREATE TABLE IF NOT EXISTS failure_labels (
    equipment_id TEXT,
    prediction_date TEXT,
    needs_maintenance_10_days TEXT,
    failure_probability REAL,
    risk_level TEXT,
    failure_reason TEXT,
    equipment_type TEXT,
    criticality TEXT,
    location TEXT,
    age_days INTEGER,
    predicted_downtime_hours REAL,
    estimated_repair_cost_inr REAL,
    FOREIGN KEY (equipment_id) REFERENCES equipment_metadata(equipment_id)
);

-- Table: maintenance_logs
CREATE TABLE IF NOT EXISTS maintenance_logs (
    maintenance_id TEXT PRIMARY KEY,
    equipment_id TEXT,
    date TEXT,
    maintenance_type TEXT,
    downtime_hours REAL,
    cost_inr REAL,
    issue_description TEXT,
    parts_replaced TEXT,
    vendor TEXT,
    technician_id TEXT,
    service_rating REAL,
    response_time_hours REAL,
    completion_status TEXT,
    warranty_covered TEXT,
    next_service_due TEXT,
    FOREIGN KEY (equipment_id) REFERENCES equipment_metadata(equipment_id)
);

-- Table: usage_logs
CREATE TABLE IF NOT EXISTS usage_logs (
    equipment_id TEXT,
    timestamp TEXT,
    usage_hours REAL,
    patients_served INTEGER,
    workload_level TEXT,
    avg_cpu_temp REAL,
    temp_C REAL,
    error_count INTEGER,
    cumulative_usage REAL,
    days_since_service INTEGER,
    power_consumption_kwh REAL,
    ambient_temp_C REAL,
    humidity_percent REAL,
    FOREIGN KEY (equipment_id) REFERENCES equipment_metadata(equipment_id)
);
