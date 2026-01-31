"""
Script 3: ML Training Pipeline
MongoDB → XGBoost Training → Predictions → MongoDB

This script:
1. Loads aggregated data from ClickHouse (via MongoDB or direct)
2. Trains XGBoost model using yno-ml pipeline
3. Generates predictions/alerts for next month
4. Saves predictions and model metrics to MongoDB
5. Exports alerts to CSV for Power BI

Run daily via cron/Task Scheduler to keep models fresh.
"""

import os
import sys
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional

import pandas as pd
from pymongo import MongoClient, ASCENDING, DESCENDING
import click

# Add yno-ml to Python path
YNOML_PATH = Path(__file__).parent.parent / "yno-ml" / "src"
if YNOML_PATH.exists():
    sys.path.insert(0, str(YNOML_PATH))

try:
    from yno_ml.mongo_source import load_from_clickhouse_via_pymongo
    from yno_ml.train import train_from_csv, TrainConfig, save_run
    from yno_ml.alerting import score_month_to_csv, latest_run_dir
    from yno_ml.data import CsvSource, load_aggregated_csv
except ImportError as e:
    print(f"❌ Error importing yno-ml: {e}")
    print(f"   Make sure yno-ml is in: {YNOML_PATH}")
    sys.exit(1)

from loguru import logger
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
CLICKHOUSE_HOST = os.getenv('CLICKHOUSE_HOST', 'localhost')
CLICKHOUSE_PORT = int(os.getenv('CLICKHOUSE_HTTP_PORT', '8123'))
CLICKHOUSE_DATABASE = os.getenv('CLICKHOUSE_DATABASE', 'airline_data')

MONGODB_HOST = os.getenv('MONGODB_HOST', 'localhost')
MONGODB_PORT = int(os.getenv('MONGODB_PORT', '27017'))
MONGODB_DATABASE = os.getenv('MONGODB_DATABASE', 'airline_cache')

# ML Configuration
ML_MODELS_DIR = os.getenv('ML_MODELS_DIR', 'models/ml_runs')
ML_TEMP_DATA = os.getenv('ML_TEMP_DATA', 'data/temp_ml_train.csv')
ML_ALERTS_CSV = os.getenv('ML_ALERTS_CSV', 'reports/ml_alerts_latest.csv')

# Setup logging
os.makedirs("logs", exist_ok=True)
logger.add("logs/ml_training.log", rotation="100 MB", retention="30 days")


class MLTrainingPipeline:
    """Orchestrates ML training using yno-ml with ynov-data-pipeline data"""
    
    def __init__(self):
        self.mongo_client = None
        self.db = None
        self.initialize_mongodb()
        
    def initialize_mongodb(self):
        """Initialize MongoDB connection"""
        self.mongo_client = MongoClient(
            host=MONGODB_HOST,
            port=MONGODB_PORT,
            serverSelectionTimeoutMS=5000
        )
        self.db = self.mongo_client[MONGODB_DATABASE]
        
        # Create collections and indexes for ML outputs
        self._setup_ml_collections()
        
        logger.info(f"MongoDB initialized: {MONGODB_HOST}:{MONGODB_PORT}")
    
    def _setup_ml_collections(self):
        """Setup MongoDB collections for ML artifacts"""
        
        # Collection 1: ML Model Metadata
        ml_models = self.db['ml_model_metadata']
        ml_models.create_index([('run_id', ASCENDING)])
        ml_models.create_index([('trained_at', DESCENDING)])
        ml_models.create_index([('model_type', ASCENDING)])
        
        # Collection 2: ML Predictions
        ml_predictions = self.db['ml_predictions']
        ml_predictions.create_index([('carrier', ASCENDING), ('airport', ASCENDING)])
        ml_predictions.create_index([('prediction_for_year', ASCENDING), ('prediction_for_month', ASCENDING)])
        ml_predictions.create_index([('risk_score', DESCENDING)])
        ml_predictions.create_index([('created_at', DESCENDING)])
        
        # Collection 3: ML Alerts (high-risk predictions)
        ml_alerts = self.db['ml_alerts']
        ml_alerts.create_index([('carrier', ASCENDING), ('airport', ASCENDING)])
        ml_alerts.create_index([('risk_score', DESCENDING)])
        ml_alerts.create_index([('created_at', DESCENDING)])
        ml_alerts.create_index([('alert_level', ASCENDING)])
        
        logger.info("ML collections and indexes created")
    
    def extract_training_data(
        self,
        min_year: Optional[int] = None,
        max_year: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Extract training data from ClickHouse.
        
        We load directly from ClickHouse instead of MongoDB because:
        1. ClickHouse has complete temporal data (2003-2025)
        2. MongoDB cache is for dashboards, not full ML training dataset
        3. Faster to query ClickHouse than reconstruct from MongoDB aggregates
        """
        logger.info(f"Extracting training data from ClickHouse...")
        logger.info(f"  Years: {min_year or 'ALL'} - {max_year or 'ALL'}")
        
        df = load_from_clickhouse_via_pymongo(
            host=CLICKHOUSE_HOST,
            port=CLICKHOUSE_PORT,
            database=CLICKHOUSE_DATABASE,
            min_year=min_year,
            max_year=max_year,
        )
        
        logger.info(f"✅ Extracted {len(df):,} records")
        logger.info(f"  Date range: {df['year'].min()}-{df['month'].min():02d} to {df['year'].max()}-{df['month'].max():02d}")
        logger.info(f"  Unique carriers: {df['carrier'].nunique()}")
        logger.info(f"  Unique airports: {df['airport'].nunique()}")
        
        return df
    
    def save_training_data_temp(self, df: pd.DataFrame, path: str):
        """Save training data to temporary CSV for yno-ml"""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        df.to_csv(path, index=False)
        logger.info(f"Saved training data to {path}")
    
    def train_model(
        self,
        data_path: str,
        target_threshold: float = 0.20,
        min_recall: float = 0.90,
        n_estimators: int = 600,
    ) -> Dict[str, Any]:
        """Train XGBoost model using yno-ml"""
        
        logger.info("=" * 80)
        logger.info("Starting ML training...")
        logger.info("=" * 80)
        
        cfg = TrainConfig(
            target_threshold=target_threshold,
            sample_weight="sqrt_flights",
            n_estimators=n_estimators,
            max_depth=5,
            learning_rate=0.05,
            subsample=0.9,
            colsample_bytree=0.9,
            reg_lambda=1.0,
            random_state=42,
            min_recall=min_recall,
        )
        
        start_time = time.time()
        result = train_from_csv(data_path=data_path, cfg=cfg)
        training_seconds = time.time() - start_time
        
        # Save model artifacts
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_sklearn"
        out_dir = os.path.join(ML_MODELS_DIR, run_id)
        
        save_run(
            result=result,
            out_dir=out_dir,
            data_path=data_path,
            cfg=cfg,
        )
        
        logger.info("=" * 80)
        logger.info(f"✅ Training completed in {training_seconds:.1f}s")
        logger.info(f"   Model saved to: {out_dir}")
        logger.info(f"   Val ROC-AUC: {result['metrics']['val']['roc_auc']:.3f}")
        logger.info(f"   Test ROC-AUC: {result['metrics']['test']['roc_auc']:.3f}")
        logger.info(f"   Recommended cutoff: {result['cutoff']['thr']:.3f}")
        logger.info("=" * 80)
        
        return {
            'run_id': run_id,
            'run_dir': out_dir,
            'result': result,
            'cfg': cfg,
            'training_seconds': training_seconds,
        }
    
    def save_model_metadata_to_mongodb(self, training_result: Dict[str, Any]):
        """Save model metadata to MongoDB"""
        
        run_id = training_result['run_id']
        result = training_result['result']
        cfg = training_result['cfg']
        
        metadata = {
            '_id': run_id,
            'run_id': run_id,
            'model_type': 'xgboost_delay_classifier',
            'backend': 'sklearn',
            'trained_at': datetime.utcnow(),
            'training_seconds': training_result['training_seconds'],
            'config': {
                'target_threshold': cfg.target_threshold,
                'sample_weight': cfg.sample_weight,
                'n_estimators': cfg.n_estimators,
                'max_depth': cfg.max_depth,
                'learning_rate': cfg.learning_rate,
                'min_recall': cfg.min_recall,
            },
            'splits': result['splits'],
            'metrics': {
                'val_roc_auc': result['metrics']['val']['roc_auc'],
                'val_pr_auc': result['metrics']['val']['pr_auc'],
                'test_roc_auc': result['metrics']['test']['roc_auc'],
                'test_pr_auc': result['metrics']['test']['pr_auc'],
                'test_recall': result['cutoff']['test_at_cutoff']['rec1'],
                'test_precision': result['cutoff']['test_at_cutoff']['prec1'],
                'test_f1': result['cutoff']['test_at_cutoff']['f1_1'],
            },
            'cutoff': {
                'threshold': result['cutoff']['thr'],
                'policy': result['cutoff']['policy'],
                'min_recall_constraint': result['cutoff']['min_recall'],
            },
            'artifacts_path': training_result['run_dir'],
        }
        
        self.db['ml_model_metadata'].replace_one(
            {'_id': run_id},
            metadata,
            upsert=True
        )
        
        logger.info(f"✅ Model metadata saved to MongoDB: {run_id}")
    
    def generate_alerts(
        self,
        run_dir: str,
        history_csv: str,
        cutoff: float,
        prediction_year: int,
        prediction_month: int,
    ) -> pd.DataFrame:
        """Generate predictions/alerts for next month"""
        
        logger.info("=" * 80)
        logger.info(f"Generating predictions for {prediction_year}-{prediction_month:02d}...")
        logger.info("=" * 80)
        
        # Use yno-ml alerting
        out_csv = ML_ALERTS_CSV
        os.makedirs(os.path.dirname(out_csv), exist_ok=True)
        
        score_month_to_csv(
            year=prediction_year,
            month=prediction_month,
            cutoff=cutoff,
            history_csv=history_csv,
            run_dir=Path(run_dir),
            out_csv=out_csv,
        )
        
        # Load predictions
        df_predictions = pd.read_csv(out_csv)
        
        logger.info(f"✅ Generated {len(df_predictions):,} predictions")
        logger.info(f"   Saved to: {out_csv}")
        
        # Calculate risk_score (0-100)
        df_predictions['risk_score'] = (df_predictions['probability'] * 100).round(1)
        
        # Add alert_level based on risk_score
        df_predictions['alert_level'] = pd.cut(
            df_predictions['risk_score'],
            bins=[0, 50, 70, 85, 100],
            labels=['low', 'medium', 'high', 'critical']
        )
        
        return df_predictions
    
    def save_predictions_to_mongodb(
        self,
        df_predictions: pd.DataFrame,
        run_id: str,
        prediction_year: int,
        prediction_month: int,
    ):
        """Save predictions to MongoDB"""
        
        # Prepare documents
        documents = []
        for _, row in df_predictions.iterrows():
            doc = {
                'run_id': run_id,
                'carrier': str(row['carrier']),
                'airport': str(row['airport']),
                'prediction_for_year': prediction_year,
                'prediction_for_month': prediction_month,
                'probability': float(row['probability']),
                'prediction': int(row['prediction']),
                'risk_score': float(row['risk_score']),
                'alert_level': str(row['alert_level']),
                'created_at': datetime.utcnow(),
            }
            documents.append(doc)
        
        # Insert predictions
        self.db['ml_predictions'].insert_many(documents)
        logger.info(f"✅ Saved {len(documents):,} predictions to MongoDB")
        
        # Save high-risk alerts (prediction=1) separately
        high_risk = df_predictions[df_predictions['prediction'] == 1].copy()
        
        if len(high_risk) > 0:
            alert_documents = []
            for _, row in high_risk.iterrows():
                alert_doc = {
                    'run_id': run_id,
                    'carrier': str(row['carrier']),
                    'airport': str(row['airport']),
                    'prediction_for_year': prediction_year,
                    'prediction_for_month': prediction_month,
                    'probability': float(row['probability']),
                    'risk_score': float(row['risk_score']),
                    'alert_level': str(row['alert_level']),
                    'created_at': datetime.utcnow(),
                }
                alert_documents.append(alert_doc)
            
            self.db['ml_alerts'].insert_many(alert_documents)
            logger.info(f"✅ Saved {len(alert_documents):,} high-risk alerts to MongoDB")
    
    def run_full_pipeline(
        self,
        min_year: Optional[int] = None,
        max_year: Optional[int] = None,
        prediction_year: Optional[int] = None,
        prediction_month: Optional[int] = None,
        skip_predictions: bool = False,
    ):
        """Run complete ML pipeline: extract → train → predict → save"""
        
        logger.info("=" * 80)
        logger.info("STARTING ML TRAINING PIPELINE")
        logger.info("=" * 80)
        
        # Default to next month for predictions
        if prediction_year is None or prediction_month is None:
            now = datetime.now()
            next_month = now + timedelta(days=32)
            prediction_year = next_month.year
            prediction_month = next_month.month
        
        try:
            # Step 1: Extract training data from ClickHouse
            df = self.extract_training_data(min_year=min_year, max_year=max_year)
            
            # Step 2: Save to temporary CSV
            self.save_training_data_temp(df, ML_TEMP_DATA)
            
            # Step 3: Train model
            training_result = self.train_model(
                data_path=ML_TEMP_DATA,
                target_threshold=0.20,
                min_recall=0.90,
                n_estimators=600,
            )
            
            # Step 4: Save model metadata to MongoDB
            self.save_model_metadata_to_mongodb(training_result)
            
            # Step 5: Generate predictions (if not skipped)
            if not skip_predictions:
                try:
                    cutoff = training_result['result']['cutoff']['thr']
                    df_predictions = self.generate_alerts(
                        run_dir=training_result['run_dir'],
                        history_csv=ML_TEMP_DATA,
                        cutoff=cutoff,
                        prediction_year=prediction_year,
                        prediction_month=prediction_month,
                    )
                    
                    # Step 6: Save predictions to MongoDB
                    self.save_predictions_to_mongodb(
                        df_predictions=df_predictions,
                        run_id=training_result['run_id'],
                        prediction_year=prediction_year,
                        prediction_month=prediction_month,
                    )
                    
                    logger.info("=" * 80)
                    logger.info("✅ ML PIPELINE COMPLETED SUCCESSFULLY")
                    logger.info(f"   Model: {training_result['run_id']}")
                    logger.info(f"   Test ROC-AUC: {training_result['result']['metrics']['test']['roc_auc']:.3f}")
                    logger.info(f"   Predictions for: {prediction_year}-{prediction_month:02d}")
                    logger.info(f"   High-risk alerts: {(df_predictions['prediction'] == 1).sum():,}")
                    logger.info("=" * 80)
                except Exception as e:
                    logger.warning(f"⚠️  Prediction generation failed: {e}")
                    logger.warning("   Model training completed successfully, but predictions skipped")
                    logger.info("=" * 80)
                    logger.info("✅ ML TRAINING COMPLETED (predictions skipped)")
                    logger.info(f"   Model: {training_result['run_id']}")
                    logger.info(f"   Test ROC-AUC: {training_result['result']['metrics']['test']['roc_auc']:.3f}")
                    logger.info(f"   Model ready for inference when new data arrives")
                    logger.info("=" * 80)
            else:
                logger.info("=" * 80)
                logger.info("✅ ML TRAINING COMPLETED (predictions skipped)")
                logger.info(f"   Model: {training_result['run_id']}")
                logger.info(f"   Test ROC-AUC: {training_result['result']['metrics']['test']['roc_auc']:.3f}")
                logger.info(f"   Model ready for inference when new data arrives")
                logger.info("=" * 80)
            
            return training_result
            
        except Exception as e:
            logger.error(f"❌ ML Pipeline failed: {e}")
            raise
        finally:
            if self.mongo_client:
                self.mongo_client.close()


@click.command()
@click.option('--min-year', type=int, help='Minimum year for training data (default: all)')
@click.option('--max-year', type=int, help='Maximum year for training data (default: all)')
@click.option('--pred-year', type=int, help='Year to predict (default: next month)')
@click.option('--pred-month', type=int, help='Month to predict (default: next month)')
@click.option('--skip-predictions', is_flag=True, help='Skip prediction generation (train model only)')
def main(min_year, max_year, pred_year, pred_month, skip_predictions):
    """
    Run ML Training Pipeline (Script 3)
    
    Example:
        python scripts/ml_training_pipeline.py
        python scripts/ml_training_pipeline.py --skip-predictions
        python scripts/ml_training_pipeline.py --min-year 2020 --pred-year 2026 --pred-month 2
    """
    pipeline = MLTrainingPipeline()
    pipeline.run_full_pipeline(
        min_year=min_year,
        max_year=max_year,
        prediction_year=pred_year,
        prediction_month=pred_month,
        skip_predictions=skip_predictions,
    )


if __name__ == "__main__":
    main()
