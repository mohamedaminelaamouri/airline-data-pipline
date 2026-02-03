"""
ML Training Pipeline - Prédiction 2026
======================================
✅ Train: 2010-2018 (données réelles)
✅ Test: 2019-2022 (validation académique)  
✅ Predict: 2026 (12 mois)
✅ Modèle: XGBoost régression
"""
import clickhouse_connect
import pandas as pd
import numpy as np
from datetime import datetime
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import xgboost as xgb
import joblib
from pymongo import MongoClient
import os
import json

print("=" * 80)
print("ML TRAINING PIPELINE - Prédiction 2026")
print("=" * 80)

# ============================================================================
# Configuration
# ============================================================================
TRAIN_YEARS = (2010, 2018)  # Entraînement
TEST_YEARS = (2019, 2022)   # Validation
PREDICT_YEAR = 2026         # Prédiction
MODEL_VERSION = f"v1.0_{datetime.now().strftime('%Y%m%d_%H%M')}"

# ============================================================================
# Connexions
# ============================================================================
print("\n[1/6] Connexions...")

# ClickHouse
ch_client = clickhouse_connect.get_client(
    host=os.getenv('CLICKHOUSE_HOST', 'localhost'),
    port=int(os.getenv('CLICKHOUSE_HTTP_PORT', '8123')),
    database='airline_data'
)

# MongoDB
mongo_client = MongoClient(os.getenv('MONGODB_URI', 'mongodb://localhost:27017/'))
mongo_db = mongo_client['airline_ml']
models_collection = mongo_db['models']

print("✅ ClickHouse + MongoDB connectés")

# ============================================================================
# Chargement des données
# ============================================================================
print(f"\n[2/6] Chargement données gold_ml_features...")

query = """
SELECT 
    carrier,
    origin_airport,
    year,
    month,
    delay_rate,
    arr_flights,
    arr_del15,
    is_summer,
    is_winter,
    is_holiday_season
FROM gold_ml_features
WHERE year BETWEEN 2010 AND 2022
ORDER BY year, month, carrier, origin_airport
"""

df = ch_client.query_df(query)
print(f"✅ {len(df):,} records chargés (2010-2022)")

# ============================================================================
# Feature Engineering (Lag features en pandas)
# ============================================================================
print("\n[3/6] Feature engineering (lags)...")

# Trier pour calculs temporels
df = df.sort_values(['carrier', 'origin_airport', 'year', 'month'])

# Lag features par paire (carrier + airport)
df['pair_lag1'] = df.groupby(['carrier', 'origin_airport'])['delay_rate'].shift(1)
df['pair_lag2'] = df.groupby(['carrier', 'origin_airport'])['delay_rate'].shift(2)
df['pair_lag3'] = df.groupby(['carrier', 'origin_airport'])['delay_rate'].shift(3)

# Moyennes carrier
carrier_means = df.groupby(['carrier', 'year', 'month'])['delay_rate'].transform('mean')
df['carrier_lag1_mean'] = df.groupby('carrier')['delay_rate'].shift(1)
df['carrier_lag2_mean'] = df.groupby('carrier')['delay_rate'].shift(2)
df['carrier_lag3_mean'] = df.groupby('carrier')['delay_rate'].shift(3)

# Moyennes airport
df['airport_lag1'] = df.groupby('origin_airport')['delay_rate'].shift(1)
df['airport_lag2'] = df.groupby('origin_airport')['delay_rate'].shift(2)
df['airport_lag3'] = df.groupby('origin_airport')['delay_rate'].shift(3)

# Rolling averages (3 et 6 mois)
df['carrier_rolling_3m'] = df.groupby('carrier')['delay_rate'].transform(
    lambda x: x.rolling(window=3, min_periods=1).mean().shift(1)
)
df['carrier_rolling_6m'] = df.groupby('carrier')['delay_rate'].transform(
    lambda x: x.rolling(window=6, min_periods=1).mean().shift(1)
)
df['airport_rolling_3m'] = df.groupby('origin_airport')['delay_rate'].transform(
    lambda x: x.rolling(window=3, min_periods=1).mean().shift(1)
)
df['airport_rolling_6m'] = df.groupby('origin_airport')['delay_rate'].transform(
    lambda x: x.rolling(window=6, min_periods=1).mean().shift(1)
)

# Remplir NaN avec 0 (premières valeurs sans historique)
df = df.fillna(0)

print(f"✅ Features calculés: {len(df.columns)} colonnes")

# ============================================================================
# Split Train/Test (académique)
# ============================================================================
print(f"\n[4/6] Split Train/Test...")

# Train: 2010-2018
train_df = df[(df['year'] >= TRAIN_YEARS[0]) & (df['year'] <= TRAIN_YEARS[1])].copy()

# Test: 2019-2022
test_df = df[(df['year'] >= TEST_YEARS[0]) & (df['year'] <= TEST_YEARS[1])].copy()

print(f"   Train: {len(train_df):,} rows ({TRAIN_YEARS[0]}-{TRAIN_YEARS[1]})")
print(f"   Test:  {len(test_df):,} rows ({TEST_YEARS[0]}-{TEST_YEARS[1]})")

# Features et target
feature_cols = [
    'arr_flights', 'pair_lag1', 'pair_lag2', 'pair_lag3',
    'carrier_lag1_mean', 'carrier_lag2_mean', 'carrier_lag3_mean',
    'airport_lag1', 'airport_lag2', 'airport_lag3',
    'carrier_rolling_3m', 'carrier_rolling_6m',
    'airport_rolling_3m', 'airport_rolling_6m',
    'is_summer', 'is_winter', 'is_holiday_season', 'month'
]

X_train = train_df[feature_cols]
y_train = train_df['delay_rate']

X_test = test_df[feature_cols]
y_test = test_df['delay_rate']

# ============================================================================
# Entraînement XGBoost
# ============================================================================
print(f"\n[5/6] Entraînement XGBoost...")

model = xgb.XGBRegressor(
    objective='reg:squarederror',
    n_estimators=200,
    max_depth=6,
    learning_rate=0.1,
    subsample=0.8,
    colsample_bytree=0.8,
    random_state=42,
    n_jobs=-1
)

model.fit(X_train, y_train, verbose=False)

# Évaluation sur test
y_pred_test = model.predict(X_test)
mae = mean_absolute_error(y_test, y_pred_test)
rmse = np.sqrt(mean_squared_error(y_test, y_pred_test))
r2 = r2_score(y_test, y_pred_test)

print(f"""
✅ Modèle entraîné:
   - MAE:  {mae:.4f} ({mae*100:.2f}%)
   - RMSE: {rmse:.4f} ({rmse*100:.2f}%)
   - R²:   {r2:.4f}
""")

# Feature importance
feature_importance = pd.DataFrame({
    'feature': feature_cols,
    'importance': model.feature_importances_
}).sort_values('importance', ascending=False)

print("Top 5 features:")
for idx, row in feature_importance.head(5).iterrows():
    print(f"   {row['feature']}: {row['importance']:.3f}")

# ============================================================================
# Prédictions 2026 (OPTIMISÉ)
# ============================================================================
print(f"\n[6/6] Prédictions 2026 (12 mois)...")

# OPTIMISATION: Précalculer les features par route (1 fois au lieu de 22K fois)
df_2022 = df[df['year'] == 2022].copy()
route_features = df_2022.groupby(['carrier', 'origin_airport']).agg({
    'arr_flights': 'mean',
    'delay_rate': 'last',  # Dernier mois pour lag1
    'carrier_lag1_mean': 'last',
    'carrier_lag2_mean': 'last',
    'carrier_lag3_mean': 'last',
    'airport_lag1': 'last',
    'airport_lag2': 'last',
    'airport_lag3': 'last',
    'carrier_rolling_3m': 'last',
    'carrier_rolling_6m': 'last',
    'airport_rolling_3m': 'last',
    'airport_rolling_6m': 'last'
}).reset_index()

print(f"   Routes actives: {len(route_features)}")

# Créer toutes les prédictions en batch
predictions_list = []

for _, route in route_features.iterrows():
    for month in range(1, 13):
        features = {
            'arr_flights': int(route['arr_flights']),
            'pair_lag1': route['delay_rate'],
            'pair_lag2': route['delay_rate'],  # Simplifié
            'pair_lag3': route['delay_rate'],
            'carrier_lag1_mean': route['carrier_lag1_mean'],
            'carrier_lag2_mean': route['carrier_lag2_mean'],
            'carrier_lag3_mean': route['carrier_lag3_mean'],
            'airport_lag1': route['airport_lag1'],
            'airport_lag2': route['airport_lag2'],
            'airport_lag3': route['airport_lag3'],
            'carrier_rolling_3m': route['carrier_rolling_3m'],
            'carrier_rolling_6m': route['carrier_rolling_6m'],
            'airport_rolling_3m': route['airport_rolling_3m'],
            'airport_rolling_6m': route['airport_rolling_6m'],
            'is_summer': 1 if month in [6, 7, 8] else 0,
            'is_winter': 1 if month in [12, 1, 2] else 0,
            'is_holiday_season': 1 if month in [11, 12] else 0,
            'month': month
        }
        predictions_list.append({
            'carrier': route['carrier'],
            'airport': route['origin_airport'],
            'month': month,
            'features': features
        })

# Prédictions en batch (beaucoup plus rapide)
print(f"   Génération {len(predictions_list):,} prédictions...")
X_pred_all = pd.DataFrame([p['features'] for p in predictions_list])[feature_cols]
preds = model.predict(X_pred_all)

# Construire résultats
top_features = feature_importance.head(3)
predictions_2026 = []

for i, (pred_info, pred_value) in enumerate(zip(predictions_list, preds)):
    risk_score = min(pred_value / 0.5, 1.0)
    risk_category = 'high' if pred_value >= 0.3 else ('medium' if pred_value >= 0.15 else 'low')
    
    predictions_2026.append({
        'carrier': pred_info['carrier'],
        'origin_airport': pred_info['airport'],
        'year': PREDICT_YEAR,
        'month': pred_info['month'],
        'predicted_delay_rate': float(pred_value),
        'risk_score': float(risk_score),
        'risk_category': risk_category,
        'arr_flights': pred_info['features']['arr_flights'],
        'model_version': MODEL_VERSION,
        'model_type': 'xgboost',
        'confidence': float(r2),
        'top_feature_1': top_features.iloc[0]['feature'],
        'top_feature_1_importance': float(top_features.iloc[0]['importance']),
        'top_feature_2': top_features.iloc[1]['feature'],
        'top_feature_2_importance': float(top_features.iloc[1]['importance']),
        'top_feature_3': top_features.iloc[2]['feature'],
        'top_feature_3_importance': float(top_features.iloc[2]['importance'])
    })

pred_df = pd.DataFrame(predictions_2026)
print(f"✅ {len(pred_df):,} prédictions générées")

# ============================================================================
# Sauvegarder dans ClickHouse
# ============================================================================
print("\nSauvegarde ClickHouse ml_predictions...")

ch_client.insert_df('ml_predictions', pred_df)

# Vérification
count = ch_client.query("SELECT count() FROM ml_predictions").result_rows[0][0]
print(f"✅ {count:,} prédictions dans ClickHouse")

# ============================================================================
# Sauvegarder modèle MongoDB
# ============================================================================
print("\nSauvegarde modèle MongoDB...")

# Sérialiser modèle
import tempfile
with tempfile.NamedTemporaryFile(delete=False, suffix='.pkl') as f:
    joblib.dump(model, f.name)
    with open(f.name, 'rb') as model_file:
        model_binary = model_file.read()
    os.unlink(f.name)

model_doc = {
    'model_version': MODEL_VERSION,
    'model_type': 'xgboost',
    'created_at': datetime.now(),
    'metrics': {
        'mae': float(mae),
        'rmse': float(rmse),
        'r2': float(r2)
    },
    'training': {
        'train_years': TRAIN_YEARS,
        'test_years': TEST_YEARS,
        'train_samples': len(train_df),
        'test_samples': len(test_df)
    },
    'features': feature_cols,
    'feature_importance': feature_importance.to_dict('records'),
    'model_binary': model_binary,
    'predictions_count': len(pred_df),
    'predict_year': PREDICT_YEAR
}

models_collection.insert_one(model_doc)
print(f"✅ Modèle sauvegardé MongoDB: {MODEL_VERSION}")

# ============================================================================
# Résumé final
# ============================================================================
print("\n" + "=" * 80)
print("✅ TRAINING PIPELINE TERMINÉ")
print("=" * 80)

summary = pred_df.groupby('risk_category').size()
print(f"""
📊 Prédictions 2026:
   - Total: {len(pred_df):,} routes × 12 mois
   - High risk: {summary.get('high', 0):,}
   - Medium risk: {summary.get('medium', 0):,}
   - Low risk: {summary.get('low', 0):,}
   
📈 Performance modèle:
   - Train: 2010-2018 ({len(train_df):,} rows)
   - Test: 2019-2022 ({len(test_df):,} rows)
   - MAE: {mae:.1%}
   - R²: {r2:.3f}
   
💾 Sauvegardé:
   - ClickHouse: ml_predictions ({count:,} rows)
   - MongoDB: {MODEL_VERSION}
""")

print("🎯 Modèle prêt pour production!")
print("=" * 80)
