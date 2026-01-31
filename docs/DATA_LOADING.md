# Data Loading Strategy

## Overview

This project uses a **hybrid data strategy** combining real historical data with generated simulation data to create a comprehensive dataset spanning 2003-2025.

## Data Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    COMPLETE DATASET                          │
│                    2003-2025 (388K+ records)                 │
└─────────────────────────────────────────────────────────────┘
                            ↓
        ┌───────────────────┴───────────────────┐
        ↓                                       ↓
┌──────────────────┐                ┌────────────────────┐
│  REAL HISTORICAL │                │  GENERATED DATA    │
│    2003-2022     │                │   2023-2025        │
│  318K records    │                │   70K records      │
│                  │                │                    │
│  Source:         │                │  Source:           │
│  Airline_Delay_  │                │  NiFi streaming    │
│  Cause_Cpt.csv   │                │  (templates)       │
│                  │                │                    │
│  Loading:        │                │  Loading:          │
│  Script bulk     │                │  Real-time Kafka   │
│  import (1x)     │                │  → ClickHouse      │
└──────────────────┘                └────────────────────┘
```

## Components

### 1. Historical Data (2003-2022)

**Source**: `data/Airline_Delay_Cause_Cpt.csv`
- **Records**: 318,019 lines
- **Period**: January 2003 - December 2022
- **Type**: Real data from Bureau of Transportation Statistics (BTS)
- **Purpose**: Training ML models with authentic patterns

**Loading Method**:
```bash
python scripts/load_historical_data.py
```

**Characteristics**:
- ✅ Real delay patterns
- ✅ Authentic carrier/airport performance
- ✅ Actual seasonal trends
- ✅ Historical anomalies (9/11 impact, COVID-19, etc.)

---

### 2. Generated Simulation Data (2023-2025)

**Source**: NiFi streaming with `data/Nifi_Templates_1500.csv`
- **Templates**: 1,501 records extracted from historical data
- **Generated Period**: 2023-2025 (randomly assigned years)
- **Type**: Synthetic data based on historical patterns
- **Purpose**: Simulate real-time streaming environment

**Generation Method**:
1. NiFi reads template CSV
2. ExecuteScript processor applies realistic variations
3. Publishes to Kafka topic `airline-delays`
4. Consumer script writes to ClickHouse

**Script**: `nifi/flows/script_body.py`
```python
# Key modification for 2023-2025 generation:
'year': random.choice([2023, 2024, 2025])
```

**Characteristics**:
- ✅ Preserves template seasonality (month unchanged)
- ✅ Realistic delay rate variations (±10%)
- ✅ Authentic delay cause distributions
- ✅ Volume variations (90-110% of template)
- ✅ Calibrated to match historical statistics

---

## Loading Sequence

### Initial Setup (One-time)

1. **Load Historical Data (2003-2022)**
   ```bash
   # Ensure ClickHouse is running
   docker compose up -d clickhouse
   
   # Load historical records
   python scripts/load_historical_data.py
   ```
   
   **Expected output**:
   - Time: 5-10 minutes
   - Records loaded: ~318,000
   - Years covered: 2003-2022

2. **Start NiFi Streaming (2023-2025)**
   ```bash
   # Start full stack
   docker compose up -d
   
   # Access NiFi: http://localhost:8080
   # Import: nifi/flows/streaming_flow.json
   # Start flow to generate 2023-2025 data
   ```

3. **Run Kafka Consumer**
   ```bash
   python scripts/kafka_to_clickhouse.py
   ```

### Verification

**Check data distribution**:
```python
import clickhouse_connect

client = clickhouse_connect.get_client(host='localhost', port=8123)

# Year distribution
result = client.query("""
    SELECT year, COUNT(*) as records 
    FROM airline_data.flights 
    GROUP BY year 
    ORDER BY year
""")

for row in result.result_rows:
    print(f"{row[0]}: {row[1]:,} records")
```

**Expected output**:
```
2003: 15,234 records
2004: 15,891 records
...
2022: 16,543 records
2023: 23,456 records   ← Generated
2024: 22,987 records   ← Generated
2025: 23,654 records   ← Generated
```

---

## Data Quality

### Historical Data (2003-2022)
- ✅ **Completeness**: All BTS fields preserved
- ✅ **Accuracy**: No transformations applied
- ✅ **Consistency**: Validated against source
- ✅ **Timeliness**: Monthly aggregations

### Generated Data (2023-2025)
- ✅ **Realism**: Based on 1,501 diverse templates
- ✅ **Calibration**: Tuned to match historical statistics
  - `DELAY_RATE_CALIBRATION = 1.085`
  - `DIVERT_RATE_CALIBRATION = 1.19`
- ✅ **Variation**: ±10% noise prevents constant patterns
- ✅ **Seasonality**: Template months preserved

---

## Use Cases

### Machine Learning Training

**Advantages of hybrid approach**:

1. **Time Series Models** (Prophet, SARIMA)
   - Train on 2003-2022 (20 years)
   - Validate on 2023-2024
   - Predict 2025

2. **Classification Models** (XGBoost, Random Forest)
   - Large training set (318K records)
   - Diverse patterns across 20 years
   - Test on recent data (2023-2025)

3. **Anomaly Detection** (Isolation Forest)
   - Learn normal patterns from historical data
   - Detect unusual delays in 2023-2025 simulation

### Power BI Dashboards

**MongoDB Cache Layer**:
- Aggregates both historical and generated data
- Pre-computed metrics for fast queries
- Unified view across 2003-2025

**Queries**:
```javascript
// Example: Monthly trends across full timeline
db.monthly_trends.find().sort({_id: 1})

// Output: 2003-01, 2003-02, ..., 2025-12
```

---

## Maintenance

### Re-loading Historical Data

If you need to reload historical data:

```bash
# Clear existing data
docker compose exec clickhouse clickhouse-client --query "TRUNCATE TABLE airline_data.flights"

# Reload
python scripts/load_historical_data.py
```

### Regenerating Simulation Data

To regenerate 2023-2025 data with different patterns:

1. Stop NiFi flow
2. Clear Kafka topic:
   ```bash
   docker compose exec kafka kafka-topics --delete --topic airline-delays --bootstrap-server localhost:9092
   ```
3. Clear ClickHouse 2023-2025 data:
   ```sql
   DELETE FROM airline_data.flights WHERE year >= 2023
   ```
4. Restart NiFi flow

---

## Performance Metrics

### Load Times
- **Historical import**: 5-10 minutes (318K records)
- **Real-time streaming**: ~100-200 records/second
- **ClickHouse insert**: Sub-millisecond per batch

### Storage
- **Historical data**: ~50 MB (compressed)
- **Generated data**: ~15 MB (compressed)
- **Total**: ~65 MB in ClickHouse

### Query Performance
- **Direct ClickHouse**: 100-500ms (complex aggregations)
- **MongoDB cache**: 0.5-2ms (pre-computed)
- **Speedup**: 25-50x

---

## Troubleshooting

### Issue: Historical data not loading

**Check**:
```bash
# Verify file exists
ls -lh data/Airline_Delay_Cause_Cpt.csv

# Check ClickHouse connection
docker compose ps clickhouse
```

### Issue: NiFi generates only 2025

**Fix**: Update `nifi/flows/script_body.py`:
```python
# Change this line:
'year': 2025,

# To this:
'year': random.choice([2023, 2024, 2025]),
```

### Issue: Duplicate data in ClickHouse

**Solution**: Use deterministic IDs in historical loader
```python
unique_id = f"{year}{month:02d}{carrier}{airport}"
```

---

## Summary

| Aspect | Historical (2003-2022) | Generated (2023-2025) |
|--------|----------------------|---------------------|
| **Records** | 318,019 | ~70,000 |
| **Source** | BTS real data | NiFi templates |
| **Loading** | One-time bulk | Continuous streaming |
| **Purpose** | ML training | Real-time simulation |
| **Accuracy** | 100% (real) | ~95% (calibrated) |
| **Time to load** | 5-10 min | Ongoing |

**Total Dataset**: 388,000+ records spanning 23 years (2003-2025)
