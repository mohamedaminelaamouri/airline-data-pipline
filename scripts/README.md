# Scripts de Pipeline

Ce dossier contient les scripts de traitement de données et d'entraînement ML.

## Architecture Medallion

```
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────────────┐
│     BRONZE      │─────▶│     SILVER      │─────▶│          GOLD           │
│   (Raw Data)    │      │   (Cleaned)     │      │  ┌─────────┬─────────┐  │
│                 │      │                 │      │  │ gold_bi │ gold_ml │  │
│ bronze_flights  │      │ silver_flights  │      │  │(PowerBI)│(XGBoost)│  │
│                 │      │                 │      │  └─────────┴─────────┘  │
│ • Données CSV   │      │ • NOT NULL      │      │           │             │
│ • Nulls OK      │      │ • Typé          │      └───────────┼─────────────┘
│ • Doublons OK   │      │ • delay_rate    │                  ▼
└─────────────────┘      └─────────────────┘         ┌─────────────────┐
                                                     │  ml_predictions │
                                                     └─────────────────┘
```

## Scripts disponibles

| Script | Description | Usage |
|--------|-------------|-------|
| `load_historical_data.py` | Chargement des données CSV dans ClickHouse | `python scripts/load_historical_data.py` |
| `load_airports_gps.py` | Chargement des coordonnées GPS des aéroports | `python scripts/load_airports_gps.py` |
| `medallion_pipeline.py` | Pipeline Bronze → Silver → Gold (features + BI) | `python scripts/medallion_pipeline.py` |
| `train_model_production.py` | Entraînement XGBoost et prédictions | `python scripts/train_model_production.py` |
| `populate_feature_store.py` | Synchronisation ClickHouse → MongoDB | `python scripts/populate_feature_store.py` |
| `kafka_to_clickhouse.py` | Consumer Kafka → ClickHouse (streaming) | `python scripts/kafka_to_clickhouse.py` |

## Ordre d'exécution

```bash
# 1. Charger les données historiques (CSV → ClickHouse)
python scripts/load_historical_data.py

# 2. Charger les coordonnées GPS des aéroports
python scripts/load_airports_gps.py

# 3. Pipeline Medallion (Bronze → Silver → Gold)
python scripts/medallion_pipeline.py

# 4. Entraîner le modèle
python scripts/train_model_production.py

# 5. Peupler le feature store MongoDB
python scripts/populate_feature_store.py

# 6. (Optionnel) Consumer Kafka pour données temps réel
python scripts/kafka_to_clickhouse.py
```

## Tables ClickHouse

| Table | Couche | Description | Usage |
|-------|--------|-------------|-------|
| `bronze_flights` | Bronze | Données brutes du CSV | Archive |
| `silver_flights` | Silver | Données nettoyées | Analyses |
| `gold_bi` | Gold | KPIs agrégés | Power BI |
| `gold_ml_features` | Gold | Features ML | XGBoost |
| `ml_predictions` | Output | Prédictions 2026 | API/Dashboard |

## Variables d'environnement

```bash
CLICKHOUSE_HOST=localhost
CLICKHOUSE_HTTP_PORT=8123
MONGODB_URL=mongodb://localhost:27017
```
