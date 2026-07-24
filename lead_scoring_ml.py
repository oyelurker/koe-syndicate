#!/usr/bin/env python3
"""
lead_scoring_ml.py
NVIDIA RAPIDS (cuML) Predictive Lead Scoring Engine for KOE Syndicate.

This module uses GPU-accelerated machine learning to predict lead conversion
probabilities. It reads leads data, builds a Random Forest Classifier
on the GPU via cuML, and outputs a 'Predictive Lead Score' for each prospect.

When NVIDIA RAPIDS is available, the entire ML pipeline runs on the GPU.

Can be used as a standalone script OR imported as a module:
    from lead_scoring_ml import score_leads
    scores = score_leads(list_of_leads)  # returns dict[name -> float 0-100]
"""

import json
import os
import warnings
import sys

warnings.filterwarnings('ignore')

# ── Attempt to import NVIDIA RAPIDS (cuML & cuDF) ────────────────────────────
HAS_CUML = False
_skRF = None
try:
    import cuml
    from cuml.ensemble import RandomForestClassifier as cuRF
    import cudf
    HAS_CUML = True
    print("[*] NVIDIA GPU Acceleration ENABLED (cuML/cuDF)")
    print(f"    cuML version: {cuml.__version__}")
except ImportError:
    print("[!] NVIDIA RAPIDS (cuML/cuDF) not found. Running in CPU fallback mode.")
    print("    Install RAPIDS: https://rapids.ai/start.html")
    try:
        from sklearn.ensemble import RandomForestClassifier as _skRF
        import pandas as pd
    except ImportError:
        _skRF = None

# ── Mock historical training data ─────────────────────────────────────────────
# In production, this would come from BigQuery
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
    {"rating": 3.5, "industry": "Real Estate",  "city": "San Francisco", "converted": 1},
    {"rating": 4.1, "industry": "Real Estate",  "city": "Austin",        "converted": 1},
    {"rating": 2.8, "industry": "Real Estate",  "city": "San Francisco", "converted": 0},
    {"rating": 4.6, "industry": "Real Estate",  "city": "San Francisco", "converted": 1},
    {"rating": 3.9, "industry": "Real Estate",  "city": "Austin",        "converted": 0},
]

MODEL_PARAMS = {"n_estimators": 200, "max_depth": 12, "random_state": 42}


def score_leads(leads: list) -> dict:
    """
    Score a list of lead dicts using GPU-accelerated (or CPU fallback) Random Forest.

    Args:
        leads: list of dicts with 'name', optionally 'rating', 'city', 'industry'

    Returns:
        dict mapping business name -> predicted conversion probability (0-100 float)
    """
    if not leads:
        return {}

    # Normalize leads - fill missing fields with sensible defaults
    normalized = []
    for lead in leads:
        normalized.append({
            "name":     lead.get("name", "Unknown"),
            "rating":   float(lead.get("rating", 3.5)),
            "industry": lead.get("industry", "General"),
            "city":     lead.get("city", "Unknown"),
        })

    if HAS_CUML:
        train_df = cudf.DataFrame(HISTORICAL_DATA)
        X_train  = _features_gpu(train_df)
        y_train  = train_df["converted"].astype("int32")
        model    = cuRF(**MODEL_PARAMS)
        model.fit(X_train, y_train)

        live_df  = cudf.DataFrame(normalized)
        X_live   = _features_gpu(live_df)
        probs    = model.predict_proba(X_live).iloc[:, 1].to_pandas().values
        print("[+] NVIDIA GPU lead scoring complete (cuML).")

    elif _skRF is not None:
        import pandas as pd
        train_df = pd.DataFrame(HISTORICAL_DATA)
        X_train  = _features_cpu(train_df)
        y_train  = train_df["converted"].astype("int32")
        model    = _skRF(**MODEL_PARAMS)
        model.fit(X_train, y_train)

        live_df  = pd.DataFrame(normalized)
        X_live   = _features_cpu(live_df)
        probs    = model.predict_proba(X_live)[:, 1]
        print("[+] CPU lead scoring complete (sklearn fallback).")

    else:
        # Ultimate fallback: deterministic rating-based score
        print("[!] sklearn not available. Using rating-based fallback scoring.")
        return {
            n["name"]: round(min(100.0, max(0.0, (n["rating"] / 5.0) * 100)), 1)
            for n in normalized
        }

    return {
        normalized[i]["name"]: round(float(probs[i]) * 100, 1)
        for i in range(len(normalized))
    }


def _features_cpu(df):
    """Build feature DataFrame from pandas df."""
    import pandas as pd
    X = pd.DataFrame()
    X["rating"] = df["rating"].astype("float32")
    X["is_tech"] = (df.get("industry", pd.Series([""] * len(df))) == "Technology").astype("int32")
    X["is_sf"]   = (df.get("city",     pd.Series([""] * len(df))) == "San Francisco").astype("int32")
    return X


def _features_gpu(df):
    """Build feature DataFrame from cuDF df."""
    X = cudf.DataFrame()
    X["rating"] = df["rating"].astype("float32")
    X["is_tech"] = (df["industry"] == "Technology").astype("int32")
    X["is_sf"]   = (df["city"]     == "San Francisco").astype("int32")
    return X


# ── Standalone script entry point ─────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="NVIDIA cuML Accelerated Lead Scoring")
    parser.add_argument('--file', type=str, default='demo_leads.json')
    args = parser.parse_args()

    if not os.path.exists(args.file):
        print(f"[-] File not found: {args.file}")
        sys.exit(1)

    with open(args.file, "r") as f:
        live_data = json.load(f)

    accel = "NVIDIA GPU (cuML)" if HAS_CUML else "CPU Fallback (sklearn)"
    print(f"\n=== KOE SYNDICATE: PREDICTIVE LEAD SCORES ({accel}) ===\n")
    print(f"{'Company':<30} | {'Score':>8} | {'City':<15} | Status")
    print("-" * 75)

    scores = score_leads(live_data)
    for lead in live_data:
        name  = lead.get("name", "Unknown")
        score = scores.get(name, 0.0)
        city  = lead.get("city", "Unknown")
        label = "HIGH ↑" if score > 70 else "MED ~" if score > 40 else "LOW ↓"
        print(f"{name:<30} | {score:>7.1f}% | {city:<15} | {label}")

    print("-" * 75)
    print(f"\n[+] Scored {len(live_data)} leads via {accel}.")
