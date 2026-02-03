# Airline Delay Prediction Platform

Pipeline de données et Machine Learning pour prédire les retards aériens avec dashboard interactif React.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DATA PIPELINE                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌──────────┐    ┌──────────┐    ┌──────────────┐    ┌──────────────┐    │
│   │  NiFi    │───▶│  Kafka   │───▶│  ClickHouse  │───▶│   ML API     │    │
│   │ Ingestion│    │ Streaming│    │   Database   │    │  (FastAPI)   │    │
│   └──────────┘    └──────────┘    └──────────────┘    └──────────────┘    │
│       :8080          :9092           :8123               :8001             │
│                                                             │              │
│                                                             ▼              │
│                                      ┌──────────────────────────────────┐  │
│                                      │        INTERFACES                │  │
│                                      ├──────────────────────────────────┤  │
│                                      │  React Dashboard    :3000        │  │
│                                      │  (Prédictions ML)               │  │
│                                      │                                  │  │
│                                      │  Streamlit Realtime :8501        │  │
│                                      │  (Monitoring Kafka)             │  │
│                                      └──────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Stack Technique

| Composant | Technologie | Port | Description |
|-----------|-------------|------|-------------|
| Database | ClickHouse 23.8 | 8123 | OLAP pour analytics rapides |
| Cache | MongoDB 7.0 | 27017 | Stockage ML artifacts |
| Message Broker | Kafka 7.5 | 9092 | Streaming temps réel |
| Ingestion | NiFi 1.23 | 8080 | ETL visuel |
| ML API | FastAPI | 8001 | REST API prédictions |
| Dashboard | React + Vite | 3000 | Interface ML |
| Monitoring | Streamlit | 8501 | Flux Kafka temps réel |

## Démarrage Rapide

### 1. Lancer tous les services

```bash
docker compose up -d
```

### 2. Vérifier les services

```bash
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

### 3. Accéder aux interfaces

| Interface | URL |
|-----------|-----|
| Dashboard ML (React) | http://localhost:3000 |
| Monitoring Temps Réel | http://localhost:8501 |
| API Documentation | http://localhost:8001/docs |
| NiFi | http://localhost:8080 |

## Structure du Projet

```
├── ml_api/                 # API FastAPI (prédictions ML)
│   ├── app.py              # Point d'entrée API
│   └── utils/              # Utilitaires
│
├── ml_ui/                  # Dashboard React
│   ├── src/
│   │   ├── App.jsx         # Application principale
│   │   ├── api.js          # Client API
│   │   └── styles.css      # Styles
│   └── package.json
│
├── scripts/                # Scripts de traitement
│   ├── build_gold_features.py   # Pipeline Medallion
│   ├── train_model_2026.py      # Entraînement ML
│   ├── load_historical_data.py  # Chargement CSV
│   └── kafka_to_clickhouse.py   # Consumer Kafka
│
├── config/                 # Configurations
│   └── clickhouse/
│       └── init.sql        # Schéma BDD
│
├── data/                   # Données source
│   ├── Airline_Delay_Cause_Cpt.csv
│   └── airports_gps.csv
│
├── nifi/                   # Flows NiFi
│   └── flows/
│
├── docs/                   # Documentation
│   ├── ARCHITECTURE.md
│   ├── ML_COMPREHENSIVE_GUIDE.md
│   └── ...
│
├── realtime_app.py         # App Streamlit monitoring
├── docker-compose.yml      # Orchestration services
├── requirements-ml-api.txt # Dépendances API
└── Makefile                # Commandes utiles
```

## API Endpoints

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET | `/health` | Santé de l'API |
| GET | `/stats/summary` | Statistiques globales |
| GET | `/predictions` | Liste des prédictions |
| GET | `/explainability/global` | Feature importance |
| GET | `/explainability/route` | Analyse par route |
| GET | `/monitoring` | Métriques monitoring |
| GET | `/metadata` | Carriers et airports |
| GET | `/stats/monthly` | Stats mensuelles |

## Commandes Utiles

```bash
# Status des services
docker compose ps

# Logs d'un service
docker compose logs -f ml_api

# Redémarrer un service
docker compose restart ml_ui

# Arrêter tout
docker compose down

# Rebuild complet
docker compose down -v && docker compose up -d --build
```

## Variables d'Environnement

```bash
# ClickHouse
CLICKHOUSE_HOST=clickhouse
CLICKHOUSE_HTTP_PORT=8123
CLICKHOUSE_DATABASE=airline_data

# Kafka
KAFKA_HOST=kafka
KAFKA_PORT=29092
KAFKA_TOPIC=airline-delays

# MongoDB
MONGODB_URL=mongodb://mongodb:27017
```

## Développement

### Backend (API)

```bash
cd ml_api
pip install -r ../requirements-ml-api.txt
uvicorn app:app --reload --port 8001
```

### Frontend (React)

```bash
cd ml_ui
npm install
npm run dev
```

## Machine Learning

Le modèle XGBoost prédit les taux de retard par route (carrier + airport) pour 2026.

- **Train**: 2010-2018 (données historiques)
- **Test**: 2019-2022 (validation)
- **Prédiction**: 2026 (12 mois)

Exécuter le pipeline ML :

```bash
python scripts/load_historical_data.py
python scripts/build_gold_features.py
python scripts/train_model_2026.py
```

## Ressources

- Documentation complète: `docs/`
- Guide ML détaillé: `docs/ML_COMPREHENSIVE_GUIDE.md`
- Architecture: `docs/ARCHITECTURE.md`
