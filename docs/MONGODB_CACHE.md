# MongoDB Cache Layer Documentation

## Overview

MongoDB serves as a cache layer for pre-computed aggregations from ClickHouse. This significantly improves dashboard query performance by storing frequently accessed metrics.

## Connection Details

- **Host**: `mongodb` (Docker) or `localhost` (from host)
- **Port**: `27017`
- **Database**: `airline_cache`
- **Update Frequency**: Every 5 minutes (configurable via `CACHE_UPDATE_INTERVAL`)

## Collections

### 1. `airport_performance` (421 documents)

Pre-computed airport metrics with GPS coordinates.

**Schema**:
```javascript
{
  _id: "ORD",  // airport code
  airport: "ORD",
  airport_name: "Chicago, IL: Chicago O'Hare International",
  city: "Chicago",
  state: "Illinois",
  latitude: 41.9786,
  longitude: -87.9048,
  total_flights: 983169,
  delayed_flights: 197038,
  cancelled_flights: 17653,
  diverted_flights: 2321,
  delay_rate: 20.04,
  avg_delay_minutes: 12.73,
  cancel_rate: 1.8,
  updated_at: ISODate("2026-01-25T17:00:14.874Z")
}
```

**Indexes**:
- `airport` (ASCENDING)
- `delay_rate` (DESCENDING)
- `updated_at` (DESCENDING)

**Use Cases**:
- Airport performance dashboards
- Geographic visualizations
- Top/worst performing airports

---

### 2. `carrier_performance` (31+ documents)

Pre-computed carrier (airline) metrics.

**Schema**:
```javascript
{
  _id: "AA",  // carrier code
  carrier: "AA",
  carrier_name: "American Airlines Inc.",
  total_flights: 1234567,
  delayed_flights: 234567,
  cancelled_flights: 12345,
  diverted_flights: 1234,
  delay_rate: 19.02,
  avg_delay_minutes: 11.5,
  cancel_rate: 1.0,
  updated_at: ISODate("2026-01-25T17:00:14.874Z")
}
```

**Indexes**:
- `carrier` (ASCENDING)
- `delay_rate` (DESCENDING)
- `updated_at` (DESCENDING)

**Use Cases**:
- Carrier comparison dashboards
- On-time performance rankings
- Airline reliability analysis

---

### 3. `monthly_trends` (13+ documents)

Monthly aggregated trends across all airlines and airports.

**Schema**:
```javascript
{
  _id: "2025-01",  // year-month
  year: 2025,
  month: 1,
  total_flights: 542123,
  delayed_flights: 98765,
  cancelled_flights: 5432,
  diverted_flights: 876,
  delay_rate: 18.22,
  avg_delay_minutes: 10.8,
  updated_at: ISODate("2026-01-25T17:00:14.874Z")
}
```

**Indexes**:
- `year, month` (ASCENDING)
- `updated_at` (DESCENDING)

**Use Cases**:
- Time series analysis
- Monthly performance trends
- Seasonal pattern detection

---

### 4. `delay_causes` (1000 documents)

Breakdown of delay causes by airport and carrier.

**Schema**:
```javascript
{
  _id: "ORD-AA",  // airport-carrier combination
  airport: "ORD",
  airport_name: "Chicago O'Hare International",
  carrier: "AA",
  carrier_name: "American Airlines Inc.",
  total_flights: 54321,
  carrier_delay_minutes: 12345,
  weather_delay_minutes: 5432,
  nas_delay_minutes: 3210,
  security_delay_minutes: 123,
  late_aircraft_delay_minutes: 7654,
  carrier_delay_pct: 42.5,
  weather_delay_pct: 18.7,
  nas_delay_pct: 11.0,
  security_delay_pct: 0.4,
  late_aircraft_delay_pct: 27.4,
  updated_at: ISODate("2026-01-25T17:00:14.874Z")
}
```

**Indexes**:
- `airport` (ASCENDING)
- `carrier` (ASCENDING)
- `updated_at` (DESCENDING)

**Filters**: Only includes airport-carrier combinations with >10 flights

**Use Cases**:
- Delay cause analysis
- Carrier performance at specific airports
- Root cause identification

---

### 5. `top_performers` (4 documents)

Pre-computed rankings of best and worst performers.

**Categories**:
- `best_airports`: Top 10 airports with lowest delay rates
- `worst_airports`: Top 10 airports with highest delay rates
- `best_carriers`: Top 10 carriers with lowest delay rates
- `worst_carriers`: Top 10 carriers with highest delay rates

**Schema**:
```javascript
{
  _id: "best_airports",
  category: "best_airports",
  items: [
    {
      airport: "HNL",
      airport_name: "Honolulu International",
      total_flights: 87654,
      delay_rate: 8.5
    },
    // ... 9 more items
  ],
  updated_at: ISODate("2026-01-25T17:00:14.874Z")
}
```

**Indexes**:
- `category` (ASCENDING)
- `updated_at` (DESCENDING)

**Filters**: Only includes airports/carriers with >1000 flights

**Use Cases**:
- Leaderboards
- Quick performance snapshots
- Executive dashboards

---

## Querying MongoDB

### Connect via Python (PyMongo)

```python
from pymongo import MongoClient

client = MongoClient('mongodb://localhost:27017/')
db = client['airline_cache']

# Get top 10 airports by delay rate
airports = db.airport_performance.find().sort('delay_rate', -1).limit(10)
for airport in airports:
    print(f"{airport['airport']}: {airport['delay_rate']}%")
```

### Connect via MongoDB Compass

1. Download [MongoDB Compass](https://www.mongodb.com/products/compass)
2. Connection string: `mongodb://localhost:27017`
3. Browse `airline_cache` database

### Connect via mongosh (CLI)

```bash
docker exec -it mongodb mongosh airline_cache

# Show collections
show collections

# Query examples
db.airport_performance.find({delay_rate: {$gt: 25}})
db.carrier_performance.find().sort({total_flights: -1})
db.monthly_trends.find({year: 2025})
```

---

## Power BI Integration

### Using MongoDB Connector

1. Install [MongoDB Power BI Connector](https://www.mongodb.com/products/connectors/power-bi)
2. Connection string: `mongodb://localhost:27017`
3. Database: `airline_cache`
4. Select collections to import

### Example Queries for Power BI

**Top Airports by Delay Rate**:
```javascript
db.airport_performance.find(
  {total_flights: {$gt: 10000}},
  {airport: 1, airport_name: 1, delay_rate: 1, total_flights: 1}
).sort({delay_rate: -1}).limit(20)
```

**Monthly Trend Analysis**:
```javascript
db.monthly_trends.find().sort({year: 1, month: 1})
```

**Carrier Comparison**:
```javascript
db.carrier_performance.find(
  {total_flights: {$gt: 5000}},
  {carrier: 1, carrier_name: 1, delay_rate: 1, cancel_rate: 1}
).sort({delay_rate: 1})
```

---

## Cache Management

### Manual Cache Update

Run the cache service once:
```bash
python scripts/clickhouse_to_mongodb.py
# Press Ctrl+C after one cycle completes
```

### Continuous Cache Service

Run as a service (updates every 5 minutes):
```bash
# Docker (recommended)
docker compose up -d

# Or manually
python scripts/clickhouse_to_mongodb.py
```

### Check Cache Freshness

```javascript
db.airport_performance.find().sort({updated_at: -1}).limit(1)
```

### Clear Cache

```javascript
// Clear all collections
db.airport_performance.deleteMany({})
db.carrier_performance.deleteMany({})
db.monthly_trends.deleteMany({})
db.delay_causes.deleteMany({})
db.top_performers.deleteMany({})
```

---

## Performance Benefits

| Query Type | ClickHouse (Direct) | MongoDB (Cached) | Speedup |
|------------|---------------------|------------------|---------|
| Airport performance | ~500-1000ms | ~10-20ms | 25-50x |
| Carrier rankings | ~300-800ms | ~5-15ms | 40-60x |
| Monthly trends | ~200-400ms | ~5-10ms | 30-40x |
| Delay causes | ~1000-2000ms | ~20-30ms | 40-70x |

**Note**: Speedup values are approximate and depend on dataset size and query complexity.

---

## Configuration

Edit `.env` file or environment variables:

```bash
# MongoDB Connection
MONGODB_HOST=mongodb           # or localhost
MONGODB_PORT=27017
MONGODB_DATABASE=airline_cache

# Cache Update Frequency
CACHE_UPDATE_INTERVAL=300      # 5 minutes (in seconds)
```

---

## Monitoring

### Check Service Logs

```bash
# Docker logs
docker logs mongodb

# Script logs
tail -f logs/clickhouse_to_mongodb.log
```

### Check Document Counts

```bash
docker exec mongodb mongosh airline_cache --quiet --eval "
  db.getCollectionNames().forEach(function(name) {
    print(name + ': ' + db[name].countDocuments({}));
  });
"
```

### Check Last Update Time

```bash
docker exec mongodb mongosh airline_cache --quiet --eval "
  db.airport_performance.find({}, {updated_at: 1}).sort({updated_at: -1}).limit(1).forEach(printjson);
"
```

---

## Troubleshooting

### Connection Refused

```bash
# Check if MongoDB is running
docker ps | grep mongodb

# Restart MongoDB
docker compose restart mongodb
```

### No Data in Collections

```bash
# Check ClickHouse connection
docker exec clickhouse clickhouse-client --query "SELECT COUNT(*) FROM airline_data.flights"

# Run cache script manually
python scripts/clickhouse_to_mongodb.py
```

### Outdated Cache

```bash
# Check last update
docker exec mongodb mongosh airline_cache --quiet --eval "
  db.airport_performance.find().sort({updated_at: -1}).limit(1).forEach(printjson);
"

# Manually trigger update
python scripts/clickhouse_to_mongodb.py
```
