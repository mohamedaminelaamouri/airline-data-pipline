# Backend API - ML Predictions Service

API REST FastAPI pour servir les prédictions ML et analytics.

## Architecture

```
backend/
├── api/
│   └── main.py              # FastAPI application
├── requirements.txt         # Dependencies
├── requirements-test.txt    # Test dependencies
└── tests/
    ├── __init__.py
    └── test_api.py          # API tests
```

## Installation

```bash
cd backend
pip install -r requirements.txt
```

## Démarrage

### Local Development
```bash
uvicorn backend.api.main:app --reload
```

### Docker
```bash
docker-compose up api
```

L'API sera disponible sur: http://localhost:8000

## Endpoints

### Health & Documentation
- `GET /` - Root endpoint
- `GET /health` - Health check
- `GET /docs` - Swagger UI (interactive docs)
- `GET /redoc` - ReDoc documentation

### Predictions
- `GET /api/predictions` - Liste toutes les prédictions
  - Query params: `risk_threshold`, `carrier`, `airport`, `skip`, `limit`
- `GET /api/predictions/high-risk` - Prédictions high risk (>80%)
- `GET /api/predictions/{carrier}/{airport}` - Prédiction par route spécifique

### Scoring
- `POST /api/score` - Score une nouvelle route en temps réel
  ```json
  {
    "carrier": "AA",
    "airport": "JFK",
    "month": 12,
    "year": 2025,
    "features": {...}
  }
  ```

### Analytics
- `GET /api/analytics/summary` - Statistiques globales
- `GET /api/analytics/carriers` - Performance par carrier
- `GET /api/analytics/airports` - Performance par airport

### Models
- `GET /api/models` - Liste des modèles enregistrés
- `GET /api/models/latest` - Dernier modèle actif

## MongoDB Collections

### 1. predictions
```javascript
{
  carrier: String,
  origin_airport: String,
  predicted_delay_rate: Number,
  risk_score: Number,  // 0-1
  model_version: String,
  explainability: {
    shap_values: Object,
    feature_importance: Object
  },
  created_at: Date
}
```
TTL: 6 mois

### 2. model_registry
```javascript
{
  model_name: String,
  version: String,
  metrics: {
    roc_auc: Number,
    precision: Number,
    recall: Number
  },
  created_at: Date,
  is_active: Boolean
}
```

### 3. model_monitoring
```javascript
{
  model_version: String,
  date: Date,
  drift_metrics: {
    psi_score: Number,
    feature_drift: Object
  },
  performance_metrics: Object
}
```

### 4. feature_store
```javascript
{
  feature_name: String,
  feature_type: String,
  statistics: Object,
  created_at: Date
}
```

### 5. api_logs (capped)
```javascript
{
  endpoint: String,
  method: String,
  status_code: Number,
  response_time_ms: Number,
  timestamp: Date
}
```
Capped: 100MB

## Tests

```bash
# Install test dependencies
pip install -r requirements-test.txt

# Run tests
pytest backend/tests/ -v

# With coverage
pytest backend/tests/ --cov=backend --cov-report=html
```

## Configuration

Variables d'environnement:

```bash
MONGODB_URL=mongodb://localhost:27017
MONGODB_DB=airline_ml
CLICKHOUSE_HOST=localhost
CLICKHOUSE_PORT=8123
MODEL_PATH=./models/ml_runs/latest
```

## Integration avec Streamlit

Le frontend Streamlit utilise l'API via `utils/api_client.py`:

```python
from utils.api_client import api_client

# Get predictions
predictions = api_client.list_predictions(risk_threshold=0.8)

# Get analytics
stats = api_client.get_summary_stats()
```

## Performance

- **Latency cible**: < 100ms pour GET endpoints
- **Throughput**: 100+ req/s sur machine standard
- **Cache**: MongoDB avec TTL indexes
- **Async**: Motor (async MongoDB driver)

## Monitoring

### Prometheus Metrics (future)
- Request count
- Response time
- Error rate
- Active connections

### Logs
JSON structured logs via uvicorn

## Security

- **CORS**: Configuré pour Streamlit (localhost:8501)
- **Rate Limiting**: À implémenter (future)
- **Auth**: À implémenter si besoin (JWT)

## API Examples

### Get High Risk Predictions
```bash
curl http://localhost:8000/api/predictions/high-risk
```

### Score Real-time
```bash
curl -X POST http://localhost:8000/api/score \
  -H "Content-Type: application/json" \
  -d '{
    "carrier": "AA",
    "airport": "JFK",
    "month": 12,
    "year": 2025,
    "features": {
      "pair_lag1": 0.28,
      "carrier_lag3_mean": 0.25
    }
  }'
```

### Get Summary Stats
```bash
curl http://localhost:8000/api/analytics/summary
```

## Troubleshooting

### MongoDB Connection Error
```bash
# Check MongoDB is running
docker ps | grep mongodb

# Check connection
mongosh mongodb://localhost:27017
```

### API Not Starting
```bash
# Check port 8000 is free
netstat -an | findstr :8000

# Check dependencies
pip list | grep fastapi
```

### No Predictions Returned
```bash
# Initialize MongoDB collections
mongosh < config/mongodb/init_ml_collections.js

# Populate with test data
python scripts/generate_predictions.py
```

## Future Improvements

1. **Authentication**: JWT tokens
2. **Rate Limiting**: Redis-based limiter
3. **Caching**: Redis for hot data
4. **Metrics**: Prometheus + Grafana
5. **Async Tasks**: Celery for batch scoring
6. **Webhooks**: Real-time notifications
7. **GraphQL**: Alternative to REST
8. **Versioning**: API v2, v3 paths
