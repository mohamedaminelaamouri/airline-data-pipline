# Plateforme Interactive ML - Frontend Streamlit

Interface web interactive pour visualiser et explorer les prédictions ML.

## Architecture

```
visualization/
├── Home.py                          # Dashboard principal
├── pages/
│   ├── 1_📊_ML_Predictions.py      # Exploration des prédictions
│   ├── 2_🧠_Explainability.py      # SHAP values & feature importance
│   ├── 3_📈_Comparaison.py         # Comparaison modèles/périodes
│   └── 4_🔍_Monitoring.py          # Drift detection & alertes
├── utils/
│   ├── __init__.py
│   └── api_client.py                # Client API REST
└── realtime_app.py                  # Legacy real-time app

```

## Installation

```bash
pip install -r requirements-streamlit.txt
```

## Démarrage

### Local Development
```bash
streamlit run visualization/Home.py
```

### Docker
```bash
docker-compose up streamlit api
```

L'interface sera disponible sur: http://localhost:8501

## Pages

### 🏠 Home (Dashboard Principal)
**Objectif**: Vue d'ensemble des prédictions ML

**Features**:
- 5 KPIs globaux (total predictions, high risk, avg score, carriers, airports)
- Top 10 routes high-risk (bar chart)
- Distribution des risk scores (histogram 4 niveaux)
- Performance par carrier (dual subplot)
- Tendances temporelles (line chart)
- Alertes critiques actives

**Visualisations**: Plotly Express + Graph Objects

**APIs consommées**:
- `GET /api/analytics/summary`
- `GET /api/predictions/high-risk`
- `GET /api/analytics/carriers`

### 📊 ML Predictions
**Objectif**: Exploration détaillée des prédictions

**Features**:
- Filtres interactifs (risk threshold, carrier, sorting)
- Table paginée des prédictions
- Distribution histogram
- Feature importance
- Export CSV

**Visualisations**: DataFrames + Plotly

**APIs consommées**:
- `GET /api/predictions?risk_threshold={}&carrier={}&skip={}&limit={}`
- `GET /api/analytics/summary`

### 🧠 Explainability
**Objectif**: Comprendre les prédictions du modèle

**Tabs**:
1. **Feature Importance Globale**
   - Bar chart horizontal (top features)
   - Pie chart par catégorie (Lag, Seasonality, Volume)
   - Interprétation textuelle

2. **Explication par Route**
   - Sélection carrier + airport
   - Waterfall chart SHAP values
   - Contribution de chaque feature
   - Explication détaillée

3. **Feature Impact**
   - Scatter plot feature vs risk score
   - Trend line (LOWESS)
   - Corrélation statistics
   - Insights automatiques

**Visualisations**: Waterfall, Scatter, Bar, Pie

**APIs consommées**:
- `GET /api/predictions/{carrier}/{airport}`

### 📈 Comparaison
**Objectif**: Analyses comparatives multi-dimensionnelles

**Tabs**:
1. **Modèles**
   - Sélection multi-modèles
   - Radar chart métriques
   - Table comparative
   - Evolution temporelle (4 subplots)
   - Statistiques d'amélioration

2. **Périodes Temporelles**
   - Date range picker
   - Line chart risk score over time
   - Volume + % high risk
   - Détection d'anomalies
   - Statistiques période

3. **Carriers vs Airports**
   - Top/Bottom par risk score
   - Scatter plot risk vs volume
   - Heatmap carrier × airport
   - Comparaison side-by-side

**Visualisations**: Radar, Heatmap, Scatter, Subplots

**APIs consommées**:
- `GET /api/models`
- `GET /api/analytics/carriers`
- `GET /api/analytics/airports`

### 🔍 Monitoring
**Objectif**: Surveillance modèle en production

**Tabs**:
1. **Data Drift**
   - PSI scores par feature
   - Status (OK/WARNING/CRITICAL)
   - Radar chart drift metrics
   - Evolution temporelle PSI
   - Détails par feature

2. **Performance Tracking**
   - 4 métriques (ROC-AUC, Precision, Recall, F1)
   - Evolution sur 60 jours
   - Volume vs Performance
   - Détection dégradation
   - Deltas 7 jours

3. **Alertes**
   - Filtres (severity, type, status)
   - Liste alertes expandables
   - Actions (résoudre)
   - Timeline 30 jours
   - Statistiques alertes

4. **Model Health**
   - 5 gauges (Data Quality, Performance, Drift, Volume, Latency)
   - Overall health score
   - Recommendations automatiques
   - Status colorés

**Visualisations**: Gauges, Timeline, Bar, Line

## API Client

Le client API (`utils/api_client.py`) abstrait toutes les calls REST:

```python
from utils.api_client import api_client

# Predictions
predictions = api_client.list_predictions(
    risk_threshold=0.8,
    carrier="AA",
    skip=0,
    limit=100
)

high_risk = api_client.get_high_risk_predictions()

route = api_client.get_prediction_by_route("AA", "JFK")

# Scoring
score = api_client.score_real_time(
    carrier="AA",
    airport="JFK",
    month=12,
    year=2025,
    features={...}
)

# Analytics
stats = api_client.get_summary_stats()
carriers = api_client.get_carrier_performance()
airports = api_client.get_airport_performance()

# Models
models = api_client.list_models()
latest = api_client.get_latest_model()

# Health
health = api_client.health_check()
```

## Configuration

Variables d'environnement:

```bash
API_URL=http://localhost:8000
KAFKA_HOST=kafka
KAFKA_PORT=29092
CLICKHOUSE_HOST=clickhouse
CLICKHOUSE_PORT=8123
```

## Interactivité

### Widgets Streamlit
- `st.selectbox` - Dropdown
- `st.multiselect` - Multi-selection
- `st.slider` - Range selection
- `st.date_input` - Date picker
- `st.button` - Actions
- `st.expander` - Collapsible sections
- `st.tabs` - Tabbed content

### Plotly Features
- Hover tooltips
- Zoom/Pan
- Download as PNG
- Select/Lasso
- Interactive legends
- Drill-down capabilities

### Layout
- `st.columns` - Multi-column layout
- `st.sidebar` - Side navigation
- `st.container` - Grouped content
- `st.metric` - KPI displays with deltas

## Performance

### Optimizations
- **API Caching**: MongoDB avec TTL
- **Pagination**: Lazy loading (100 items/page)
- **Async**: Pas de blocking calls
- **Debouncing**: Filtres avec re-run minimal

### Best Practices
- Avoid `st.experimental_rerun()` loops
- Use `@st.cache_data` pour données statiques
- Minimize API calls avec filtering côté serveur
- Progressive loading pour large datasets

## Styling

### Couleurs
- **Critical/High Risk**: Rouge (#FF6B6B)
- **Warning**: Orange
- **Success/OK**: Vert (#4ECDC4)
- **Primary**: Bleu (#45B7D1)

### Layout
- **Wide mode**: `st.set_page_config(layout="wide")`
- **Icons**: Emojis dans page titles
- **Typography**: Markdown headers (###, ####)

## Déploiement

### Docker Compose
```yaml
streamlit:
  image: python:3.11-slim
  ports:
    - "8501:8501"
  environment:
    API_URL: http://api:8000
  command: streamlit run visualization/Home.py
```

### Production
- **Streamlit Cloud**: Free tier disponible
- **AWS EC2**: t3.small suffisant
- **Azure Container Instances**: Alternative légère

## Troubleshooting

### API Connection Error
```python
# Vérifier API status
import requests
response = requests.get("http://localhost:8000/health")
print(response.json())
```

### No Data Displayed
```bash
# Vérifier MongoDB contient données
mongosh
> use airline_ml
> db.predictions.countDocuments()
```

### Slow Performance
- Activer `@st.cache_data` sur fonctions lourdes
- Réduire `limit` dans API calls
- Vérifier MongoDB indexes

### Plotly Not Rendering
```bash
# Re-install plotly
pip install --upgrade plotly streamlit
```

## Examples

### Filtrage Multi-Dimensionnel
```python
risk = st.slider("Risk Threshold", 0.0, 1.0, 0.8)
carriers = st.multiselect("Carriers", ["AA", "UA", "DL"])

predictions = api_client.list_predictions(
    risk_threshold=risk,
    carrier=",".join(carriers)
)

st.dataframe(predictions)
```

### Drill-Down sur Route
```python
col1, col2 = st.columns(2)
carrier = col1.selectbox("Carrier", carriers)
airport = col2.selectbox("Airport", airports)

if st.button("Analyser"):
    prediction = api_client.get_prediction_by_route(carrier, airport)
    st.metric("Risk Score", f"{prediction['risk_score']:.1%}")
```

### Export CSV
```python
if st.button("Export"):
    df = pd.DataFrame(predictions)
    csv = df.to_csv(index=False)
    st.download_button(
        "Download CSV",
        csv,
        "predictions.csv",
        "text/csv"
    )
```

## Future Improvements

1. **Real-time Updates**: WebSockets pour live data
2. **Custom Dashboards**: User-defined layouts
3. **Alertes Push**: Email/Slack notifications
4. **Multi-User**: Authentication + permissions
5. **Saved Filters**: Persistent user preferences
6. **Report Generation**: Automated PDF reports
7. **A/B Testing**: Compare model versions live
8. **Mobile Responsive**: Optimized for tablets

## Screenshots

(À ajouter après déploiement)

- Dashboard principal
- SHAP waterfall chart
- Heatmap carrier × airport
- Model health gauges
