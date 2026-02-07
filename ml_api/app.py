from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
import uuid
import logging
import traceback

import joblib

print(f"DEBUG: LOADED APP FROM {__file__}")
try:
    from ml_api.utils.clickhouse_client import query_df
except ImportError:
    from utils.clickhouse_client import query_df

try:
    from ml_api.utils.mongodb_client import get_mongo_client
    from ml_api.utils.ml_inference import get_ml_service, FEATURE_COLUMNS
    from ml_api.alerts import get_alert_service, check_prediction_for_alerts, AlertFilter, AlertStatus, AlertType, AlertSeverity
except ImportError:
    from utils.mongodb_client import get_mongo_client
    from utils.ml_inference import get_ml_service, FEATURE_COLUMNS
    from alerts import get_alert_service, check_prediction_for_alerts, AlertFilter, AlertStatus, AlertType, AlertSeverity

import pandas as pd
import random

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="ML Dashboard API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Données mock pour démo (quand ClickHouse n'est pas accessible)
MOCK_CARRIERS = ["AA", "DL", "UA", "WN", "B6", "AS", "NK", "F9"]
MOCK_AIRPORTS = ["ATL", "DFW", "DEN", "ORD", "LAX", "CLT", "LAS", "PHX", "MIA", "SEA"]
MOCK_RISK_CATEGORIES = ["critical", "high", "medium", "low"]

def generate_mock_predictions(limit=100):
    """Génère des prédictions factices pour la démo"""
    data = []
    for i in range(limit):
        month = random.randint(1, 12)
        risk_idx = random.choices([0, 1, 2, 3], weights=[0.05, 0.15, 0.30, 0.50])[0]
        risk_cat = MOCK_RISK_CATEGORIES[risk_idx]
        
        # Delay rate selon le risque
        if risk_cat == "critical":
            delay_rate = random.uniform(0.50, 0.80)
            risk_score = random.uniform(80, 100)
        elif risk_cat == "high":
            delay_rate = random.uniform(0.30, 0.50)
            risk_score = random.uniform(60, 80)
        elif risk_cat == "medium":
            delay_rate = random.uniform(0.15, 0.30)
            risk_score = random.uniform(40, 60)
        else:
            delay_rate = random.uniform(0.05, 0.15)
            risk_score = random.uniform(0, 40)
            
        data.append({
            "carrier": random.choice(MOCK_CARRIERS),
            "origin_airport": random.choice(MOCK_AIRPORTS),
            "year": 2026,
            "month": month,
            "predicted_delay_rate": round(delay_rate, 4),
            "risk_score": round(risk_score, 2),
            "risk_category": risk_cat,
            "arr_flights": random.randint(100, 5000),
            "model_version": "xgb_classifier_demo_v1.0",
            "confidence": round(random.uniform(0.75, 0.95), 3),
            "top_feature_1": "historical_delay_rate",
            "top_feature_1_importance": round(random.uniform(0.25, 0.35), 3),
            "top_feature_2": "carrier_severity",
            "top_feature_2_importance": round(random.uniform(0.15, 0.25), 3),
            "top_feature_3": "monthly_seasonality",
            "top_feature_3_importance": round(random.uniform(0.10, 0.20), 3),
        })
    return data


@app.get("/health")
def health():
    return {"status": "ok"}


# =============================================================================
# PREDICT ENDPOINT - ML Serving Layer
# =============================================================================

class PredictRequest(BaseModel):
    """Request model for prediction endpoint."""
    carrier: str = Field(..., description="Airline carrier code (e.g., 'AA', 'DL')")
    airport: str = Field(..., description="Airport code (e.g., 'ATL', 'ORD')")
    month: int = Field(..., ge=1, le=12, description="Month (1-12)")
    year: int = Field(..., ge=2000, le=2050, description="Year")


class PredictResponse(BaseModel):
    """Response model for prediction endpoint."""
    request_id: str = Field(..., description="Unique request identifier (UUID)")
    prediction: float = Field(..., description="Probability of high delay (0-1)")
    risk_category: str = Field(..., description="Risk classification: low, medium, high, critical")
    model_version: str = Field(..., description="Model version used for prediction")
    timestamp: str = Field(..., description="ISO format timestamp")
    inputs: Dict[str, Any] = Field(..., description="Echo of input parameters")


@app.post("/predict", response_model=PredictResponse)
async def predict(request: PredictRequest):
    """
    Run online ML prediction for flight delay risk.
    
    This endpoint:
    1. Validates carrier and airport codes
    2. Retrieves pre-computed features from MongoDB
    3. Runs inference using the production XGBoost model
    4. Stores prediction in MongoDB
    5. Returns the prediction result
    
    **Constraints:**
    - ClickHouse is NOT used during inference
    - MongoDB is the sole data source for features
    """
    request_id = str(uuid.uuid4())
    timestamp = datetime.utcnow().isoformat() + "Z"
    
    try:
        # Get services
        ml_service = get_ml_service()
        mongo_client = get_mongo_client()
        
        # Validate carrier and airport
        if not ml_service.is_valid_carrier(request.carrier):
            logger.warning(f"Unknown carrier: {request.carrier}")
            # Still allow prediction with unknown carrier (encoded as 0)
        
        if not ml_service.is_valid_airport(request.airport):
            logger.warning(f"Unknown airport: {request.airport}")
            # Still allow prediction with unknown airport (encoded as 0)
        
        # Try to get pre-computed features from MongoDB
        stored_features = mongo_client.get_features(
            carrier=request.carrier,
            airport=request.airport,
            year=request.year,
            month=request.month
        )
        
        if stored_features:
            logger.info(f"Found pre-computed features for {request.carrier}/{request.airport}/{request.year}/{request.month}")
        else:
            # Try to get latest features for this route to use as baseline
            latest = mongo_client.get_latest_features_for_route(
                carrier=request.carrier,
                airport=request.airport
            )
            if latest and "features" in latest:
                stored_features = latest["features"]
                logger.info(f"Using latest features from {latest.get('year')}/{latest.get('month')}")
            else:
                logger.info("No historical features found, using defaults")
        
        # Build complete feature vector
        features = ml_service.build_features(
            carrier=request.carrier,
            airport=request.airport,
            year=request.year,
            month=request.month,
            stored_features=stored_features
        )
        
        # Run prediction
        prediction, risk_category = ml_service.predict(features)
        
        logger.info(
            f"Prediction: {request.carrier}/{request.airport} {request.year}/{request.month} "
            f"-> {prediction:.4f} ({risk_category})"
        )
        
        # Store prediction in MongoDB
        mongo_client.store_prediction(
            request_id=request_id,
            carrier=request.carrier,
            airport=request.airport,
            year=request.year,
            month=request.month,
            prediction=prediction,
            risk_category=risk_category,
            model_version=ml_service.model_version,
            features_used=dict(zip(ml_service.feature_columns, features.flatten().tolist()))
        )
        
        # Check for alerts on high-risk predictions
        try:
            alert_service = get_alert_service()
            alert = check_prediction_for_alerts(
                prediction=prediction,
                carrier=request.carrier,
                airport=request.airport,
                year=request.year,
                month=request.month,
                alert_service=alert_service
            )
            if alert:
                logger.info(f"Alert created: {alert.type.value} for {request.carrier}/{request.airport}")
        except Exception as e:
            logger.warning(f"Failed to create alert: {e}")
        
        return PredictResponse(
            request_id=request_id,
            prediction=round(prediction, 4),
            risk_category=risk_category,
            model_version=ml_service.model_version,
            timestamp=timestamp,
            inputs={
                "carrier": request.carrier,
                "airport": request.airport,
                "month": request.month,
                "year": request.year
            }
        )
        
    except FileNotFoundError as e:
        logger.error(f"Model not found: {e}")
        raise HTTPException(status_code=503, detail="ML model not available")
    except Exception as e:
        logger.error(f"Prediction error: {e}")
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")


@app.get("/predict/metadata")
def predict_metadata():
    """Get metadata for the prediction service: valid carriers, airports, and model info."""
    try:
        ml_service = get_ml_service()
        return {
            "carriers": ml_service.carriers,
            "airports": ml_service.airports,
            "model_version": ml_service.model_version,
            "cutoff": ml_service.cutoff,
            "feature_columns": FEATURE_COLUMNS,
            "status": "ready"
        }
    except Exception as e:
        return {
            "carriers": MOCK_CARRIERS,
            "airports": MOCK_AIRPORTS,
            "model_version": "unavailable",
            "cutoff": 0.5,
            "feature_columns": [],
            "status": f"degraded: {str(e)}"
        }


# =============================================================================
# BATCH PREDICTION ENDPOINT
# =============================================================================

class BatchPredictRequest(BaseModel):
    """Request model for batch predictions."""
    predictions: list[PredictRequest] = Field(..., max_length=100, description="List of predictions (max 100)")


class BatchPredictResponse(BaseModel):
    """Response model for batch predictions."""
    batch_id: str
    total: int
    successful: int
    failed: int
    results: list[PredictResponse]
    errors: list[Dict[str, Any]]
    timestamp: str


@app.post("/predict/batch", response_model=BatchPredictResponse)
async def predict_batch(request: BatchPredictRequest):
    """
    Run batch ML predictions for multiple carrier/airport/month combinations.
    
    Maximum 100 predictions per batch.
    Each prediction is processed independently.
    """
    batch_id = str(uuid.uuid4())
    timestamp = datetime.utcnow().isoformat() + "Z"
    
    results = []
    errors = []
    
    try:
        ml_service = get_ml_service()
        mongo_client = get_mongo_client()
    except Exception as e:
        logger.error(f"Service init failed: {traceback.format_exc()}")
        raise HTTPException(status_code=503, detail=f"Service unavailable: {str(e)}")
    
    for idx, pred_request in enumerate(request.predictions):
        try:
            request_id = str(uuid.uuid4())
            
            # Get features
            stored_features = mongo_client.get_features(
                carrier=pred_request.carrier,
                airport=pred_request.airport,
                year=pred_request.year,
                month=pred_request.month
            )
            
            if not stored_features:
                latest = mongo_client.get_latest_features_for_route(
                    carrier=pred_request.carrier,
                    airport=pred_request.airport
                )
                if latest and "features" in latest:
                    stored_features = latest["features"]
            
            # Build features and predict
            features = ml_service.build_features(
                carrier=pred_request.carrier,
                airport=pred_request.airport,
                year=pred_request.year,
                month=pred_request.month,
                stored_features=stored_features
            )
            
            prediction, risk_category = ml_service.predict(features)
            
            logger.info(f"DEBUG: features type: {type(features)}")
            logger.info(f"DEBUG: prediction type: {type(prediction)}")
            
            # Store in MongoDB
            features_dict = dict(zip(FEATURE_COLUMNS, features.flatten().tolist()))
            logger.info(f"DEBUG: features_dict type: {type(features_dict)}")
            
            mongo_client.store_prediction(
                request_id=request_id,
                carrier=pred_request.carrier,
                airport=pred_request.airport,
                year=pred_request.year,
                month=pred_request.month,
                prediction=prediction,
                risk_category=risk_category,
                model_version="v3",
                features_used=features_dict
            )
            
            results.append(PredictResponse(
                request_id=request_id,
                prediction=round(prediction, 4),
                risk_category=risk_category,
                model_version="v3",
                timestamp=timestamp,
                inputs={
                    "carrier": pred_request.carrier,
                    "airport": pred_request.airport,
                    "month": pred_request.month,
                    "year": pred_request.year
                }
            ))
            
        except Exception as e:
            logger.error("DEBUG MARKER: Exception caught in batch loop")
            logger.error(f"Traceback: {traceback.format_exc()}")
            errors.append({
                "index": idx,
                "error": str(e),
                "traceback": traceback.format_exc()
            })
    
    logger.info(f"Batch {batch_id}: {len(results)} successful, {len(errors)} failed")
    
    return BatchPredictResponse(
        batch_id=batch_id,
        total=len(request.predictions),
        successful=len(results),
        failed=len(errors),
        results=results,
        errors=errors,
        timestamp=timestamp
    )


# =============================================================================
# PREDICTION HISTORY ENDPOINTS
# =============================================================================

class PredictionHistoryItem(BaseModel):
    """Single prediction history item."""
    request_id: str
    carrier: str
    airport: str
    year: int
    month: int
    prediction: float
    risk_category: str
    model_version: str
    timestamp: str


class PredictionHistoryResponse(BaseModel):
    """Response for prediction history."""
    total: int
    page: int
    page_size: int
    predictions: list[PredictionHistoryItem]


@app.get("/predictions/history", response_model=PredictionHistoryResponse)
def predictions_history(
    carrier: Optional[str] = Query(default=None, description="Filter by carrier"),
    airport: Optional[str] = Query(default=None, description="Filter by airport"),
    risk_category: Optional[str] = Query(default=None, description="Filter by risk category"),
    year: Optional[int] = Query(default=None, description="Filter by year"),
    month: Optional[int] = Query(default=None, description="Filter by month"),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=50, ge=1, le=200, description="Items per page")
):
    """
    Get prediction history from MongoDB with optional filters.
    
    Supports pagination and filtering by carrier, airport, risk_category, year, month.
    """
    try:
        mongo_client = get_mongo_client()
        
        # Build query
        query = {}
        if carrier:
            query["carrier"] = carrier
        if airport:
            query["airport"] = airport
        if risk_category:
            query["risk_category"] = risk_category
        if year:
            query["year"] = year
        if month:
            query["month"] = month
        
        # Get total count
        total = mongo_client.predictions.count_documents(query)
        
        # Get paginated results
        skip = (page - 1) * page_size
        cursor = mongo_client.predictions.find(query).sort("timestamp", -1).skip(skip).limit(page_size)
        
        predictions = []
        for doc in cursor:
            predictions.append(PredictionHistoryItem(
                request_id=doc.get("request_id", ""),
                carrier=doc.get("carrier", ""),
                airport=doc.get("airport", ""),
                year=doc.get("year", 0),
                month=doc.get("month", 0),
                prediction=doc.get("prediction", 0.0),
                risk_category=doc.get("risk_category", ""),
                model_version=doc.get("model_version", ""),
                timestamp=doc.get("timestamp", "")
            ))
        
        return PredictionHistoryResponse(
            total=total,
            page=page,
            page_size=page_size,
            predictions=predictions
        )
        
    except Exception as e:
        logger.error(f"History query error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve history: {str(e)}")


@app.get("/predictions/{request_id}")
def get_prediction(request_id: str):
    """
    Get a single prediction by its request_id.
    """
    try:
        mongo_client = get_mongo_client()
        
        doc = mongo_client.predictions.find_one({"request_id": request_id})
        
        if not doc:
            raise HTTPException(status_code=404, detail=f"Prediction {request_id} not found")
        
        # Remove MongoDB _id from response
        doc.pop("_id", None)
        return doc
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get prediction error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve prediction: {str(e)}")


@app.delete("/predictions/{request_id}")
def delete_prediction(request_id: str):
    """
    Delete a prediction by its request_id.
    """
    try:
        mongo_client = get_mongo_client()
        
        result = mongo_client.predictions.delete_one({"request_id": request_id})
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail=f"Prediction {request_id} not found")
        
        return {"message": f"Prediction {request_id} deleted", "deleted": True}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete prediction error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete prediction: {str(e)}")

@app.get("/stats/summary")
def summary_stats():
    try:
        sql = """
        SELECT
            count() AS total_predictions,
            countIf(risk_category = 'critical') AS critical_risk_routes,
            countIf(risk_category = 'high') AS high_risk_routes,
            countIf(risk_category = 'medium') AS medium_risk_routes,
            countIf(risk_category = 'low') AS low_risk_routes,
            countDistinct(carrier) AS carriers_analyzed,
            countDistinct(origin_airport) AS airports_analyzed,
            avg(predicted_delay_rate) AS avg_predicted_delay,
            avg(risk_score) AS avg_risk_score
        FROM ml_predictions
        """
        df = query_df(sql)
        if df.empty:
            raise ValueError("No data")
        row = df.iloc[0].to_dict()
        total = float(row.get("total_predictions") or 0)
        high = float(row.get("high_risk_routes") or 0)
        critical = float(row.get("critical_risk_routes") or 0)
        row["high_risk_percentage"] = (high / total * 100) if total else 0
        row["critical_risk_percentage"] = (critical / total * 100) if total else 0
        return row
    except Exception:
        # Mode DEMO avec données mock
        mock_data = generate_mock_predictions(500)
        df_mock = pd.DataFrame(mock_data)
        total = len(df_mock)
        critical = len(df_mock[df_mock["risk_category"] == "critical"])
        high = len(df_mock[df_mock["risk_category"] == "high"])
        medium = len(df_mock[df_mock["risk_category"] == "medium"])
        low = len(df_mock[df_mock["risk_category"] == "low"])
        return {
            "total_predictions": total,
            "critical_risk_routes": critical,
            "high_risk_routes": high,
            "medium_risk_routes": medium,
            "low_risk_routes": low,
            "carriers_analyzed": len(df_mock["carrier"].unique()),
            "airports_analyzed": len(df_mock["origin_airport"].unique()),
            "avg_predicted_delay": float(df_mock["predicted_delay_rate"].mean()),
            "avg_risk_score": float(df_mock["risk_score"].mean()),
            "high_risk_percentage": (high / total * 100),
            "critical_risk_percentage": (critical / total * 100),
        }


@app.get("/predictions")
def predictions(
    carrier: Optional[str] = Query(default=None),
    airport: Optional[str] = Query(default=None),
    risk_category: Optional[str] = Query(default=None),
    month: Optional[int] = Query(default=None),
):
    try:
        where = []
        params = {}
        if carrier:
            where.append("carrier = %(carrier)s")
            params["carrier"] = carrier
        if airport:
            where.append("origin_airport = %(airport)s")
            params["airport"] = airport
        if risk_category:
            where.append("risk_category = %(risk_category)s")
            params["risk_category"] = risk_category
        if month:
            where.append("month = %(month)s")
            params["month"] = int(month)

        where_sql = ("WHERE " + " AND ".join(where)) if where else ""

        sql = f"""
        SELECT
            carrier,
            origin_airport,
            year,
            month,
            predicted_delay_rate,
            risk_score,
            risk_category,
            arr_flights,
            model_version,
            confidence
        FROM ml_predictions
        {where_sql}
        ORDER BY year, month
        LIMIT 5000
        """
        df = query_df(sql, parameters=params)
        return df.to_dict(orient="records")
    except Exception:
        # Mode DEMO avec données mock
        mock_data = generate_mock_predictions(200)
        df_mock = pd.DataFrame(mock_data)
        
        # Appliquer les filtres
        if carrier:
            df_mock = df_mock[df_mock["carrier"] == carrier]
        if airport:
            df_mock = df_mock[df_mock["origin_airport"] == airport]
        if risk_category:
            df_mock = df_mock[df_mock["risk_category"] == risk_category]
        if month:
            df_mock = df_mock[df_mock["month"] == month]
        
        return df_mock.to_dict(orient="records")


@app.get("/explainability/global")
def explainability_global():
    try:
        features_sql = """
        SELECT
            top_feature_1,
            AVG(top_feature_1_importance) AS avg_importance_1,
            top_feature_2,
            AVG(top_feature_2_importance) AS avg_importance_2,
            top_feature_3,
            AVG(top_feature_3_importance) AS avg_importance_3
        FROM ml_predictions
        GROUP BY top_feature_1, top_feature_2, top_feature_3
        LIMIT 1
        """
        features_df = query_df(features_sql)

        risk_sql = """
        SELECT risk_category, count() AS count
        FROM ml_predictions
        GROUP BY risk_category
        """
        risk_df = query_df(risk_sql)

        return {
            "features": features_df.to_dict(orient="records"),
            "risk_distribution": risk_df.to_dict(orient="records"),
        }
    except Exception:
        # Mode DEMO avec données mock
        mock_data = generate_mock_predictions(500)
        df_mock = pd.DataFrame(mock_data)
        
        risk_dist = df_mock["risk_category"].value_counts().reset_index()
        risk_dist.columns = ["risk_category", "count"]
        
        return {
            "features": [{
                "top_feature_1": "historical_delay_rate",
                "avg_importance_1": 0.32,
                "top_feature_2": "carrier_severity",
                "avg_importance_2": 0.21,
                "top_feature_3": "monthly_seasonality",
                "avg_importance_3": 0.15,
            }],
            "risk_distribution": risk_dist.to_dict(orient="records"),
        }


@app.get("/explainability/route")
def explainability_route(
    carrier: str = Query(...),
    airport: str = Query(...),
):
    try:
        sql = """
        SELECT
            carrier,
            origin_airport,
            year,
            month,
            predicted_delay_rate,
            risk_score,
            risk_category,
            arr_flights,
            model_version,
            top_feature_1,
            top_feature_1_importance,
            top_feature_2,
            top_feature_2_importance,
            top_feature_3,
            top_feature_3_importance
        FROM ml_predictions
        WHERE carrier = %(carrier)s AND origin_airport = %(airport)s
        ORDER BY month
        """
        df = query_df(sql, parameters={"carrier": carrier, "airport": airport})
        return df.to_dict(orient="records")
    except Exception:
        # Mode DEMO avec données mock
        mock_data = generate_mock_predictions(12)  # 12 mois
        df_mock = pd.DataFrame(mock_data)
        df_mock["carrier"] = carrier
        df_mock["origin_airport"] = airport
        df_mock["month"] = range(1, 13)
        return df_mock.to_dict(orient="records")


@app.get("/monitoring")
def monitoring():
    return summary_stats()


@app.get("/metadata")
def metadata():
    try:
        carriers_sql = """
        SELECT DISTINCT carrier
        FROM ml_predictions
        ORDER BY carrier
        """
        airports_sql = """
        SELECT DISTINCT origin_airport
        FROM ml_predictions
        ORDER BY origin_airport
        """
        carriers_df = query_df(carriers_sql)
        airports_df = query_df(airports_sql)
        return {
            "carriers": carriers_df["carrier"].dropna().tolist() if not carriers_df.empty else [],
            "airports": airports_df["origin_airport"].dropna().tolist() if not airports_df.empty else [],
        }
    except Exception:
        # Mode DEMO avec données mock
        return {
            "carriers": sorted(MOCK_CARRIERS),
            "airports": sorted(MOCK_AIRPORTS),
        }


@app.get("/stats/monthly")
def monthly_stats():
    try:
        sql = """
        SELECT
            month,
            avg(predicted_delay_rate) AS avg_predicted_delay,
            avg(risk_score) AS avg_risk_score,
            sum(arr_flights) AS total_flights
        FROM ml_predictions
        WHERE year = 2026
        GROUP BY month
        ORDER BY month
        """
        df = query_df(sql)
        return df.to_dict(orient="records")
    except Exception:
        # Mode DEMO avec données mock
        mock_data = generate_mock_predictions(500)
        df_mock = pd.DataFrame(mock_data)
        monthly = df_mock.groupby('month').agg({
            'predicted_delay_rate': 'mean',
            'risk_score': 'mean',
            'arr_flights': 'sum'
        }).reset_index()
        monthly.columns = ['month', 'avg_predicted_delay', 'avg_risk_score', 'total_flights']
        return monthly.to_dict(orient="records")


@app.get("/stats/classification")
def classification_stats():
    """
    Statistiques du modèle de classification.
    Expose les métriques ROC-AUC, cutoff, et distribution des risques.
    """
    try:
        # Distribution par catégorie de risque
        risk_sql = """
        SELECT 
            risk_category,
            count() as count,
            avg(predicted_delay_rate) as avg_probability,
            avg(risk_score) as avg_risk_score
        FROM ml_predictions
        WHERE year = 2026
        GROUP BY risk_category
        ORDER BY 
            CASE risk_category
                WHEN 'critical' THEN 1
                WHEN 'high' THEN 2
                WHEN 'medium' THEN 3
                WHEN 'low' THEN 4
            END
        """
        risk_df = query_df(risk_sql)
        
        # Statistiques globales
        stats_sql = """
        SELECT
            count() as total_predictions,
            countIf(predicted_delay_rate >= 0.47) as above_cutoff,
            avg(predicted_delay_rate) as avg_probability,
            min(predicted_delay_rate) as min_probability,
            max(predicted_delay_rate) as max_probability,
            countDistinct(carrier) as unique_carriers,
            countDistinct(origin_airport) as unique_airports
        FROM ml_predictions
        WHERE year = 2026
        """
        stats_df = query_df(stats_sql)
        
        stats = stats_df.iloc[0].to_dict() if not stats_df.empty else {}
        total = float(stats.get("total_predictions", 0))
        above = float(stats.get("above_cutoff", 0))
    except Exception:
        # Mode DEMO avec données mock
        mock_data = generate_mock_predictions(500)
        df_mock = pd.DataFrame(mock_data)
        
        risk_df = df_mock.groupby('risk_category').agg({
            'predicted_delay_rate': ['count', 'mean'],
            'risk_score': 'mean'
        }).reset_index()
        risk_df.columns = ['risk_category', 'count', 'avg_probability', 'avg_risk_score']
        
        total = len(df_mock)
        above = len(df_mock[df_mock['predicted_delay_rate'] >= 0.47])
        stats = {
            'total_predictions': total,
            'above_cutoff': above,
            'avg_probability': df_mock['predicted_delay_rate'].mean(),
            'unique_carriers': df_mock['carrier'].nunique(),
            'unique_airports': df_mock['origin_airport'].nunique(),
        }
    
    # Métriques du modèle production (mis à jour)
    model_metrics = {
        "model_type": "XGBoost Classifier",
        "accuracy": 0.790,
        "roc_auc_test": 0.810,
        "precision": 0.718,
        "recall": 0.421,
        "f1_score": 0.530,
        "cutoff": 0.47,
        "target_threshold": 0.20,  # delay_rate > 20% = risque
        "n_features": 20,
        "train_samples": 216019,
    }
    
    total = float(stats.get("total_predictions", 0))
    above = float(stats.get("above_cutoff", 0))
    
    return {
        "model": model_metrics,
        "predictions": {
            "total": int(total),
            "above_cutoff": int(above),
            "above_cutoff_pct": round(above / total * 100, 2) if total > 0 else 0,
            "avg_probability": round(float(stats.get("avg_probability", 0)), 4),
            "unique_carriers": int(stats.get("unique_carriers", 0)),
            "unique_airports": int(stats.get("unique_airports", 0)),
        },
        "risk_distribution": risk_df.to_dict(orient="records"),
    }


@app.get("/stats/cost")
def cost_stats():
    """
    Métriques de coût des retards - inspiré des calculs DAX de Power BI.
    - Airline Delay Cost = SUM(arr_delay) * 100.76 par carrier
    - Airport Delay Cost = SUM(arr_delay) * 100.76 par airport
    - Avg Minutes Per Delayed Flight = SUM(arr_delay) / SUM(arr_del15)
    """
    COST_PER_MINUTE = 100.76  # Coût en dollars par minute de retard
    
    try:
        # Statistiques globales depuis ClickHouse
        global_sql = """
        SELECT
            SUM(arr_delay) as total_delay_minutes,
            SUM(arr_del15) as total_delayed_flights,
            COUNT(DISTINCT carrier) as carriers_count,
            COUNT(DISTINCT origin_airport) as airports_count
        FROM flights
        WHERE arr_delay > 0
        """
        global_df = query_df(global_sql)
        
        # Top compagnies par coût
        carriers_sql = """
        SELECT
            carrier,
            carrier_name,
            SUM(arr_delay) as delay_minutes,
            SUM(arr_del15) as delayed_flights,
            SUM(arr_flights) as total_flights
        FROM flights
        WHERE arr_delay > 0
        GROUP BY carrier, carrier_name
        ORDER BY delay_minutes DESC
        LIMIT 10
        """
        carriers_df = query_df(carriers_sql)
        
        # Top aéroports par coût
        airports_sql = """
        SELECT
            airport,
            airport_name,
            SUM(arr_delay) as delay_minutes,
            SUM(arr_del15) as delayed_flights,
            SUM(arr_flights) as total_flights
        FROM flights
        WHERE arr_delay > 0
        GROUP BY airport, airport_name
        ORDER BY delay_minutes DESC
        LIMIT 10
        """
        airports_df = query_df(airports_sql)
        
        # Calculer les métriques
        total_delay_minutes = float(global_df.iloc[0]['total_delay_minutes']) if not global_df.empty else 0
        total_delayed_flights = float(global_df.iloc[0]['total_delayed_flights']) if not global_df.empty else 0
        
        total_cost = total_delay_minutes * COST_PER_MINUTE
        avg_minutes_per_delayed = total_delay_minutes / total_delayed_flights if total_delayed_flights > 0 else 0
        
        # Enrichir les compagnies
        carriers_list = []
        if not carriers_df.empty:
            carriers_df['delay_cost'] = carriers_df['delay_minutes'] * COST_PER_MINUTE
            carriers_df['avg_delay_per_flight'] = carriers_df['delay_minutes'] / carriers_df['delayed_flights']
            carriers_list = carriers_df.to_dict(orient='records')
        
        # Enrichir les aéroports
        airports_list = []
        if not airports_df.empty:
            airports_df['delay_cost'] = airports_df['delay_minutes'] * COST_PER_MINUTE
            airports_df['avg_delay_per_flight'] = airports_df['delay_minutes'] / airports_df['delayed_flights']
            airports_list = airports_df.to_dict(orient='records')
        
        return {
            "total_delay_cost": round(total_cost, 2),
            "total_delay_minutes": int(total_delay_minutes),
            "avg_minutes_per_delayed_flight": round(avg_minutes_per_delayed, 2),
            "cost_per_minute": COST_PER_MINUTE,
            "top_carriers_by_cost": carriers_list,
            "top_airports_by_cost": airports_list
        }
        
    except Exception:
        # Mode DEMO avec données mock
        # Générer des stats réalistes basées sur les prédictions mock
        mock_data = generate_mock_predictions(500)
        df = pd.DataFrame(mock_data)
        
        # Simuler arr_delay basé sur le risk score et arr_flights
        df['arr_delay'] = (df['predicted_delay_rate'] * df['arr_flights'] * random.uniform(15, 45)).astype(int)
        df['arr_del15'] = (df['predicted_delay_rate'] * df['arr_flights']).astype(int)
        
        # Stats globales
        total_delay_minutes = df['arr_delay'].sum()
        total_delayed_flights = df['arr_del15'].sum()
        total_cost = total_delay_minutes * COST_PER_MINUTE
        avg_minutes_per_delayed = total_delay_minutes / total_delayed_flights if total_delayed_flights > 0 else 0
        
        # Top carriers
        carriers = df.groupby('carrier').agg({
            'arr_delay': 'sum',
            'arr_del15': 'sum',
            'arr_flights': 'sum'
        }).reset_index()
        carriers['delay_cost'] = carriers['arr_delay'] * COST_PER_MINUTE
        carriers['avg_delay_per_flight'] = carriers['arr_delay'] / carriers['arr_del15']
        carriers = carriers.nlargest(10, 'delay_cost')
        carriers['carrier_name'] = carriers['carrier'] + ' Airlines'
        
        # Top airports
        airports = df.groupby('origin_airport').agg({
            'arr_delay': 'sum',
            'arr_del15': 'sum',
            'arr_flights': 'sum'
        }).reset_index()
        airports.columns = ['airport', 'delay_minutes', 'delayed_flights', 'total_flights']
        airports['delay_cost'] = airports['delay_minutes'] * COST_PER_MINUTE
        airports['avg_delay_per_flight'] = airports['delay_minutes'] / airports['delayed_flights']
        airports = airports.nlargest(10, 'delay_cost')
        airports['airport_name'] = airports['airport'] + ' Airport'
        
        return {
            "total_delay_cost": round(total_cost, 2),
            "total_delay_minutes": int(total_delay_minutes),
            "avg_minutes_per_delayed_flight": round(avg_minutes_per_delayed, 2),
            "cost_per_minute": COST_PER_MINUTE,
            "top_carriers_by_cost": carriers.to_dict(orient='records'),
            "top_airports_by_cost": airports.to_dict(orient='records')
        }


# =============================================================================
# ALERT ENDPOINTS
# =============================================================================

@app.get("/alerts")
async def get_alerts(
    type: Optional[str] = None,
    severity: Optional[str] = None,
    status: Optional[str] = None,
    carrier: Optional[str] = None,
    airport: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0)
):
    """
    Get alerts with optional filters.
    
    Filters:
    - type: HIGH_DELAY_RISK, CRITICAL_DELAY, ANOMALY, DATA_QUALITY
    - severity: critical, high, medium, low
    - status: active, acknowledged, resolved
    - carrier: carrier code
    - airport: airport code
    """
    try:
        alert_service = get_alert_service()
        
        filter_params = AlertFilter(
            type=AlertType(type) if type else None,
            severity=AlertSeverity(severity) if severity else None,
            status=AlertStatus(status) if status else None,
            carrier=carrier,
            airport=airport,
            limit=limit,
            offset=offset
        )
        
        alerts = alert_service.get_alerts(filter_params)
        
        return {
            "alerts": alerts,
            "count": len(alerts),
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        logger.error(f"Failed to get alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/alerts/stats")
async def get_alert_stats():
    """Get alert statistics."""
    try:
        alert_service = get_alert_service()
        stats = alert_service.get_stats()
        
        return {
            "total": stats.total,
            "active": stats.active,
            "acknowledged": stats.acknowledged,
            "resolved": stats.resolved,
            "by_severity": stats.by_severity,
            "by_type": stats.by_type
        }
    except Exception as e:
        logger.error(f"Failed to get alert stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str, user: str = "system"):
    """Acknowledge an alert."""
    try:
        alert_service = get_alert_service()
        success = alert_service.acknowledge_alert(alert_id, user)
        
        if success:
            return {"status": "acknowledged", "alert_id": alert_id}
        else:
            raise HTTPException(status_code=404, detail="Alert not found or already acknowledged")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to acknowledge alert: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/alerts/{alert_id}/resolve")
async def resolve_alert(alert_id: str):
    """Resolve an alert."""
    try:
        alert_service = get_alert_service()
        success = alert_service.resolve_alert(alert_id)
        
        if success:
            return {"status": "resolved", "alert_id": alert_id}
        else:
            raise HTTPException(status_code=404, detail="Alert not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to resolve alert: {e}")
        raise HTTPException(status_code=500, detail=str(e))
