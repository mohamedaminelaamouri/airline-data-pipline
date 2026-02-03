# Architecture Détaillée - Airline Data Pipeline

**Date:** 3 Février 2026  
**Version:** 7.0  
**Statut:** Production

---

## 📋 Vue d'Ensemble

### Objectif Principal
Pipeline de données temps réel avec Machine Learning pour prédire les retards aériens en 2026, basé sur des données historiques 2003-2022.

### Architecture Globale
```
┌─────────────────────────────────────────────────────────────────────┐
│                      AIRLINE DATA PIPELINE                           │
└─────────────────────────────────────────────────────────────────────┘

┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   INGESTION  │────▶│   STOCKAGE   │────▶│      ML      │
│              │     │              │     │              │
│ NiFi + Kafka │     │  ClickHouse  │     │   XGBoost    │
│              │     │  (Medallion) │     │   MongoDB    │
└──────────────┘     └──────────────┘     └──────────────┘
                                                   │
                    ┌──────────────────────────────┴──────┐
                    ↓                                     ↓
            ┌──────────────┐                    ┌──────────────┐
            │   FastAPI    │                    │  Streamlit   │
            │  (port 8001) │                    │  (port 8501) │
            └──────────────┘                    └──────────────┘
                    │
                    ↓
            ┌──────────────┐
            │  React UI    │
            │  (port 3000) │
            └──────────────┘
```

---

## 🏗️ Architecture en Couches

### **COUCHE 1: INGESTION**

#### **NiFi (Port 8080)**
- **Rôle:** ETL visuel pour l'orchestration des flux de données
- **Configuration:**
  - Image: `apache/nifi:1.23.2`
  - RAM: 1536 MB
  - Credentials: admin / adminadminadmin

**Flows NiFi:**
- Lecture des données sources (CSV, base SQL)
- Transformation JSON
- Routage et filtrage
- Publication vers Kafka

**Template:**
- `nifi/flows/streaming_flow__v_(1).json`

#### **Kafka (Ports 9092/29092)**
- **Rôle:** Message broker pour streaming temps réel
- **Configuration:**
  - Image: `confluentinc/cp-kafka:7.5.0`
  - RAM: 768 MB
  - Broker ID: 1

**Topic Principal:**
- **Nom:** `airline-delays`
- **Messages:** 128,501+ enregistrements
- **Partitions:** 3
- **Replication:** 1
- **Retention:** 24 heures

**Consumer Groups:**
1. `streamlit-realtime-dashboard` - Monitoring live
2. `clickhouse-ingestion` - Persistence Bronze

#### **Zookeeper (Port 2181)**
- **Rôle:** Coordination Kafka
- RAM: 256 MB

---

### **COUCHE 2: STOCKAGE (ClickHouse)**

#### **Architecture Medallion**

```
┌─────────────────────────────────────────────────────────────────┐
│                    BRONZE (Données Brutes)                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  flights (478,109 rows)                                         │
│  ├─ Source 1: CSV historiques (2003-2022)                      │
│  │   └─ Fichier: Airline_Delay_Cause_Cpt.csv                   │
│  ├─ Source 2: Flux NiFi → Kafka (temps réel)                   │
│  │   └─ Consumer: kafka_to_clickhouse.py                       │
│  └─ Colonnes: year, month, carrier, airport, delays, causes    │
│                                                                 │
│  airports_gps (421 rows)                                        │
│  └─ Géolocalisation: latitude, longitude, city, state          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                            ↓ Transformation
┌─────────────────────────────────────────────────────────────────┐
│                    SILVER (Données Nettoyées)                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  silver_flights (346,511 rows)                                  │
│  ├─ Nettoyage: exclusion arr_flights = 0                       │
│  ├─ Calcul: delay_rate = arr_del15 / arr_flights               │
│  ├─ Validation: NOT NULL sur colonnes critiques                │
│  ├─ Deduplication: par (year, month, carrier, airport)         │
│  ├─ Data quality score: 1.0 (complétude)                       │
│  └─ ENGINE: ReplacingMergeTree                                  │
│      ├─ PARTITION BY: year                                      │
│      └─ ORDER BY: (year, month, carrier, airport)               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                            ↓ Agrégation
┌─────────────────────────────────────────────────────────────────┐
│                     GOLD (Agrégations & ML)                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  gold_bi (KPIs pour Business Intelligence)                      │
│  ├─ Granularité: (carrier, airport, year, month)              │
│  ├─ KPIs: delay_rate, on_time_rate, cancel_rate               │
│  ├─ Causes: carrier_delay_pct, weather_delay_pct, ...         │
│  └─ Usage: Dashboards Power BI                                 │
│                                                                 │
│  gold_ml_features (Features pour Machine Learning)             │
│  ├─ Granularité: (carrier, airport, year, month)              │
│  ├─ TARGET: delay_rate                                         │
│  ├─ Lags: 1m, 2m, 3m (par paire carrier+airport)              │
│  ├─ Rolling avg: 3m, 6m (carrier & airport)                   │
│  ├─ Features temporelles: month_sin/cos, season               │
│  └─ Usage: Entraînement XGBoost                                │
│                                                                 │
│  ml_predictions (Prédictions 2026)                              │
│  ├─ predicted_delay_rate (point estimate)                      │
│  ├─ risk_score: 0-1 (niveau de risque)                        │
│  ├─ risk_category: low/medium/high                             │
│  ├─ Top 3 features SHAP (explicabilité)                        │
│  ├─ Total: ~22,000 prédictions (routes × 12 mois)             │
│  └─ Usage: API FastAPI + Dashboard React                       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### **Configuration ClickHouse**
- **Image:** `clickhouse/clickhouse-server:23.8`
- **Ports:** 8123 (HTTP), 9000 (Native)
- **RAM:** 2048 MB
- **Database:** `airline_data`

**Init Script:** `config/clickhouse/init.sql`

---

### **COUCHE 3: MACHINE LEARNING**

#### **Pipeline ML Complet**

```
┌─────────────────────────────────────────────────────────────────┐
│                   DONNÉES D'ENTRAÎNEMENT                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  gold_ml_features (ClickHouse)                                  │
│    ↓                                                            │
│  Extraction: 2010-2022                                          │
│    ↓                                                            │
│  Split:                                                         │
│    ├─ Train: 2010-2018 (données historiques)                   │
│    └─ Test:  2019-2022 (validation académique)                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│                    FEATURE ENGINEERING                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Features Temporelles (Lags):                                  │
│  ├─ pair_lag1/2/3: Lags par (carrier + airport)               │
│  ├─ carrier_lag1_mean: Moyenne carrier lag 1 mois             │
│  ├─ airport_lag1/2/3: Lags par airport                        │
│  └─ Total: 3 niveaux de profondeur                             │
│                                                                 │
│  Features Rolling Averages:                                    │
│  ├─ carrier_rolling_3m/6m: Moyennes mobiles carrier           │
│  ├─ airport_rolling_3m/6m: Moyennes mobiles airport           │
│  └─ Window: 3 et 6 mois glissants                              │
│                                                                 │
│  Features Saisonnières:                                        │
│  ├─ is_summer: juin, juillet, août                            │
│  ├─ is_winter: décembre, janvier, février                     │
│  ├─ is_holiday_season: novembre, décembre                     │
│  └─ month: 1-12 (cyclique)                                     │
│                                                                 │
│  Total Features: 18 variables                                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│                    MODÈLE XGBOOST                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Type: XGBRegressor (régression)                                │
│  Objective: reg:squarederror                                    │
│                                                                 │
│  Hyperparamètres:                                              │
│  ├─ n_estimators: 200                                          │
│  ├─ max_depth: 6                                               │
│  ├─ learning_rate: 0.1                                         │
│  ├─ subsample: 0.8                                             │
│  ├─ colsample_bytree: 0.8                                      │
│  └─ random_state: 42                                            │
│                                                                 │
│  Performance (Test 2019-2022):                                 │
│  ├─ MAE: ~0.03-0.05 (3-5%)                                     │
│  ├─ RMSE: ~0.04-0.06                                            │
│  └─ R²: ~0.75-0.85                                              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│                    PRÉDICTIONS 2026                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Génération:                                                    │
│  ├─ Routes actives (2022): ~1,800 paires carrier+airport      │
│  ├─ Période: 12 mois (janvier-décembre 2026)                   │
│  └─ Total: ~22,000 prédictions                                 │
│                                                                 │
│  Contenu par prédiction:                                       │
│  ├─ predicted_delay_rate: Taux prédit                         │
│  ├─ risk_score: 0-1 (normalisé)                               │
│  ├─ risk_category: low/medium/high                             │
│  ├─ confidence: R² du modèle                                    │
│  ├─ top_feature_1/2/3: Top 3 features SHAP                    │
│  └─ importance_1/2/3: Poids des features                       │
│                                                                 │
│  Stockage:                                                      │
│  ├─ ClickHouse: ml_predictions (consultation rapide)           │
│  └─ MongoDB: Modèle binaire + métadonnées                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### **MongoDB (Port 27017)**
- **Rôle:** Stockage artifacts ML
- **Database:** `airline_ml`
- **Collection:** `models`

**Contenu:**
- Modèle XGBoost sérialisé (binaire pickle)
- Métadonnées: version, metrics, features
- Feature importance complète
- Historique des entraînements

---

### **COUCHE 4: API & INTERFACES**

#### **FastAPI (Port 8001)**

**Architecture:**
```
FastAPI Application
├─ app.py (point d'entrée)
└─ utils/
    └─ clickhouse_client.py
```

**Endpoints REST:**

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET | `/health` | Santé de l'API |
| GET | `/stats/summary` | Stats globales (total, risk breakdown) |
| GET | `/predictions` | Liste prédictions (filtres disponibles) |
| GET | `/explainability/global` | Feature importance globale |
| GET | `/explainability/route` | Analyse par route (carrier+airport) |
| GET | `/monitoring` | Métriques monitoring |
| GET | `/metadata` | Liste carriers & airports |
| GET | `/stats/monthly` | Statistiques mensuelles 2026 |

**Filtres disponibles sur `/predictions`:**
- `carrier`: Code compagnie (ex: AA, DL, UA)
- `airport`: Code aéroport (ex: ATL, ORD, DFW)
- `risk_category`: low/medium/high
- `month`: 1-12

**Configuration:**
- Image: `python:3.11-slim`
- RAM: 512 MB
- Dependencies: `requirements-ml-api.txt`
- CORS: Activé (allow all origins)

---

#### **React Dashboard (Port 3000)**

**Architecture:**
```
ml_ui/
├─ src/
│   ├─ App.jsx (Application principale)
│   ├─ api.js (Client REST)
│   ├─ main.jsx (Point d'entrée)
│   └─ styles.css (Styles)
├─ index.html
├─ package.json
└─ vite.config.js
```

**Fonctionnalités:**

1. **Dashboard Home**
   - Statistiques globales (KPI cards)
   - Distribution des risques (graphique)
   - Top carriers/airports à risque

2. **Explorer Prédictions**
   - Tableau interactif des prédictions
   - Filtres multi-critères (carrier, airport, risk, month)
   - Recherche textuelle
   - Pagination (25/50/100 items)
   - Tri dynamique sur toutes les colonnes

3. **Explicabilité ML**
   - Feature importance globale (barres)
   - Analyse par route spécifique
   - Top 3 features SHAP par prédiction
   - Graphiques Plotly interactifs

4. **Statistiques Mensuelles**
   - Évolution mensuelle 2026
   - Courbes: delay_rate, risk_score, flights
   - Heatmap risques par mois

5. **Monitoring**
   - Status des services
   - Refresh manuel
   - Last update timestamp

**Technologies:**
- React 18 + Vite
- Plotly.js (graphiques)
- Fetch API (REST calls)
- CSS moderne (grid, flexbox)

---

#### **Streamlit Real-time (Port 8501)**

**Architecture:**
```
realtime_app.py (1428 lignes)
├─ Configuration
├─ Kafka Consumer Thread
├─ ClickHouse Client
└─ 5 Onglets UI
```

**Fonctionnalités:**

1. **Overview**
   - Métriques ClickHouse (total records, flights, carriers)
   - Métriques Kafka (messages/min, buffer size)
   - Status services (ClickHouse, Kafka, NiFi)

2. **Kafka Live Messages**
   - Cards des derniers messages Kafka
   - Affichage: carrier, airport, flights, delays
   - Auto-scroll
   - Limit: 50 derniers messages

3. **Kafka Stats**
   - Graphique messages/min (30 dernières minutes)
   - Taux de consommation
   - Buffer usage (gauge)

4. **ClickHouse Data**
   - Graphiques évolution temporelle
   - Distribution carriers/airports
   - Top 10 routes à risque

5. **Status & Logs**
   - État détaillé des services
   - Logs thread Kafka
   - Uptime consumer

**Thread Kafka Background:**
- Threading daemon en background
- Buffer partagé (`@st.cache_resource`)
- Deque(maxlen=5000) - rotation automatique
- Auto-retry (3 tentatives)
- Parsing JSON robuste (format NiFi Pretty Print)

**Auto-refresh:**
- Interval: 30 secondes
- Library: `streamlit-autorefresh`

---

## 🔄 Flux de Données Complets

### **Flux 1: Historique (Batch)**

```
CSV Files (data/)
  ├─ Airline_Delay_Cause_Cpt.csv (318K records)
  └─ airports_gps.csv (421 records)
        ↓
Python Script: load_historical_data.py
  ├─ Lecture CSV avec pandas
  ├─ Validation & typage
  ├─ Batch insert (5000 rows)
  └─ Progress logging
        ↓
ClickHouse Bronze (flights)
  ├─ 478,109 records total
  ├─ Partitioning: YYYYMM
  └─ Order: (year, month, carrier, airport)
        ↓
Python Script: build_gold_features.py
  ├─ Bronze → Silver (nettoyage)
  ├─ Silver → Gold BI (agrégations)
  └─ Silver → Gold ML (features)
        ↓
ClickHouse Gold
  ├─ gold_bi (Power BI ready)
  ├─ gold_ml_features (ML ready)
  └─ 346,511 records silver
        ↓
Python Script: train_model_2026.py
  ├─ Load features from ClickHouse
  ├─ Feature engineering (lags, rolling)
  ├─ Train XGBoost (2010-2018)
  ├─ Validate (2019-2022)
  ├─ Predict 2026 (12 months)
  └─ Save: ClickHouse + MongoDB
        ↓
ml_predictions + MongoDB artifacts
  ├─ 22,000 predictions (ClickHouse)
  └─ Model binary + metadata (MongoDB)
```

---

### **Flux 2: Temps Réel (Streaming)**

```
NiFi ProcessGroup (port 8080)
  ├─ Source: QueryDatabaseTable / CSV
  ├─ Transform: JSON conversion
  ├─ Route: Validation & filtering
  └─ Sink: KafkaProducer
        ↓
Kafka Topic: airline-delays
  ├─ Broker: localhost:9092
  ├─ Partitions: 3
  ├─ Messages: 128,501+
  └─ Format: JSON (NiFi Pretty Print)
        ↓
        ├────────────────────────┬──────────────────┐
        ↓                        ↓                  ↓
Consumer 1:              Consumer 2:         (Future)
Streamlit               kafka_to_clickhouse
  ├─ Thread background    ├─ Batch insert
  ├─ Buffer 5000 msgs     ├─ flights table
  ├─ Real-time display    └─ Append-only
  └─ Monitoring UI              ↓
        ↓                   ClickHouse Bronze
  Live Dashboard              ↓
  (port 8501)            Continuously processed
                         → Silver → Gold
```

---

### **Flux 3: Consommation (BI & ML)**

```
ClickHouse Gold Tables
        ↓
        ├────────────────────┬──────────────────┐
        ↓                    ↓                  ↓
   Power BI            FastAPI (8001)     Streamlit (8501)
   (External)          REST API           Real-time Monitor
        │                   │                    │
        │                   ↓                    │
        │            React Dashboard             │
        │            (port 3000)                 │
        │            ML Predictions UI           │
        │                                        │
        └────────────────────┴────────────────────┘
                    Users / Analysts
```

---

## 📦 Services Docker Compose

### **Configuration Réseau**

**Network:** `airline-network` (bridge)

**Services Overview:**

| Service | Image | Port(s) | RAM | CPU | Fonction |
|---------|-------|---------|-----|-----|----------|
| zookeeper | cp-zookeeper:7.5 | 2181 | 256MB | - | Coordination Kafka |
| kafka | cp-kafka:7.5 | 9092, 29092 | 768MB | - | Message broker |
| nifi | apache/nifi:1.23 | 8080 | 1536MB | - | ETL orchestration |
| clickhouse | clickhouse:23.8 | 8123, 9000 | 2048MB | - | OLAP database |
| mongodb | mongo:7.0 | 27017 | 1024MB | - | ML artifacts |
| ml_api | python:3.11-slim | 8001 | 512MB | - | REST API ML |
| ml_ui | node:20-alpine | 3000 | 512MB | - | Dashboard React |
| streamlit | python:3.11-slim | 8501 | 512MB | - | Monitoring |

**Total RAM:** ~8GB (optimisé)

### **Volumes Persistants**

```
volumes:
  ├─ zookeeper-data
  ├─ zookeeper-logs
  ├─ kafka-data
  ├─ nifi-database
  ├─ nifi-flowfile
  ├─ nifi-content
  ├─ nifi-state
  ├─ nifi-logs
  ├─ clickhouse-data
  ├─ clickhouse-logs
  └─ mongodb-data
```

---

## 📝 Scripts Principaux

### **1. Data Pipeline**

#### `load_historical_data.py` (333 lignes)
**Fonction:** Charge CSV historiques → ClickHouse Bronze

**Process:**
1. Connexion ClickHouse
2. Lecture `Airline_Delay_Cause_Cpt.csv`
3. Validation & typage (UInt8, UInt16, UInt32, Float32)
4. Génération ID unique: `{year}{month}{carrier}{airport}`
5. Batch insert (5000 rows)
6. Logging progress

**Output:** 318,019 records → `flights` table

---

#### `load_airports_gps.py`
**Fonction:** Charge coordonnées GPS aéroports

**Process:**
1. Lecture `airports_gps.csv`
2. Insert ClickHouse `airports_gps`
3. 421 aéroports avec lat/long

---

#### `build_gold_features.py` (277 lignes)
**Fonction:** Pipeline Medallion Bronze → Silver → Gold

**Process:**

**Étape 1: Bronze → Silver**
```sql
INSERT INTO silver_flights
SELECT ..., 
  CASE WHEN arr_flights > 0 
    THEN arr_del15 / arr_flights 
    ELSE 0 
  END as delay_rate
FROM flights
WHERE arr_flights > 0
```

**Étape 2: Silver → Gold ML Features**
```sql
-- Lag features avec lagInFrame()
-- Rolling averages avec window functions
-- Features saisonnières (summer, winter, holidays)
```

**Output:** 
- silver_flights: 346,511 rows
- gold_ml_features: prêt pour ML

---

#### `kafka_to_clickhouse.py` (300 lignes)
**Fonction:** Consumer Kafka → ClickHouse Bronze

**Process:**
1. Connexion Kafka (confluent-kafka)
2. Subscribe topic `airline-delays`
3. Poll messages (timeout 1s)
4. Parse JSON (format NiFi)
5. Batch insert ClickHouse (configurable)
6. Auto-commit offsets

**Parsing JSON NiFi:**
```python
# Format: [{"{": "\"key\" : value"}, ...]
# → Reconstruction objet {key: value}
```

**Configuration:**
- `BATCH_SIZE`: 1 (temps réel)
- `CONSUMER_GROUP_ID`: airline-consumer-group
- Auto-retry: 3 tentatives

---

### **2. Machine Learning**

#### `train_model_2026.py` (500 lignes)
**Fonction:** Pipeline ML complet

**Process:**

1. **Chargement données**
   ```python
   query = "SELECT * FROM gold_ml_features WHERE year BETWEEN 2010 AND 2022"
   df = ch_client.query_df(query)
   ```

2. **Feature Engineering (pandas)**
   - Lags: `groupby().shift(1/2/3)`
   - Rolling: `rolling(window=3/6).mean()`
   - Fill NaN: 0

3. **Split Train/Test**
   - Train: 2010-2018
   - Test: 2019-2022

4. **Entraînement XGBoost**
   ```python
   model = xgb.XGBRegressor(
       n_estimators=200,
       max_depth=6,
       learning_rate=0.1
   )
   model.fit(X_train, y_train)
   ```

5. **Évaluation**
   - MAE, RMSE, R²
   - Feature importance

6. **Prédictions 2026**
   - Précalcul features par route (optimisation)
   - Batch predict (pandas DataFrame)
   - Risk scoring: `min(delay_rate / 0.5, 1.0)`
   - Risk category: low/medium/high

7. **Sauvegarde**
   - ClickHouse: `ml_predictions` (22K rows)
   - MongoDB: modèle binaire + métadonnées

**Output:** Modèle prêt pour production

---

## 🎯 Variables d'Environnement

### **Configuration Services**

```bash
# ClickHouse
CLICKHOUSE_HOST=localhost
CLICKHOUSE_HTTP_PORT=8123
CLICKHOUSE_DATABASE=airline_data
CLICKHOUSE_USER=default
CLICKHOUSE_PASSWORD=

# Kafka
KAFKA_HOST=localhost
KAFKA_PORT=9092
KAFKA_TOPIC=airline-delays
CONSUMER_GROUP_ID=airline-consumer-group

# MongoDB
MONGODB_URI=mongodb://localhost:27017/
MONGODB_DATABASE=airline_ml

# API
VITE_API_URL=http://localhost:8001

# Batch Processing
BATCH_SIZE=5000
```

---

## 📊 Schémas de Données

### **Table: flights (Bronze)**

```sql
CREATE TABLE flights (
    id String,                    -- UUID unique
    year UInt16,                  -- 2003-2025
    month UInt8,                  -- 1-12
    carrier String,               -- Code compagnie (AA, DL...)
    carrier_name String,          -- Nom complet
    airport String,               -- Code aéroport (ATL, ORD...)
    airport_name String,          -- Nom complet
    arr_flights UInt32,           -- Nombre de vols arrivés
    arr_del15 UInt32,             -- Vols retardés 15+ min
    carrier_ct Float32,           -- Minutes retard compagnie
    weather_ct Float32,           -- Minutes retard météo
    nas_ct Float32,               -- Minutes retard NAS
    security_ct Float32,          -- Minutes retard sécurité
    late_aircraft_ct Float32,     -- Minutes retard avion
    arr_cancelled UInt32,         -- Vols annulés
    arr_diverted UInt32,          -- Vols détournés
    arr_delay UInt32,             -- Total minutes retard
    carrier_delay UInt32,         -- Total retard compagnie
    weather_delay UInt32,         -- Total retard météo
    nas_delay UInt32,             -- Total retard NAS
    security_delay UInt32,        -- Total retard sécurité
    late_aircraft_delay UInt32,   -- Total retard avion
    ingestion_timestamp DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY (year, month, carrier, airport)
PARTITION BY toYYYYMM(toDate(concat(toString(year), '-', toString(month), '-01')));
```

---

### **Table: gold_ml_features (Gold)**

```sql
CREATE TABLE gold_ml_features (
    carrier String,
    origin_airport String,
    year UInt16,
    month UInt8,
    
    -- Target
    delay_rate Float32,
    arr_flights UInt32,
    arr_del15 UInt32,
    
    -- Lag features
    pair_lag1 Float32,
    pair_lag2 Float32,
    pair_lag3 Float32,
    
    carrier_lag1_mean Float32,
    carrier_lag2_mean Float32,
    carrier_lag3_mean Float32,
    
    airport_lag1 Float32,
    airport_lag2 Float32,
    airport_lag3 Float32,
    
    -- Rolling averages
    carrier_rolling_3m Float32,
    carrier_rolling_6m Float32,
    airport_rolling_3m Float32,
    airport_rolling_6m Float32,
    
    -- Seasonal features
    is_summer UInt8,              -- 1 si juin/juillet/août
    is_winter UInt8,              -- 1 si déc/janv/fév
    is_holiday_season UInt8       -- 1 si nov/déc
) ENGINE = MergeTree()
ORDER BY (carrier, origin_airport, year, month);
```

---

### **Table: ml_predictions (Gold)**

```sql
CREATE TABLE ml_predictions (
    carrier String,
    origin_airport String,
    year UInt16,
    month UInt8,
    
    -- Prédictions
    predicted_delay_rate Float32,
    risk_score Float32,           -- 0-1
    risk_category String,         -- low/medium/high
    
    -- Metadata
    arr_flights UInt32,
    model_version String,
    model_type String,            -- xgboost
    confidence Float32,           -- R²
    
    -- Explicabilité (SHAP)
    top_feature_1 String,
    top_feature_1_importance Float32,
    top_feature_2 String,
    top_feature_2_importance Float32,
    top_feature_3 String,
    top_feature_3_importance Float32
) ENGINE = MergeTree()
ORDER BY (year, month, carrier, origin_airport);
```

---

## ✅ Checklist Déploiement

### **Phase 1: Infrastructure**
- [x] Docker Compose configuré
- [x] Network bridge créé
- [x] Volumes persistants définis
- [x] Ports exposés correctement
- [x] RAM allouée (8GB total)

### **Phase 2: Services**
- [x] Zookeeper: Running
- [x] Kafka: Topic créé, 3 partitions
- [x] NiFi: Flows configurés
- [x] ClickHouse: 8 tables créées
- [x] MongoDB: Collection models prête

### **Phase 3: Data Pipeline**
- [x] CSV historiques chargés (318K)
- [x] GPS airports chargés (421)
- [x] Pipeline Medallion exécuté
- [x] Silver: 346K records
- [x] Gold BI: KPIs calculés
- [x] Gold ML: Features prêts

### **Phase 4: Machine Learning**
- [x] Modèle entraîné (2010-2018)
- [x] Validation effectuée (2019-2022)
- [x] R² > 0.75
- [x] Prédictions 2026: 22K rows
- [x] Modèle sauvegardé MongoDB

### **Phase 5: APIs & UIs**
- [x] FastAPI: 8 endpoints actifs
- [x] React UI: Dashboard fonctionnel
- [x] Streamlit: Monitoring live
- [x] CORS configuré
- [x] Health checks OK

### **Phase 6: Streaming**
- [x] Kafka consumer thread démarré
- [x] Buffer 5000 messages
- [x] Consumer ClickHouse actif
- [x] 128K+ messages traités

---

## 🚀 Commandes Essentielles

### **Démarrage**
```bash
# Lancer tous les services
docker compose up -d

# Vérifier status
docker compose ps

# Logs d'un service
docker compose logs -f ml_api
```

### **Data Pipeline**
```bash
# 1. Charger données historiques
python scripts/load_historical_data.py

# 2. Pipeline Medallion
python scripts/build_gold_features.py

# 3. Entraîner modèle
python scripts/train_model_2026.py

# 4. Consumer Kafka (optionnel)
python scripts/kafka_to_clickhouse.py
```

### **Monitoring**
```bash
# ClickHouse query
docker exec -it clickhouse clickhouse-client

# Kafka topics
docker exec -it kafka kafka-topics --list --bootstrap-server localhost:9092

# NiFi UI
http://localhost:8080
```

### **Arrêt & Nettoyage**
```bash
# Arrêter services
docker compose down

# Arrêter + supprimer volumes
docker compose down -v

# Rebuild complet
docker compose up -d --build
```

---

## 📈 Métriques & Performance

### **Données**
- **Bronze:** 478,109 records
- **Silver:** 346,511 records (72% de Bronze)
- **Gold ML Features:** Prêt pour entraînement
- **Prédictions 2026:** 22,000 prédictions

### **Modèle ML**
- **MAE:** 3-5%
- **RMSE:** 4-6%
- **R²:** 0.75-0.85
- **Temps entraînement:** ~5-10 minutes
- **Temps prédiction:** ~30 secondes (22K rows)

### **Kafka**
- **Messages total:** 128,501+
- **Partitions:** 3
- **Taux consommation:** Variable (temps réel)
- **Latence:** <100ms

### **ClickHouse**
- **Requêtes SELECT:** <100ms (index efficaces)
- **Inserts batch:** 5000 rows en ~1s
- **Compression:** Ratio ~10x
- **Storage:** ~500MB pour 478K records

---

## 🔐 Sécurité & Best Practices

### **Actuellement**
- ✅ Network isolé (bridge)
- ✅ Volumes persistants
- ✅ Healthchecks services
- ✅ Logging centralisé
- ✅ Error handling robuste

### **À Améliorer (Production)**
- [ ] Authentication Kafka (SASL)
- [ ] TLS/SSL pour communications
- [ ] Secrets management (Vault)
- [ ] Rate limiting API
- [ ] Backup automatique ClickHouse/MongoDB
- [ ] Monitoring Prometheus + Grafana
- [ ] Alerting (email, Slack)

---

## 📚 Documentation Complémentaire

- **README.md** - Vue d'ensemble et quick start
- **ARCHITECTURE_GLOBALE.md** - Architecture détaillée (746 lignes)
- **GUIDE_REDEMARRAGE.md** - Procédures restart
- **docs/ARCHITECTURE.md** - Architecture technique
- **docs/ML_COMPREHENSIVE_GUIDE.md** - Guide ML complet
- **scripts/README.md** - Documentation scripts

---

## 🎯 Statut Actuel: PRODUCTION READY ✅

Le projet est **opérationnel** avec:
- ✅ 478K records Bronze
- ✅ Pipeline Medallion fonctionnel
- ✅ Modèle ML entraîné (R² > 0.75)
- ✅ 22K prédictions 2026 disponibles
- ✅ API REST 8 endpoints actifs
- ✅ Dashboard React interactif
- ✅ Monitoring Streamlit temps réel
- ✅ Kafka streaming 128K+ messages

**Prêt pour démo et utilisation! 🚀**
