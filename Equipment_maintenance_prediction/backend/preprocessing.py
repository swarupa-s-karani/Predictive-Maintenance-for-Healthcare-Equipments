# backend/preprocessing.py
import pandas as pd
import pickle
import numpy as np

# Load pre-trained artifacts
with open("backend/models/scaler.pkl", "rb") as f:
    scaler = pickle.load(f)

with open("backend/models/label_encoders.pkl", "rb") as f:
    label_encoders = pickle.load(f)

with open("backend/models/feature_columns.pkl", "rb") as f:
    feature_columns = pickle.load(f)

def preprocess_input(input_dict: dict) -> np.ndarray:
    """
    Preprocess user input using scaler and label encoders
    """
    df = pd.DataFrame([input_dict])

    # Apply label encoding
    for col, le in label_encoders.items():
        if col in df.columns:
            df[col] = le.transform(df[col])

    # Select required columns
    df = df[feature_columns]

    # Scale features
    scaled_input = scaler.transform(df)

    return scaled_input
