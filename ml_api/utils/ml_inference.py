"""
ML Inference Utilities
======================
Model loading, caching, and prediction for the serving layer.
Uses the production XGBoost model from ml/models/runs/production/
"""
import os
import json
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import logging

import joblib
import numpy as np
import pandas as pd

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Feature columns expected by the model (from training)
FEATURE_COLUMNS = [
    "year",
    "month",
    "month_sin",
    "month_cos",
    "is_summer",
    "is_winter",
    "is_holiday_season",
    "carrier_encoded",
    "airport_encoded",
    "arr_flights",
    "log_arr_flights",
    "pair_lag1",
    "pair_lag3_mean",
    "pair_expanding_mean",
    "airport_lag1",
    "airport_lag3_mean",
    "airport_expanding_mean",
    "carrier_lag1",
    "carrier_lag3_mean",
    "carrier_expanding_mean",
]


class MLModelService:
    """
    Singleton service for ML model loading and inference.
    Caches the model in memory for low-latency predictions.
    """
    
    _instance: Optional['MLModelService'] = None
    _model = None
    _imputer = None
    _le_carrier = None
    _le_airport = None
    _metrics: Dict[str, Any] = {}
    _model_version: str = "unknown"
    _cutoff: float = 0.5
    
    def __new__(cls) -> 'MLModelService':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._model is None:
            self._load_model()
    
    def _get_model_path(self) -> Path:
        """Get the path to production model directory."""
        # Try relative path from project root
        base_paths = [
            Path(__file__).parent.parent.parent / "ml" / "models" / "runs" / "production",
            Path(os.getcwd()) / "ml" / "models" / "runs" / "production",
            Path("c:/Users/laamo/ynov-data-pipeline-main/ml/models/runs/production"),
        ]
        
        for path in base_paths:
            if path.exists() and (path / "model.pkl").exists():
                return path
        
        raise FileNotFoundError(
            f"Model not found. Searched paths: {[str(p) for p in base_paths]}"
        )
    
    def _load_model(self) -> None:
        """Load the production model and encoders."""
        try:
            model_dir = self._get_model_path()
            logger.info(f"Loading model from: {model_dir}")
            
            # Load model pipeline (includes imputer)
            model_path = model_dir / "model.pkl"
            self._model = joblib.load(model_path)
            logger.info("✅ Model loaded")
            
            # Load imputer separately if exists
            imputer_path = model_dir / "imputer.pkl"
            if imputer_path.exists():
                self._imputer = joblib.load(imputer_path)
                logger.info("✅ Imputer loaded")
            
            # Load label encoders
            le_carrier_path = model_dir / "label_encoder_carrier.pkl"
            le_airport_path = model_dir / "label_encoder_airport.pkl"
            
            self._le_carrier = joblib.load(le_carrier_path)
            self._le_airport = joblib.load(le_airport_path)
            logger.info("✅ Label encoders loaded")
            
            # Load metrics
            metrics_path = model_dir / "metrics.json"
            if metrics_path.exists():
                with open(metrics_path, 'r') as f:
                    self._metrics = json.load(f)
                self._model_version = self._metrics.get("run_id", "unknown")
                self._cutoff = self._metrics.get("cutoff", 0.5)
                logger.info(f"✅ Metrics loaded, version: {self._model_version}")
            
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise
    
    @property
    def model_version(self) -> str:
        """Get the current model version."""
        return self._model_version
    
    @property
    def cutoff(self) -> float:
        """Get the classification cutoff threshold."""
        return self._cutoff
    
    @property
    def carriers(self) -> list:
        """Get list of known carriers."""
        return list(self._le_carrier.classes_)
    
    @property
    def airports(self) -> list:
        """Get list of known airports."""
        return list(self._le_airport.classes_)
    
    def is_valid_carrier(self, carrier: str) -> bool:
        """Check if carrier is known to the model."""
        return carrier in self._le_carrier.classes_
    
    def is_valid_airport(self, airport: str) -> bool:
        """Check if airport is known to the model."""
        return airport in self._le_airport.classes_
    
    def encode_carrier(self, carrier: str) -> int:
        """Encode carrier string to integer."""
        if not self.is_valid_carrier(carrier):
            return 0  # Default for unknown
        return int(self._le_carrier.transform([carrier])[0])
    
    def encode_airport(self, airport: str) -> int:
        """Encode airport string to integer."""
        if not self.is_valid_airport(airport):
            return 0  # Default for unknown
        return int(self._le_airport.transform([airport])[0])
    
    def compute_seasonality_features(self, month: int) -> Dict[str, float]:
        """Compute seasonality features from month."""
        return {
            "month_sin": float(np.sin(2 * np.pi * month / 12)),
            "month_cos": float(np.cos(2 * np.pi * month / 12)),
            "is_summer": 1 if month in [6, 7, 8] else 0,
            "is_winter": 1 if month in [12, 1, 2] else 0,
            "is_holiday_season": 1 if month in [11, 12] else 0,
        }
    
    def build_features(
        self,
        carrier: str,
        airport: str,
        year: int,
        month: int,
        stored_features: Optional[Dict[str, Any]] = None,
        arr_flights: float = 500.0,
        default_lag: float = 0.15
    ) -> Dict[str, Any]:
        """
        Build complete feature vector for prediction.
        
        Args:
            carrier: Carrier code
            airport: Airport code
            year: Year
            month: Month (1-12)
            stored_features: Pre-computed features from MongoDB (optional)
            arr_flights: Number of flights (default 500)
            default_lag: Default value for lag features if not available
            
        Returns:
            Dictionary with all required features
        """
        # Start with stored features or defaults
        if stored_features:
            features = stored_features.copy()
        else:
            # Build from scratch with defaults
            features = {
                "arr_flights": float(arr_flights),
                "log_arr_flights": float(np.log1p(arr_flights)),
                "pair_lag1": default_lag,
                "pair_lag3_mean": default_lag,
                "pair_expanding_mean": default_lag,
                "airport_lag1": default_lag,
                "airport_lag3_mean": default_lag,
                "airport_expanding_mean": default_lag,
                "carrier_lag1": default_lag,
                "carrier_lag3_mean": default_lag,
                "carrier_expanding_mean": default_lag,
            }
        
        # Add basic features
        features["year"] = year
        features["month"] = month
        features["carrier_encoded"] = self.encode_carrier(carrier)
        features["airport_encoded"] = self.encode_airport(airport)
        
        # Add seasonality features
        seasonality = self.compute_seasonality_features(month)
        features.update(seasonality)
        
        # Ensure log_arr_flights is computed
        if "log_arr_flights" not in features and "arr_flights" in features:
            features["log_arr_flights"] = float(np.log1p(max(features["arr_flights"], 0)))
        
        return features
    
    def predict(self, features: Dict[str, Any]) -> Tuple[float, str]:
        """
        Run prediction using the loaded model.
        
        Args:
            features: Feature dictionary
            
        Returns:
            Tuple of (probability, risk_category)
        """
        # Create feature vector in correct order
        feature_vector = [features.get(col, 0.0) for col in FEATURE_COLUMNS]
        X = np.array([feature_vector])
        
        # Apply imputer if available (for handling NaN)
        if self._imputer is not None:
            X = self._imputer.transform(X)
        
        # Get prediction probability
        if hasattr(self._model, 'predict_proba'):
            proba = self._model.predict_proba(X)[0, 1]
        else:
            # For regression models or pipelines
            proba = float(self._model.predict(X)[0])
            proba = max(0.0, min(1.0, proba))  # Clip to [0, 1]
        
        # Determine risk category based on cutoff
        if proba >= 0.75:
            risk_category = "critical"
        elif proba >= self._cutoff:
            risk_category = "high"
        elif proba >= 0.25:
            risk_category = "medium"
        else:
            risk_category = "low"
        
        return float(proba), risk_category


# Singleton accessor
def get_ml_service() -> MLModelService:
    """Get the singleton ML service instance."""
    return MLModelService()
