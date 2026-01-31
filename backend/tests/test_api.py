"""
Tests pour l'API Predictions
"""
import pytest
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


class TestPredictionsAPI:
    """Tests des endpoints predictions"""
    
    def test_list_predictions_success(self):
        """Test GET /api/predictions avec succès"""
        response = client.get("/api/predictions")
        assert response.status_code == 200
        data = response.json()
        assert "predictions" in data
        assert "total" in data
        assert isinstance(data["predictions"], list)
    
    def test_list_predictions_with_filters(self):
        """Test filtres risk_threshold et carrier"""
        response = client.get("/api/predictions?risk_threshold=0.8&carrier=AA")
        assert response.status_code == 200
        data = response.json()
        
        # Vérifier que tous les résultats respectent les filtres
        for pred in data["predictions"]:
            assert pred["risk_score"] >= 0.8
            assert pred["carrier"] == "AA"
    
    def test_list_predictions_pagination(self):
        """Test pagination avec skip et limit"""
        response = client.get("/api/predictions?skip=0&limit=10")
        assert response.status_code == 200
        data = response.json()
        assert len(data["predictions"]) <= 10
    
    def test_high_risk_predictions(self):
        """Test GET /api/predictions/high-risk"""
        response = client.get("/api/predictions/high-risk")
        assert response.status_code == 200
        predictions = response.json()
        
        # Vérifier que tous ont risk_score > 0.80
        for pred in predictions:
            assert pred["risk_score"] > 0.80
    
    def test_get_prediction_by_route(self):
        """Test GET /api/predictions/{carrier}/{airport}"""
        response = client.get("/api/predictions/AA/JFK")
        
        if response.status_code == 200:
            data = response.json()
            assert data["carrier"] == "AA"
            assert data["airport"] == "JFK"
            assert "risk_score" in data
            assert "explainability" in data
        elif response.status_code == 404:
            # Acceptable si pas de prédiction pour cette route
            assert response.json()["detail"] == "Prediction not found"
    
    def test_get_prediction_invalid_carrier(self):
        """Test avec carrier invalide"""
        response = client.get("/api/predictions/INVALID/JFK")
        assert response.status_code in [404, 422]
    
    def test_real_time_scoring(self):
        """Test POST /api/score pour scoring temps réel"""
        payload = {
            "carrier": "AA",
            "airport": "JFK",
            "month": 2,
            "year": 2026,
            "features": {
                "arr_flights": 1000,
                "pair_lag1": 0.25,
                "is_winter": 1
            }
        }
        
        response = client.post("/api/score", json=payload)
        assert response.status_code == 200
        result = response.json()
        
        assert "risk_score" in result
        assert "predicted_delay_rate" in result
        assert 0 <= result["risk_score"] <= 1
    
    def test_real_time_scoring_missing_fields(self):
        """Test scoring avec champs manquants"""
        payload = {
            "carrier": "AA"
            # Manque airport, month, etc.
        }
        
        response = client.post("/api/score", json=payload)
        assert response.status_code == 422  # Validation error


class TestAnalyticsAPI:
    """Tests des endpoints analytics"""
    
    def test_get_summary_stats(self):
        """Test GET /api/analytics/summary"""
        response = client.get("/api/analytics/summary")
        assert response.status_code == 200
        data = response.json()
        
        assert "total_predictions" in data
        assert "high_risk_count" in data
        assert "avg_risk_score" in data
        assert "carriers_analyzed" in data
    
    def test_get_carrier_performance(self):
        """Test GET /api/analytics/carriers"""
        response = client.get("/api/analytics/carriers")
        assert response.status_code == 200
        carriers = response.json()
        
        assert isinstance(carriers, list)
        if len(carriers) > 0:
            assert "carrier" in carriers[0]
            assert "avg_risk" in carriers[0]


class TestModelsAPI:
    """Tests des endpoints models registry"""
    
    def test_list_models(self):
        """Test GET /api/models"""
        response = client.get("/api/models")
        assert response.status_code == 200
        models = response.json()
        
        assert isinstance(models, list)
        if len(models) > 0:
            model = models[0]
            assert "model_id" in model
            assert "roc_auc" in model
            assert "deployed_at" in model
    
    def test_get_latest_model(self):
        """Test GET /api/models/latest"""
        response = client.get("/api/models/latest")
        
        if response.status_code == 200:
            model = response.json()
            assert "model_id" in model
            assert "metrics" in model
        elif response.status_code == 404:
            assert response.json()["detail"] == "No model found"


class TestHealthCheck:
    """Tests de santé de l'API"""
    
    def test_root_endpoint(self):
        """Test GET / (health check)"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
    
    def test_openapi_docs(self):
        """Test que la documentation Swagger est accessible"""
        response = client.get("/docs")
        assert response.status_code == 200
    
    def test_redoc_docs(self):
        """Test que ReDoc est accessible"""
        response = client.get("/redoc")
        assert response.status_code == 200


# Fixtures pour tests d'intégration
@pytest.fixture
def sample_prediction():
    """Fixture: prédiction exemple pour tests"""
    return {
        "carrier": "AA",
        "airport": "JFK",
        "risk_score": 0.87,
        "predicted_delay_rate": 0.31,
        "confidence_lower": 0.25,
        "confidence_upper": 0.37,
        "model_version": "xgb_v3.2",
        "explainability": {
            "top_features": [
                {"name": "pair_lag1", "shap_value": 0.23},
                {"name": "is_winter", "shap_value": 0.15}
            ]
        }
    }


@pytest.fixture
def mock_mongodb(monkeypatch):
    """Fixture: Mock MongoDB pour tests unitaires"""
    class MockCollection:
        async def find(self, *args, **kwargs):
            return []
        
        async def find_one(self, *args, **kwargs):
            return None
    
    class MockDB:
        predictions = MockCollection()
        model_registry = MockCollection()
    
    # Monkeypatch la connexion MongoDB
    monkeypatch.setattr("api.main.mongo_db", MockDB())
