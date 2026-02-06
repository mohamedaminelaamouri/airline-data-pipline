# Guide Complet du Projet - Ligne par Ligne

## Vue d'Ensemble

Ce projet est un **pipeline de donnees complet** pour la prediction des retards aeriens.

```
CSV Brut → NiFi → Kafka → ClickHouse → ML Model → API → Dashboard
```

---

## 1. Architecture Docker (docker-compose.yml)

### Services (7 containers)

| Service | Port | Role |
|---------|------|------|
| **zookeeper** | 2181 | Coordination Kafka |
| **kafka** | 9092 | Message broker streaming |
| **nifi** | 8080 | ETL no-code |
| **clickhouse** | 8123 | Base analytique (OLAP) |
| **mongodb** | 27017 | Metadonnees ML |
| **ml_api** | 8001 | API predictions |
| **ml_ui** | 3000 | Interface React |
| **streamlit** | 8501 | Dashboard temps reel |

### Limites Memoire
- Total: ~6.5 GB (optimise pour 8GB RAM)
- Kafka: 768MB
- ClickHouse: 2GB  
- NiFi: 1.5GB

---

## 2. Base de Donnees ClickHouse

### Tables Principales

```sql
-- Table des vols bruts
flights (
    id, year, month, carrier, airport,
    arr_flights, arr_del15, carrier_delay, weather_delay, ...
)

-- Table des predictions ML
ml_predictions (
    carrier, origin_airport, year, month,
    predicted_delay_rate, risk_score, risk_category, ...
)

-- Features ML pre-calculees
gold_ml_features (
    carrier, airport, year, month, delay_rate,
    lag1, lag3_mean, expanding_mean, ...
)
```

---

## 3. Scripts Python (scripts/)

### Pipeline de Donnees

| Script | Role |
|--------|------|
| `load_historical_data.py` | Charge le CSV dans ClickHouse |
| `medallion_pipeline.py` | Transforme Bronze → Silver → Gold |
| `build_gold_features.py` | Calcule les features ML |
| `kafka_to_clickhouse.py` | Consomme Kafka → insere ClickHouse |

### Machine Learning

| Script | Role |
|--------|------|
| `train_model_local.py` | Entraine le modele XGBoost |
| `integrate_classification_model.py` | Genere predictions 2026 |

---

## 4. Module ML (ml/)

### Structure

```
ml/
├── src/yno_ml/           # Code source ML
│   ├── features.py       # Feature engineering
│   ├── train.py          # Entrainement
│   └── alerting.py       # Systeme d'alertes
├── models/runs/          # Modeles sauvegardes
│   └── production/       # Modele actuel
├── notebooks/            # Notebooks Colab
│   └── training_complete.py
└── RAPPORT_FINAL_ML.md   # Documentation
```

### Modele Production

| Fichier | Contenu |
|---------|---------|
| model.pkl | XGBoost entraine |
| metrics.json | Accuracy=79%, ROC-AUC=0.81 |
| label_encoder_*.pkl | Encodeurs categoriques |

---

## 5. API FastAPI (ml_api/)

### Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Status API |
| `/predictions` | GET | Liste predictions avec filtres |
| `/stats/summary` | GET | Resume global |
| `/stats/classification` | GET | Metriques modele ML |
| `/stats/monthly` | GET | Stats par mois |
| `/explainability/global` | GET | Feature importance |
| `/metadata` | GET | Liste carriers/airports |

### Exemple de Reponse

```json
GET /stats/classification

{
  "model": {
    "model_type": "XGBoost Classifier",
    "accuracy": 0.790,
    "roc_auc_test": 0.810,
    "cutoff": 0.47
  },
  "predictions": {
    "total": 34716,
    "above_cutoff": 8500
  }
}
```

---

## 6. Dashboard Streamlit (streamlit_app/)

### 3 Vues

1. **Dashboard Pipeline**
   - Metriques ClickHouse (total records, predictions)
   - Distribution des risques (critical, high, medium, low)
   - Top 10 routes critiques

2. **Predictions ML**
   - Filtres: carrier, airport, risque
   - Tableau des predictions

3. **Kafka Messages**
   - Simulation temps reel
   - Buffer de messages

### Fonctionnalites
- Auto-refresh (5 sec)
- Codes couleur risque
- Metriques modele en footer

---

## 7. Flux de Donnees Complet

### A. Ingestion (NiFi)

```
1. NiFi lit le CSV
2. Transforme les colonnes
3. Genere un ID unique
4. Publie dans Kafka topic "airline-data"
```

### B. Streaming (Kafka → ClickHouse)

```
1. kafka_to_clickhouse.py consomme le topic
2. Valide les donnees
3. Insere dans ClickHouse.flights
```

### C. Transformation (Medallion)

```
Bronze: Donnees brutes (flights)
   ↓
Silver: Donnees nettoyees + delay_rate
   ↓
Gold: Features ML pre-calculees
```

### D. Prediction (ML)

```
1. Charge le modele XGBoost
2. Pour chaque paire carrier+airport:
   - Calcule les features
   - Predit probabilite de retard
   - Categorise le risque
3. Insere dans ml_predictions
```

### E. Visualisation

```
Streamlit: Consomme ClickHouse + Kafka
Power BI: Connecte a ClickHouse
React UI: Appelle ml_api
```

---

## 8. Variables d'Environnement

```bash
# ClickHouse
CLICKHOUSE_HOST=localhost
CLICKHOUSE_HTTP_PORT=8123
CLICKHOUSE_DATABASE=airline_data

# Kafka
KAFKA_BOOTSTRAP=localhost:9092

# MongoDB
MONGO_URI=mongodb://localhost:27017
```

---

## 9. Commandes Utiles

```bash
# Demarrer tout
docker-compose up -d

# Voir les logs
docker-compose logs -f kafka

# Arreter
docker-compose down

# Charger les donnees
python scripts/load_historical_data.py

# Entrainer le modele
python scripts/train_model_local.py

# Generer predictions
python scripts/integrate_classification_model.py

# Lancer Streamlit
streamlit run streamlit_app/app.py
```

---

## 10. Metriques Cles

| Metrique | Valeur |
|----------|--------|
| **Donnees** | 318,017 lignes |
| **Periode** | 2003-2022 |
| **Carriers** | 30 |
| **Airports** | 421 |
| **Features ML** | 20 |
| **Accuracy** | 79.0% |
| **ROC-AUC** | 0.810 |
| **Predictions 2026** | ~34,716 |
