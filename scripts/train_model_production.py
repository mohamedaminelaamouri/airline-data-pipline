#!/usr/bin/env python3
"""
Production ML Training Script (v3)
===================================
Trains XGBoost model using pre-computed features from ClickHouse gold_ml_features.

IMPORTANT: This script does NO feature engineering.
All features are pre-computed in ClickHouse via medallion_pipeline.py.

Features used (from gold_ml_features):
- carrier_id, airport_id: Hash-based categorical encoding
- month_sin, month_cos: Cyclical month encoding
- is_summer, is_winter, is_holiday_season: Seasonal indicators
- pair_lag1, pair_lag3_mean, pair_expanding_mean: Pair-level lags
- airport_lag1, airport_lag3_mean, airport_expanding_mean: Airport-level lags
- carrier_lag1, carrier_lag3_mean, carrier_expanding_mean: Carrier-level lags
- log_arr_flights: Log-transformed flight count
- is_delayed: Target variable (1 if delay_rate > 0.20)

Usage:
    python scripts/train_model_production.py
"""
import os
import sys
import json
import time
from datetime import datetime
from pathlib import Path

import clickhouse_connect
import joblib
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    roc_auc_score, average_precision_score, confusion_matrix, 
    classification_report
)
from sklearn.pipeline import Pipeline
from xgboost import XGBClassifier


# =============================================================================
# CONFIGURATION
# =============================================================================

# Feature columns (must match gold_ml_features schema)
FEATURE_COLUMNS = [
    "year", "month", "month_sin", "month_cos",
    "is_summer", "is_winter", "is_holiday_season",
    "carrier_id", "airport_id",
    "arr_flights", "log_arr_flights",
    "pair_lag1", "pair_lag3_mean", "pair_expanding_mean",
    "airport_lag1", "airport_lag3_mean", "airport_expanding_mean",
    "carrier_lag1", "carrier_lag3_mean", "carrier_expanding_mean",
]

TARGET_COLUMN = "is_delayed"
TARGET_THRESHOLD = 0.20  # delay_rate threshold for classification

# Output paths
PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_DIR = PROJECT_ROOT / "ml" / "models" / "runs" / "production"


def get_clickhouse_client():
    """Connect to ClickHouse."""
    return clickhouse_connect.get_client(
        host=os.getenv('CLICKHOUSE_HOST', 'localhost'),
        port=int(os.getenv('CLICKHOUSE_HTTP_PORT', '8123')),
        database='airline_data'
    )


def load_data_from_clickhouse(client):
    """
    Load pre-computed features from ClickHouse gold_ml_features.
    No feature engineering - just SELECT.
    """
    print("\n[1/6] Loading data from ClickHouse gold_ml_features...")
    
    # Build column list
    all_columns = FEATURE_COLUMNS + [TARGET_COLUMN, 'delay_rate']
    columns_sql = ', '.join(all_columns)
    
    query = f"""
    SELECT {columns_sql}
    FROM gold_ml_features
    WHERE year >= 2003
    ORDER BY year, month, carrier_id, airport_id
    """
    
    data = client.query_df(query)
    
    print(f"   ✅ Loaded {len(data):,} records")
    print(f"   ✅ Period: {data['year'].min()} - {data['year'].max()}")
    print(f"   ✅ Features: {len(FEATURE_COLUMNS)}")
    
    # Data quality check
    null_counts = data[FEATURE_COLUMNS].isnull().sum()
    if null_counts.any():
        print(f"\n   ⚠️ Null values detected:")
        for col, count in null_counts[null_counts > 0].items():
            print(f"      {col}: {count:,} nulls")
    
    return data


def temporal_split(data, train_ratio=0.70, val_ratio=0.20):
    """
    Temporal train/validation/test split.
    Respects time order to prevent data leakage.
    """
    print("\n[2/6] Temporal train/val/test split...")
    
    # Create period index for temporal ordering
    data = data.copy()
    data['period'] = data['year'] * 12 + data['month']
    
    # Get unique periods in order
    unique_periods = sorted(data['period'].unique())
    n_periods = len(unique_periods)
    
    # Calculate split points
    n_train = int(n_periods * train_ratio)
    n_val = int(n_periods * val_ratio)
    
    train_periods = set(unique_periods[:n_train])
    val_periods = set(unique_periods[n_train:n_train + n_val])
    test_periods = set(unique_periods[n_train + n_val:])
    
    # Create masks
    train_mask = data['period'].isin(train_periods)
    val_mask = data['period'].isin(val_periods)
    test_mask = data['period'].isin(test_periods)
    
    print(f"   Train: {train_mask.sum():,} samples ({train_mask.mean()*100:.1f}%)")
    print(f"   Val:   {val_mask.sum():,} samples ({val_mask.mean()*100:.1f}%)")
    print(f"   Test:  {test_mask.sum():,} samples ({test_mask.mean()*100:.1f}%)")
    
    # Split data
    X_train = data.loc[train_mask, FEATURE_COLUMNS]
    y_train = data.loc[train_mask, TARGET_COLUMN]
    
    X_val = data.loc[val_mask, FEATURE_COLUMNS]
    y_val = data.loc[val_mask, TARGET_COLUMN]
    
    X_test = data.loc[test_mask, FEATURE_COLUMNS]
    y_test = data.loc[test_mask, TARGET_COLUMN]
    
    # Class balance
    print(f"\n   Class balance (is_delayed=1):")
    print(f"   Train: {y_train.mean()*100:.1f}%")
    print(f"   Val:   {y_val.mean()*100:.1f}%")
    print(f"   Test:  {y_test.mean()*100:.1f}%")
    
    return (X_train, y_train), (X_val, y_val), (X_test, y_test), data.loc[train_mask, 'arr_flights']


def train_model(X_train, y_train, sample_weights):
    """Train XGBoost classifier with sample weighting."""
    print("\n[3/6] Training XGBoost classifier...")
    
    # Clean sample weights
    sample_weights = np.nan_to_num(sample_weights, nan=1.0)
    sample_weights = np.sqrt(np.clip(sample_weights, 1, None))
    
    # Pipeline with imputation + XGBoost
    pipeline = Pipeline([
        ('imputer', SimpleImputer(strategy='median')),
        ('model', XGBClassifier(
            n_estimators=600,
            max_depth=5,
            learning_rate=0.05,
            subsample=0.9,
            colsample_bytree=0.9,
            reg_lambda=1.0,
            random_state=42,
            n_jobs=-1,
            eval_metric='logloss',
            use_label_encoder=False
        ))
    ])
    
    # Train
    start = time.time()
    pipeline.fit(X_train, y_train, model__sample_weight=sample_weights)
    train_time = time.time() - start
    
    print(f"   ✅ Model trained in {train_time:.2f}s")
    
    return pipeline, train_time


def evaluate_model(pipeline, X_train, y_train, X_val, y_val, X_test, y_test):
    """Evaluate model on all splits."""
    print("\n[4/6] Evaluating model...")
    
    results = {}
    
    for name, X, y in [('train', X_train, y_train), 
                       ('val', X_val, y_val), 
                       ('test', X_test, y_test)]:
        proba = pipeline.predict_proba(X)[:, 1]
        
        results[name] = {
            'roc_auc': roc_auc_score(y, proba),
            'pr_auc': average_precision_score(y, proba),
            'n_samples': len(y),
            'positive_rate': float(y.mean())
        }
        
        print(f"   {name.capitalize():6} - ROC-AUC: {results[name]['roc_auc']:.4f}, "
              f"PR-AUC: {results[name]['pr_auc']:.4f}")
    
    # Find optimal cutoff for accuracy on validation
    best_cutoff = 0.5
    best_acc = 0
    proba_val = pipeline.predict_proba(X_val)[:, 1]
    
    for cutoff in np.arange(0.1, 0.9, 0.01):
        acc = ((proba_val >= cutoff) == y_val).mean()
        if acc > best_acc:
            best_acc = acc
            best_cutoff = cutoff
    
    results['optimal_cutoff'] = float(best_cutoff)
    results['val_accuracy_at_cutoff'] = float(best_acc)
    
    print(f"\n   Optimal cutoff: {best_cutoff:.3f} (accuracy: {best_acc:.4f})")
    
    # Test metrics at optimal cutoff
    proba_test = pipeline.predict_proba(X_test)[:, 1]
    y_pred_test = (proba_test >= best_cutoff).astype(int)
    
    tn, fp, fn, tp = confusion_matrix(y_test, y_pred_test).ravel()
    
    results['test_detailed'] = {
        'TP': int(tp), 'TN': int(tn), 'FP': int(fp), 'FN': int(fn),
        'accuracy': float((tp + tn) / (tp + tn + fp + fn)),
        'precision': float(tp / (tp + fp)) if (tp + fp) > 0 else 0,
        'recall': float(tp / (tp + fn)) if (tp + fn) > 0 else 0,
        'f1': float(2 * tp / (2 * tp + fp + fn)) if (2 * tp + fp + fn) > 0 else 0
    }
    
    print(f"\n   Test @ cutoff {best_cutoff:.2f}:")
    print(f"   Accuracy:  {results['test_detailed']['accuracy']:.4f}")
    print(f"   Precision: {results['test_detailed']['precision']:.4f}")
    print(f"   Recall:    {results['test_detailed']['recall']:.4f}")
    print(f"   F1-Score:  {results['test_detailed']['f1']:.4f}")
    
    return results


def get_feature_importance(pipeline, feature_columns):
    """Extract feature importance from XGBoost model."""
    xgb_model = pipeline.named_steps['model']
    
    importance = pd.DataFrame({
        'feature': feature_columns,
        'importance': xgb_model.feature_importances_
    }).sort_values('importance', ascending=False)
    
    return importance


def save_model(pipeline, metrics, feature_importance, train_time):
    """Save model, metrics, and artifacts."""
    print("\n[5/6] Saving model and artifacts...")
    
    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    run_id = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Save model
    model_path = OUTPUT_DIR / "xgboost_classifier.pkl"
    joblib.dump(pipeline, model_path)
    print(f"   ✅ Model saved: {model_path}")
    
    # Save metrics and config
    output = {
        'run_id': run_id,
        'feature_version': 'v3',
        'feature_columns': FEATURE_COLUMNS,
        'target_column': TARGET_COLUMN,
        'target_threshold': TARGET_THRESHOLD,
        'train_time_seconds': train_time,
        'metrics': metrics,
        'feature_importance': feature_importance.to_dict('records'),
        'notes': 'Features computed in ClickHouse. No LabelEncoder - uses hash-based IDs.'
    }
    
    metrics_path = OUTPUT_DIR / "metrics.json"
    with open(metrics_path, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"   ✅ Metrics saved: {metrics_path}")
    
    # Save feature columns for serving layer verification
    feature_config = {
        'feature_columns': FEATURE_COLUMNS,
        'feature_version': 'v3'
    }
    config_path = OUTPUT_DIR / "feature_config.json"
    with open(config_path, 'w') as f:
        json.dump(feature_config, f, indent=2)
    print(f"   ✅ Feature config saved: {config_path}")
    
    return run_id


def main():
    print("=" * 80)
    print("PRODUCTION ML TRAINING - ClickHouse Feature Store")
    print("=" * 80)
    print(f"Feature version: v3 (ClickHouse pre-computed)")
    print(f"Output directory: {OUTPUT_DIR}")
    
    # Connect to ClickHouse
    client = get_clickhouse_client()
    
    # Load data
    data = load_data_from_clickhouse(client)
    
    # Split
    (X_train, y_train), (X_val, y_val), (X_test, y_test), arr_flights = temporal_split(data)
    
    # Train
    pipeline, train_time = train_model(X_train, y_train, arr_flights)
    
    # Evaluate
    metrics = evaluate_model(pipeline, X_train, y_train, X_val, y_val, X_test, y_test)
    
    # Feature importance
    feature_importance = get_feature_importance(pipeline, FEATURE_COLUMNS)
    
    print("\n   Top 5 Features:")
    for i, row in feature_importance.head(5).iterrows():
        print(f"   {i+1}. {row['feature']}: {row['importance']:.4f}")
    
    # Save
    run_id = save_model(pipeline, metrics, feature_importance, train_time)
    
    # Summary
    print("\n[6/6] Training Complete!")
    print("=" * 80)
    print(f"""
Summary:
   Run ID: {run_id}
   Features: {len(FEATURE_COLUMNS)} (version v3)
   Train samples: {len(X_train):,}
   Test ROC-AUC: {metrics['test']['roc_auc']:.4f}
   Test Accuracy: {metrics['test_detailed']['accuracy']:.4f}
   Optimal Cutoff: {metrics['optimal_cutoff']:.3f}
   
Model files:
   - xgboost_classifier.pkl
   - metrics.json
   - feature_config.json
   
Ready for serving!
""")
    print("=" * 80)


if __name__ == "__main__":
    main()
