"""
ML Predictions Dashboard
Affiche les prédictions de retards avec explainability
Consomme l'API REST FastAPI
"""
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import sys
from pathlib import Path

# Ajouter utils au path
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.api_client import api_client

st.set_page_config(page_title="ML Predictions", page_icon="ML", layout="wide")

# Vérifier santé de l'API
try:
    health = api_client.health_check()
    if health["status"] != "healthy":
        st.error("API non disponible. Démarrez le service API: docker compose up -d api")
        st.stop()
except Exception as e:
    st.error(f"Impossible de contacter l'API: {e}")
    st.info("Assurez-vous que le service API est démarré: docker compose up -d api")
    st.stop()

# Header
st.title("ML Predictions - Airline Delays")
st.markdown("Prédictions XGBoost pour le mois prochain avec explainability")

# Métriques globales via API
col1, col2, col3, col4 = st.columns(4)

try:
    stats = api_client.get_summary_stats()
    
    col1.metric("Total Prédictions", f"{stats['total_predictions']:,}")
    col2.metric("Routes Haut Risque", f"{stats['high_risk_count']:,}", 
                delta=f"{stats['high_risk_percentage']:.1f}%")
    col3.metric("Score Risque Moyen", f"{stats['avg_risk_score']:.2%}")
    col4.metric("Carriers Analysés", stats['carriers_analyzed'])
except Exception as e:
    st.warning(f"Impossible de charger les statistiques: {e}")
    st.info("Lancez d'abord: python scripts/batch_predictions_demo.py")
    st.stop()

# Filtres
st.markdown("---")
col1, col2, col3 = st.columns(3)

with col1:
    risk_threshold = st.slider("Seuil de Risque Minimum", 0.0, 1.0, 0.70, 0.05)

with col2:
    # Récupérer carriers via API
    try:
        carrier_perf = api_client.get_carrier_performance()
        carriers = [c['carrier'] for c in carrier_perf]
        selected_carriers = st.multiselect("Filtrer par Carrier", carriers, default=carriers[:5] if len(carriers) >= 5 else carriers)
    except:
        selected_carriers = []

with col3:
    sort_by = st.selectbox("Trier par", ["Score Risque", "Delay Rate", "Carrier", "Airport"])

# Table prédictions via API
st.markdown("### Table Prédictions Détaillées")

try:
    # Appel API avec filtres
    result = api_client.list_predictions(
        risk_threshold=risk_threshold,
        carrier=selected_carriers[0] if selected_carriers else None,
        limit=100
    )
    
    predictions = result['predictions']
    
    if len(predictions) > 0:
        df = pd.DataFrame(predictions)
        
        # Formatage
        df['Route'] = df['carrier'] + ' → ' + df['airport']
        df['Risk'] = df['risk_score'].apply(lambda x: f"{x:.1%}")
        df['Delay Rate'] = df['predicted_delay_rate'].apply(lambda x: f"{x:.1%}")
        
        # Affichage
        display_df = df[['Route', 'airport_name', 'Risk', 'Delay Rate', 'model_version']].head(50)
        st.dataframe(display_df, use_container_width=True, height=400)
        
        # Visualisations
        st.markdown("### Visualisations")
        
        tab1, tab2 = st.tabs(["Distribution", "Top Features"])
        
        with tab1:
            fig = px.histogram(df, x='risk_score', nbins=20,
                              title="Distribution des Scores de Risque")
            fig.add_vline(x=0.80, line_dash="dash", line_color="red")
            st.plotly_chart(fig, use_container_width=True)
        
        with tab2:
            if 'top_features' in df.columns:
                st.write("Feature importance disponible via explainability")
    
    else:
        st.warning("Aucune prédiction ne correspond aux filtres")
        
except Exception as e:
    st.error(f"Erreur lors du chargement des prédictions: {e}")

st.markdown("---")
st.caption("Modèle: XGBoost | Données: API REST | Rafraîchi toutes les 24h")
