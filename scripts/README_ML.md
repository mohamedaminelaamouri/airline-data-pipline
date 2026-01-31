# ML Scripts Guide

## Available Scripts

### 1. Training Pipeline
**File**: `scripts/ml_training_pipeline.py`

Train XGBoost model on complete dataset (348K records).

```bash
# Quick training (skip predictions)
make ml-train

# Or manually
python scripts/ml_training_pipeline.py --skip-predictions

# With options
python scripts/ml_training_pipeline.py --min-year 2020 --skip-predictions
```

**Output**:
- Model artifacts: `models/ml_runs/YYYYMMDD_HHMMSS_sklearn/`
- MongoDB: `ml_model_metadata` collection
- Logs: `logs/ml_training.log`

**Duration**: ~2.5 minutes

---

### 2. Batch Predictions (Demo)
**File**: `scripts/batch_predictions_demo.py`

Generate predictions from recent historical data (last 6 months).

```bash
# Generate predictions
make ml-predict

# Or manually
python scripts/batch_predictions_demo.py
```

**Output**:
- CSV: `reports/ml_predictions_demo.csv` (228 predictions)
- MongoDB: `ml_predictions` collection (with `is_demo: true`)
- MongoDB: `ml_alerts` collection (178 high-risk alerts)

**What it does**:
1. Loads latest trained model
2. Samples 1000 recent records
3. Computes features and generates predictions
4. Saves to CSV and MongoDB
5. Shows performance summary

**Duration**: ~3 seconds

---

### 3. Future Predictions (WIP)
**File**: `scripts/generate_predictions.py`

Generate predictions for specific months (currently has issues).

```bash
# Try to predict for a month
python scripts/generate_predictions.py --year 2025 --month 11
```

**Status**: ⚠️ **HAS ISSUES** - Infinity values in lag features  
**Workaround**: Use `batch_predictions_demo.py` instead  
**Future Fix**: Modify yno-ml alerting module

---

### 4. Prerequisites Test
**File**: `scripts/test_ml_prerequisites.py`

Verify all dependencies and connections before training.

```bash
python scripts/test_ml_prerequisites.py
```

**Tests**:
1. ClickHouse connection (348K records)
2. MongoDB connection
3. yno-ml imports
4. ML dependencies (sklearn, xgboost)
5. Data extraction

**Expected**: All 5 tests pass ✅

---

## Workflow

### Complete ML Pipeline

```bash
# 1. Test prerequisites
python scripts/test_ml_prerequisites.py

# 2. Train model
make ml-train

# 3. Generate predictions
make ml-predict

# 4. Verify MongoDB
docker exec -it mongodb mongosh airline_cache --eval "
  db.ml_predictions.find({is_demo: true}).limit(5).pretty()
"

# 5. Check CSV
cat reports/ml_predictions_demo.csv | head -20
```

### Daily Retraining (Scheduled)

```bash
# Add to crontab
crontab -e

# Run training daily at 2 AM
0 2 * * * cd /workspaces/ynov-data-pipeline && make ml-train >> logs/ml_cron.log 2>&1

# Run predictions at 2:10 AM
10 2 * * * cd /workspaces/ynov-data-pipeline && make ml-predict >> logs/ml_predict_cron.log 2>&1
```

---

## Output Files

### Model Artifacts
```
models/ml_runs/20260125_234947_sklearn/
├── model.pkl                    # 1.6 MB - XGBoost Pipeline
├── label_encoder_carrier.pkl    # 789 B  - Carrier encoding
├── label_encoder_airport.pkl    # 5.2 KB - Airport encoding
└── metrics.json                 # 1.6 KB - Performance metrics
```

### Predictions
```
reports/
└── ml_predictions_demo.csv      # 228 predictions

Columns:
  - carrier, airport, year, month
  - actual_delay_rate (ground truth)
  - probability (0-1)
  - prediction (0 or 1)
  - risk_score (0-100)
  - alert_level (low/medium/high/critical)
```

### MongoDB
```javascript
// Model metadata
db.ml_model_metadata.find().pretty()

// All predictions
db.ml_predictions.find({is_demo: true}).pretty()

// High-risk alerts only
db.ml_alerts.find({is_demo: true, alert_level: "critical"}).pretty()
```

---

## Troubleshooting

### Issue: "ImportError: No module named xgboost"
```bash
pip install -r requirements.txt
# Or
make ml-install
```

### Issue: "ClickHouse connection refused"
```bash
docker ps | grep clickhouse
docker logs clickhouse
```

### Issue: "No trained model found"
```bash
# Train first
make ml-train

# Verify model exists
ls -lh models/ml_runs/
```

### Issue: "Input X contains infinity"
- **Expected**: This is a known issue with future month predictions
- **Solution**: Use `batch_predictions_demo.py` for demo data
- **Status**: Will be fixed in yno-ml alerting module

---

## Script Comparison

| Script | Purpose | Duration | Output | Status |
|--------|---------|----------|--------|--------|
| `ml_training_pipeline.py` | Train XGBoost | ~2.5 min | Model artifacts | ✅ Works |
| `batch_predictions_demo.py` | Demo predictions | ~3 sec | CSV + MongoDB | ✅ Works |
| `generate_predictions.py` | Future predictions | N/A | CSV + MongoDB | ⚠️ Has issues |
| `test_ml_prerequisites.py` | Verify setup | ~3 sec | Console output | ✅ Works |

---

## Performance Metrics

### Training
- **Dataset**: 348,113 records (2003-2025)
- **Duration**: 150 seconds
- **Validation ROC-AUC**: 0.842
- **Test ROC-AUC**: 0.738
- **Test Recall**: 91.7%

### Predictions (Demo)
- **Input**: 1,000 recent records
- **Valid Predictions**: 228 (772 dropped due to missing lags)
- **High-Risk Alerts**: 178 (78.1%)
- **Top Risk Score**: 99.9% (AA → IND)

---

## Next Steps

1. **Connect Power BI** to MongoDB collections
2. **Fix alerting module** for future predictions
3. **Schedule cron jobs** for daily retraining
4. **Monitor model performance** over time
5. **Create alerts dashboard** for operations team

---

For more details, see:
- [ML Integration Guide](../docs/ML_INTEGRATION.md)
- [Script 3 Summary](../docs/SCRIPT3_SUMMARY.md)
- [Final Report](../docs/ML_PIPELINE_FINAL.md)
