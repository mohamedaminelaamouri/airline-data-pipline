# Power BI Integration Guide

## 🔌 Connecting to MongoDB

### Step 1: Install MongoDB Connector

1. Open Power BI Desktop
2. Go to **Get Data** → **More**
3. Search for "MongoDB"
4. Install **MongoDB BI Connector** if not already installed

### Step 2: Connection Settings

```
Server: localhost:27017
Database: airline_cache
Authentication: None (or Windows/MongoDB credentials)
```

---

## 📊 Data Sources

### Available Collections

| Collection | Records | Purpose |
|------------|---------|---------|
| `ml_predictions` | 228 | All ML predictions with risk scores |
| `ml_alerts` | 178 | High-risk routes only (prediction=1) |
| `ml_model_metadata` | 3 | Model performance metrics |
| `monthly_trends` | 264 | Aggregated monthly statistics |
| `airport_performance` | 421 | Airport-level KPIs |
| `carrier_performance` | 30 | Carrier-level KPIs |

---

## 🔍 Power Query Examples

### Query 1: Load All ML Predictions

```m
let
    Source = MongoDB.Database("localhost:27017", "airline_cache"),
    ml_predictions = Source{[Name="ml_predictions"]}[Data],
    FilterDemo = Table.SelectRows(ml_predictions, each [is_demo] = true),
    RemovedColumns = Table.RemoveColumns(FilterDemo,{"_id", "is_demo"}),
    SortedRows = Table.Sort(RemovedColumns,{{"risk_score", Order.Descending}})
in
    SortedRows
```

### Query 2: Top 50 Highest Risk Routes

```m
let
    Source = MongoDB.Database("localhost:27017", "airline_cache"),
    ml_predictions = Source{[Name="ml_predictions"]}[Data],
    FilterDemo = Table.SelectRows(ml_predictions, each [is_demo] = true),
    SortedRows = Table.Sort(FilterDemo,{{"risk_score", Order.Descending}}),
    Top50 = Table.FirstN(SortedRows, 50),
    SelectedColumns = Table.SelectColumns(Top50,{
        "carrier", "airport", "risk_score", "probability", 
        "alert_level", "prediction_for_year", "prediction_for_month"
    })
in
    SelectedColumns
```

### Query 3: Risk by Carrier (Aggregated)

```m
let
    Source = MongoDB.Database("localhost:27017", "airline_cache"),
    ml_predictions = Source{[Name="ml_predictions"]}[Data],
    FilterDemo = Table.SelectRows(ml_predictions, each [is_demo] = true),
    GroupedRows = Table.Group(FilterDemo, {"carrier"}, {
        {"avg_risk_score", each List.Average([risk_score]), type number},
        {"high_risk_count", each List.Count(List.Select([prediction], each _ = 1)), type number},
        {"total_predictions", each Table.RowCount(_), type number}
    }),
    AddedRiskRate = Table.AddColumn(GroupedRows, "high_risk_rate", 
        each [high_risk_count] / [total_predictions], type number),
    SortedRows = Table.Sort(AddedRiskRate,{{"avg_risk_score", Order.Descending}})
in
    SortedRows
```

### Query 4: Model Performance Over Time

```m
let
    Source = MongoDB.Database("localhost:27017", "airline_cache"),
    ml_model_metadata = Source{[Name="ml_model_metadata"]}[Data],
    ExpandedMetrics = Table.ExpandRecordColumn(ml_model_metadata, "metrics", 
        {"test_roc_auc", "test_recall", "test_precision"}),
    ExpandedCutoff = Table.ExpandRecordColumn(ExpandedMetrics, "cutoff", 
        {"threshold"}),
    SelectedColumns = Table.SelectColumns(ExpandedCutoff,{
        "run_id", "trained_at", "test_roc_auc", 
        "test_recall", "test_precision", "threshold"
    }),
    SortedRows = Table.Sort(SelectedColumns,{{"trained_at", Order.Descending}})
in
    SortedRows
```

---

## 📈 Dashboard Templates

### Dashboard 1: Risk Overview

**Visualizations**:

1. **Card**: Total High-Risk Routes
   - Measure: `COUNT([prediction]) WHERE [prediction] = 1`

2. **Card**: Average Risk Score
   - Measure: `AVERAGE([risk_score])`

3. **Donut Chart**: Alert Level Distribution
   - Legend: `[alert_level]`
   - Values: `COUNT([carrier])`

4. **Bar Chart**: Top 20 Carriers by Risk
   - Axis: `[carrier]`
   - Values: `AVERAGE([risk_score])`
   - Sort: Descending by risk score

### Dashboard 2: Geographic Risk Map

**Visualizations**:

1. **Map Visual**: Airports by Risk
   - Location: `[airport]` (join with `airports_gps` table)
   - Size: `AVERAGE([risk_score])`
   - Color: `[alert_level]`

2. **Table**: Top 50 Routes
   - Columns: Carrier, Airport, Risk Score, Alert Level, Month
   - Conditional Formatting: Color by `alert_level`

### Dashboard 3: Model Performance

**Visualizations**:

1. **Line Chart**: ROC-AUC Over Time
   - Axis: `[trained_at]`
   - Values: `[test_roc_auc]`

2. **KPI Cards**:
   - Latest ROC-AUC
   - Latest Recall
   - Latest Precision

3. **Table**: Model History
   - Run ID, Trained At, ROC-AUC, Recall, Precision

---

## 🎨 DAX Measures

### Measure 1: High Risk Count
```dax
HighRiskCount = 
COUNTROWS(
    FILTER(
        ml_predictions,
        ml_predictions[prediction] = 1
    )
)
```

### Measure 2: Risk Category
```dax
RiskCategory = 
SWITCH(
    TRUE(),
    ml_predictions[risk_score] >= 85, "Critical",
    ml_predictions[risk_score] >= 70, "High",
    ml_predictions[risk_score] >= 50, "Medium",
    "Low"
)
```

### Measure 3: Risk Color
```dax
RiskColor = 
SWITCH(
    ml_predictions[alert_level],
    "critical", "#DC3545",
    "high", "#FD7E14",
    "medium", "#FFC107",
    "low", "#28A745",
    "#6C757D"
)
```

### Measure 4: High Risk Rate
```dax
HighRiskRate = 
DIVIDE(
    [HighRiskCount],
    COUNTROWS(ml_predictions),
    0
)
```

### Measure 5: Latest Model ROC-AUC
```dax
LatestROC = 
CALCULATE(
    MAX(ml_model_metadata[test_roc_auc]),
    TOPN(1, ml_model_metadata, ml_model_metadata[trained_at], DESC)
)
```

---

## 🔗 Table Relationships

### Recommended Data Model

```
ml_predictions
    ├── carrier (Many) → carrier_performance (One)
    ├── airport (Many) → airport_performance (One)
    └── run_id (Many) → ml_model_metadata (One)

airport_performance
    └── airport (One) → airports_gps (One)
```

### Creating Relationships

1. **ml_predictions to carrier_performance**:
   - From: `ml_predictions[carrier]`
   - To: `carrier_performance[carrier]`
   - Cardinality: Many-to-One

2. **ml_predictions to airport_performance**:
   - From: `ml_predictions[airport]`
   - To: `airport_performance[airport]`
   - Cardinality: Many-to-One

3. **ml_predictions to ml_model_metadata**:
   - From: `ml_predictions[run_id]`
   - To: `ml_model_metadata[run_id]`
   - Cardinality: Many-to-One

---

## 🎯 Example Dashboard Layout

### Page 1: Executive Summary

```
┌─────────────────────────────────────────────────────────────┐
│  ML Risk Predictions Dashboard                              │
├───────────┬───────────┬───────────┬──────────────────────────┤
│ Total     │ High Risk │ Avg Risk  │ Latest Model             │
│ Predictions│ Routes   │ Score     │ ROC-AUC: 0.738          │
│   228     │   178    │   54.6    │ Recall: 91.7%           │
├───────────┴───────────┴───────────┴──────────────────────────┤
│                                                               │
│  Alert Level Distribution        Risk by Carrier             │
│  ┌─────────────────────┐        ┌────────────────────┐      │
│  │    Donut Chart      │        │   Bar Chart        │      │
│  │                     │        │                    │      │
│  │  Critical: 25%      │        │  AA: 65.2          │      │
│  │  High: 18%          │        │  UA: 58.9          │      │
│  │  Medium: 13%        │        │  DL: 52.3          │      │
│  │  Low: 44%           │        │  WN: 48.7          │      │
│  └─────────────────────┘        └────────────────────┘      │
│                                                               │
│  Top 20 Highest Risk Routes                                  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ Carrier  Airport  Risk  Level     Month              │  │
│  │ AA       IND      99.9  Critical  2025-12            │  │
│  │ MQ       GPT      99.7  Critical  2025-10            │  │
│  │ UA       STL      99.6  Critical  2024-09            │  │
│  └───────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────┘
```

### Page 2: Geographic View

```
┌─────────────────────────────────────────────────────────────┐
│  Geographic Risk Analysis                                    │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  US Map with Airport Risk Indicators                         │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                                                        │  │
│  │         ⬤ ORD                                         │  │
│  │                    ⬤ BOS                              │  │
│  │    ⬤ SFO                                              │  │
│  │              ⬤ DEN      ⬤ DFW                        │  │
│  │                                   ⬤ ATL               │  │
│  │    ⬤ LAX                     ⬤ MIA                   │  │
│  │                                                        │  │
│  │  Legend: Size = Risk Score, Color = Alert Level       │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                               │
│  Filters:                                                     │
│  [ ] Alert Level  [ ] Carrier  [ ] Month                    │
└───────────────────────────────────────────────────────────────┘
```

### Page 3: Model Performance

```
┌─────────────────────────────────────────────────────────────┐
│  Model Performance Tracking                                  │
├───────────┬───────────┬───────────┬──────────────────────────┤
│ Latest    │ Test      │ Test      │ Training                 │
│ ROC-AUC   │ Recall    │ Precision │ Time                     │
│  0.738    │  91.7%    │  56.7%    │  150s                   │
├───────────┴───────────┴───────────┴──────────────────────────┤
│                                                               │
│  ROC-AUC Over Time                                           │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ 0.90 ┤                                                │  │
│  │ 0.85 ┤  ●─────●                                       │  │
│  │ 0.80 ┤           ╲                                    │  │
│  │ 0.75 ┤            ●──●──●                            │  │
│  │ 0.70 ┤                                                │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                               │
│  Model Training History                                      │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ Run ID              Trained At      ROC-AUC  Recall   │  │
│  │ 20260125_234947... 2026-01-25 23:49  0.738   91.7%   │  │
│  │ 20260125_234619... 2026-01-25 23:46  0.738   91.7%   │  │
│  └───────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Method 1: Direct MongoDB Connection

1. Open Power BI Desktop
2. **Get Data** → **MongoDB**
3. Server: `localhost:27017`
4. Database: `airline_cache`
5. Select tables:
   - `ml_predictions`
   - `ml_alerts`
   - `ml_model_metadata`
6. Click **Load**

### Method 2: Import CSV (Fallback)

If MongoDB connector doesn't work:

1. **Get Data** → **Text/CSV**
2. Select: `reports/ml_predictions_demo.csv`
3. Click **Load**

---

## 📝 Sample Queries for Testing

### MongoDB Shell Queries

```javascript
// Top 10 highest risk
db.ml_predictions.find({is_demo: true})
  .sort({risk_score: -1})
  .limit(10)
  .pretty()

// Critical alerts only
db.ml_alerts.find({
  alert_level: "critical",
  is_demo: true
}).pretty()

// Risk by carrier
db.ml_predictions.aggregate([
  {$match: {is_demo: true}},
  {$group: {
    _id: "$carrier",
    avg_risk: {$avg: "$risk_score"},
    count: {$sum: 1}
  }},
  {$sort: {avg_risk: -1}}
])

// Count by alert level
db.ml_predictions.aggregate([
  {$match: {is_demo: true}},
  {$group: {
    _id: "$alert_level",
    count: {$sum: 1}
  }}
])
```

---

## 🎨 Color Schemes

### Alert Level Colors

| Level | Hex Color | RGB |
|-------|-----------|-----|
| **Critical** | `#DC3545` | rgb(220, 53, 69) |
| **High** | `#FD7E14` | rgb(253, 126, 20) |
| **Medium** | `#FFC107` | rgb(255, 193, 7) |
| **Low** | `#28A745` | rgb(40, 167, 69) |

### Gradient for Risk Score

```
0-50:   Green (#28A745)
50-70:  Yellow (#FFC107)
70-85:  Orange (#FD7E14)
85-100: Red (#DC3545)
```

---

## 🔧 Troubleshooting

### Issue: "Cannot connect to MongoDB"

**Solution**:
```bash
# Check MongoDB is running
docker ps | grep mongodb

# Check port is accessible
curl http://localhost:27017

# Restart MongoDB
docker restart mongodb
```

### Issue: "Empty dataset in Power BI"

**Solution**:
```bash
# Verify data exists
docker exec -it mongodb mongosh airline_cache --eval "
  db.ml_predictions.countDocuments({is_demo: true})
"

# Should return: 228
```

### Issue: "Relationships not working"

**Solution**:
- Check that carrier/airport values match between tables
- Ensure cardinality is set to Many-to-One
- Verify no null values in join keys

---

## 📚 Additional Resources

- **MongoDB Power BI Connector**: https://www.mongodb.com/products/bi-connector
- **Power BI DAX Reference**: https://dax.guide/
- **Data Modeling Best Practices**: https://docs.microsoft.com/power-bi/guidance/

---

**Next Steps**:
1. Connect Power BI to MongoDB
2. Load `ml_predictions` table
3. Create visualizations using examples above
4. Schedule daily refresh (after setting up cron jobs)
5. Share dashboard with operations team
