# Plateforme Interactive ML - Documentation Complète

## Vue d'Ensemble

Plateforme web interactive pour présenter, explorer et monitorer les résultats de machine learning du projet Airline Delay Prediction.

## Architecture Globale

```
┌─────────────────────────────────────────────────────────────┐
│                    FRONTEND (Streamlit)                      │
│                                                               │
│  ┌────────────┐  ┌──────────────┐  ┌─────────┐  ┌─────────┐│
│  │   Home     │  │ Predictions  │  │  SHAP   │  │Monitoring││
│  │ Dashboard  │  │  Explorer    │  │Explain. │  │  Drift   ││
│  └────────────┘  └──────────────┘  └─────────┘  └─────────┘│
│         │                │                │           │       │
│         └────────────────┴────────────────┴───────────┘       │
│                          │                                    │
│                 ┌────────▼────────┐                          │
│                 │  API Client     │                          │
│                 │  (REST Wrapper) │                          │
│                 └────────┬────────┘                          │
└──────────────────────────┼───────────────────────────────────┘
                           │ HTTP/REST
                           │
┌──────────────────────────▼───────────────────────────────────┐
│                     BACKEND (FastAPI)                         │
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Predictions  │  │  Analytics   │  │    Models    │      │
│  │  Endpoints   │  │  Endpoints   │  │  Endpoints   │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
│         │                  │                  │               │
│         └──────────────────┴──────────────────┘               │
│                           │                                   │
│                   ┌───────▼────────┐                         │
│                   │  MongoDB Driver │                         │
│                   │     (Motor)     │                         │
│                   └───────┬─────────┘                         │
└───────────────────────────┼───────────────────────────────────┘
                            │
                   ┌────────▼────────┐
                   │    MongoDB      │
                   │  (ML Artifacts) │
                   │                 │
                   │  • predictions  │
                   │  • models       │
                   │  • monitoring   │
                   │  • features     │
                   └─────────────────┘
```

## Composants

### 1. Frontend Streamlit (Port 8501)

#### Pages Interactives

**Home.py - Dashboard Principal**
- **Objectif**: Vue d'ensemble instantanée
- **Contenu**:
  - 5 KPIs clés (total predictions, high risk %, avg score, carriers, airports)
  - Top 10 routes à haut risque (bar chart interactif)
  - Distribution des risk scores (histogram 4 niveaux)
  - Performance par carrier (dual subplot: risque + volume)
  - Tendances temporelles (30 derniers jours)
  - Alertes critiques actives (expandable)
- **Interactivité**:
  - Hover tooltips sur tous les charts
  - API status indicator (sidebar)
  - Auto-refresh possible
  - Navigation vers pages détaillées

**1_📊_ML_Predictions.py - Exploration Prédictions**
- **Objectif**: Drill-down détaillé dans les prédictions
- **Contenu**:
  - Filtres multi-dimensionnels:
    * Risk threshold slider (0-100%)
    * Carrier multi-select
    * Sort by (risk_score, delay_rate, created_at)
  - Table paginée (100 items/page)
  - Distribution histogram avec 4 risk levels
  - Feature importance globale
  - Export CSV
- **Interactivité**:
  - Filtres temps réel (debounced)
  - Pagination lazy loading
  - Click-to-drill sur rows
  - Download button

**2_🧠_Explainability.py - SHAP & Feature Importance**
- **Objectif**: Comprendre les décisions du modèle
- **Tabs**:
  1. **Feature Importance Globale**
     - Bar chart horizontal (top 12 features)
     - Pie chart par catégorie (Lag, Seasonality, Volume)
     - Interprétation textuelle automatique
  
  2. **Explication par Route**
     - Sélecteur carrier + airport
     - Waterfall chart SHAP values (baseline → prediction)
     - Contribution de chaque feature (+/-%)
     - Explication détaillée par feature
  
  3. **Feature Impact**
     - Scatter plot: feature value → risk score
     - Trend line LOWESS
     - Corrélation statistics
     - Insights automatiques (forte/faible corrélation)
- **Interactivité**:
  - Dynamic feature selection
  - Hover pour valeurs exactes
  - Color-coded positive/negative impacts
  - Interactive legends

**3_📈_Comparaison.py - Analyses Comparatives**
- **Objectif**: Comparer modèles, périodes, entités
- **Tabs**:
  1. **Modèles**
     - Multi-select modèles à comparer
     - Radar chart 4 métriques (ROC-AUC, Precision, Recall, F1)
     - Table comparative avec highlight max
     - Evolution temporelle (4 subplots)
     - Deltas entre versions
  
  2. **Périodes Temporelles**
     - Date range picker (start/end)
     - Line chart risk score over time
     - Volume + % high risk (dual subplot)
     - Détection anomalies (mean + 2σ)
     - Statistiques période
  
  3. **Carriers vs Airports**
     - Top/Bottom 5 par risk score (side-by-side bars)
     - Scatter plot: risk vs volume (bubble size = high risk count)
     - Heatmap carrier × airport (color scale red-green)
- **Interactivité**:
  - Date pickers
  - Multi-select avec preview
  - Hover sur heatmap cells
  - Zoom/Pan sur scatter

**4_🔍_Monitoring.py - Surveillance Production**
- **Objectif**: Détecter drifts, tracker performance, gérer alertes
- **Tabs**:
  1. **Data Drift**
     - PSI scores par feature (bar chart horizontal)
     - Status color-coded (OK/WARNING/CRITICAL)
     - Radar chart 3 métriques (PSI, KS, Wasserstein)
     - Table détaillée
     - Evolution temporelle PSI moyen (30 jours)
     - Seuils: PSI < 0.1 (OK), 0.1-0.25 (WARNING), ≥0.25 (CRITICAL)
  
  2. **Performance Tracking**
     - 4 line charts (ROC-AUC, Precision, Recall, F1) sur 60 jours
     - Baselines en pointillés
     - Volume vs Performance (dual axis)
     - Statistiques 7 jours vs 30 jours (deltas)
     - Détection dégradation (moving average < threshold)
  
  3. **Alertes**
     - Filtres: severity, type, status
     - Liste alertes expandables
     - Actions: résoudre alerte (button)
     - Timeline 30 jours (stacked bar chart)
     - Statistiques: total, actives, critical, routes affectées
     - Types: DATA_DRIFT, PERFORMANCE, HIGH_RISK, DATA_QUALITY
  
  4. **Model Health**
     - 5 gauges circulaires (Data Quality, Performance Stability, Drift Status, Prediction Volume, API Latency)
     - Overall health score (moyenne)
     - Recommendations automatiques selon scores
     - Status colorés (vert ≥80, orange 60-80, rouge <60)
- **Interactivité**:
  - Filtres temps réel
  - Expand/collapse alertes
  - Boutons actions
  - Gauges animées

### 2. Backend FastAPI (Port 8000)

#### Endpoints REST

**Health & Docs**
```
GET  /                   Root endpoint
GET  /health            Health check
GET  /docs              Swagger UI
GET  /redoc             ReDoc
```

**Predictions**
```
GET  /api/predictions
     ?risk_threshold=0.8
     &carrier=AA
     &airport=JFK
     &skip=0
     &limit=100

GET  /api/predictions/high-risk

GET  /api/predictions/{carrier}/{airport}
```

**Scoring**
```
POST /api/score
     {
       "carrier": "AA",
       "airport": "JFK",
       "month": 12,
       "year": 2025,
       "features": {...}
     }
```

**Analytics**
```
GET  /api/analytics/summary
GET  /api/analytics/carriers
GET  /api/analytics/airports
```

**Models**
```
GET  /api/models
GET  /api/models/latest
```

#### Schémas MongoDB

**predictions** (TTL 6 mois)
```json
{
  "carrier": "AA",
  "origin_airport": "JFK",
  "predicted_delay_rate": 0.28,
  "risk_score": 0.85,
  "model_version": "v2.1.0",
  "explainability": {
    "shap_values": {
      "pair_lag1": 0.15,
      "carrier_lag3": -0.05
    },
    "feature_importance": {...}
  },
  "created_at": "2025-01-15T10:00:00Z"
}
```

**model_registry**
```json
{
  "model_name": "xgboost_delay_classifier",
  "version": "v2.1.0",
  "metrics": {
    "roc_auc": 0.745,
    "precision": 0.77,
    "recall": 0.79,
    "f1_score": 0.78
  },
  "hyperparameters": {...},
  "created_at": "2025-01-10T00:00:00Z",
  "is_active": true
}
```

**model_monitoring**
```json
{
  "model_version": "v2.1.0",
  "date": "2025-01-15",
  "drift_metrics": {
    "psi_score": 0.12,
    "feature_drift": {
      "pair_lag1": 0.08,
      "airport_lag1": 0.25
    }
  },
  "performance_metrics": {
    "roc_auc": 0.738,
    "precision": 0.73
  }
}
```

**feature_store**
```json
{
  "feature_name": "pair_lag1",
  "feature_type": "lag",
  "statistics": {
    "mean": 0.22,
    "std": 0.08,
    "min": 0.0,
    "max": 0.95
  },
  "created_at": "2025-01-01T00:00:00Z"
}
```

**api_logs** (capped 100MB)
```json
{
  "endpoint": "/api/predictions",
  "method": "GET",
  "status_code": 200,
  "response_time_ms": 45,
  "timestamp": "2025-01-15T10:30:15Z"
}
```

### 3. API Client (utils/api_client.py)

Wrapper Python qui abstrait tous les appels REST:

```python
class APIClient:
    base_url = "http://localhost:8000"
    
    def list_predictions(risk_threshold, carrier, airport, skip, limit)
    def get_high_risk_predictions()
    def get_prediction_by_route(carrier, airport)
    def score_real_time(carrier, airport, month, year, features)
    def get_summary_stats()
    def get_carrier_performance()
    def get_airport_performance()
    def list_models()
    def get_latest_model()
    def health_check()
```

## Stack Technique

### Frontend
- **Streamlit 1.30+**: Multi-page app framework
- **Plotly 5.18+**: Interactive charts (express + graph_objects)
- **Pandas 2.1+**: Data manipulation
- **Requests**: HTTP client

### Backend
- **FastAPI 0.109+**: Async web framework
- **Motor 3.3+**: Async MongoDB driver
- **Pydantic 2.5+**: Data validation
- **Uvicorn**: ASGI server

### Database
- **MongoDB 7.0**: Document store pour ML artifacts
- **ClickHouse**: OLAP pour Bronze/Silver/Gold data

### Infrastructure
- **Docker Compose**: Orchestration
- **Pytest**: Testing (backend)
- **GitHub Actions**: CI/CD (future)

## Déploiement

### Docker Compose

```bash
# Démarrer tous les services
docker-compose up -d

# Services démarrés:
# - zookeeper (2181)
# - kafka (9092, 29092)
# - nifi (8080)
# - clickhouse (8123, 9000)
# - mongodb (27017)
# - api (8000)
# - streamlit (8501)
```

### Accès

- **Streamlit**: http://localhost:8501
- **API Swagger**: http://localhost:8000/docs
- **MongoDB**: mongodb://localhost:27017
- **ClickHouse**: http://localhost:8123

## Workflow Utilisateur

### 1. Vue d'Ensemble (Home)
1. Utilisateur ouvre http://localhost:8501
2. Voit dashboard avec 5 KPIs instantanés
3. Identifie top 10 routes à haut risque
4. Observe tendances temporelles

### 2. Exploration Détaillée (Predictions)
1. Clique sur "ML Predictions" dans sidebar
2. Applique filtres (risk threshold, carriers)
3. Explore table paginée
4. Exporte CSV si besoin

### 3. Explainability (SHAP)
1. Clique sur "Explainability"
2. Voit feature importance globale
3. Sélectionne route spécifique (AA → JFK)
4. Analyse waterfall SHAP values
5. Comprend pourquoi risk score = 85%

### 4. Comparaison (Models/Periods)
1. Clique sur "Comparaison"
2. Compare v2.0.0 vs v2.1.0 (radar chart)
3. Observe amélioration ROC-AUC (+0.004)
4. Analyse période décembre 2024 vs janvier 2025
5. Compare carriers AA vs UA

### 5. Monitoring (Production)
1. Clique sur "Monitoring"
2. Vérifie drift (PSI scores par feature)
3. Voit alerte CRITICAL pour airport_lag1
4. Consulte performance tracking (stable)
5. Vérifie model health (87/100 - excellent)

## Métriques Clés

### Performance
- **API Latency**: < 100ms (p95)
- **Page Load**: < 2s
- **Charts Render**: < 500ms

### Scalabilité
- **Concurrent Users**: 10-20 (Streamlit free)
- **API Throughput**: 100+ req/s
- **MongoDB**: 1000+ docs/s

### Données
- **Predictions**: ~350K records (2003-2025)
- **Models**: 5 versions tracked
- **Features**: 21 features engineered

## Security

### Actuel
- **CORS**: Configuré pour localhost:8501
- **MongoDB**: Pas d'auth (dev only)
- **API**: Pas d'auth (interne)

### Production (Recommandé)
- **JWT Auth**: Token-based authentication
- **MongoDB Auth**: Username/password
- **HTTPS**: TLS certificates
- **Rate Limiting**: 100 req/min/user

## Monitoring & Logging

### Logs
- **Backend**: uvicorn JSON logs
- **Frontend**: streamlit console logs
- **MongoDB**: query logs
- **Docker**: json-file driver (10MB max, 3 files)

### Metrics (Future)
- **Prometheus**: Metrics collector
- **Grafana**: Dashboards
- **Alerting**: Email/Slack

## Tests

### Backend Tests
```bash
cd backend
pytest tests/ -v --cov=backend --cov-report=html
```

**Coverage**: 4 test classes, 14 tests
- TestPredictionsAPI: 7 tests
- TestAnalyticsAPI: 2 tests
- TestModelsAPI: 2 tests
- TestHealthCheck: 3 tests

### Frontend Tests (Future)
```bash
# Streamlit testing avec pytest
pytest visualization/tests/ -v
```

## Documentation

### API Docs
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- OpenAPI spec: http://localhost:8000/openapi.json

### README Files
- `/backend/README.md` - Backend API doc
- `/visualization/README.md` - Frontend Streamlit doc
- `/docs/ARCHITECTURE.md` - Architecture globale

## Maintenance

### Updates
```bash
# Update dependencies
pip install --upgrade -r requirements.txt
pip install --upgrade -r requirements-streamlit.txt

# Rebuild containers
docker-compose build --no-cache
docker-compose up -d
```

### Backups
```bash
# MongoDB backup
mongodump --uri mongodb://localhost:27017/airline_ml --out backup/

# Restore
mongorestore --uri mongodb://localhost:27017/airline_ml backup/airline_ml/
```

### Cleanup
```bash
# Clean old predictions (TTL 6 months)
mongosh airline_ml
> db.predictions.deleteMany({"created_at": {$lt: new Date("2024-07-01")}})

# Clean Docker volumes
docker-compose down -v
```

## Troubleshooting

### API ne démarre pas
```bash
# Check port 8000
netstat -an | findstr :8000

# Check MongoDB connection
mongosh mongodb://localhost:27017

# Check logs
docker logs api-backend
```

### Streamlit no data
```bash
# Check API health
curl http://localhost:8000/health

# Populate test data
python scripts/generate_predictions.py

# Check MongoDB data
mongosh airline_ml
> db.predictions.countDocuments()
```

### Visualizations not rendering
```bash
# Clear Streamlit cache
rm -rf ~/.streamlit/cache

# Reinstall plotly
pip install --upgrade plotly
```

## Future Roadmap

### Phase 2 (Q2 2025)
- [ ] Real-time updates (WebSockets)
- [ ] Custom dashboards (user-defined layouts)
- [ ] Email/Slack alerting
- [ ] Multi-user auth (JWT)
- [ ] Report generation (PDF)

### Phase 3 (Q3 2025)
- [ ] A/B testing framework
- [ ] Mobile responsive design
- [ ] Prometheus + Grafana
- [ ] CI/CD GitHub Actions
- [ ] Kubernetes deployment

### Phase 4 (Q4 2025)
- [ ] GraphQL API
- [ ] React.js SPA (alternative frontend)
- [ ] Real-time streaming predictions
- [ ] AutoML integration
- [ ] Multi-tenant architecture

## Conclusion

Cette plateforme interactive offre:

✅ **Accessibilité**: Interface web sans installation
✅ **Interactivité**: Plotly charts, filtres dynamiques, drill-down
✅ **Explainability**: SHAP values, feature importance, waterfall charts
✅ **Monitoring**: Drift detection, alertes, model health
✅ **Professionalisme**: API-First, tests, documentation
✅ **Scalabilité**: Architecture microservices, async

**Objectif atteint**: Plateforme professionnelle pour présenter résultats ML de manière interactive.
