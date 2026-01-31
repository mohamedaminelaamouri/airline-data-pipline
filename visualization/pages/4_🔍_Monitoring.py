"""
Monitoring - Surveillance du Modèle en Production
Drift Detection, Performance Tracking, Alertes
"""
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.api_client import api_client

st.set_page_config(
    page_title="Monitoring",
    page_icon="🔍",
    layout="wide"
)

st.title("🔍 Monitoring - Surveillance du Modèle")
st.markdown("Détectez les drifts, suivez les performances, gérez les alertes")

# Tabs pour différents types de monitoring
tab1, tab2, tab3, tab4 = st.tabs([
    "📉 Data Drift",
    "🎯 Performance Tracking",
    "⚠️ Alertes",
    "🔄 Model Health"
])

with tab1:
    st.markdown("### Data Drift Detection")
    st.markdown("Surveillez les changements de distribution des features")
    
    # Simuler drift data
    features = ['pair_lag1', 'carrier_lag3_mean', 'airport_lag1', 'arr_flights', 'is_winter']
    
    np.random.seed(42)
    drift_data = pd.DataFrame({
        'feature': features,
        'psi_score': np.random.uniform(0.05, 0.35, len(features)),
        'ks_statistic': np.random.uniform(0.1, 0.4, len(features)),
        'wasserstein_distance': np.random.uniform(0.05, 0.25, len(features)),
        'status': ['OK', 'WARNING', 'CRITICAL', 'OK', 'WARNING']
    })
    
    # PSI Scores
    st.markdown("#### Population Stability Index (PSI)")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Bar chart PSI
        colors = {
            'OK': 'green',
            'WARNING': 'orange',
            'CRITICAL': 'red'
        }
        
        fig = px.bar(
            drift_data.sort_values('psi_score', ascending=False),
            y='feature',
            x='psi_score',
            color='status',
            orientation='h',
            color_discrete_map=colors,
            title="PSI Scores par Feature"
        )
        
        fig.add_vline(x=0.1, line_dash="dash", line_color="orange",
                     annotation_text="Warning (0.1)")
        fig.add_vline(x=0.25, line_dash="dash", line_color="red",
                     annotation_text="Critical (0.25)")
        
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.markdown("**Interprétation PSI:**")
        st.info("""
        **Seuils:**
        - PSI < 0.1: ✅ Stable
        - 0.1 ≤ PSI < 0.25: ⚠️ Warning
        - PSI ≥ 0.25: 🔴 Critical
        
        **Status:**
        - 2 features OK
        - 2 features WARNING
        - 1 feature CRITICAL
        """)
        
        # Pie chart status
        status_counts = drift_data['status'].value_counts()
        fig_pie = px.pie(
            values=status_counts.values,
            names=status_counts.index,
            title="Distribution Status",
            color=status_counts.index,
            color_discrete_map=colors
        )
        st.plotly_chart(fig_pie, use_container_width=True)
    
    # Detailed drift metrics
    st.markdown("#### Métriques de Drift Détaillées")
    
    # Radar chart avec toutes les métriques
    fig = go.Figure()
    
    for metric in ['psi_score', 'ks_statistic', 'wasserstein_distance']:
        # Normaliser pour radar
        normalized = (drift_data[metric] - drift_data[metric].min()) / (drift_data[metric].max() - drift_data[metric].min())
        
        fig.add_trace(go.Scatterpolar(
            r=normalized.tolist(),
            theta=drift_data['feature'].tolist(),
            fill='toself',
            name=metric.replace('_', ' ').title()
        ))
    
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 1])),
        showlegend=True,
        title="Drift Metrics Comparison (Normalized)",
        height=500
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Table détaillée
    st.markdown("#### Tableau Détaillé")
    st.dataframe(
        drift_data.style.applymap(
            lambda x: 'background-color: lightcoral' if x == 'CRITICAL' 
            else 'background-color: lightyellow' if x == 'WARNING'
            else '', subset=['status']
        ),
        use_container_width=True
    )
    
    # Temporal drift evolution
    st.markdown("#### Evolution Temporelle du Drift")
    
    dates = pd.date_range(end=datetime.now(), periods=30, freq='D')
    temporal_drift = pd.DataFrame({
        'date': dates,
        'avg_psi': 0.12 + 0.05 * np.sin(np.arange(30) / 5) + np.random.normal(0, 0.02, 30)
    })
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=temporal_drift['date'],
        y=temporal_drift['avg_psi'],
        mode='lines+markers',
        name='PSI Moyen',
        line=dict(color='#4ECDC4', width=2)
    ))
    
    fig.add_hline(y=0.1, line_dash="dash", line_color="orange", annotation_text="Warning")
    fig.add_hline(y=0.25, line_dash="dash", line_color="red", annotation_text="Critical")
    
    fig.update_layout(
        title="PSI Moyen sur 30 Jours",
        xaxis_title="Date",
        yaxis_title="PSI",
        height=400
    )
    
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.markdown("### Performance Tracking")
    st.markdown("Suivez les performances du modèle en production")
    
    # Simuler performance over time
    dates = pd.date_range(end=datetime.now(), periods=60, freq='D')
    np.random.seed(42)
    
    performance_data = pd.DataFrame({
        'date': dates,
        'roc_auc': 0.738 + np.random.normal(0, 0.01, len(dates)),
        'precision': 0.73 + np.random.normal(0, 0.015, len(dates)),
        'recall': 0.76 + np.random.normal(0, 0.015, len(dates)),
        'f1_score': 0.74 + np.random.normal(0, 0.012, len(dates)),
        'predictions_count': np.random.randint(100, 300, len(dates))
    })
    
    # Metrics evolution
    st.markdown("#### Evolution des Métriques")
    
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=('ROC-AUC', 'Precision', 'Recall', 'F1-Score'),
        vertical_spacing=0.15
    )
    
    # ROC-AUC
    fig.add_trace(
        go.Scatter(x=performance_data['date'], y=performance_data['roc_auc'],
                  mode='lines', name='ROC-AUC', line=dict(color='#FF6B6B')),
        row=1, col=1
    )
    fig.add_hline(y=0.738, line_dash="dash", line_color="gray", row=1, col=1)
    
    # Precision
    fig.add_trace(
        go.Scatter(x=performance_data['date'], y=performance_data['precision'],
                  mode='lines', name='Precision', line=dict(color='#4ECDC4')),
        row=1, col=2
    )
    fig.add_hline(y=0.73, line_dash="dash", line_color="gray", row=1, col=2)
    
    # Recall
    fig.add_trace(
        go.Scatter(x=performance_data['date'], y=performance_data['recall'],
                  mode='lines', name='Recall', line=dict(color='#45B7D1')),
        row=2, col=1
    )
    fig.add_hline(y=0.76, line_dash="dash", line_color="gray", row=2, col=1)
    
    # F1-Score
    fig.add_trace(
        go.Scatter(x=performance_data['date'], y=performance_data['f1_score'],
                  mode='lines', name='F1-Score', line=dict(color='#95E1D3')),
        row=2, col=2
    )
    fig.add_hline(y=0.74, line_dash="dash", line_color="gray", row=2, col=2)
    
    fig.update_layout(height=600, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)
    
    # Statistiques période
    col1, col2, col3, col4 = st.columns(4)
    
    col1.metric(
        "ROC-AUC Moyen",
        f"{performance_data['roc_auc'].mean():.3f}",
        f"{performance_data['roc_auc'].iloc[-7:].mean() - performance_data['roc_auc'].iloc[-30:-7].mean():+.3f}"
    )
    col2.metric(
        "Precision Moyenne",
        f"{performance_data['precision'].mean():.3f}",
        f"{performance_data['precision'].iloc[-7:].mean() - performance_data['precision'].iloc[-30:-7].mean():+.3f}"
    )
    col3.metric(
        "Recall Moyen",
        f"{performance_data['recall'].mean():.3f}",
        f"{performance_data['recall'].iloc[-7:].mean() - performance_data['recall'].iloc[-30:-7].mean():+.3f}"
    )
    col4.metric(
        "F1-Score Moyen",
        f"{performance_data['f1_score'].mean():.3f}",
        f"{performance_data['f1_score'].iloc[-7:].mean() - performance_data['f1_score'].iloc[-30:-7].mean():+.3f}"
    )
    
    # Volume vs Performance
    st.markdown("#### Volume vs Performance")
    
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    fig.add_trace(
        go.Scatter(x=performance_data['date'], y=performance_data['predictions_count'],
                  mode='lines', name='Volume', fill='tozeroy', line=dict(color='lightblue')),
        secondary_y=False
    )
    
    fig.add_trace(
        go.Scatter(x=performance_data['date'], y=performance_data['roc_auc'],
                  mode='lines', name='ROC-AUC', line=dict(color='red', width=2)),
        secondary_y=True
    )
    
    fig.update_xaxes(title_text="Date")
    fig.update_yaxes(title_text="Volume Prédictions", secondary_y=False)
    fig.update_yaxes(title_text="ROC-AUC", secondary_y=True)
    
    fig.update_layout(title="Correlation Volume & Performance", height=400)
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Degradation detection
    st.markdown("#### Détection de Dégradation")
    
    # Calculer moving average
    window = 7
    performance_data['roc_auc_ma'] = performance_data['roc_auc'].rolling(window=window).mean()
    
    # Détecter chutes
    threshold = 0.73
    degraded = performance_data[performance_data['roc_auc_ma'] < threshold]
    
    if len(degraded) > 0:
        st.warning(f"⚠️ {len(degraded)} jour(s) avec performance dégradée (ROC-AUC < {threshold})")
        st.dataframe(degraded[['date', 'roc_auc', 'roc_auc_ma']], use_container_width=True)
    else:
        st.success(f"✅ Performance stable au-dessus du seuil ({threshold})")

with tab3:
    st.markdown("### Système d'Alertes")
    st.markdown("Gérez et visualisez les alertes actives")
    
    # Simuler alertes
    alerts_data = [
        {
            'id': 'ALT001',
            'type': 'DATA_DRIFT',
            'severity': 'CRITICAL',
            'message': 'PSI > 0.25 pour feature "airport_lag1"',
            'created_at': datetime.now() - timedelta(hours=2),
            'status': 'ACTIVE',
            'affected_routes': 12
        },
        {
            'id': 'ALT002',
            'type': 'PERFORMANCE',
            'severity': 'WARNING',
            'message': 'ROC-AUC en baisse de 2% sur 7 jours',
            'created_at': datetime.now() - timedelta(hours=5),
            'status': 'ACTIVE',
            'affected_routes': 0
        },
        {
            'id': 'ALT003',
            'type': 'HIGH_RISK',
            'severity': 'HIGH',
            'message': '15 nouvelles routes avec risk > 80%',
            'created_at': datetime.now() - timedelta(hours=1),
            'status': 'ACTIVE',
            'affected_routes': 15
        },
        {
            'id': 'ALT004',
            'type': 'DATA_QUALITY',
            'severity': 'WARNING',
            'message': '5% de valeurs manquantes détectées',
            'created_at': datetime.now() - timedelta(days=1),
            'status': 'RESOLVED',
            'affected_routes': 8
        }
    ]
    
    df_alerts = pd.DataFrame(alerts_data)
    
    # Filtres
    col1, col2, col3 = st.columns(3)
    
    with col1:
        severity_filter = st.multiselect(
            "Severity",
            ['CRITICAL', 'HIGH', 'WARNING'],
            default=['CRITICAL', 'HIGH', 'WARNING']
        )
    
    with col2:
        type_filter = st.multiselect(
            "Type",
            df_alerts['type'].unique().tolist(),
            default=df_alerts['type'].unique().tolist()
        )
    
    with col3:
        status_filter = st.selectbox("Status", ['ALL', 'ACTIVE', 'RESOLVED'])
    
    # Appliquer filtres
    filtered_alerts = df_alerts[
        (df_alerts['severity'].isin(severity_filter)) &
        (df_alerts['type'].isin(type_filter))
    ]
    
    if status_filter != 'ALL':
        filtered_alerts = filtered_alerts[filtered_alerts['status'] == status_filter]
    
    # Afficher alertes
    st.markdown("---")
    st.markdown(f"#### {len(filtered_alerts)} Alerte(s) Trouvée(s)")
    
    for idx, alert in filtered_alerts.iterrows():
        severity_colors = {
            'CRITICAL': '🔴',
            'HIGH': '🟠',
            'WARNING': '🟡'
        }
        
        with st.expander(f"{severity_colors[alert['severity']]} {alert['id']} - {alert['message']}", expanded=alert['status']=='ACTIVE'):
            col1, col2 = st.columns(2)
            
            with col1:
                st.write(f"**Type:** {alert['type']}")
                st.write(f"**Severity:** {alert['severity']}")
                st.write(f"**Status:** {alert['status']}")
            
            with col2:
                st.write(f"**Created:** {alert['created_at'].strftime('%Y-%m-%d %H:%M')}")
                st.write(f"**Affected Routes:** {alert['affected_routes']}")
            
            if alert['status'] == 'ACTIVE':
                if st.button(f"Résoudre {alert['id']}", key=f"resolve_{alert['id']}"):
                    st.success(f"Alerte {alert['id']} marquée comme résolue")
    
    # Statistiques alertes
    st.markdown("---")
    st.markdown("#### Statistiques Alertes")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Alertes", len(df_alerts))
    col2.metric("Actives", len(df_alerts[df_alerts['status'] == 'ACTIVE']))
    col3.metric("Critical", len(df_alerts[df_alerts['severity'] == 'CRITICAL']))
    col4.metric("Routes Affectées", df_alerts['affected_routes'].sum())
    
    # Timeline alertes
    st.markdown("#### Timeline des Alertes (30 jours)")
    
    dates = pd.date_range(end=datetime.now(), periods=30, freq='D')
    np.random.seed(42)
    alerts_timeline = pd.DataFrame({
        'date': dates,
        'critical': np.random.randint(0, 3, len(dates)),
        'high': np.random.randint(0, 5, len(dates)),
        'warning': np.random.randint(1, 8, len(dates))
    })
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=alerts_timeline['date'],
        y=alerts_timeline['critical'],
        name='Critical',
        marker_color='red'
    ))
    
    fig.add_trace(go.Bar(
        x=alerts_timeline['date'],
        y=alerts_timeline['high'],
        name='High',
        marker_color='orange'
    ))
    
    fig.add_trace(go.Bar(
        x=alerts_timeline['date'],
        y=alerts_timeline['warning'],
        name='Warning',
        marker_color='yellow'
    ))
    
    fig.update_layout(
        barmode='stack',
        title="Alertes par Jour",
        xaxis_title="Date",
        yaxis_title="Nombre d'Alertes",
        height=400
    )
    
    st.plotly_chart(fig, use_container_width=True)

with tab4:
    st.markdown("### Model Health Dashboard")
    st.markdown("Vue d'ensemble de la santé du modèle")
    
    # Health score
    health_scores = {
        'Data Quality': 85,
        'Performance Stability': 92,
        'Drift Status': 75,
        'Prediction Volume': 95,
        'API Latency': 88
    }
    
    # Gauges
    st.markdown("#### Health Scores")
    
    cols = st.columns(len(health_scores))
    
    for idx, (metric, score) in enumerate(health_scores.items()):
        with cols[idx]:
            color = 'green' if score >= 80 else 'orange' if score >= 60 else 'red'
            
            fig = go.Figure(go.Indicator(
                mode="gauge+number",
                value=score,
                title={'text': metric},
                gauge={
                    'axis': {'range': [0, 100]},
                    'bar': {'color': color},
                    'steps': [
                        {'range': [0, 60], 'color': 'lightgray'},
                        {'range': [60, 80], 'color': 'lightyellow'},
                        {'range': [80, 100], 'color': 'lightgreen'}
                    ],
                    'threshold': {
                        'line': {'color': "red", 'width': 4},
                        'thickness': 0.75,
                        'value': 70
                    }
                }
            ))
            
            fig.update_layout(height=250, margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig, use_container_width=True)
    
    # Overall health
    overall_health = np.mean(list(health_scores.values()))
    
    st.markdown("---")
    st.markdown("#### Overall Model Health")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        if overall_health >= 85:
            st.success(f"✅ Excellent - Score: {overall_health:.1f}/100")
        elif overall_health >= 70:
            st.warning(f"⚠️ Attention Requise - Score: {overall_health:.1f}/100")
        else:
            st.error(f"🔴 Action Immédiate Requise - Score: {overall_health:.1f}/100")
    
    # Recommendations
    st.markdown("#### Recommandations")
    
    if health_scores['Drift Status'] < 80:
        st.warning("📊 **Data Drift:** Ré-entraînement du modèle recommandé")
    
    if health_scores['Performance Stability'] < 80:
        st.warning("🎯 **Performance:** Vérifier la qualité des données récentes")
    
    if health_scores['Data Quality'] < 80:
        st.warning("🔍 **Data Quality:** Investiguer les pipelines de données")
    
    if overall_health >= 85:
        st.success("✅ Aucune action immédiate requise - Monitoring continu")

# Footer
st.markdown("---")
st.caption("🔍 Drift Detection | 🎯 Performance Tracking | ⚠️ Alert Management | 🔄 Model Health")
