"""
Explainability - Comprendre les Prédictions du Modèle
Visualisation SHAP values et feature importance
"""
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.api_client import api_client

st.set_page_config(
    page_title="Explainability",
    page_icon="🧠",
    layout="wide"
)

st.title("🧠 Explainability - Comprendre le Modèle")
st.markdown("Visualisez pourquoi le modèle fait certaines prédictions")

# Tabs pour différents types d'explainability
tab1, tab2, tab3 = st.tabs([
    "🎯 Feature Importance Globale",
    "🔍 Explication par Route",
    "📊 Feature Impact"
])

with tab1:
    st.markdown("### Feature Importance Globale")
    st.markdown("Quelles features influencent le plus les prédictions?")
    
    # Simuler feature importance (à remplacer par vraies données depuis modèle)
    features_data = {
        'feature': [
            'pair_lag1', 'carrier_lag3_mean', 'airport_lag1',
            'is_winter', 'month_sin', 'arr_flights',
            'pair_expanding_mean', 'is_holiday_season', 'log_arr_flights',
            'carrier_lag1', 'airport_lag3_mean', 'month_cos'
        ],
        'importance': [0.23, 0.18, 0.15, 0.12, 0.08, 0.07, 0.05, 0.04, 0.04, 0.02, 0.01, 0.01],
        'category': [
            'Lag', 'Lag', 'Lag',
            'Seasonality', 'Seasonality', 'Volume',
            'Lag', 'Seasonality', 'Volume',
            'Lag', 'Lag', 'Seasonality'
        ]
    }
    df_features = pd.DataFrame(features_data)
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Bar chart horizontal
        fig = px.bar(
            df_features.sort_values('importance', ascending=True),
            y='feature',
            x='importance',
            color='category',
            orientation='h',
            title="Importance des Features (XGBoost)",
            labels={'importance': 'Importance', 'feature': 'Feature'},
            color_discrete_map={
                'Lag': '#FF6B6B',
                'Seasonality': '#4ECDC4',
                'Volume': '#45B7D1'
            }
        )
        fig.update_layout(height=500)
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.markdown("**Interprétation:**")
        st.info("""
        **Top 3 Features:**
        
        1. **pair_lag1** (23%): Performance du mois précédent pour cette route spécifique
        
        2. **carrier_lag3_mean** (18%): Moyenne des 3 derniers mois pour cette compagnie
        
        3. **airport_lag1** (15%): Performance du mois précédent pour cet aéroport
        
        Les features de **lag** (historique) représentent 70% de l'importance totale.
        """)
        
        # Pie chart catégories
        category_importance = df_features.groupby('category')['importance'].sum().reset_index()
        fig_pie = px.pie(
            category_importance,
            values='importance',
            names='category',
            title="Importance par Catégorie"
        )
        st.plotly_chart(fig_pie, use_container_width=True)

with tab2:
    st.markdown("### Explication par Route Spécifique")
    st.markdown("Sélectionnez une route pour comprendre sa prédiction")
    
    col1, col2 = st.columns(2)
    
    with col1:
        carrier = st.selectbox("Carrier", ["AA", "UA", "DL", "WN", "B6"])
    
    with col2:
        airport = st.selectbox("Airport", ["JFK", "ORD", "ATL", "LAX", "DFW"])
    
    if st.button("Analyser Route", type="primary"):
        try:
            prediction = api_client.get_prediction_by_route(carrier, airport)
            
            st.markdown("---")
            
            # Métriques de la prédiction
            col1, col2, col3 = st.columns(3)
            col1.metric("Risk Score", f"{prediction['risk_score']:.1%}")
            col2.metric("Delay Rate Prédit", f"{prediction['predicted_delay_rate']:.1%}")
            col3.metric("Modèle", prediction.get('model_version', 'N/A'))
            
            st.markdown("---")
            
            # SHAP values (waterfall chart)
            st.markdown("#### 💧 Waterfall Plot - Contribution des Features")
            
            # Simuler SHAP values
            baseline = 0.20  # Base delay rate
            shap_data = {
                'feature': ['pair_lag1', 'is_winter', 'carrier_lag3', 'airport_lag1', 'arr_flights'],
                'shap_value': [0.15, 0.08, -0.05, 0.06, -0.02],
                'feature_value': [0.28, 1, 0.22, 0.25, 850]
            }
            df_shap = pd.DataFrame(shap_data)
            
            # Créer waterfall
            fig = go.Figure(go.Waterfall(
                name="SHAP",
                orientation="v",
                measure=["relative"] * len(df_shap) + ["total"],
                x=df_shap['feature'].tolist() + ['Prédiction'],
                y=df_shap['shap_value'].tolist() + [baseline + df_shap['shap_value'].sum()],
                text=[f"+{v:.2%}" if v > 0 else f"{v:.2%}" for v in df_shap['shap_value'].tolist()] + [f"{baseline + df_shap['shap_value'].sum():.1%}"],
                connector={"line": {"color": "rgb(63, 63, 63)"}},
            ))
            
            fig.add_hline(y=baseline, line_dash="dash", line_color="gray",
                         annotation_text=f"Baseline: {baseline:.1%}")
            
            fig.update_layout(
                title=f"Contribution des Features pour {carrier} → {airport}",
                showlegend=False,
                height=400
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Explication textuelle
            st.markdown("#### 📝 Explication Détaillée")
            
            for idx, row in df_shap.iterrows():
                impact = "augmente" if row['shap_value'] > 0 else "diminue"
                color = "🔴" if row['shap_value'] > 0 else "🟢"
                st.write(f"{color} **{row['feature']}** (valeur: {row['feature_value']}) {impact} le risque de {abs(row['shap_value']):.1%}")
        
        except Exception as e:
            st.error(f"Erreur: {e}")
            st.info("Assurez-vous que la prédiction existe pour cette route")

with tab3:
    st.markdown("### Impact des Features sur les Prédictions")
    st.markdown("Comment chaque feature influence les prédictions?")
    
    # Sélection feature
    selected_feature = st.selectbox(
        "Feature à analyser",
        ['pair_lag1', 'carrier_lag3_mean', 'airport_lag1', 'is_winter', 'arr_flights']
    )
    
    # Simuler données scatter
    np.random.seed(42)
    n_points = 200
    feature_values = np.random.uniform(0, 0.5, n_points) if 'lag' in selected_feature else np.random.randint(0, 2, n_points)
    risk_scores = 0.2 + 0.4 * feature_values + np.random.normal(0, 0.05, n_points)
    risk_scores = np.clip(risk_scores, 0, 1)
    
    df_scatter = pd.DataFrame({
        'feature_value': feature_values,
        'risk_score': risk_scores,
        'carrier': np.random.choice(['AA', 'UA', 'DL', 'WN'], n_points)
    })
    
    # Scatter plot avec trend line
    fig = px.scatter(
        df_scatter,
        x='feature_value',
        y='risk_score',
        color='carrier',
        trendline="lowess",
        title=f"Impact de '{selected_feature}' sur le Risk Score",
        labels={
            'feature_value': f'Valeur de {selected_feature}',
            'risk_score': 'Risk Score'
        }
    )
    fig.update_layout(height=500)
    st.plotly_chart(fig, use_container_width=True)
    
    # Statistics
    col1, col2, col3 = st.columns(3)
    col1.metric("Corrélation", f"{np.corrcoef(feature_values, risk_scores)[0,1]:.3f}")
    col2.metric("Moyenne Feature", f"{feature_values.mean():.3f}")
    col3.metric("Std Feature", f"{feature_values.std():.3f}")
    
    st.markdown("#### Insights")
    if np.corrcoef(feature_values, risk_scores)[0,1] > 0.5:
        st.success(f"✅ Corrélation forte positive: Quand {selected_feature} augmente, le risque augmente")
    elif np.corrcoef(feature_values, risk_scores)[0,1] < -0.5:
        st.success(f"✅ Corrélation forte négative: Quand {selected_feature} augmente, le risque diminue")
    else:
        st.info(f"ℹ️ Corrélation faible: {selected_feature} a un impact modéré")

# Footer
st.markdown("---")
st.caption("🧠 SHAP Explainability | 📊 Feature Importance | 🎯 Model Interpretability")
