"""
Alert Models and Schemas
========================
Pydantic models for the alert system.
"""
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
import uuid


class AlertType(str, Enum):
    """Types of alerts in the system."""
    HIGH_DELAY_RISK = "HIGH_DELAY_RISK"      # Prediction > 70%
    CRITICAL_DELAY = "CRITICAL_DELAY"         # Prediction > 85%
    ANOMALY = "ANOMALY"                       # Unusual pattern
    DATA_QUALITY = "DATA_QUALITY"             # Missing/invalid data
    MODEL_DRIFT = "MODEL_DRIFT"               # Model performance issue


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    CRITICAL = "critical"  # Immediate action required
    HIGH = "high"          # Urgent attention needed
    MEDIUM = "medium"      # Should be reviewed
    LOW = "low"            # Informational


class AlertStatus(str, Enum):
    """Alert status."""
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class AlertCreate(BaseModel):
    """Schema for creating a new alert."""
    type: AlertType
    severity: AlertSeverity
    title: str
    message: str
    carrier: Optional[str] = None
    airport: Optional[str] = None
    year: Optional[int] = None
    month: Optional[int] = None
    prediction: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


class Alert(BaseModel):
    """Full alert model."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: AlertType
    severity: AlertSeverity
    status: AlertStatus = AlertStatus.ACTIVE
    title: str
    message: str
    carrier: Optional[str] = None
    airport: Optional[str] = None
    year: Optional[int] = None
    month: Optional[int] = None
    prediction: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None


class AlertResponse(BaseModel):
    """Response model for alerts."""
    id: str
    type: str
    severity: str
    status: str
    title: str
    message: str
    carrier: Optional[str]
    airport: Optional[str]
    year: Optional[int]
    month: Optional[int]
    prediction: Optional[float]
    created_at: str
    acknowledged_at: Optional[str]


class AlertStats(BaseModel):
    """Alert statistics."""
    total: int
    active: int
    acknowledged: int
    resolved: int
    by_severity: Dict[str, int]
    by_type: Dict[str, int]


class AlertFilter(BaseModel):
    """Filter parameters for alerts."""
    type: Optional[AlertType] = None
    severity: Optional[AlertSeverity] = None
    status: Optional[AlertStatus] = None
    carrier: Optional[str] = None
    airport: Optional[str] = None
    limit: int = 50
    offset: int = 0
