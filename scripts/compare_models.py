"""
Comparaison Modèle V1 vs V2
===========================
Compare les performances et la logique des prédictions
"""
import clickhouse_connect
import pandas as pd
import numpy as np
import os

print("=" * 60)
print("🔬 COMPARAISON V1 vs V2")
print("=" * 60)

ch_client = clickhouse_connect.get_client(
    host=os.getenv('CLICKHOUSE_HOST', 'localhost'),
    port=int(os.getenv('CLICKHOUSE_HTTP_PORT', '8123')),
    database='airline_data'
)

# Charger les prédictions actuelles (V1)
v1_df = ch_client.query_df("""
    SELECT 
        month,
        predicted_delay_rate,
        risk_category,
        model_version
    FROM ml_predictions 
    WHERE year = 2026
""")

if len(v1_df) > 0:
    print("\n📊 Prédictions V1 actuelles:")
    monthly_v1 = v1_df.groupby('month')['predicted_delay_rate'].agg(['mean', 'std', 'min', 'max'])
    print(monthly_v1.to_string())
    
    print(f"\nMoyenne globale V1: {v1_df['predicted_delay_rate'].mean()*100:.1f}%")
    
    # Distribution des risques
    print("\nDistribution risques V1:")
    print(v1_df['risk_category'].value_counts())
    
    # Saisonnalité
    summer_v1 = v1_df[v1_df['month'].isin([6,7,8])]['predicted_delay_rate'].mean()
    fall_v1 = v1_df[v1_df['month'].isin([9,10,11])]['predicted_delay_rate'].mean()
    print(f"\nSaisonnalité V1: Été={summer_v1*100:.1f}%, Automne={fall_v1*100:.1f}%")
else:
    print("⚠️ Aucune prédiction V1 trouvée")

# Charger données historiques pour comparaison
print("\n📊 Référence historique (2019-2022):")
hist_df = ch_client.query_df("""
    SELECT 
        month,
        avg(delay_rate) as avg_delay,
        stddevPop(delay_rate) as std_delay
    FROM gold_ml_features
    WHERE year BETWEEN 2019 AND 2022
    GROUP BY month
    ORDER BY month
""")
print(hist_df.to_string())

# Graphique en ASCII
print("\n📊 Pattern saisonnier historique:")
for _, row in hist_df.iterrows():
    bars = int(row['avg_delay'] * 100)
    print(f"Mois {int(row['month']):2d}: {'█' * bars} {row['avg_delay']*100:.1f}%")

print("\n" + "=" * 60)
print("✅ Pour exécuter le nouveau modèle:")
print("   python scripts/train_model_2026_v2.py")
print("=" * 60)
