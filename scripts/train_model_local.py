"""
Script d'entrainement du modele ML (Version Locale)
====================================================
Ce script entraine le modele XGBoost optimise pour Accuracy et sauvegarde
les artefacts dans ml/models/runs/production/
"""
import pandas as pd
import numpy as np
from sklearn.preprocessing import LabelEncoder
from sklearn.impute import SimpleImputer
from sklearn.metrics import roc_auc_score, confusion_matrix, classification_report
from xgboost import XGBClassifier
import joblib
import json
import os
from datetime import datetime
from pathlib import Path

print("=" * 70)
print("ENTRAINEMENT DU MODELE ML - Version Production")
print("=" * 70)

# Configuration
BASE_DIR = Path(__file__).parent.parent
DATA_FILE = BASE_DIR / "data" / "Airline_Delay_Cause_Cpt.csv"
OUTPUT_DIR = BASE_DIR / "ml" / "models" / "runs" / "production"
TARGET_THRESHOLD = 0.20

# Creer le dossier de sortie
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================================
# 1. Chargement des donnees
# ============================================================================
print("\n[1/6] Chargement des donnees...")
df = pd.read_csv(DATA_FILE)
print(f"      {len(df):,} lignes chargees")

# Renommer les colonnes si necessaire
col_mapping = {
    'origin_airport': 'airport',
    'YEAR': 'year', 'MONTH': 'month', 'CARRIER': 'carrier',
    'AIRPORT': 'airport', 'ARR_FLIGHTS': 'arr_flights', 'ARR_DEL15': 'arr_del15'
}
for old, new in col_mapping.items():
    if old in df.columns and new not in df.columns:
        df = df.rename(columns={old: new})

# Calculer delay_rate
df['delay_rate'] = df['arr_del15'] / df['arr_flights'].clip(lower=1)

# ============================================================================
# 2. Feature Engineering
# ============================================================================
print("[2/6] Feature Engineering...")

data = df.copy()
data['target'] = (data['delay_rate'] > TARGET_THRESHOLD).astype(int)

# Encodage
le_carrier = LabelEncoder()
le_airport = LabelEncoder()
data['carrier_encoded'] = le_carrier.fit_transform(data['carrier'].astype(str))
data['airport_encoded'] = le_airport.fit_transform(data['airport'].astype(str))

# Saisonnalite
data['month_sin'] = np.sin(2 * np.pi * data['month'] / 12)
data['month_cos'] = np.cos(2 * np.pi * data['month'] / 12)
data['is_summer'] = data['month'].isin([6, 7, 8]).astype(int)
data['is_winter'] = data['month'].isin([12, 1, 2]).astype(int)
data['is_holiday_season'] = data['month'].isin([11, 12, 6, 7, 8]).astype(int)

# Volume
data['log_arr_flights'] = np.log1p(data['arr_flights'].clip(lower=0))

# Lags
data['period'] = data['year'] * 12 + data['month']
data = data.sort_values(['carrier', 'airport', 'period']).reset_index(drop=True)

# Lag features
data['pair_lag1'] = data.groupby(['carrier', 'airport'])['delay_rate'].shift(1)
data['pair_lag3_mean'] = data.groupby(['carrier', 'airport'])['delay_rate'].transform(
    lambda x: x.shift(1).rolling(3, min_periods=1).mean())
data['pair_expanding_mean'] = data.groupby(['carrier', 'airport'])['delay_rate'].transform(
    lambda x: x.shift(1).expanding(min_periods=1).mean())

data['airport_lag1'] = data.groupby('airport')['delay_rate'].shift(1)
data['airport_lag3_mean'] = data.groupby('airport')['delay_rate'].transform(
    lambda x: x.shift(1).rolling(3, min_periods=1).mean())
data['airport_expanding_mean'] = data.groupby('airport')['delay_rate'].transform(
    lambda x: x.shift(1).expanding(min_periods=1).mean())

data['carrier_lag1'] = data.groupby('carrier')['delay_rate'].shift(1)
data['carrier_lag3_mean'] = data.groupby('carrier')['delay_rate'].transform(
    lambda x: x.shift(1).rolling(3, min_periods=1).mean())
data['carrier_expanding_mean'] = data.groupby('carrier')['delay_rate'].transform(
    lambda x: x.shift(1).expanding(min_periods=1).mean())

FEATURE_COLS = [
    'year', 'month', 'month_sin', 'month_cos',
    'is_summer', 'is_winter', 'is_holiday_season',
    'carrier_encoded', 'airport_encoded',
    'arr_flights', 'log_arr_flights',
    'pair_lag1', 'pair_lag3_mean', 'pair_expanding_mean',
    'airport_lag1', 'airport_lag3_mean', 'airport_expanding_mean',
    'carrier_lag1', 'carrier_lag3_mean', 'carrier_expanding_mean'
]

print(f"      {len(FEATURE_COLS)} features creees")

# ============================================================================
# 3. Split des donnees
# ============================================================================
print("[3/6] Split temporel...")

unique_periods = sorted(data['period'].unique())
n_periods = len(unique_periods)
n_train = int(n_periods * 0.70)
n_val = int(n_periods * 0.20)

train_periods = set(unique_periods[:n_train])
val_periods = set(unique_periods[n_train:n_train + n_val])
test_periods = set(unique_periods[n_train + n_val:])

train_mask = data['period'].isin(train_periods)
val_mask = data['period'].isin(val_periods)
test_mask = data['period'].isin(test_periods)

X_train = data.loc[train_mask, FEATURE_COLS]
y_train = data.loc[train_mask, 'target']
X_val = data.loc[val_mask, FEATURE_COLS]
y_val = data.loc[val_mask, 'target']
X_test = data.loc[test_mask, FEATURE_COLS]
y_test = data.loc[test_mask, 'target']

print(f"      Train: {len(X_train):,} | Val: {len(X_val):,} | Test: {len(X_test):,}")

# Imputation
imputer = SimpleImputer(strategy='median')
X_train_imp = imputer.fit_transform(X_train)
X_val_imp = imputer.transform(X_val)
X_test_imp = imputer.transform(X_test)

# Sample weights
sample_weights = np.sqrt(X_train['arr_flights'].fillna(1).clip(lower=1)).values
sample_weights = np.nan_to_num(sample_weights, nan=1.0)
sample_weights = np.clip(sample_weights, 0.001, None)

# ============================================================================
# 4. Entrainement
# ============================================================================
print("[4/6] Entrainement XGBoost...")

model = XGBClassifier(
    n_estimators=600,
    max_depth=5,
    learning_rate=0.05,
    subsample=0.8,
    colsample_bytree=0.8,
    random_state=42,
    n_jobs=-1,
    use_label_encoder=False,
    eval_metric='logloss'
)

import time
start = time.time()
model.fit(X_train_imp, y_train, sample_weight=sample_weights)
train_time = time.time() - start

print(f"      Entraine en {train_time:.2f} secondes")

# ============================================================================
# 5. Evaluation
# ============================================================================
print("[5/6] Evaluation...")

proba_val = model.predict_proba(X_val_imp)[:, 1]
proba_test = model.predict_proba(X_test_imp)[:, 1]

# Trouver le cutoff optimal pour accuracy
def find_optimal_cutoff_accuracy(y_true, proba):
    best_acc = 0
    best_cutoff = 0.5
    for cutoff in np.arange(0.1, 0.9, 0.01):
        y_pred = (proba >= cutoff).astype(int)
        acc = (y_pred == y_true).mean()
        if acc > best_acc:
            best_acc = acc
            best_cutoff = cutoff
    return best_cutoff, best_acc

optimal_cutoff, val_accuracy = find_optimal_cutoff_accuracy(y_val, proba_val)

# Metriques sur test
y_pred_test = (proba_test >= optimal_cutoff).astype(int)
test_accuracy = (y_pred_test == y_test).mean()
test_roc_auc = roc_auc_score(y_test, proba_test)

tn, fp, fn, tp = confusion_matrix(y_test, y_pred_test).ravel()
precision = tp / (tp + fp) if (tp + fp) > 0 else 0
recall = tp / (tp + fn) if (tp + fn) > 0 else 0
f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

print(f"\n      Cutoff Optimal: {optimal_cutoff:.3f}")
print(f"      Accuracy (Test): {test_accuracy*100:.1f}%")
print(f"      ROC-AUC (Test):  {test_roc_auc:.4f}")
print(f"      Precision:       {precision*100:.1f}%")
print(f"      Recall:          {recall*100:.1f}%")

# ============================================================================
# 6. Sauvegarde
# ============================================================================
print("\n[6/6] Sauvegarde des artefacts...")

# Sauvegarder le modele
joblib.dump(model, OUTPUT_DIR / "model.pkl")
joblib.dump(imputer, OUTPUT_DIR / "imputer.pkl")
joblib.dump(le_carrier, OUTPUT_DIR / "label_encoder_carrier.pkl")
joblib.dump(le_airport, OUTPUT_DIR / "label_encoder_airport.pkl")

# Metriques
metrics = {
    "run_id": datetime.now().strftime('%Y%m%d_%H%M%S'),
    "model_type": "XGBClassifier",
    "target_threshold": TARGET_THRESHOLD,
    "cutoff": optimal_cutoff,
    "feature_columns": FEATURE_COLS,
    "n_features": len(FEATURE_COLS),
    "train_samples": len(X_train),
    "val_samples": len(X_val),
    "test_samples": len(X_test),
    "train_time_seconds": train_time,
    "metrics": {
        "test": {
            "accuracy": float(test_accuracy),
            "roc_auc": float(test_roc_auc),
            "precision": float(precision),
            "recall": float(recall),
            "f1_score": float(f1)
        },
        "val": {
            "accuracy": float(val_accuracy)
        }
    },
    "confusion_matrix": {
        "tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)
    },
    "feature_importance": dict(zip(FEATURE_COLS, model.feature_importances_.tolist()))
}

with open(OUTPUT_DIR / "metrics.json", "w", encoding="utf-8") as f:
    json.dump(metrics, f, indent=2)

print(f"      Modele sauvegarde dans: {OUTPUT_DIR}")

# ============================================================================
# Resume
# ============================================================================
print("\n" + "=" * 70)
print("RESUME")
print("=" * 70)
print(f"""
Modele:      XGBoost Classifier
Features:    {len(FEATURE_COLS)}
Accuracy:    {test_accuracy*100:.1f}%
ROC-AUC:     {test_roc_auc:.4f}
Cutoff:      {optimal_cutoff:.3f}

Fichiers sauvegardes:
   - model.pkl
   - imputer.pkl
   - label_encoder_carrier.pkl
   - label_encoder_airport.pkl
   - metrics.json
""")
print("=" * 70)
print("[OK] ENTRAINEMENT TERMINE!")
print("=" * 70)
