#!/usr/bin/env python3
"""
lead_scoring_ml.py
NVIDIA RAPIDS (cuML) Predictive Lead Scoring Engine for KOE Syndicate.

This script uses GPU-accelerated machine learning to predict lead conversion
probabilities. It reads from demo_leads.json, builds a Random Forest Classifier
on the GPU via cuML, and outputs a 'Predictive Lead Score' for each prospect.

When NVIDIA RAPIDS is available, the entire ML pipeline (data loading, feature
engineering, model training, and inference) runs on the GPU.
"""

import json
import numpy as np
import os
import warnings
import sys

warnings.filterwarnings('ignore')

# ── Attempt to import NVIDIA RAPIDS (cuML & cuDF) ────────────────────────────
HAS_CUML = False
try:
    import cuml
    from cuml.ensemble import RandomForestClassifier as cuRF
    import cudf
    from cuml.preprocessing import LabelEncoder
    HAS_CUML = True
    print("[*] NVIDIA GPU Acceleration ENABLED (cuML/cuDF)")
    print(f"    cuML version: {cuml.__version__}")
except ImportError:
    print("[!] NVIDIA RAPIDS (cuML/cuDF) not found. Running in CPU fallback mode.")
    print("    To enable GPU acceleration, install: conda install -c rapidsai cuml cudf")
    print("    or follow: https://rapids.ai/start.html")
    print("[+] Falling back to scikit-learn for demonstration...\n")
    try:
        from sklearn.ensemble import RandomForestClassifier as skRF
    except ImportError:
        print("ERROR: scikit-learn is also missing. Please run: pip install scikit-learn pandas numpy")
        sys.exit(1)
    import pandas as pd
    from sklearn.preprocessing import LabelEncoder as skLabelEncoder

# ── Configuration ────────────────────────────────────────────────────────────
JSON_PATH = "demo_leads.json"
MODEL_PARAMS = {
    "n_estimators": 200,
    "max_depth": 12,
    "min_samples_leaf": 1,
    "min_samples_split": 2,
    "random_state": 42,
}

# ── Load live pipeline data ──────────────────────────────────────────────────
with open(JSON_PATH, "r") as f:
    live_data = json.load(f)

# ── Mock historical training data ─────────────────────────────────────────────
# In production, this would come from a warehouse (BigQuery, etc.)
HISTORICAL_DATA = [
    {"rating": 4.9, "industry": "Technology",   "city": "San Francisco", "converted": 1},
    {"rating": 4.8, "industry": "Technology",   "city": "San Francisco", "converted": 1},
    {"rating": 3.2, "industry": "Technology",   "city": "Austin",        "converted": 0},
    {"rating": 4.5, "industry": "Technology",   "city": "San Francisco", "converted": 1},
    {"rating": 2.1, "industry": "Marketing",    "city": "San Francisco", "converted": 0},
    {"rating": 4.7, "industry": "Technology",   "city": "Austin",        "converted": 1},
    {"rating": 3.8, "industry": "Logistics",    "city": "Austin",        "converted": 0},
    {"rating": 4.2, "industry": "Construction", "city": "San Francisco", "converted": 0},
    {"rating": 4.9, "industry": "Technology",   "city": "San Francisco", "converted": 1},
    {"rating": 4.6, "industry": "Technology",   "city": "San Francisco", "converted": 1},
]

def build_features(df, has_cuml):
    """Engineer numeric features from raw lead data."""
    if has_cuml:
        X = cudf.DataFrame()
        X["rating"] = df["rating"].astype("float32")
        X["is_tech"] = (df["industry"] == "Technology").astype("int32")
        X["is_sf"] = (df["city"] == "San Francisco").astype("int32")
        return X
    else:
        X = pd.DataFrame()
        X["rating"] = df["rating"].astype("float32")
        X["is_tech"] = (df["industry"] == "Technology").astype("int32")
        X["is_sf"] = (df["city"] == "San Francisco").astype("int32")
        return X

# ── Build training set from historical data ──────────────────────────────────
if HAS_CUML:
    train_df = cudf.DataFrame(HISTORICAL_DATA)
    X_train = build_features(train_df, has_cuml=True)
    y_train = train_df["converted"].astype("int32")
else:
    train_df = pd.DataFrame(HISTORICAL_DATA)
    X_train = build_features(train_df, has_cuml=False)
    y_train = train_df["converted"].astype("int32")

# ── Train the Random Forest on GPU (or CPU fallback) ─────────────────────────
print("[*] Training Random Forest Classifier...")
if HAS_CUML:
    model = cuRF(**MODEL_PARAMS)
    model.fit(X_train, y_train)
    print("[+] Model training complete on NVIDIA GPU.")
else:
    model = skRF(**MODEL_PARAMS)
    model.fit(X_train, y_train)
    print("[+] Model training complete on CPU (GPU not available).")

# ── Infer on live pipeline data ──────────────────────────────────────────────
# Convert live leads to a dataframe and engineer the same features
if HAS_CUML:
    live_df = cudf.DataFrame(live_data)
    X_live = build_features(live_df, has_cuml=True)
    # cuML predict_proba returns a cuDF DataFrame
    probs_gpu = model.predict_proba(X_live)
    probs = probs_gpu.iloc[:, 1].to_pandas().values
else:
    live_df = pd.DataFrame(live_data)
    X_live = build_features(live_df, has_cuml=False)
    probs = model.predict_proba(X_live)[:, 1]

# ── Output results ───────────────────────────────────────────────────────────
print("\n=== KOE SYNDICATE: PREDICTIVE LEAD SCORES ===\n")
print(f"{'Company':<30} | {'Score':>8} | {'City':<15} | {'Industry':<15} | Status")
print("-" * 90)

for i, lead in enumerate(live_data):
    score = float(probs[i]) * 100
    status_label = "HIGH" if score > 70 else "MED" if score > 40 else "LOW"
    print(f"{lead['name']:<30} | {score:>7.1f}% | {lead['city']:<15} | {lead['industry']:<15} | {status_label}")

print("-" * 90)
print(f"\n[+] Inference complete. Predicted conversion probabilities above.")
if HAS_CUML:
    print("    GPU-accelerated via NVIDIA RAPIDS cuML.")
else:
    print("    CPU fallback mode. Install RAPIDS for GPU acceleration.")
