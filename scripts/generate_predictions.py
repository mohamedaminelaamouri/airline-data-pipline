#!/usr/bin/env python3
"""
Generate ML Predictions for Historical Months

This script generates predictions using a trained model for months
that have historical context (lag features available).

Usage:
    python scripts/generate_predictions.py
    python scripts/generate_predictions.py --year 2025 --month 11
    python scripts/generate_predictions.py --run-id 20260125_234947_sklearn
"""

import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

import pandas as pd
from pymongo import MongoClient, ASCENDING, DESCENDING
import click
from loguru import logger

# Add yno-ml to path
YNOML_PATH = Path(__file__).parent.parent / "yno-ml" / "src"
sys.path.insert(0, str(YNOML_PATH))

from yno_ml.alerting import score_month_to_csv, latest_run_dir
from yno_ml.data import CsvSource, load_aggregated_csv

from dotenv import load_dotenv
load_dotenv()

# Configuration
MONGODB_HOST = os.getenv('MONGODB_HOST', 'localhost')
MONGODB_PORT = int(os.getenv('MONGODB_PORT', '27017'))
MONGODB_DATABASE = os.getenv('MONGODB_DATABASE', 'airline_cache')

ML_TEMP_DATA = os.getenv('ML_TEMP_DATA', 'data/temp_ml_train.csv')
ML_ALERTS_CSV = os.getenv('ML_ALERTS_CSV', 'reports/ml_alerts_latest.csv')
ML_MODELS_DIR = os.getenv('ML_MODELS_DIR', 'models/ml_runs')

# Setup logging
os.makedirs("logs", exist_ok=True)
logger.add("logs/ml_predictions.log", rotation="50 MB", retention="30 days")


def get_latest_model_from_mongodb() -> Optional[dict]:
    """Get latest trained model metadata from MongoDB"""
    client = MongoClient(host=MONGODB_HOST, port=MONGODB_PORT, serverSelectionTimeoutMS=5000)
    db = client[MONGODB_DATABASE]
    
    result = db['ml_model_metadata'].find_one(
        sort=[('trained_at', DESCENDING)]
    )
    client.close()
    return result


def get_safe_prediction_month(history_csv: str) -> tuple[int, int]:
    """
    Get a safe month to predict (one that has historical lag context).
    
    Returns the last complete month in the dataset (so lag features are available).
    """
    df = pd.read_csv(history_csv)
    
    # Get last month in dataset
    last_year = int(df['year'].max())
    last_month_df = df[df['year'] == last_year]
    last_month = int(last_month_df['month'].max())
    
    # For safety, predict for the last month in the data
    # (this ensures all lag features are computable)
    logger.info(f"Dataset spans: {df['year'].min()}-{df['month'].min():02d} to {last_year}-{last_month:02d}")
    logger.info(f"Using last month as prediction target: {last_year}-{last_month:02d}")
    
    return last_year, last_month


def generate_predictions(
    year: Optional[int] = None,
    month: Optional[int] = None,
    run_id: Optional[str] = None,
    history_csv: str = ML_TEMP_DATA,
) -> pd.DataFrame:
    """
    Generate predictions for a specific month using trained model.
    
    Args:
        year: Year to predict (if None, uses safe month from history)
        month: Month to predict (if None, uses safe month from history)
        run_id: Model run ID (if None, uses latest from MongoDB)
        history_csv: Path to historical data CSV
    
    Returns:
        DataFrame with predictions
    """
    logger.info("=" * 80)
    logger.info("GENERATING ML PREDICTIONS")
    logger.info("=" * 80)
    
    # Get model
    if run_id:
        run_dir = Path(ML_MODELS_DIR) / run_id
        if not run_dir.exists():
            raise ValueError(f"Model run not found: {run_dir}")
        logger.info(f"Using specified model: {run_id}")
    else:
        model_metadata = get_latest_model_from_mongodb()
        if not model_metadata:
            raise RuntimeError("No trained model found in MongoDB. Train a model first.")
        
        run_id = model_metadata['run_id']
        run_dir = Path(model_metadata['artifacts_path'])
        logger.info(f"Using latest model from MongoDB: {run_id}")
        logger.info(f"  Trained: {model_metadata['trained_at']}")
        logger.info(f"  Test ROC-AUC: {model_metadata['metrics']['test_roc_auc']:.3f}")
    
    cutoff = 0.19  # Default from model training
    
    # Try to get cutoff from model metadata
    if not run_id:
        try:
            model_metadata = get_latest_model_from_mongodb()
            if model_metadata and 'cutoff' in model_metadata:
                cutoff = float(model_metadata['cutoff']['threshold'])
        except:
            pass
    
    logger.info(f"  Using cutoff: {cutoff}")
    
    # Verify history data exists
    if not os.path.exists(history_csv):
        raise FileNotFoundError(
            f"History CSV not found: {history_csv}\n"
            "Run training first: make ml-train"
        )
    
    # Get safe prediction month if not specified
    if year is None or month is None:
        year, month = get_safe_prediction_month(history_csv)
    
    logger.info(f"\nPredicting for: {year}-{month:02d}")
    logger.info(f"History data: {history_csv}")
    logger.info(f"Model: {run_dir}")
    
    # Generate predictions
    out_csv = ML_ALERTS_CSV
    os.makedirs(os.path.dirname(out_csv), exist_ok=True)
    
    try:
        score_month_to_csv(
            year=year,
            month=month,
            cutoff=cutoff,
            history_csv=history_csv,
            run_dir=run_dir,
            out_csv=out_csv,
        )
        
        # Load and enhance predictions
        df = pd.read_csv(out_csv)
        df['risk_score'] = (df['probability'] * 100).round(1)
        df['alert_level'] = pd.cut(
            df['risk_score'],
            bins=[0, 50, 70, 85, 100],
            labels=['low', 'medium', 'high', 'critical']
        )
        
        logger.info("\n" + "=" * 80)
        logger.info(f"✅ Generated {len(df):,} predictions")
        logger.info(f"   High-risk (prediction=1): {(df['prediction'] == 1).sum():,}")
        logger.info(f"   Saved to: {out_csv}")
        logger.info("=" * 80)
        
        return df
        
    except Exception as e:
        logger.error(f"❌ Prediction generation failed: {e}")
        logger.error("\nPossible reasons:")
        logger.error("  1. Predicting for a month without lag context (try earlier month)")
        logger.error("  2. Data quality issues (check for NaN/infinity)")
        logger.error("  3. Model/history data mismatch")
        raise


def save_predictions_to_mongodb(
    df: pd.DataFrame,
    run_id: str,
    year: int,
    month: int,
):
    """Save predictions to MongoDB"""
    logger.info("\nSaving predictions to MongoDB...")
    
    client = MongoClient(host=MONGODB_HOST, port=MONGODB_PORT)
    db = client[MONGODB_DATABASE]
    
    # Prepare documents
    documents = []
    for _, row in df.iterrows():
        doc = {
            'run_id': run_id,
            'carrier': str(row['carrier']),
            'airport': str(row['airport']),
            'prediction_for_year': int(year),
            'prediction_for_month': int(month),
            'probability': float(row['probability']),
            'prediction': int(row['prediction']),
            'risk_score': float(row['risk_score']),
            'alert_level': str(row['alert_level']),
            'created_at': datetime.utcnow(),
        }
        documents.append(doc)
    
    # Clear old predictions for this month
    db['ml_predictions'].delete_many({
        'prediction_for_year': int(year),
        'prediction_for_month': int(month)
    })
    
    # Insert new predictions
    db['ml_predictions'].insert_many(documents)
    logger.info(f"✅ Saved {len(documents):,} predictions to MongoDB")
    
    # Save high-risk alerts
    high_risk = df[df['prediction'] == 1].copy()
    if len(high_risk) > 0:
        alert_documents = []
        for _, row in high_risk.iterrows():
            alert_doc = {
                'run_id': run_id,
                'carrier': str(row['carrier']),
                'airport': str(row['airport']),
                'prediction_for_year': int(year),
                'prediction_for_month': int(month),
                'probability': float(row['probability']),
                'risk_score': float(row['risk_score']),
                'alert_level': str(row['alert_level']),
                'created_at': datetime.utcnow(),
            }
            alert_documents.append(alert_doc)
        
        # Clear old alerts for this month
        db['ml_alerts'].delete_many({
            'prediction_for_year': int(year),
            'prediction_for_month': int(month)
        })
        
        db['ml_alerts'].insert_many(alert_documents)
        logger.info(f"✅ Saved {len(alert_documents):,} high-risk alerts to MongoDB")
    
    client.close()


def show_prediction_summary(df: pd.DataFrame):
    """Display prediction summary statistics"""
    logger.info("\n" + "=" * 80)
    logger.info("PREDICTION SUMMARY")
    logger.info("=" * 80)
    
    logger.info(f"\nTotal Predictions: {len(df):,}")
    logger.info(f"  High-risk (prediction=1): {(df['prediction'] == 1).sum():,} ({(df['prediction'] == 1).mean()*100:.1f}%)")
    logger.info(f"  Low-risk (prediction=0): {(df['prediction'] == 0).sum():,} ({(df['prediction'] == 0).mean()*100:.1f}%)")
    
    logger.info(f"\nRisk Score Distribution:")
    logger.info(f"  Mean: {df['risk_score'].mean():.1f}")
    logger.info(f"  Median: {df['risk_score'].median():.1f}")
    logger.info(f"  Min: {df['risk_score'].min():.1f}")
    logger.info(f"  Max: {df['risk_score'].max():.1f}")
    
    logger.info(f"\nAlert Levels:")
    for level in ['critical', 'high', 'medium', 'low']:
        count = (df['alert_level'] == level).sum()
        pct = count / len(df) * 100
        logger.info(f"  {level.capitalize():8s}: {count:4d} ({pct:5.1f}%)")
    
    logger.info(f"\nTop 10 Highest Risk Routes:")
    top10 = df.nlargest(10, 'risk_score')[['carrier', 'airport', 'risk_score', 'probability', 'alert_level']]
    for i, row in top10.iterrows():
        logger.info(f"  {row['carrier']:3s} → {row['airport']:3s}  |  Risk: {row['risk_score']:5.1f}  |  Prob: {row['probability']:.3f}  |  Level: {row['alert_level']}")
    
    logger.info("=" * 80)


@click.command()
@click.option('--year', type=int, help='Year to predict (default: last month in data)')
@click.option('--month', type=int, help='Month to predict (default: last month in data)')
@click.option('--run-id', type=str, help='Model run ID (default: latest from MongoDB)')
@click.option('--save-to-mongo', is_flag=True, default=True, help='Save predictions to MongoDB (default: True)')
@click.option('--history-csv', type=str, default=ML_TEMP_DATA, help=f'Path to history CSV (default: {ML_TEMP_DATA})')
def main(year, month, run_id, save_to_mongo, history_csv):
    """
    Generate ML predictions for a specific month.
    
    Examples:
        # Use last month in dataset + latest model
        python scripts/generate_predictions.py
        
        # Specify month
        python scripts/generate_predictions.py --year 2025 --month 10
        
        # Use specific model
        python scripts/generate_predictions.py --run-id 20260125_234947_sklearn
        
        # Don't save to MongoDB (CSV only)
        python scripts/generate_predictions.py --no-save-to-mongo
    """
    try:
        # Generate predictions
        df = generate_predictions(
            year=year,
            month=month,
            run_id=run_id,
            history_csv=history_csv,
        )
        
        # Show summary
        show_prediction_summary(df)
        
        # Save to MongoDB
        if save_to_mongo:
            # Get run_id if not specified
            if not run_id:
                model_metadata = get_latest_model_from_mongodb()
                run_id = model_metadata['run_id']
            
            # Get year/month if not specified
            if year is None or month is None:
                year, month = get_safe_prediction_month(history_csv)
            
            save_predictions_to_mongodb(df, run_id, year, month)
        
        logger.info("\n✅ Prediction generation completed successfully!")
        logger.info(f"   CSV: {ML_ALERTS_CSV}")
        if save_to_mongo:
            logger.info(f"   MongoDB: ml_predictions, ml_alerts collections")
        
    except Exception as e:
        logger.error(f"\n❌ Failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
