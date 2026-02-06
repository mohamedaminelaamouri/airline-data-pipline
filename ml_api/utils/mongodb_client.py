"""
MongoDB Client for ML Serving Layer
====================================
Provides connection singleton and utility functions for:
- Feature store access (pre-computed features)
- Prediction storage
- Model metadata
"""
import os
from typing import Optional, Dict, Any, List
from datetime import datetime

from pymongo import MongoClient, ASCENDING
from pymongo.collection import Collection
from pymongo.database import Database


class MongoDBClient:
    """Singleton MongoDB client for ML serving."""
    
    _instance: Optional['MongoDBClient'] = None
    _client: Optional[MongoClient] = None
    _db: Optional[Database] = None
    
    def __new__(cls) -> 'MongoDBClient':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._client is None:
            self._connect()
    
    def _connect(self) -> None:
        """Establish MongoDB connection."""
        mongo_uri = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/')
        db_name = os.getenv('MONGODB_DATABASE', 'airline_ml')
        
        self._client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        self._db = self._client[db_name]
        
        # Ensure indexes exist
        self._create_indexes()
    
    def _create_indexes(self) -> None:
        """Create indexes for fast lookups."""
        # Feature store: lookup by carrier, airport, year, month
        self.feature_store.create_index(
            [("carrier", ASCENDING), ("airport", ASCENDING), 
             ("year", ASCENDING), ("month", ASCENDING)],
            unique=True,
            background=True
        )
        
        # Predictions: lookup by request_id and timestamp
        self.predictions.create_index([("request_id", ASCENDING)], unique=True, background=True)
        self.predictions.create_index([("timestamp", ASCENDING)], background=True)
        self.predictions.create_index(
            [("carrier", ASCENDING), ("airport", ASCENDING)],
            background=True
        )
    
    @property
    def feature_store(self) -> Collection:
        """Get feature_store collection."""
        return self._db['feature_store']
    
    @property
    def predictions(self) -> Collection:
        """Get predictions collection."""
        return self._db['predictions']
    
    @property
    def models(self) -> Collection:
        """Get models collection."""
        return self._db['models']
    
    def get_features(
        self, 
        carrier: str, 
        airport: str, 
        year: int, 
        month: int
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve pre-computed features for a specific route and time.
        
        Args:
            carrier: Airline carrier code (e.g., "AA")
            airport: Airport code (e.g., "ATL")
            year: Year (e.g., 2026)
            month: Month (1-12)
            
        Returns:
            Feature dictionary or None if not found
        """
        doc = self.feature_store.find_one({
            "carrier": carrier,
            "airport": airport,
            "year": year,
            "month": month
        })
        
        if doc and "features" in doc:
            return doc["features"]
        return None
    
    def store_prediction(
        self,
        request_id: str,
        carrier: str,
        airport: str,
        year: int,
        month: int,
        prediction: float,
        risk_category: str,
        model_version: str,
        features_used: Dict[str, Any]
    ) -> str:
        """
        Store a prediction result in MongoDB.
        
        Returns:
            The inserted document ID as string
        """
        doc = {
            "request_id": request_id,
            "carrier": carrier,
            "airport": airport,
            "year": year,
            "month": month,
            "prediction": prediction,
            "risk_category": risk_category,
            "model_version": model_version,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "features_used": features_used
        }
        
        result = self.predictions.insert_one(doc)
        return str(result.inserted_id)
    
    def get_latest_features_for_route(
        self, 
        carrier: str, 
        airport: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get the most recent features for a carrier-airport pair.
        Useful for computing lag features for future predictions.
        """
        doc = self.feature_store.find_one(
            {"carrier": carrier, "airport": airport},
            sort=[("year", -1), ("month", -1)]
        )
        
        if doc:
            return doc
        return None
    
    def get_historical_data(
        self,
        carrier: Optional[str] = None,
        airport: Optional[str] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Get historical feature data for computing lag features.
        """
        query = {}
        if carrier:
            query["carrier"] = carrier
        if airport:
            query["airport"] = airport
            
        cursor = self.feature_store.find(query).sort([
            ("year", ASCENDING), 
            ("month", ASCENDING)
        ]).limit(limit)
        
        return list(cursor)
    
    def health_check(self) -> bool:
        """Check if MongoDB connection is healthy."""
        try:
            self._client.admin.command('ping')
            return True
        except Exception:
            return False


# Singleton instance
def get_mongo_client() -> MongoDBClient:
    """Get the singleton MongoDB client instance."""
    return MongoDBClient()
