# ML Serving Layer - Documentation

## Overview
FastAPI `/predict` endpoint for online ML inference using **MongoDB as the sole data source** (no ClickHouse during inference).

## Architecture

```
UI (React) → FastAPI /predict → MongoDB (feature_store) → XGBoost Model → MongoDB (predictions) → UI
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/predict` | POST | Single prediction |
| `/predict/batch` | POST | Batch predictions (max 100) |
| `/predict/metadata` | GET | Model info, carriers, airports |
| `/predictions/history` | GET | Prediction history with filters |
| `/predictions/{request_id}` | GET | Get single prediction |
| `/predictions/{request_id}` | DELETE | Delete prediction |

---

## Files

| File | Description |
|------|-------------|
| `ml_api/utils/mongodb_client.py` | MongoDB singleton, feature store access |
| `ml_api/utils/ml_inference.py` | Model loading, caching, prediction |
| `scripts/populate_feature_store.py` | ClickHouse → MongoDB sync |
| `prediction_ui/` | New React UI for predictions |

---

## API Examples

### Single Prediction
```bash
curl -X POST http://localhost:8001/predict \
  -H "Content-Type: application/json" \
  -d '{"carrier":"AA","airport":"ATL","month":6,"year":2026}'
```

### Batch Prediction
```bash
curl -X POST http://localhost:8001/predict/batch \
  -H "Content-Type: application/json" \
  -d '{"predictions":[
    {"carrier":"AA","airport":"ATL","month":6,"year":2026},
    {"carrier":"DL","airport":"ORD","month":7,"year":2026}
  ]}'
```

### History with Filters
```bash
curl "http://localhost:8001/predictions/history?carrier=AA&page=1&page_size=20"
```

---

## Quick Start

```bash
# Start services
docker-compose up -d mongodb clickhouse ml_api prediction_ui

# Populate feature store (one-time)
python scripts/populate_feature_store.py

# Access UI
open http://localhost:3001
```

---

## Constraints
- ✅ ClickHouse NOT used during inference
- ✅ MongoDB is the only database for feature serving
- ✅ Model NOT retrained (loaded from `ml/models/runs/production/`)
- ✅ Each prediction has `request_id`, `model_version`, `timestamp`

