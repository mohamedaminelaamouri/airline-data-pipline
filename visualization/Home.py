"""
Plateforme Interactive ML - Page d'Accueil
Dashboard global des prédictions et métriques clés
"""
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.api_client import api_clientfrom utils.clickhouse_client import ch_client
st.set_page_config(
    page_title="ML Platform - Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Sidebar
with st.sidebar:
    st.title("ML Platform")
    st.markdown("---")
    st.markdown("**Navigation**")
    st.info("""
    - 📊 Dashboard: Vue globale
    - 🔮 Predictions: Explorer prédictions
    - 🧠 Explainability: Comprendre modèle
    - 📈 Comparaison: Analyser performance
    - 🔍 Monitoring: Détecter drift
    """)
    
    st.markdown("---")
    st.markdown("**System Status**")
    
    # ClickHouse status
    if ch_client.health_check():
        st.success("ClickHouse: Connected")
    else:
        st.error("ClickHouse: Disconnected")
    
    # API status
    try:
        health = api_client.health_check()
        st.success(f"API: {health['status']}")
        st.caption(f"Version: {health.get('version', 'N/A')}")
    except:
        st.warning("API: Unavailable")

# Header
st.title("📊 ML Platform - Dashboard Global")
st.markdown("Plateforme interactive pour visualiser et analyser les prédictions ML")

# KPIs principaux
st.markdown("### Métriques Clés")
try:
    # Use ClickHouse for fast analytics queries
    stats = ch_client.get_summary_stats()
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric(
            label="Total Prédictions",
            value=f"{stats['total_predictions']:,}",
            help="Nombre total de prédictions générées"
        )
    
    with col2:
        st.metric(
            label="Haut Risque",
            value=f"{stats['high_risk_count']:,}",
            delta=f"{stats['high_risk_percentage']:.1f}%",
            delta_color="inverse",
            help="Routes avec risque > 80%"
        )
    
    with col3:
        st.metric(
            label="Score Moyen",
            value=f"{stats['avg_risk_score']:.1%}",
            help="Score de risque moyen"
        )
    
    with col4:
        st.metric(
            label="Carriers",
            value=stats['carriers_analyzed'],
            help="Nombre de compagnies analysées"
        )
    
    with col5:
        st.metric(
            label="Airports",
            value=stats.get('airports_analyzed', 'N/A'),
            help="Nombre d'aéroports analysés"
        )

except Exception as e:
    st.error(f"Impossible de charger les statistiques: {e}")
    st.info("Lancez: python scripts/batch_predictions_demo.py")
    st.stop()

st.markdown("---")

# Layout 2 colonnes
col_left, col_right = st.columns([1, 1])

with col_left:
    st.markdown("### Top 10 Routes a Haut Risque")
    
    try:
        # Use ClickHouse for top risky routes
        df_high_risk = ch_client.get_top_risky_routes(limit=10)
        
        if len(df_high_risk) > 0:
            df_high_risk['route'] = df_high_risk['carrier'] + ' - ' + df_high_risk['origin_airport']
            
            # Graphique horizontal
            fig = px.bar(
                df_high_risk,
                y='route',
                x='risk_score',
                orientation='h',
                text='risk_score',
                labels={'risk_score': 'Risk Score', 'route': 'Route'},
                color='risk_score',
                color_continuous_scale='Reds'
            )
            fig.update_traces(texttemplate='%{text:.1%}', textposition='outside')
            fig.update_layout(height=400, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
            
        else:
            st.info("Aucune route à haut risque détectée")
    
    except Exception as e:
        st.warning(f"Données non disponibles: {e}")

with col_right:
    st.markdown("### Distribution des Risques")
    
    try:
        # Use ClickHouse for risk distribution
        df_distribution = ch_client.get_risk_distribution()
        
        if len(df_distribution) > 0:
            fig = px.bar(
                df_distribution,
                x='risk_level',
                y='count',
                labels={'risk_level': 'Niveau de Risque', 'count': 'Nombre'},
                color='risk_level',
                color_discrete_map={
                    'Low (0-20%)': '#28a745',
                    'Medium (20-50%)': '#ffc107',
                    'High (50-80%)': '#fd7e14',
                    'Critical (80-100%)': '#dc3545'
                }
            )
            fig.update_layout(height=400, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        
    except Exception as e:
        st.warning(f"Données non disponibles: {e}")

st.markdown("---")

# Performance par carrier
st.markdown("### Performance par Compagnie")

try:
    # Use ClickHouse for carrier performance
    df_carriers = ch_client.get_carrier_performance()
    
    if len(df_carriers) > 0:
        # Créer 2 graphiques côte à côte
        fig = make_subplots(
            rows=1, cols=2,
            subplot_titles=('Risque Moyen par Carrier', 'Nombre de Prédictions'),
            specs=[[{"type": "bar"}, {"type": "bar"}]]
        )
        
        # Graphique 1: Risque moyen
        fig.add_trace(
            go.Bar(
                x=df_carriers['carrier'],
                y=df_carriers['avg_risk'],
                name='Risque Moyen',
                marker_color='lightcoral'
            ),
            row=1, col=1
        )
        
        # Graphique 2: Volume
        fig.add_trace(
            go.Bar(
                x=df_carriers['carrier'],
                y=df_carriers['total_routes'],
                name='Routes',
                marker_color='lightblue'
            ),
            row=1, col=2
        )
        
        fig.update_layout(height=400, showlegend=False)
        fig.update_yaxes(title_text="Risk Score", row=1, col=1)
        fig.update_yaxes(title_text="Nombre de Routes", row=1, col=2)
        
        st.plotly_chart(fig, use_container_width=True)

except Exception as e:
    st.warning(f"Données carriers non disponibles: {e}")

st.markdown("---")

# Timeline / Tendances
st.markdown("### Tendances Temporelles")

try:
    # Use ClickHouse for temporal trends
    df_temporal = ch_client.get_temporal_trends(days=30)
    
    if len(df_temporal) > 0:
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=df_temporal['date'],
            y=df_temporal['avg_risk'],
            mode='lines+markers',
            name='Risk Score Moyen',
            line=dict(color='red', width=2),
            marker=dict(size=6)
        ))
        
        fig.update_layout(
            title="Evolution Risk Score sur 30 jours",
            xaxis_title="Date",
            yaxis_title="Risk Score",
            height=400,
            hovermode='x unified'
        )
        
        st.plotly_chart(fig, use_container_width=True)

except Exception as e:
    st.warning(f"Donnees timeline non disponibles: {e}")

st.markdown("---")

# Alertes actives - Use API for ML-enriched data
st.markdown("### Alertes Actives")

try:
    # API still useful for explainability data
    high_risk = api_client.get_high_risk_predictions()
    critical = [p for p in high_risk if p.get('risk_score', 0) > 0.85]
    
    if critical:
        st.error(f"{len(critical)} alertes critiques necessitent une attention immediate")
        
        for pred in critical[:5]:
            with st.expander(f"CRITICAL {pred['carrier']} -> {pred.get('airport', 'N/A')} - Risque: {pred.get('risk_score', 0):.1%}"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("**Details Route:**")
                    st.write(f"- Aeroport: {pred.get('airport', 'N/A')}")
                    st.write(f"- Delay Rate Predit: {pred.get('predicted_delay_rate', 0):.1%}")
                    st.write(f"- Modele: {pred.get('model_version', 'N/A')}")
                
                with col2:
                    st.write("**Actions Recommandées:**")
                    st.write("- ✅ Ajouter personnel check-in")
                    st.write("- ✅ Notifier passagers 48h avant")
                    st.write("- ✅ Préparer équipes maintenance")
    else:
        st.success("✅ Aucune alerte critique. Situation nominale.")

except Exception as e:
    st.warning(f"Impossible de charger les alertes: {e}")

# Footer
st.markdown("---")
st.caption("🤖 Modèle: XGBoost v3.2 | 📡 API REST | 🔄 Mis à jour: Temps réel")
