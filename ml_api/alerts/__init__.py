"""
Alerts Module
=============
Alert system for the ML platform.
"""
from .models import (
    Alert, AlertCreate, AlertType, AlertSeverity, 
    AlertStatus, AlertStats, AlertFilter, AlertResponse
)
from .service import (
    AlertService, get_alert_service, check_prediction_for_alerts
)

__all__ = [
    'Alert', 'AlertCreate', 'AlertType', 'AlertSeverity',
    'AlertStatus', 'AlertStats', 'AlertFilter', 'AlertResponse',
    'AlertService', 'get_alert_service', 'check_prediction_for_alerts'
]
