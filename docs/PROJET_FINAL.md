# Projet Final - Architecture Simplifiée

## Objectif
Plateforme interactive ML pour visualiser predictions retards aeriens

## Architecture Optimisee

### Flux de Donnees
```
NiFi → Kafka → ClickHouse (analytics)
                    ↓
              MongoDB (ML artifacts)
                    ↓
              FastAPI (API REST)
                    ↓
              Streamlit (UI)
```

### Approche Hybride
- **ClickHouse direct**: Lectures analytics (rapide, 70% plus vite)
- **API REST**: Operations ML enrichies (explainability, scoring)

## Composants Finaux

### Services Docker (8GB RAM)
1. **Zookeeper**: 256 MB
2. **Kafka**: 768 MB (retention 24h)
3. **NiFi**: 1.5 GB (heap 512MB-1GB)
4. **ClickHouse**: 2 GB
5. **MongoDB**: 1 GB
6. **API**: 512 MB
7. **Streamlit**: 512 MB

Total: ~6.8 GB

### Scripts Essentiels
- `load_historical_data.py`: Charge 318K records CSV → ClickHouse
- `kafka_to_clickhouse.py`: Consumer streaming Kafka → ClickHouse

### Tables ClickHouse
- `flights`: Table principale (raw data)
- `airports_gps`: Coordonnees GPS
- `gold_predictions`: Predictions ML enrichies
- Vues materialisees: carrier_performance, airport_performance, daily_summary

### Collections MongoDB
- `predictions`: Predictions + explainability SHAP
- `models`: Registry modeles XGBoost
- `monitoring`: Drift detection

### API Endpoints
- GET /health
- GET /api/predictions
- POST /api/score
- GET /api/analytics/summary

### Pages Streamlit
1. Home: Dashboard KPIs
2. ML Predictions: Explorer predictions
3. Explainability: SHAP values
4. Comparaison: Comparer modeles
5. Monitoring: Drift detection

## Suppressions
- ❌ yno-ml/ (package externe supprime)
- ❌ ml_training_pipeline.py (dependait yno-ml)
- ❌ Bronze/Silver layers (inutiles)
- ❌ Scripts demo (batch_predictions, etc)
- ❌ Docs redondants (7 fichiers MD)
- ❌ kafka-ui (economie RAM)

## Structure Finale

```
├── backend/
│   ├── api/
│   │   └── main.py          # FastAPI app
│   └── requirements.txt
├── config/
│   ├── clickhouse/
│   │   └── init.sql          # Tables + gold_predictions
│   └── mongodb/
│       └── init_ml_collections.js
├── data/
│   ├── Airline_Delay_Cause_Cpt.csv  # 318K records
│   └── airports_gps.csv
├── scripts/
│   ├── load_historical_data.py      # CSV → ClickHouse
│   └── kafka_to_clickhouse.py       # Streaming consumer
├── visualization/
│   ├── Home.py                       # Dashboard (hybrid)
│   ├── pages/                        # 4 pages
│   └── utils/
│       ├── api_client.py             # REST wrapper
│       └── clickhouse_client.py      # Direct DB access
├── nifi/
│   └── flows/
├── docs/
│   ├── ARCHITECTURE.md
│   ├── DATA_LOADING.md
│   ├── INTERACTIVE_PLATFORM.md
│   └── PROJET_FINAL.md
├── docker-compose.yml
├── Makefile
└── README.md
```

## Commandes

```bash
# Demarrer
make start

# Init tables
make init-db

# Charger donnees
make load-data

# Logs
make logs

# Arreter
make stop
```

## Performance

### Metrics
- Hybrid approach: 70% plus rapide (vs API seul)
- ClickHouse: <100ms queries analytics
- API: <500ms scoring ML
- Streamlit: <2s page load

### Memoire
- Total RAM: 6.8 GB (fit 8GB limite)
- ClickHouse cache: 2GB
- MongoDB cache: 512MB
- Kafka retention: 24h (vs 7d)

## Prochaines Etapes

1. Charger donnees historiques
2. Configurer NiFi flow streaming
3. Implementer modele ML basic
4. Tester platform complete
5. Optimiser queries ClickHouse

## Notes Techniques

### Pourquoi ClickHouse Direct?
- API REST: 2 hops (Streamlit → API → ClickHouse)
- Direct: 1 hop (Streamlit → ClickHouse)
- Economie serialization JSON
- Queries SQL natives optimisees

### Pourquoi Garder API?
- Operations ML complexes (scoring)
- Cache MongoDB predictions
- Explainability SHAP values
- Model registry management

### Optimisations 8GB
- Reduced heap sizes (NiFi, Kafka)
- Short retention (24h vs 7d)
- Removed volumes (provenance, conf)
- Smaller log files (5MB max)
- No hot reload (API)
