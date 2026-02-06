# 🛫 Airline Delay Prediction Pipeline
## Documentation Technique Complète

---

# Table des Matières

1. [Vue d'ensemble](#1-vue-densemble)
2. [Architecture Data Pipeline](#2-architecture-data-pipeline)
3. [Architecture ML Pipeline](#3-architecture-ml-pipeline)
4. [Architecture Serving Layer](#4-architecture-serving-layer)
5. [Détail des Composants](#5-détail-des-composants)
6. [Flux de Données End-to-End](#6-flux-de-données-end-to-end)
7. [Structure des Fichiers](#7-structure-des-fichiers)

---

# 1. Vue d'ensemble

## Objectif du Projet
Prédire la **probabilité de retards aériens** pour une combinaison `(carrier, airport, month, year)` en temps réel, avec une latence < 100ms.

## Stack Technologique

| Couche | Technologies | Rôle |
|--------|--------------|------|
| **Ingestion** | Apache NiFi, Kafka | ETL streaming temps réel |
| **Stockage Analytics** | ClickHouse | Data warehouse OLAP |
| **Stockage Serving** | MongoDB | Feature store + prédictions |
| **ML Training** | Python, XGBoost, Pandas | Entraînement du modèle |
| **ML Serving** | FastAPI, Joblib | API de prédiction |
| **Frontend** | React, Vite | Interface utilisateur |
| **Monitoring** | Streamlit | Dashboard temps réel |

---

# 2. Architecture Data Pipeline

## 2.1 Schéma Global

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  CSV Files   │────►│  Apache      │────►│    Kafka     │────►│  ClickHouse  │
│  (raw data)  │     │    NiFi      │     │  (streaming) │     │   (OLAP)     │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
                           │                                          │
                           │ ETL:                                     │
                           │ - Validation                             │
                           │ - Nettoyage                              │
                           │ - Enrichissement                         │
                           │                                          ▼
                                                              ┌──────────────┐
                                                              │  3 Tables:   │
                                                              │ - bronze     │
                                                              │ - silver     │
                                                              │ - gold       │
                                                              └──────────────┘
```

## 2.2 Tables ClickHouse (Modèle Medallion)

### Bronze Layer: `bronze_raw_delays`
- Données brutes, non transformées
- Schéma identique au CSV source
- Utilisé pour audit et retraitement

### Silver Layer: `silver_delays`  
- Données nettoyées et validées
- Types de données corrects
- Clés primaires définies

```sql
CREATE TABLE silver_delays (
    year UInt16,
    month UInt8,
    carrier String,
    carrier_name String,
    airport String,
    airport_name String,
    arr_flights Float64,
    arr_del15 Float64,
    carrier_ct Float64,
    weather_ct Float64,
    nas_ct Float64,
    security_ct Float64,
    late_aircraft_ct Float64,
    arr_cancelled Float64,
    arr_diverted Float64,
    arr_delay Float64,
    carrier_delay Float64,
    weather_delay Float64,
    nas_delay Float64,
    security_delay Float64,
    late_aircraft_delay Float64
) ENGINE = MergeTree()
PARTITION BY year
ORDER BY (year, month, carrier, airport)
```

### Gold Layer: `gold_ml_features`
- Agrégations pour le ML
- Features pré-calculées
- Prêt pour l'entraînement

```sql
CREATE TABLE gold_ml_features AS
SELECT
    carrier,
    origin_airport,
    year,
    month,
    SUM(arr_flights) as arr_flights,
    SUM(arr_del15) as arr_del15,
    arr_del15 / arr_flights as delay_rate,  -- Target variable
    -- Seasonality flags
    month IN (6,7,8) as is_summer,
    month IN (12,1,2) as is_winter,
    month IN (11,12) as is_holiday_season
FROM silver_delays
GROUP BY carrier, origin_airport, year, month
```

## 2.3 Kafka Topics

| Topic | Format | Contenu |
|-------|--------|---------|
| `airline-delays` | JSON | Messages de vols individuels |

---

# 3. Architecture ML Pipeline

## 3.1 Feature Engineering

### Features Utilisées (20 total)

```python
FEATURE_COLUMNS = [
    # Temporel
    "year",                    # Année (2003-2025)
    "month",                   # Mois (1-12)
    "month_sin",               # sin(2π × month/12)
    "month_cos",               # cos(2π × month/12)
    
    # Saisonnalité
    "is_summer",               # 1 si juin/juillet/août
    "is_winter",               # 1 si décembre/janvier/février
    "is_holiday_season",       # 1 si novembre/décembre
    
    # Encodages catégoriels
    "carrier_encoded",         # LabelEncoder(carrier)
    "airport_encoded",         # LabelEncoder(airport)
    
    # Volume
    "arr_flights",             # Nombre de vols
    "log_arr_flights",         # log(1 + arr_flights)
    
    # Lag Features - Historique de retards
    "pair_lag1",               # Retard du mois précédent (carrier+airport)
    "pair_lag3_mean",          # Moyenne retards 3 derniers mois
    "pair_expanding_mean",     # Moyenne historique complète
    
    "airport_lag1",            # Retard aéroport mois-1
    "airport_lag3_mean",       # Moyenne aéroport 3 mois
    "airport_expanding_mean",  # Moyenne aéroport historique
    
    "carrier_lag1",            # Retard carrier mois-1
    "carrier_lag3_mean",       # Moyenne carrier 3 mois
    "carrier_expanding_mean",  # Moyenne carrier historique
]
```

### Importance des Features

Les **lag features** sont les plus importantes car elles capturent les tendances historiques:
- `pair_lag1` (retard du mois précédent) est souvent le meilleur prédicteur
- Les moyennes glissantes lissent la variance

### Calcul des Lag Features

```python
# Pour chaque paire (carrier, airport)
df['pair_lag1'] = df.groupby(['carrier', 'airport'])['delay_rate'].shift(1)
df['pair_lag3_mean'] = df.groupby(['carrier', 'airport'])['delay_rate'].transform(
    lambda x: x.shift(1).rolling(3, min_periods=1).mean()
)
```

## 3.2 Modèle XGBoost

### Configuration

```python
XGBClassifier(
    n_estimators=100,
    max_depth=6,
    learning_rate=0.1,
    objective='binary:logistic',
    eval_metric='auc'
)
```

### Target Variable

```python
# Classification binaire: taux de retard > 15% ?
y = (df['delay_rate'] > 0.15).astype(int)
```

### Métriques de Performance

| Métrique | Valeur |
|----------|--------|
| Accuracy | ~85% |
| ROC AUC | ~0.90 |
| Precision | ~0.82 |
| Recall | ~0.78 |

## 3.3 Fichiers du Modèle

```
ml/models/runs/production/
├── model.pkl              # XGBoost classifier
├── imputer.pkl            # SimpleImputer pour NaN
├── label_encoder_carrier.pkl
├── label_encoder_airport.pkl
└── metrics.json           # Métriques et version
```

---

# 4. Architecture Serving Layer

## 4.1 Pourquoi MongoDB et pas ClickHouse pour l'inférence?

| Critère | ClickHouse | MongoDB |
|---------|------------|---------|
| **Type** | OLAP (analytics) | OLTP (transactions) |
| **Latence lecture** | ~100-500ms | ~5-10ms |
| **Optimisé pour** | Agrégations sur millions de lignes | Lecture document unique |
| **Use case** | Training, analytics | Serving temps réel |

**Conclusion**: On utilise MongoDB pour des réponses < 100ms.

## 4.2 Flow d'une Prédiction

```
┌─────────────────────────────────────────────────────────────────┐
│                     FLOW DE PRÉDICTION                          │
└─────────────────────────────────────────────────────────────────┘

1. REQUEST → POST /predict
   {carrier: "AA", airport: "ATL", month: 6, year: 2026}
                    │
                    ▼
2. FEATURE LOOKUP → MongoDB.feature_store.find({
                       carrier: "AA", 
                       airport: "ATL",
                       year: 2026, 
                       month: 6
                    })
                    │
           ┌────────┴─────────┐
           ▼                  ▼
   FOUND: use stored    NOT FOUND: fallback
   lag features         to latest historical
                        or defaults (0.15)
                    │
                    ▼
3. BUILD FEATURES → {
      year: 2026,
      month: 6,
      month_sin: 0.866,
      month_cos: 0.5,
      is_summer: 1,
      carrier_encoded: 3,
      airport_encoded: 45,
      pair_lag1: 0.18,
      ...
   }
                    │
                    ▼
4. PREDICT → model.predict_proba(features)
             → 0.92 (92% probabilité de >15% retards)
                    │
                    ▼
5. CLASSIFY → proba >= 0.75 → "critical"
              proba >= 0.50 → "high"
              proba >= 0.25 → "medium"
              proba <  0.25 → "low"
                    │
                    ▼
6. STORE → MongoDB.predictions.insert({
              request_id: "uuid-v4",
              carrier: "AA",
              airport: "ATL",
              prediction: 0.92,
              risk_category: "critical",
              model_version: "20260205_232640",
              timestamp: "2026-02-06T...",
              features_used: {...}
           })
                    │
                    ▼
7. RESPONSE → {
      request_id: "...",
      prediction: 0.92,
      risk_category: "critical",
      model_version: "20260205_232640",
      inputs: {carrier, airport, month, year}
   }
```

## 4.3 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/predict` | POST | Prédiction unique |
| `/predict/batch` | POST | Batch de prédictions (max 100) |
| `/predict/metadata` | GET | Info modèle, carriers, airports |
| `/predictions/history` | GET | Historique avec filtres et pagination |
| `/predictions/{id}` | GET | Une prédiction par ID |
| `/predictions/{id}` | DELETE | Supprimer une prédiction |
| `/health` | GET | Health check |

---

# 5. Détail des Composants

## 5.1 MongoDB Collections

### `feature_store` (346,506 documents)

```javascript
{
  "_id": ObjectId("..."),
  "carrier": "AA",
  "airport": "ATL",
  "year": 2025,
  "month": 12,
  "features": {
    "delay_rate": 0.18,
    "arr_flights": 1234,
    "log_arr_flights": 7.12,
    "pair_lag1": 0.16,
    "pair_lag3_mean": 0.15,
    "pair_expanding_mean": 0.14,
    "airport_lag1": 0.17,
    "carrier_lag1": 0.15,
    ...
  },
  "created_at": "2026-02-06T..."
}
```

**Index**: `(carrier, airport, year, month)` → lookup < 5ms

### `predictions` (historique)

```javascript
{
  "_id": ObjectId("..."),
  "request_id": "48404a04-728d-43ad-a42f-5b61304883ff",
  "carrier": "AA",
  "airport": "ATL",
  "year": 2026,
  "month": 6,
  "prediction": 0.92,
  "risk_category": "critical",
  "model_version": "20260205_232640",
  "timestamp": "2026-02-06T20:27:46.082559Z",
  "features_used": {...}
}
```

## 5.2 ML Service (Singleton Pattern)

```python
class MLModelService:
    _instance = None  # Singleton
    _model = None     # XGBoost (chargé 1 fois)
    _imputer = None
    _le_carrier = None
    _le_airport = None
    
    def predict(self, features: dict) -> tuple[float, str]:
        # 1. Construire vecteur de features
        X = np.array([[features[col] for col in FEATURE_COLUMNS]])
        
        # 2. Appliquer imputer
        X = self._imputer.transform(X)
        
        # 3. Prédire probabilité
        proba = self._model.predict_proba(X)[0, 1]
        
        # 4. Classifier le risque
        if proba >= 0.75: return proba, "critical"
        elif proba >= 0.50: return proba, "high"
        ...
```

**Avantage du Singleton**: Le modèle est chargé 1 seule fois → latence réduite.

---

# 6. Flux de Données End-to-End

```
                              ENTRAÎNEMENT (offline)
┌─────────────────────────────────────────────────────────────────┐
│                                                                  │
│  CSV ──► NiFi ──► Kafka ──► ClickHouse ──► Training Script      │
│                                 │              │                 │
│                                 │              ▼                 │
│                                 │         model.pkl              │
│                                 │              │                 │
│                                 ▼              │                 │
│                          gold_ml_features      │                 │
│                                 │              │                 │
│                                 ▼              │                 │
│                    populate_feature_store.py   │                 │
│                                 │              │                 │
│                                 ▼              │                 │
│                           MongoDB ◄────────────┘                 │
│                        (feature_store)                           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘

                              INFERENCE (online)
┌─────────────────────────────────────────────────────────────────┐
│                                                                  │
│  React UI ──► FastAPI ──► MongoDB.feature_store ──► XGBoost     │
│     │                          │                        │        │
│     │                          │                        ▼        │
│     │                          │                   prediction    │
│     │                          │                        │        │
│     │                          ▼                        ▼        │
│     │                    features           MongoDB.predictions  │
│     │                                              │             │
│     ◄──────────────────────────────────────────────┘             │
│                         response                                 │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

# 7. Structure des Fichiers

```
ynov-data-pipeline-main/
│
├── docker-compose.yml          # Orchestration containers
│
├── ml_api/                     # API FastAPI
│   ├── app.py                  # Endpoints /predict, /history, etc.
│   └── utils/
│       ├── mongodb_client.py   # Connexion MongoDB
│       └── ml_inference.py     # Chargement modèle + prédiction
│
├── prediction_ui/              # React UI (Vite)
│   ├── src/
│   │   ├── App.jsx             # Main component
│   │   └── components/
│   │       ├── PredictionForm.jsx
│   │       ├── BatchPrediction.jsx
│   │       └── PredictionHistory.jsx
│   └── vite.config.js
│
├── ml/                         # ML Pipeline
│   ├── models/runs/production/ # Modèle de production
│   │   ├── model.pkl
│   │   ├── imputer.pkl
│   │   └── label_encoder_*.pkl
│   ├── notebooks/
│   │   └── training_complete.py
│   └── src/yno_ml/
│       ├── features.py         # Feature engineering
│       └── train.py            # Training script
│
├── scripts/
│   ├── populate_feature_store.py  # Sync ClickHouse → MongoDB
│   └── train_model_2026.py
│
├── realtime_app.py             # Streamlit dashboard
│
└── docs/
    └── ML_SERVING_LAYER.md     # Documentation API
```

---

# Résumé

| Composant | Technologie | Port | Rôle |
|-----------|-------------|------|------|
| Data Warehouse | ClickHouse | 8123 | Stockage analytics (OLAP) |
| Feature Store | MongoDB | 27017 | Stockage temps réel (OLTP) |
| ML Model | XGBoost | - | Classification binaire |
| API | FastAPI | 8001 | Serving layer |
| UI | React/Vite | 3001 | Interface prédiction |
| Dashboard | Streamlit | 8501 | Monitoring temps réel |
| Streaming | Kafka | 9092 | Messages temps réel |
| ETL | NiFi | 8080 | Ingestion données |
