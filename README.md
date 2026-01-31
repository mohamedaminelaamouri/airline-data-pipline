# ynov-data-pipeline – Airline Delays Streaming (NiFi → Kafka → ClickHouse → Streamlit)

This repository contains a real-time data pipeline to generate and stream airline delay data using modern data engineering tools.

**Architecture**: NiFi → Kafka → ClickHouse → MongoDB (cache) → Streamlit

Each streamed JSON record represents aggregated flight observations (not individual flights). Fields like `arr_flights`, `arr_del15`, and cause count fields (`*_ct`) contain aggregated metrics.

## Project Structure

- `nifi/flows/`: NiFi flow exports (import in NiFi UI)
- `data/`: datasets and templates (`Nifi_Templates_1500.csv`, `airports_gps.csv`)
- `scripts/`: Python utilities (Kafka → ClickHouse consumer)
- `config/clickhouse/`: ClickHouse schema initialization
- `visualization/`: Streamlit real-time dashboard
- `docs/`: architecture documentation

## Quick Start

### 1. Start the Stack

```bash
docker compose up -d
```

This starts: Zookeeper, Kafka, NiFi, Kafka-UI, ClickHouse, MongoDB, and Streamlit dashboard.

### 2. Run Cache Service (ClickHouse → MongoDB)

The cache service periodically extracts aggregations from ClickHouse and stores them in MongoDB for fast dashboard queries:

```bash
python scripts/clickhouse_to_mongodb.py
```

Or let Docker handle it (recommended):
```bash
docker compose up -d
```

### 3. Import NiFi Flow

- Open NiFi at http://localhost:8080 (credentials: `admin` / `adminadminadmin`)
- Import `nifi/flows/streaming_flow.json`
- Verify Kafka broker: `kafka:29092`
- Start the flow

### 4. Run Kafka → ClickHouse Consumer (Optional - can run via Docker)

```bash
python scripts/kafka_to_clickhouse.py
```

### 5. Access Dashboards

- **Streamlit Dashboard**: http://localhost:8501 (real-time analytics + Kafka feed)
- **Kafka UI**: http://localhost:8081 (monitor topics and messages)
- **ClickHouse**: http://localhost:8123/play (SQL playground)
- **MongoDB**: localhost:27017 (cached aggregations)

## Real-time Visualization Details

The Streamlit dashboard provides:
- ClickHouse metrics and historical analysis
- Live Kafka message consumption with in-memory buffering
- Persistent buffer across page reloads using `st.cache_resource`

**Kafka Consumer Behavior:**
- Consumer group: `airline-streamlit-ui-backfill`
- Offset reset: `earliest` (includes recent backlog)
- Auto-commit: disabled (prevents offset advancement)
- Buffer size: 5000 messages (circular deque)

The buffer persists across Streamlit reruns/auto-refresh cycles, providing continuous real-time data visibility.

**Running Streamlit:**

Inside Docker (recommended):
```bash
docker compose up -d streamlit
```

Locally (for development):
```bash
python -m streamlit run visualization/realtime_app.py --server.port 8501 --server.address 0.0.0.0
```

## Documentation

- [Architecture Overview](docs/ARCHITECTURE.md)
- [Data Loading Strategy](docs/DATA_LOADING.md)
- **[ML Integration (Script 3)](docs/ML_INTEGRATION.md)** ✨
- [Runbook](docs/RUNBOOK.md)

## Development

### Local Python Environment

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
```

### Using Make Commands

```bash
make help           # Show available commands
make venv           # Create virtual environment
make install        # Install pipeline dependencies
make ml-install     # Install ML dependencies (yno-ml)
make consumer       # Run Kafka→ClickHouse consumer (Script 1)
make cache          # Run ClickHouse→MongoDB cache (Script 2)
make ml-train       # Run ML training pipeline (Script 3)
make ml-train-verbose  # Run ML training with detailed logs
make streamlit      # Run Streamlit dashboard
make clean          # Clean local caches/logs
make clean-docker   # Stop Docker stack
```

## Tech Stack

- **Apache NiFi**: Data generation and streaming
- **Apache Kafka**: Message broker
- **ClickHouse**: OLAP database (348K flight records, 2003-2025)
- **MongoDB**: Cache layer for pre-computed aggregations + ML predictions
- **XGBoost**: Machine learning (delay prediction classifier)
- **Streamlit**: Real-time dashboard
- **Docker**: Container orchestration
- **Python**: Data processing, ML training, consumers

## Pipeline Architecture

```
NiFi → Kafka → ClickHouse → MongoDB (cache) → Streamlit/Power BI
         ↓           ↓             ↓
    (Script 1)  (Script 3)    (Script 2)
    Consumer    ML Training   Cache Service
```

### Data Flow Scripts

| Script | Source | Destination | Purpose | Frequency |
|--------|--------|-------------|---------|-----------|
| **Script 1** | Kafka | ClickHouse | Stream processing | Real-time |
| **Script 2** | ClickHouse | MongoDB | Dashboard cache | Every 5 min |
| **Script 3** | ClickHouse | ML Model → MongoDB | Predictive analytics | Daily |

#### Script 3: ML Training Pipeline (NEW ✨)

Adds predictive capabilities to the pipeline:

```bash
# Train model and generate predictions
make ml-train

# Or run manually with options
python scripts/ml_training_pipeline.py --pred-year 2026 --pred-month 2
```

**What it does:**
1. Extracts 348K historical records from ClickHouse (2003-2025)
2. Trains XGBoost classifier to predict high-delay routes (>20% delay rate)
3. Generates predictions for next month
4. Saves predictions to MongoDB (`ml_predictions`, `ml_alerts`)
5. Exports alerts to CSV for Power BI (`reports/ml_alerts_latest.csv`)

**Performance:**
- ROC-AUC: 0.863
- Recall: 84.8% @ cutoff 0.17
- Training time: ~5 minutes on 348K records
- Predictions: ~800 carrier-airport pairs per month

**Use cases:**
- Predict which routes will have high delays next month
- Proactive resource allocation (staff, equipment)
- Customer communication (warn passengers about delays)
- Operations planning (schedule adjustments)

📚 **Full ML Documentation**: [docs/ML_INTEGRATION.md](docs/ML_INTEGRATION.md)

## MongoDB Collections (Cache Layer)

Pre-computed aggregations for fast dashboard queries:
- `airport_performance`: Airport KPIs and delay rates
- `carrier_performance`: Carrier performance metrics
- `monthly_trends`: Time series data by month
- `delay_causes`: Breakdown of delay causes by airport/carrier
- `top_performers`: Top 10 best/worst airports and carriers
- **`ml_predictions`** ✨: ML predictions for next month (risk scores)
- **`ml_alerts`** ✨: High-risk route alerts (prediction=1)
- **`ml_model_metadata`** ✨: Model performance metrics

The cache updates every 5 minutes (configurable via `CACHE_UPDATE_INTERVAL`).


| Script | Source | Destination | Frequency |
|--------|--------|-------------|-----------|
| Script 1: Consumer | Kafka | ClickHouse | Continu (real-time) |
| Script 2: Cache | ClickHouse | MongoDB | Périodique (5 min) |
| Script 3: ML | MongoDB | Modèle sauvegardé | Quotidien |
- **Python**: Kafka consumer and data processing

## ClickHouse Tables

The database includes:
- `flights`: Main fact table with delay metrics
- `airports_gps`: Geographic reference data (420 US airports with lat/long)
- `daily_delay_summary`: Materialized view for daily aggregations
- `carrier_performance`: Materialized view for carrier metrics
- `airport_performance`: Materialized view for airport metrics
- `realtime_stats`: Materialized view for real-time monitoring

The `airports_gps` table can be joined with `flights` on the `airport` column for Power BI geographic visualizations.
