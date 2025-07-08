# backend/predict.py
import pickle
import numpy as np
import tensorflow as tf
from backend.preprocessing import preprocess_input

# Load XGBoost model
with open("backend/models/xgb_model.pkl", "rb") as f:
    xgb_model = pickle.load(f)

# Load LSTM model
lstm_model = tf.keras.models.load_model("backend/models/lstm_model.h5")

def predict_equipment_maintenance(input_data: dict):
    """
    Run predictions using both XGBoost and LSTM, return combined output
    """
    # Preprocess input
    X = preprocess_input(input_data)

    # XGBoost prediction
    xgb_pred = xgb_model.predict(X)[0]

    # LSTM expects 3D input: (samples, time_steps, features)
    lstm_input = np.expand_dims(X, axis=1)
    lstm_pred = lstm_model.predict(lstm_input)[0][0]
    lstm_pred_binary = int(lstm_pred > 0.5)

    # Majority voting (can be changed to probability average)
    final_pred = int((xgb_pred + lstm_pred_binary) >= 1)

    return {
        "XGBoost Prediction": int(xgb_pred),
        "LSTM Prediction": int(lstm_pred_binary),
        "Final Ensemble Prediction": final_pred,
        "Interpretation": "Needs Maintenance" if final_pred else "No Maintenance"
    }
