# 🚀 Scénario A: Architecture Médaillon + App Web Interactive

**Branch:** `feature/scenario-a-medallion-api-webapp`  
**Status:** 🚧 En développement  
**Date:** 31 Janvier 2026

---

## 🎯 Objectif

Transformer le projet actuel en une **application web interactive** avec:
1. **Architecture Médaillon** dans ClickHouse (Bronze → Silver → Gold)
2. **API REST** (FastAPI) pour servir les prédictions ML
3. **MongoDB** uniquement pour artifacts ML complexes
4. **Frontend React** pour visualisation interactive

---

## 📊 Architecture Avant/Après

### **AVANT (État Actuel)**
```
NiFi → Kafka → ClickHouse (table unique "flights")
                    ↓
              MongoDB (cache dashboard)
                    ↓
          Streamlit / Power BI
```

**Problèmes:**
- ❌ Pas de séparation Bronze/Silver/Gold
- ❌ MongoDB utilisé comme cache (inutile)
- ❌ Pas d'API REST (hard to extend)
- ❌ Streamlit limité pour interactivité

---

### **APRÈS (Scénario A)**
```
┌─────────────────────────────────────────────────────────────┐
│ Layer 1: DATA INGESTION                                     │
├─────────────────────────────────────────────────────────────┤
│ NiFi → Kafka → Script 1 → ClickHouse BRONZE                │
│                           (raw JSON, 90 days TTL)           │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Layer 2: DATA TRANSFORMATION                                │
├─────────────────────────────────────────────────────────────┤
│ Script Bronze→Silver → ClickHouse SILVER                    │
│                        (validated, enriched)                │
│                              ↓                              │
│                   Materialized Views → GOLD                 │
│                   (business aggregates)                     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Layer 3: ML PIPELINE                                        │
├─────────────────────────────────────────────────────────────┤
│ Script ML Training → XGBoost → MongoDB ML Collections      │
│                                  ├─ predictions (enriched)  │
│                                  ├─ model_registry          │
│                                  └─ explainability (SHAP)   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Layer 4: API & WEB APP                                      │
├─────────────────────────────────────────────────────────────┤
│ FastAPI Backend                                             │
│ ├─ GET /api/predictions/high-risk                          │
│ ├─ GET /api/predictions/:carrier/:airport                  │
│ ├─ POST /api/predict (real-time scoring)                   │
│ └─ GET /api/explainability/:prediction_id                  │
│                              ↓                              │
│ React Frontend                                              │
│ ├─ Interactive risk map                                     │
│ ├─ Route-level predictions                                  │
│ ├─ SHAP explanations                                        │
│ └─ Historical comparisons                                   │
└─────────────────────────────────────────────────────────────┘
```

---

## 📁 Nouvelle Structure de Fichiers

```
ynov-data-pipeline/
├── backend/                          # ← NOUVEAU
│   ├── api/
│   │   ├── main.py                  # FastAPI app
│   │   ├── routes/
│   │   │   ├── predictions.py      # Endpoints prédictions
│   │   │   ├── models.py           # Endpoints modèles
│   │   │   └── analytics.py        # Endpoints analytics
│   │   ├── models/
│   │   │   ├── prediction.py       # Pydantic models
│   │   │   └── response.py
│   │   └── database/
│   │       ├── clickhouse.py       # ClickHouse connector
│   │       └── mongodb.py          # MongoDB connector
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/                         # ← NOUVEAU
│   ├── src/
│   │   ├── components/
│   │   │   ├── RiskMap.jsx         # Carte interactive
│   │   │   ├── PredictionTable.jsx
│   │   │   └── ShapExplanation.jsx
│   │   ├── pages/
│   │   │   ├── Dashboard.jsx
│   │   │   └── RouteDetail.jsx
│   │   └── App.jsx
│   ├── package.json
│   └── Dockerfile
│
├── config/
│   └── clickhouse/
│       ├── init.sql                 # ← MODIFIÉ (Bronze/Silver/Gold)
│       └── medallion_schema.sql     # ← NOUVEAU
│
├── scripts/
│   ├── kafka_to_bronze.py          # ← RENOMMÉ (était kafka_to_clickhouse.py)
│   ├── bronze_to_silver.py         # ← NOUVEAU
│   ├── ml_training_pipeline.py     # ← MODIFIÉ (MongoDB ML only)
│   └── clickhouse_to_mongodb.py    # ← SUPPRIMÉ (plus nécessaire)
│
└── docker-compose.yml               # ← MODIFIÉ (ajout backend, frontend)
```

---

## 🛠️ Plan d'Implémentation (7 Phases)

### **Phase 1: Architecture Médaillon ClickHouse** ⏱️ 2h
- [x] Créer branche `feature/scenario-a-medallion-api-webapp`
- [ ] Créer schéma Bronze/Silver/Gold
- [ ] Migrer script Kafka → Bronze
- [ ] Créer script Bronze → Silver
- [ ] Tester pipeline complet

**Fichiers:**
- `config/clickhouse/medallion_schema.sql`
- `scripts/kafka_to_bronze.py`
- `scripts/bronze_to_silver.py`

---

### **Phase 2: Optimiser MongoDB pour ML** ⏱️ 1h
- [ ] Supprimer collections cache dashboard
- [ ] Créer collections ML optimisées
- [ ] Migrer script ML pour nouveau format
- [ ] Ajouter SHAP values storage

**Collections MongoDB:**
```javascript
ml.predictions: {
  prediction: {...},
  explainability: {shap_values: [...], top_features: [...]},
  metadata: {...}
}

ml.model_registry: {
  model_id, artifacts_path, metrics, deployed_at
}

ml.monitoring: {
  drift_metrics, accuracy_tracking, alerts
}
```

---

### **Phase 3: Backend FastAPI** ⏱️ 3h
- [ ] Setup FastAPI project structure
- [ ] Créer endpoints prédictions
- [ ] Implémenter real-time scoring
- [ ] Ajouter CORS pour frontend
- [ ] Documentation OpenAPI

**Endpoints:**
```python
GET  /api/predictions/high-risk
GET  /api/predictions/{carrier}/{airport}
POST /api/predict
GET  /api/explainability/{prediction_id}
GET  /api/models/latest
GET  /api/analytics/historical
```

---

### **Phase 4: Frontend React** ⏱️ 4h
- [ ] Setup React + Vite
- [ ] Composant carte interactive (Leaflet/Mapbox)
- [ ] Table prédictions avec filtres
- [ ] Page détail route
- [ ] Intégration API backend

**Pages:**
- Dashboard (overview + carte)
- Route Detail (drill-down)
- Model Performance
- Historical Trends

---

### **Phase 5: Docker Integration** ⏱️ 1h
- [ ] Dockerfile backend
- [ ] Dockerfile frontend
- [ ] Mise à jour docker-compose.yml
- [ ] Networks et volumes
- [ ] Healthchecks

---

### **Phase 6: Tests & Quality** ⏱️ 2h
- [ ] Tests unitaires backend (pytest)
- [ ] Tests API (pytest + httpx)
- [ ] Tests frontend (Vitest)
- [ ] Linting (black, eslint)
- [ ] Coverage >80%

---

### **Phase 7: Documentation & CI/CD** ⏱️ 1h
- [ ] README API
- [ ] README Frontend
- [ ] GitHub Actions CI
- [ ] Deployment guide
- [ ] Video demo

---

## 📊 Métriques de Succès

### Performance
- [ ] API latency < 100ms (p95)
- [ ] Frontend load < 2s
- [ ] Real-time scoring < 50ms

### Qualité
- [ ] Test coverage > 80%
- [ ] No critical security issues (Snyk)
- [ ] Lighthouse score > 90

### Fonctionnel
- [ ] 20+ endpoints API documentés
- [ ] Interactive map avec 300+ aéroports
- [ ] SHAP explanations pour toutes prédictions

---

## 🎓 Valeur Pédagogique

Ce projet démontre:
1. ✅ **Data Engineering:** Architecture Médaillon (Bronze/Silver/Gold)
2. ✅ **MLOps:** Model registry, versioning, monitoring
3. ✅ **Backend:** FastAPI, REST API design, async
4. ✅ **Frontend:** React, modern UI/UX
5. ✅ **DevOps:** Docker, CI/CD, multi-service orchestration
6. ✅ **Full-Stack:** End-to-end data product

---

## 📅 Timeline

- **Semaine 1:** Phases 1-2 (Architecture + ML)
- **Semaine 2:** Phases 3-4 (Backend + Frontend)
- **Semaine 3:** Phases 5-7 (Integration + Tests + Doc)

**Total estimé:** ~14 heures de dev

---

## 🔗 Liens Utiles

- **GitHub Branch:** https://github.com/mohamedaminelaamouri/ynov-data-pipeline/tree/feature/scenario-a-medallion-api-webapp
- **Pull Request:** (à créer après Phase 7)
- **Demo Video:** (à créer)
- **Live Demo:** (à déployer sur Render/Railway)

---

## 🚦 Status Tracking

| Phase | Status | Completion | Notes |
|-------|--------|------------|-------|
| Phase 1 | 🟡 In Progress | 10% | Branche créée |
| Phase 2 | ⚪ Not Started | 0% | - |
| Phase 3 | ⚪ Not Started | 0% | - |
| Phase 4 | ⚪ Not Started | 0% | - |
| Phase 5 | ⚪ Not Started | 0% | - |
| Phase 6 | ⚪ Not Started | 0% | - |
| Phase 7 | ⚪ Not Started | 0% | - |

---

**Prochaine étape:** Commencer Phase 1 - Architecture Médaillon ClickHouse 🚀
