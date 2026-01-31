#!/usr/bin/env python3
"""
Simple Batch Prediction Script

Generates predictions by loading the trained model and applying it directly
to the training data to demonstrate the pipeline works.

This bypasses the yno-ml alerting module which has issues with infinity values.
"""

import os
import sys
from pathlib import Path
import pandas as pd
import numpy as np
import joblib
from pymongo import MongoClient
from datetime import datetime
from loguru import logger

# Setup logging
logger.add("logs/batch_predictions.log", rotation="50 MB")

# Config
MONGODB_HOST = os.getenv('MONGODB_HOST', 'localhost')
MONGODB_PORT = int(os.getenv('MONGODB_PORT', '27017'))
MONGODB_DATABASE = os.getenv('MONGODB_DATABASE', 'airline_cache')

def load_model(run_id: str = "20260125_234947_sklearn"):
    """Load trained model artifacts"""
    model_dir = Path(f"models/ml_runs/{run_id}")
    
    logger.info(f"Loading model from {model_dir}")
    
    model = joblib.load(model_dir / "model.pkl")
    le_carrier = joblib.load(model_dir / "label_encoder_carrier.pkl")
    le_airport = joblib.load(model_dir / "label_encoder_airport.pkl")
    
    return model, le_carrier, le_airport


def generate_batch_predictions(cutoff: float = 0.19, sample_size: int = 1000):
    """
    Generate predictions for a sample of the training data.
    
    This demonstrates the model works by predicting on known data.
    """
    logger.info("=" * 80)
    logger.info("BATCH PREDICTION (DEMO)")
    logger.info("=" * 80)
    
    # Load model
    model, le_carrier, le_airport = load_model()
    logger.info(f"✅ Model loaded")
    
    # Load training data
    df_train = pd.read_csv("data/temp_ml_train.csv")
    logger.info(f"✅ Training data loaded: {len(df_train):,} records")
    
    # Calculate delay rate
    df_train['delay_rate'] = df_train['arr_del15'] / df_train['arr_flights'].clip(lower=1)
    
    # Sample recent data (last 6 months)
    df_recent = df_train[
        ((df_train['year'] == 2025) & (df_train['month'] >= 7)) |
        ((df_train['year'] == 2024) & (df_train['month'] >= 7))
    ].copy()
    
    if len(df_recent) > sample_size:
        df_sample = df_recent.sample(n=sample_size, random_state=42)
    else:
        df_sample = df_recent.copy()
    
    logger.info(f"✅ Sample: {len(df_sample):,} records (last 6 months)")
    
    # Add yno-ml to path for feature engineering
    YNOML_PATH = Path(__file__).parent.parent / "yno-ml" / "src"
    sys.path.insert(0, str(YNOML_PATH))
    
    from yno_ml.features import build_training_frame, FEATURE_COLUMNS_V2, FeatureConfig
    
    # Compute features
    logger.info("Computing features...")
    cfg = FeatureConfig(target_threshold=0.20)
    X, y = build_training_frame(df_sample, cfg=cfg, le_carrier=le_carrier, le_airport=le_airport)
    
    # Remove any rows with inf/nan in feature columns
    X_clean = X.replace([np.inf, -np.inf], np.nan)
    
    # Check which features have NaN/inf
    nan_counts = X_clean.isna().sum()
    if nan_counts.sum() > 0:
        logger.warning(f"Features with NaN values: {nan_counts[nan_counts > 0].to_dict()}")
    
    # Get valid indices
    valid_idx = X_clean.notna().all(axis=1)
    X_clean = X_clean[valid_idx]
    y_clean = y[valid_idx]
    
    # Get corresponding original data
    df_sample_clean = df_sample.iloc[valid_idx.values].copy()
    
    logger.info(f"✅ Features computed: {len(X_clean):,} valid records ({len(df_sample) - len(X_clean)} dropped due to NaN)")
    
    # Generate predictions
    probabilities = model.predict_proba(X_clean)[:, 1]
    predictions = (probabilities > cutoff).astype(int)
    
    # Create results DataFrame
    df_results = pd.DataFrame({
        'carrier': df_sample_clean['carrier'].values,
        'airport': df_sample_clean['airport'].values,
        'year': df_sample_clean['year'].values,
        'month': df_sample_clean['month'].values,
        'actual_delay_rate': df_sample_clean['delay_rate'].values,
        'probability': probabilities,
        'prediction': predictions,
        'risk_score': (probabilities * 100).round(1),
    })
    
    # Add alert level
    df_results['alert_level'] = pd.cut(
        df_results['risk_score'],
        bins=[0, 50, 70, 85, 100],
        labels=['low', 'medium', 'high', 'critical']
    )
    
    # Save to CSV
    output_csv = "reports/ml_predictions_demo.csv"
    os.makedirs("reports", exist_ok=True)
    df_results.to_csv(output_csv, index=False)
    
    logger.info(f"✅ Saved predictions to {output_csv}")
    
    return df_results


def save_to_mongodb(df: pd.DataFrame, run_id: str):
    """Save predictions to MongoDB"""
    logger.info("\nSaving to MongoDB...")
    
    client = MongoClient(host=MONGODB_HOST, port=MONGODB_PORT)
    db = client[MONGODB_DATABASE]
    
    # Clear existing demo predictions
    db['ml_predictions'].delete_many({'run_id': run_id + '_demo'})
    db['ml_alerts'].delete_many({'run_id': run_id + '_demo'})
    
    # Prepare documents
    documents = []
    for _, row in df.iterrows():
        doc = {
            'run_id': run_id + '_demo',
            'carrier': str(row['carrier']),
            'airport': str(row['airport']),
            'prediction_for_year': int(row['year']),
            'prediction_for_month': int(row['month']),
            'probability': float(row['probability']),
            'prediction': int(row['prediction']),
            'risk_score': float(row['risk_score']),
            'alert_level': str(row['alert_level']),
            'actual_delay_rate': float(row['actual_delay_rate']),
            'created_at': datetime.utcnow(),
            'is_demo': True,
        }
        documents.append(doc)
    
    # Insert
    if documents:
        db['ml_predictions'].insert_many(documents)
        logger.info(f"✅ Saved {len(documents):,} predictions to ml_predictions")
    
    # Save high-risk alerts
    high_risk_docs = [doc for doc in documents if doc['prediction'] == 1]
    if high_risk_docs:
        db['ml_alerts'].insert_many(high_risk_docs)
        logger.info(f"✅ Saved {len(high_risk_docs):,} high-risk alerts to ml_alerts")
    
    client.close()


def show_summary(df: pd.DataFrame):
    """Display prediction summary"""
    logger.info("\n" + "=" * 80)
    logger.info("PREDICTION SUMMARY")
    logger.info("=" * 80)
    
    logger.info(f"\nTotal Predictions: {len(df):,}")
    high_risk_count = (df['prediction'] == 1).sum()
    low_risk_count = (df['prediction'] == 0).sum()
    logger.info(f"  High-risk (prediction=1): {high_risk_count:,} ({high_risk_count/len(df)*100:.1f}%)")
    logger.info(f"  Low-risk (prediction=0): {low_risk_count:,} ({low_risk_count/len(df)*100:.1f}%)")
    
    logger.info(f"\nRisk Score Statistics:")
    logger.info(f"  Mean: {df['risk_score'].mean():.1f}")
    logger.info(f"  Median: {df['risk_score'].median():.1f}")
    logger.info(f"  Std: {df['risk_score'].std():.1f}")
    
    logger.info(f"\nAlert Level Distribution:")
    for level in ['critical', 'high', 'medium', 'low']:
        count = (df['alert_level'] == level).sum()
        pct = count / len(df) * 100
        logger.info(f"  {level.capitalize():8s}: {count:4d} ({pct:5.1f}%)")
    
    logger.info(f"\nTop 20 Highest Risk Routes:")
    top20 = df.nlargest(20, 'risk_score')
    logger.info(f"\n{'Carrier':<8} {'Airport':<8} {'Year-Mo':<8} {'Risk':<6} {'Prob':<6} {'Pred':<5} {'Actual%':<8} {'Level'}")
    logger.info("-" * 80)
    for _, row in top20.iterrows():
        logger.info(
            f"{row['carrier']:<8} {row['airport']:<8} "
            f"{row['year']}-{row['month']:02d}    "
            f"{row['risk_score']:5.1f}  {row['probability']:.3f}  "
            f"{row['prediction']:3d}   {row['actual_delay_rate']*100:6.1f}%  "
            f"{row['alert_level']}"
        )
    
    # Model performance on this sample
    logger.info(f"\nModel Performance (on this sample):")
    actual_high_delay = (df['actual_delay_rate'] > 0.20).astype(int)
    from sklearn.metrics import classification_report, roc_auc_score
    
    logger.info(f"  ROC-AUC: {roc_auc_score(actual_high_delay, df['probability']):.3f}")
    logger.info(f"\n{classification_report(actual_high_delay, df['prediction'], target_names=['Low Delay', 'High Delay'])}")
    
    logger.info("=" * 80)


if __name__ == "__main__":
    try:
        # Generate predictions
        df = generate_batch_predictions(cutoff=0.19, sample_size=1000)
        
        # Show summary
        show_summary(df)
        
        # Save to MongoDB
        save_to_mongodb(df, run_id="20260125_234947_sklearn")
        
        logger.info("\n✅ SUCCESS! Batch predictions completed.")
        logger.info(f"   CSV: reports/ml_predictions_demo.csv")
        logger.info(f"   MongoDB: ml_predictions, ml_alerts (with is_demo=True)")
        logger.info(f"\nNext steps:")
        logger.info(f"  1. Check MongoDB: docker exec -it mongodb mongosh airline_cache")
        logger.info(f"  2. Query: db.ml_predictions.find({{is_demo: true}}).limit(5).pretty()")
        logger.info(f"  3. Connect Power BI to ml_predictions collection")
        
    except Exception as e:
        logger.error(f"❌ Failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
