"""
FastAPI Backend for Airline Delay Prediction
Serves ML predictions with real-time scoring capabilities
"""
from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, date
from motor.motor_asyncio import AsyncIOMotorClient
import numpy as np
import joblib
from pathlib import Path
import os

# ============================================================================
# Configuration
# ============================================================================

MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
MONGODB_DB = "airline_ml"
MODEL_PATH = "models/ml_runs/latest"

# ============================================================================
# FastAPI App
# ============================================================================

app = FastAPI(
    title="Airline Delay Prediction API",
    description="Real-time ML predictions for airline delays",
    version="1.0.0"
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# Database Connection
# ============================================================================

mongodb_client: Optional[AsyncIOMotorClient] = None

@app.on_event("startup")
async def startup_db_client():
    global mongodb_client
    mongodb_client = AsyncIOMotorClient(MONGODB_URL)
    print(f"✅ Connected to MongoDB: {MONGODB_URL}")

@app.on_event("shutdown")
async def shutdown_db_client():
    if mongodb_client:
        mongodb_client.close()
        print("✅ MongoDB connection closed")

def get_database():
    return mongodb_client[MONGODB_DB]

# ============================================================================
# Models (Pydantic)
# ============================================================================

class PredictionResponse(BaseModel):
    carrier: str
    airport: str
    month: date
    risk_score: float = Field(..., ge=0, le=1)
    predicted_delay_rate: float
    confidence_interval: Optional[List[float]] = None
    model_version: str
    top_features: Optional[List[Dict[str, Any]]] = None

class HighRiskRoute(BaseModel):
    route: str
    carrier: str
    airport: str
    risk_score: float
    predicted_delay_rate: float
    alerts: List[str]

class ModelInfo(BaseModel):
    model_id: str
    version: str
    status: str
    metrics: Dict[str, float]
    trained_at: datetime

class ScoringRequest(BaseModel):
    carrier: str
    airport: str
    month: str  # Format: "2026-02"
    features: Optional[Dict[str, float]] = None

class ScoringResponse(BaseModel):
    carrier: str
    airport: str
    risk_score: float
    prediction: str  # "high_risk" | "medium_risk" | "low_risk"
    confidence: float

# ============================================================================
# Endpoints
# ============================================================================

@app.get("/")
async def root():
    return {
        "service": "Airline Delay Prediction API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "predictions": "/api/predictions",
            "high_risk": "/api/predictions/high-risk",
            "models": "/api/models",
            "score": "/api/score"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    db = get_database()
    try:
        # Test MongoDB connection
        await db.command("ping")
        return {"status": "healthy", "mongodb": "connected"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"MongoDB unhealthy: {str(e)}")

# ============================================================================
# Predictions Endpoints
# ============================================================================

@app.get("/api/predictions", response_model=List[PredictionResponse])
async def get_predictions(
    carrier: Optional[str] = Query(None, description="Filter by carrier code"),
    airport: Optional[str] = Query(None, description="Filter by airport code"),
    min_risk: Optional[float] = Query(0.0, ge=0, le=1, description="Minimum risk score"),
    limit: int = Query(20, ge=1, le=100, description="Maximum results")
):
    """Get predictions with optional filters"""
    db = get_database()
    
    # Build query
    query = {}
    if carrier:
        query["prediction.carrier"] = carrier.upper()
    if airport:
        query["prediction.airport"] = airport.upper()
    if min_risk > 0:
        query["prediction.risk_score"] = {"$gte": min_risk}
    
    # Execute query
    cursor = db.predictions.find(query).sort("prediction.risk_score", -1).limit(limit)
    predictions = await cursor.to_list(length=limit)
    
    # Transform response
    results = []
    for pred in predictions:
        results.append(PredictionResponse(
            carrier=pred["prediction"]["carrier"],
            airport=pred["prediction"]["airport"],
            month=pred["prediction"]["month"],
            risk_score=pred["prediction"]["risk_score"],
            predicted_delay_rate=pred["prediction"].get("predicted_delay_rate", 0.0),
            confidence_interval=pred["prediction"].get("confidence_interval"),
            model_version=pred["model_info"]["model_id"],
            top_features=pred.get("explainability", {}).get("top_features", [])
        ))
    
    return results

@app.get("/api/predictions/high-risk", response_model=List[HighRiskRoute])
async def get_high_risk_routes(
    threshold: float = Query(0.80, ge=0, le=1, description="Risk threshold"),
    limit: int = Query(20, ge=1, le=100)
):
    """Get high-risk routes above threshold"""
    db = get_database()
    
    cursor = db.predictions.aggregate([
        {"$match": {"prediction.risk_score": {"$gte": threshold}}},
        {"$sort": {"prediction.risk_score": -1}},
        {"$limit": limit},
        {"$project": {
            "route": {"$concat": ["$prediction.carrier", " → ", "$prediction.airport"]},
            "carrier": "$prediction.carrier",
            "airport": "$prediction.airport",
            "risk_score": "$prediction.risk_score",
            "predicted_delay_rate": "$prediction.predicted_delay_rate",
            "alerts": "$alerts"
        }}
    ])
    
    routes = await cursor.to_list(length=limit)
    
    results = []
    for route in routes:
        alerts_list = [alert["message"] for alert in route.get("alerts", [])]
        results.append(HighRiskRoute(
            route=route["route"],
            carrier=route["carrier"],
            airport=route["airport"],
            risk_score=route["risk_score"],
            predicted_delay_rate=route.get("predicted_delay_rate", 0.0),
            alerts=alerts_list
        ))
    
    return results

@app.get("/api/predictions/{carrier}/{airport}", response_model=PredictionResponse)
async def get_prediction_for_route(
    carrier: str,
    airport: str,
    month: Optional[str] = Query(None, description="Month in format YYYY-MM")
):
    """Get prediction for specific carrier-airport pair"""
    db = get_database()
    
    query = {
        "prediction.carrier": carrier.upper(),
        "prediction.airport": airport.upper()
    }
    
    if month:
        # Parse month and create date range
        try:
            month_date = datetime.strptime(month, "%Y-%m")
            query["prediction.month"] = month_date
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid month format. Use YYYY-MM")
    
    # Get most recent prediction
    pred = await db.predictions.find_one(
        query,
        sort=[("created_at", -1)]
    )
    
    if not pred:
        raise HTTPException(
            status_code=404,
            detail=f"No prediction found for {carrier} → {airport}"
        )
    
    return PredictionResponse(
        carrier=pred["prediction"]["carrier"],
        airport=pred["prediction"]["airport"],
        month=pred["prediction"]["month"],
        risk_score=pred["prediction"]["risk_score"],
        predicted_delay_rate=pred["prediction"].get("predicted_delay_rate", 0.0),
        confidence_interval=pred["prediction"].get("confidence_interval"),
        model_version=pred["model_info"]["model_id"],
        top_features=pred.get("explainability", {}).get("top_features", [])
    )

# ============================================================================
# Model Management Endpoints
# ============================================================================

@app.get("/api/models", response_model=List[ModelInfo])
async def list_models(
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(10, ge=1, le=50)
):
    """List available models"""
    db = get_database()
    
    query = {}
    if status:
        query["status"] = status
    
    cursor = db.model_registry.find(query).sort("trained_at", -1).limit(limit)
    models = await cursor.to_list(length=limit)
    
    return [ModelInfo(**model) for model in models]

@app.get("/api/models/latest", response_model=ModelInfo)
async def get_latest_model():
    """Get latest deployed model"""
    db = get_database()
    
    model = await db.model_registry.find_one(
        {"status": "deployed"},
        sort=[("trained_at", -1)]
    )
    
    if not model:
        raise HTTPException(status_code=404, detail="No deployed model found")
    
    return ModelInfo(**model)

# ============================================================================
# Real-time Scoring Endpoint
# ============================================================================

@app.post("/api/score", response_model=ScoringResponse)
async def score_route(request: ScoringRequest):
    """
    Real-time scoring endpoint
    Loads model and predicts for given carrier-airport-month
    """
    # TODO: Load model from disk/cache
    # TODO: Extract features from ClickHouse
    # TODO: Run prediction
    # This is a placeholder for now
    
    # Simulate scoring
    risk_score = np.random.uniform(0.3, 0.9)
    
    if risk_score > 0.8:
        prediction = "high_risk"
    elif risk_score > 0.5:
        prediction = "medium_risk"
    else:
        prediction = "low_risk"
    
    return ScoringResponse(
        carrier=request.carrier.upper(),
        airport=request.airport.upper(),
        risk_score=risk_score,
        prediction=prediction,
        confidence=0.85
    )

# ============================================================================
# Analytics Endpoints
# ============================================================================

@app.get("/api/analytics/summary")
async def get_analytics_summary():
    """Get overall analytics summary"""
    db = get_database()
    
    # Aggregate statistics
    pipeline = [
        {
            "$group": {
                "_id": None,
                "total_predictions": {"$sum": 1},
                "avg_risk_score": {"$avg": "$prediction.risk_score"},
                "high_risk_count": {
                    "$sum": {
                        "$cond": [{"$gte": ["$prediction.risk_score", 0.8]}, 1, 0]
                    }
                }
            }
        }
    ]
    
    cursor = db.predictions.aggregate(pipeline)
    results = await cursor.to_list(length=1)
    
    if not results:
        return {
            "total_predictions": 0,
            "avg_risk_score": 0,
            "high_risk_count": 0,
            "high_risk_percentage": 0
        }
    
    summary = results[0]
    summary["high_risk_percentage"] = (
        summary["high_risk_count"] / summary["total_predictions"] * 100
        if summary["total_predictions"] > 0 else 0
    )
    
    return summary

# ============================================================================
# Run with: uvicorn backend.api.main:app --reload --port 8000
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
