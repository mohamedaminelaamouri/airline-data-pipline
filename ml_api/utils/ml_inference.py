"""
ML Inference Utilities (v3)
===========================
Model loading and prediction for the serving layer.
Uses MongoDB feature_store with pre-computed features from ClickHouse.

IMPORTANT: No feature engineering is done in this module.
All features are pre-computed in ClickHouse and stored in MongoDB.
"""
import os
import json
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
import logging

import joblib
import numpy as np
import pandas as pd
from cityhash import CityHash64

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# =============================================================================
# FEATURE COLUMNS (must match ClickHouse gold_ml_features schema)
# =============================================================================
FEATURE_COLUMNS = [
    "year", "month", "month_sin", "month_cos",
    "is_summer", "is_winter", "is_holiday_season",
    "carrier_id", "airport_id",
    "arr_flights", "log_arr_flights",
    "pair_lag1", "pair_lag3_mean", "pair_expanding_mean",
    "airport_lag1", "airport_lag3_mean", "airport_expanding_mean",
    "carrier_lag1", "carrier_lag3_mean", "carrier_expanding_mean",
]

# =============================================================================
# MODEL PATH
# =============================================================================
PROJECT_ROOT = Path(__file__).parent.parent.parent
MODEL_DIR = PROJECT_ROOT / "ml" / "models" / "runs" / "production"

# Global cache for model and hash mappings
_model_cache = None
_hash_mappings = None


def get_carrier_id(carrier: str) -> int:
    """
    Generate deterministic carrier ID using CityHash64.
    Matches ClickHouse: cityHash64(carrier) % 100000
    """
    # Use CityHash64 to match ClickHouse exactly
    return CityHash64(carrier.encode('utf-8')) % 100000


def get_airport_id(airport: str) -> int:
    """
    Generate deterministic airport ID using CityHash64.
    Matches ClickHouse: cityHash64(airport) % 100000
    """
    return CityHash64(airport.encode('utf-8')) % 100000


def load_model():
    """Load XGBoost model from production directory."""
    global _model_cache
    
    if _model_cache is not None:
        return _model_cache
    
    model_path = MODEL_DIR / "xgboost_classifier.pkl"
    
    if not model_path.exists():
        # Try alternative paths
        alt_paths = [
            MODEL_DIR / "model.pkl",
            PROJECT_ROOT / "ml" / "models" / "xgboost_classifier.pkl",
            PROJECT_ROOT / "models" / "xgboost_classifier.pkl",
        ]
        for path in alt_paths:
            if path.exists():
                model_path = path
                break
        else:
            raise FileNotFoundError(
                f"Model not found. Checked: {model_path} and alternatives"
            )
    
    logger.info(f"Loading model from: {model_path}")
    _model_cache = joblib.load(model_path)
    logger.info(f"Model loaded successfully. Type: {type(_model_cache)}")
    
    return _model_cache


def build_features_from_stored(stored_features: Dict[str, Any]) -> np.ndarray:
    """
    Build feature vector from MongoDB stored features.
    
    IMPORTANT: No feature computation here - all features come from MongoDB.
    
    Args:
        stored_features: Features dict from MongoDB feature_store document
        
    Returns:
        np.ndarray: Feature vector in correct order for model
    """
    features = []
    
    for col in FEATURE_COLUMNS:
        value = stored_features.get(col)
        
        if value is None:
            logger.warning(f"Missing feature: {col}, using 0.0")
            value = 0.0
        
        # Handle any numpy type conversions
        if hasattr(value, 'item'):
            value = value.item()
        
        features.append(float(value))
    
    return np.array(features).reshape(1, -1)


def predict_with_features(features: np.ndarray) -> Dict[str, Any]:
    """
    Make prediction with pre-built feature vector.
    
    Args:
        features: Feature vector (1, n_features)
        
    Returns:
        Dict with prediction, probability, and risk category
    """
    model = load_model()
    
    # Make prediction
    prediction = model.predict(features)[0]
    
    # Get probability if available
    try:
        probabilities = model.predict_proba(features)[0]
        probability = float(probabilities[1])  # P(delayed)
    except AttributeError:
        probability = float(prediction)
    
    # Determine risk category based on probability
    if probability >= 0.7:
        risk_category = "critical"
    elif probability >= 0.5:
        risk_category = "high"
    elif probability >= 0.3:
        risk_category = "medium"
    else:
        risk_category = "low"
    
    return {
        "prediction": int(prediction),
        "probability": round(probability, 4),
        "risk_category": risk_category,
        "is_delayed": bool(prediction == 1),
        "feature_count": features.shape[1],
        "feature_version": "v3"
    }


def predict_from_mongodb_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Make prediction from a MongoDB feature_store document.
    
    Args:
        doc: Document from MongoDB feature_store collection
        
    Returns:
        Dict with prediction results
    """
    if 'features' not in doc:
        raise ValueError("Document missing 'features' key")
    
    stored_features = doc['features']
    feature_vector = build_features_from_stored(stored_features)
    
    result = predict_with_features(feature_vector)
    result['carrier'] = doc.get('carrier')
    result['airport'] = doc.get('airport')
    result['year'] = doc.get('year')
    result['month'] = doc.get('month')
    
    return result


def predict_new_input(
    carrier: str,
    airport: str,
    year: int,
    month: int,
    mongo_collection
) -> Dict[str, Any]:
    """
    Make prediction for a new input by looking up features from MongoDB.
    
    This is the main entry point for the serving API.
    
    Args:
        carrier: Carrier code (e.g., 'AA')
        airport: Airport code (e.g., 'ATL')
        year: Year
        month: Month (1-12)
        mongo_collection: MongoDB feature_store collection
        
    Returns:
        Dict with prediction and metadata
    """
    # Try exact match first
    doc = mongo_collection.find_one({
        "carrier": carrier,
        "airport": airport,
        "year": year,
        "month": month
    })
    
    if doc:
        # Exact match found
        result = predict_from_mongodb_doc(doc)
        result['lookup_method'] = 'exact_match'
        return result
    
    # Fallback: Find most recent data for this carrier-airport pair
    fallback_doc = mongo_collection.find_one(
        {"carrier": carrier, "airport": airport},
        sort=[("year", -1), ("month", -1)]
    )
    
    if fallback_doc:
        # Use fallback features but update year/month
        stored_features = dict(fallback_doc['features'])
        stored_features['year'] = year
        stored_features['month'] = month
        
        # Recompute cyclical features for the new month
        import math
        stored_features['month_sin'] = math.sin(2 * math.pi * month / 12)
        stored_features['month_cos'] = math.cos(2 * math.pi * month / 12)
        stored_features['is_summer'] = 1 if month in (6, 7, 8) else 0
        stored_features['is_winter'] = 1 if month in (12, 1, 2) else 0
        stored_features['is_holiday_season'] = 1 if month in (11, 12) else 0
        
        feature_vector = build_features_from_stored(stored_features)
        result = predict_with_features(feature_vector)
        result['carrier'] = carrier
        result['airport'] = airport
        result['year'] = year
        result['month'] = month
        result['lookup_method'] = 'fallback_latest'
        result['fallback_source'] = f"{fallback_doc['year']}/{fallback_doc['month']}"
        
        return result
    
    # No data at all - cannot make prediction
    raise ValueError(
        f"No feature data found for carrier={carrier}, airport={airport}. "
        "Please ensure the feature store is populated."
    )


def batch_predict(
    inputs: List[Dict[str, Any]],
    mongo_collection
) -> List[Dict[str, Any]]:
    """
    Make predictions for multiple inputs.
    
    Args:
        inputs: List of dicts with carrier, airport, year, month
        mongo_collection: MongoDB feature_store collection
        
    Returns:
        List of prediction results
    """
    results = []
    
    for inp in inputs:
        try:
            result = predict_new_input(
                carrier=inp['carrier'],
                airport=inp['airport'],
                year=inp['year'],
                month=inp['month'],
                mongo_collection=mongo_collection
            )
            result['status'] = 'success'
        except Exception as e:
            result = {
                'carrier': inp.get('carrier'),
                'airport': inp.get('airport'),
                'year': inp.get('year'),
                'month': inp.get('month'),
                'status': 'error',
                'error': str(e)
            }
        
        results.append(result)
    
    return results


def get_model_info() -> Dict[str, Any]:
    """Get information about the loaded model."""
    model = load_model()
    
    info = {
        "model_type": type(model).__name__,
        "feature_columns": FEATURE_COLUMNS,
        "n_features": len(FEATURE_COLUMNS),
        "feature_version": "v3",
        "model_dir": str(MODEL_DIR)
    }
    
    # Try to get XGBoost-specific info
    if hasattr(model, 'get_booster'):
        booster = model.get_booster()
        info['n_trees'] = booster.num_trees()
    
    if hasattr(model, 'n_estimators'):
        info['n_estimators'] = model.n_estimators
    
    if hasattr(model, 'max_depth'):
        info['max_depth'] = model.max_depth
    
    return info


# =============================================================================
# ML SERVICE CLASS (for API compatibility)
# =============================================================================
class MLService:
    """
    ML Service class for FastAPI integration.
    Wraps the stateless functions into a class interface expected by app.py.
    """
    
    def __init__(self):
        self.model = load_model()
        self.feature_columns = FEATURE_COLUMNS
    
    def is_valid_carrier(self, carrier: str) -> bool:
        """Check if carrier is valid (always True for hash-based encoding)."""
        return carrier is not None and len(carrier) > 0
    
    def is_valid_airport(self, airport: str) -> bool:
        """Check if airport is valid (always True for hash-based encoding)."""
        return airport is not None and len(airport) > 0
    
    def build_features(
        self, 
        carrier: str, 
        airport: str, 
        year: int, 
        month: int, 
        stored_features: Optional[Dict[str, Any]] = None
    ) -> np.ndarray:
        """
        Build feature vector from inputs and stored features.
        
        Args:
            carrier: Carrier code
            airport: Airport code
            year: Year
            month: Month
            stored_features: Pre-computed features from MongoDB
            
        Returns:
            Feature vector as numpy array
        """
        import math
        
        # Start with stored features or empty dict
        features = dict(stored_features) if stored_features else {}
        
        # Always set base features
        features['year'] = year
        features['month'] = month
        features['carrier_id'] = get_carrier_id(carrier)
        features['airport_id'] = get_airport_id(airport)
        
        # Compute cyclical features
        features['month_sin'] = math.sin(2 * math.pi * month / 12)
        features['month_cos'] = math.cos(2 * math.pi * month / 12)
        
        # Seasonal features
        features['is_summer'] = 1 if month in (6, 7, 8) else 0
        features['is_winter'] = 1 if month in (12, 1, 2) else 0
        features['is_holiday_season'] = 1 if month in (11, 12) else 0
        
        # Set defaults for lag features if not present
        default_delay = 0.20  # Assume average delay rate
        for col in self.feature_columns:
            if col not in features:
                if 'lag' in col or 'expanding' in col:
                    features[col] = default_delay
                elif col == 'arr_flights':
                    features[col] = 500  # Default flight count
                elif col == 'log_arr_flights':
                    import math
                    features[col] = math.log(501)
                elif col not in ['year', 'month', 'carrier_id', 'airport_id', 
                                 'month_sin', 'month_cos', 'is_summer', 
                                 'is_winter', 'is_holiday_season']:
                    features[col] = 0.0
        
        # Build feature vector in correct order
        return build_features_from_stored(features)
    
    def predict(self, features: np.ndarray) -> Tuple[float, str]:
        """
        Make prediction with feature vector.
        
        Args:
            features: Feature vector from build_features()
            
        Returns:
            Tuple of (probability, risk_category)
        """
        result = predict_with_features(features)
        return result['probability'], result['risk_category']
    
    def get_feature_columns(self) -> List[str]:
        """Return the feature columns used by the model."""
        return self.feature_columns


# Singleton instance
_ml_service_instance = None


def get_ml_service() -> MLService:
    """Get or create the ML service singleton."""
    global _ml_service_instance
    
    if _ml_service_instance is None:
        _ml_service_instance = MLService()
    
    return _ml_service_instance
