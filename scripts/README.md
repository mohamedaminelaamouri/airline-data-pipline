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
| `medallion_pipeline.py` | Pipeline complet Bronze → Silver → Gold | `python scripts/medallion_pipeline.py` |
| `train_model_2026.py` | Entraînement XGBoost et prédictions 2026 | `python scripts/train_model_2026.py` |
| `load_historical_data.py` | Chargement des données CSV dans ClickHouse | `python scripts/load_historical_data.py` |
| `kafka_to_clickhouse.py` | Consumer Kafka → ClickHouse (streaming) | `python scripts/kafka_to_clickhouse.py` |
| `build_gold_features.py` | (Legacy) Ancien script features | Remplacé par medallion_pipeline.py |

## Ordre d'exécution

```bash
# 1. Charger les données historiques (CSV → bronze_flights)
python scripts/load_historical_data.py

# 2. Pipeline Medallion (Bronze → Silver → Gold)
python scripts/medallion_pipeline.py

# 3. Entraîner le modèle et générer les prédictions 2026
python scripts/train_model_2026.py
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
