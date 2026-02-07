"""
Alert Service
=============
Business logic for creating, managing, and triggering alerts.
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from pymongo import MongoClient, DESCENDING
from pymongo.collection import Collection
import os

from .models import (
    Alert, AlertCreate, AlertType, AlertSeverity, 
    AlertStatus, AlertStats, AlertFilter
)


class AlertService:
    """Service for managing alerts."""
    
    def __init__(self, mongo_collection: Collection):
        self.collection = mongo_collection
        self._ensure_indexes()
    
    def _ensure_indexes(self):
        """Create necessary indexes."""
        self.collection.create_index([("created_at", DESCENDING)])
        self.collection.create_index([("status", 1)])
        self.collection.create_index([("severity", 1)])
        self.collection.create_index([("type", 1)])
        self.collection.create_index([("carrier", 1), ("airport", 1)])
    
    def create_alert(self, alert_data: AlertCreate) -> Alert:
        """Create a new alert."""
        alert = Alert(
            type=alert_data.type,
            severity=alert_data.severity,
            title=alert_data.title,
            message=alert_data.message,
            carrier=alert_data.carrier,
            airport=alert_data.airport,
            year=alert_data.year,
            month=alert_data.month,
            prediction=alert_data.prediction,
            metadata=alert_data.metadata
        )
        
        doc = {
            "_id": alert.id,
            "type": alert.type.value,
            "severity": alert.severity.value,
            "status": alert.status.value,
            "title": alert.title,
            "message": alert.message,
            "carrier": alert.carrier,
            "airport": alert.airport,
            "year": alert.year,
            "month": alert.month,
            "prediction": alert.prediction,
            "metadata": alert.metadata,
            "created_at": alert.created_at,
            "acknowledged_at": None,
            "resolved_at": None,
            "acknowledged_by": None
        }
        
        self.collection.insert_one(doc)
        return alert
    
    def get_alerts(self, filter_params: AlertFilter) -> List[Dict]:
        """Get alerts with filters."""
        query = {}
        
        if filter_params.type:
            query["type"] = filter_params.type.value
        if filter_params.severity:
            query["severity"] = filter_params.severity.value
        if filter_params.status:
            query["status"] = filter_params.status.value
        if filter_params.carrier:
            query["carrier"] = filter_params.carrier
        if filter_params.airport:
            query["airport"] = filter_params.airport
        
        cursor = self.collection.find(query)\
            .sort("created_at", DESCENDING)\
            .skip(filter_params.offset)\
            .limit(filter_params.limit)
        
        alerts = []
        for doc in cursor:
            alerts.append({
                "id": doc["_id"],
                "type": doc["type"],
                "severity": doc["severity"],
                "status": doc["status"],
                "title": doc["title"],
                "message": doc["message"],
                "carrier": doc.get("carrier"),
                "airport": doc.get("airport"),
                "year": doc.get("year"),
                "month": doc.get("month"),
                "prediction": doc.get("prediction"),
                "created_at": doc["created_at"].isoformat() + "Z",
                "acknowledged_at": doc["acknowledged_at"].isoformat() + "Z" if doc.get("acknowledged_at") else None
            })
        
        return alerts
    
    def acknowledge_alert(self, alert_id: str, user: str = "system") -> bool:
        """Mark an alert as acknowledged."""
        result = self.collection.update_one(
            {"_id": alert_id, "status": AlertStatus.ACTIVE.value},
            {
                "$set": {
                    "status": AlertStatus.ACKNOWLEDGED.value,
                    "acknowledged_at": datetime.utcnow(),
                    "acknowledged_by": user
                }
            }
        )
        return result.modified_count > 0
    
    def resolve_alert(self, alert_id: str) -> bool:
        """Mark an alert as resolved."""
        result = self.collection.update_one(
            {"_id": alert_id},
            {
                "$set": {
                    "status": AlertStatus.RESOLVED.value,
                    "resolved_at": datetime.utcnow()
                }
            }
        )
        return result.modified_count > 0
    
    def get_stats(self) -> AlertStats:
        """Get alert statistics."""
        pipeline = [
            {
                "$facet": {
                    "by_status": [
                        {"$group": {"_id": "$status", "count": {"$sum": 1}}}
                    ],
                    "by_severity": [
                        {"$group": {"_id": "$severity", "count": {"$sum": 1}}}
                    ],
                    "by_type": [
                        {"$group": {"_id": "$type", "count": {"$sum": 1}}}
                    ],
                    "total": [
                        {"$count": "count"}
                    ]
                }
            }
        ]
        
        result = list(self.collection.aggregate(pipeline))[0]
        
        status_counts = {r["_id"]: r["count"] for r in result["by_status"]}
        severity_counts = {r["_id"]: r["count"] for r in result["by_severity"]}
        type_counts = {r["_id"]: r["count"] for r in result["by_type"]}
        total = result["total"][0]["count"] if result["total"] else 0
        
        return AlertStats(
            total=total,
            active=status_counts.get("active", 0),
            acknowledged=status_counts.get("acknowledged", 0),
            resolved=status_counts.get("resolved", 0),
            by_severity=severity_counts,
            by_type=type_counts
        )


def check_prediction_for_alerts(
    prediction: float,
    carrier: str,
    airport: str,
    year: int,
    month: int,
    alert_service: AlertService
) -> Optional[Alert]:
    """
    Check if a prediction should trigger an alert.
    Called after each prediction.
    """
    if prediction >= 0.85:
        # Critical delay risk
        return alert_service.create_alert(AlertCreate(
            type=AlertType.CRITICAL_DELAY,
            severity=AlertSeverity.CRITICAL,
            title=f"Critical Delay Risk: {carrier}/{airport}",
            message=f"Prediction de retard de {prediction*100:.1f}% pour {carrier} a {airport} ({month}/{year}). Action immediate requise.",
            carrier=carrier,
            airport=airport,
            year=year,
            month=month,
            prediction=prediction
        ))
    
    elif prediction >= 0.70:
        # High delay risk
        return alert_service.create_alert(AlertCreate(
            type=AlertType.HIGH_DELAY_RISK,
            severity=AlertSeverity.HIGH,
            title=f"High Delay Risk: {carrier}/{airport}",
            message=f"Risque eleve de retard ({prediction*100:.1f}%) pour {carrier} a {airport} ({month}/{year}).",
            carrier=carrier,
            airport=airport,
            year=year,
            month=month,
            prediction=prediction
        ))
    
    return None


# Global alert service instance
_alert_service: Optional[AlertService] = None


def get_alert_service() -> AlertService:
    """Get or create the alert service singleton."""
    global _alert_service
    
    if _alert_service is None:
        mongo_uri = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/')
        client = MongoClient(mongo_uri)
        db = client['airline_ml']
        collection = db['alerts']
        _alert_service = AlertService(collection)
    
    return _alert_service
