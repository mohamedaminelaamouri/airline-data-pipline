"""
Client API pour Streamlit
Abstraction des appels API REST
"""
import requests
from typing import List, Dict, Optional
from datetime import datetime
import os

API_BASE_URL = os.getenv("API_BASE_URL", "http://api:8000")


class APIClient:
    """Client pour interagir avec l'API FastAPI"""
    
    def __init__(self, base_url: str = API_BASE_URL):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def _get(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """GET request wrapper"""
        url = f"{self.base_url}{endpoint}"
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()
    
    def _post(self, endpoint: str, data: Dict) -> Dict:
        """POST request wrapper"""
        url = f"{self.base_url}{endpoint}"
        response = self.session.post(url, json=data)
        response.raise_for_status()
        return response.json()
    
    # Predictions
    def list_predictions(
        self,
        risk_threshold: float = 0.5,
        carrier: Optional[str] = None,
        airport: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> Dict:
        """Liste les prédictions avec filtres"""
        params = {
            "risk_threshold": risk_threshold,
            "skip": skip,
            "limit": limit
        }
        if carrier:
            params["carrier"] = carrier
        if airport:
            params["airport"] = airport
        
        return self._get("/api/predictions", params=params)
    
    def get_high_risk_predictions(self) -> List[Dict]:
        """Récupère les prédictions à haut risque (>80%)"""
        return self._get("/api/predictions/high-risk")
    
    def get_prediction_by_route(self, carrier: str, airport: str) -> Dict:
        """Récupère la prédiction pour une route spécifique"""
        return self._get(f"/api/predictions/{carrier}/{airport}")
    
    def score_real_time(
        self,
        carrier: str,
        airport: str,
        month: int,
        year: int,
        features: Dict
    ) -> Dict:
        """Score en temps réel une nouvelle observation"""
        payload = {
            "carrier": carrier,
            "airport": airport,
            "month": month,
            "year": year,
            "features": features
        }
        return self._post("/api/score", payload)
    
    # Analytics
    def get_summary_stats(self) -> Dict:
        """Récupère les statistiques globales"""
        return self._get("/api/analytics/summary")
    
    def get_carrier_performance(self) -> List[Dict]:
        """Récupère la performance par carrier"""
        return self._get("/api/analytics/carriers")
    
    def get_airport_performance(self) -> List[Dict]:
        """Récupère la performance par airport"""
        return self._get("/api/analytics/airports")
    
    # Models
    def list_models(self) -> List[Dict]:
        """Liste tous les modèles enregistrés"""
        return self._get("/api/models")
    
    def get_latest_model(self) -> Dict:
        """Récupère le dernier modèle déployé"""
        return self._get("/api/models/latest")
    
    # Health
    def health_check(self) -> Dict:
        """Vérifie la santé de l'API"""
        return self._get("/")


# Instance globale
api_client = APIClient()
