"""
Comparaison - Comparer Modèles, Périodes, Carriers
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
    page_title="Comparaison",
    page_icon="📈",
    layout="wide"
)

st.title("📈 Comparaison - Analyse Comparative")
st.markdown("Comparez modèles, périodes temporelles, et performances carriers")

# Tabs pour différents types de comparaisons
tab1, tab2, tab3 = st.tabs([
    "🔬 Modèles",
    "📅 Périodes Temporelles",
    "✈️ Carriers vs Airports"
])

with tab1:
    st.markdown("### Comparaison des Modèles")
    st.markdown("Comparez les performances de différentes versions du modèle")
    
    # Simuler données modèles
    models_data = {
        'version': ['v1.0.0', 'v1.1.0', 'v1.2.0', 'v2.0.0', 'v2.1.0'],
        'train_date': pd.date_range(end=datetime.now(), periods=5, freq='30D'),
        'roc_auc': [0.725, 0.732, 0.738, 0.741, 0.745],
        'precision': [0.68, 0.71, 0.73, 0.75, 0.77],
        'recall': [0.72, 0.74, 0.76, 0.78, 0.79],
        'f1_score': [0.70, 0.72, 0.74, 0.76, 0.78],
        'train_samples': [280000, 300000, 320000, 340000, 348000],
        'features': [18, 19, 21, 21, 23]
    }
    df_models = pd.DataFrame(models_data)
    
    # Sélection modèles à comparer
    st.markdown("#### Sélectionnez les Modèles à Comparer")
    selected_models = st.multiselect(
        "Versions",
        df_models['version'].tolist(),
        default=[df_models['version'].iloc[-2], df_models['version'].iloc[-1]]
    )
    
    if len(selected_models) >= 2:
        df_compare = df_models[df_models['version'].isin(selected_models)]
        
        st.markdown("---")
        st.markdown("#### Comparaison des Métriques")
        
        # Radar chart
        fig = go.Figure()
        
        metrics = ['roc_auc', 'precision', 'recall', 'f1_score']
        
        for idx, row in df_compare.iterrows():
            fig.add_trace(go.Scatterpolar(
                r=[row[m] for m in metrics],
                theta=['ROC-AUC', 'Precision', 'Recall', 'F1-Score'],
                fill='toself',
                name=row['version']
            ))
        
        fig.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[0.6, 0.85]
                )
            ),
            showlegend=True,
            title="Radar Chart - Performance Metrics"
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Table comparative
        st.markdown("#### Tableau Comparatif Détaillé")
        
        # Calculer améliorations
        df_display = df_compare.copy()
        df_display['train_date'] = df_display['train_date'].dt.strftime('%Y-%m-%d')
        
        st.dataframe(
            df_display.style.highlight_max(
                subset=['roc_auc', 'precision', 'recall', 'f1_score'],
                color='lightgreen'
            ),
            use_container_width=True
        )
        
        # Evolution temporelle
        st.markdown("#### Evolution des Métriques")
        
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=('ROC-AUC', 'Precision', 'Recall', 'F1-Score')
        )
        
        fig.add_trace(
            go.Scatter(x=df_models['version'], y=df_models['roc_auc'], 
                      mode='lines+markers', name='ROC-AUC'),
            row=1, col=1
        )
        fig.add_trace(
            go.Scatter(x=df_models['version'], y=df_models['precision'],
                      mode='lines+markers', name='Precision'),
            row=1, col=2
        )
        fig.add_trace(
            go.Scatter(x=df_models['version'], y=df_models['recall'],
                      mode='lines+markers', name='Recall'),
            row=2, col=1
        )
        fig.add_trace(
            go.Scatter(x=df_models['version'], y=df_models['f1_score'],
                      mode='lines+markers', name='F1-Score'),
            row=2, col=2
        )
        
        fig.update_layout(height=600, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
        
        # Statistiques d'amélioration
        if len(selected_models) == 2:
            v1, v2 = selected_models[0], selected_models[1]
            row1 = df_models[df_models['version'] == v1].iloc[0]
            row2 = df_models[df_models['version'] == v2].iloc[0]
            
            st.markdown(f"#### Amélioration de {v1} à {v2}")
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("ROC-AUC", f"{row2['roc_auc']:.3f}", f"+{(row2['roc_auc'] - row1['roc_auc']):.3f}")
            col2.metric("Precision", f"{row2['precision']:.3f}", f"+{(row2['precision'] - row1['precision']):.3f}")
            col3.metric("Recall", f"{row2['recall']:.3f}", f"+{(row2['recall'] - row1['recall']):.3f}")
            col4.metric("F1-Score", f"{row2['f1_score']:.3f}", f"+{(row2['f1_score'] - row1['f1_score']):.3f}")

with tab2:
    st.markdown("### Comparaison Temporelle")
    st.markdown("Analysez les tendances et changements dans le temps")
    
    # Date range selector
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Date Début", datetime.now() - timedelta(days=180))
    with col2:
        end_date = st.date_input("Date Fin", datetime.now())
    
    # Simuler données temporelles
    dates = pd.date_range(start=start_date, end=end_date, freq='D')
    np.random.seed(42)
    
    df_temporal = pd.DataFrame({
        'date': dates,
        'avg_risk_score': 0.25 + 0.05 * np.sin(np.arange(len(dates)) / 30) + np.random.normal(0, 0.02, len(dates)),
        'predictions_count': np.random.randint(100, 300, len(dates)),
        'high_risk_count': np.random.randint(20, 80, len(dates))
    })
    
    df_temporal['high_risk_pct'] = df_temporal['high_risk_count'] / df_temporal['predictions_count']
    
    # Line chart risk score over time
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=df_temporal['date'],
        y=df_temporal['avg_risk_score'],
        mode='lines',
        name='Risk Score Moyen',
        line=dict(color='#FF6B6B', width=2),
        fill='tonexty'
    ))
    
    fig.add_hline(
        y=df_temporal['avg_risk_score'].mean(),
        line_dash="dash",
        line_color="gray",
        annotation_text=f"Moyenne: {df_temporal['avg_risk_score'].mean():.2%}"
    )
    
    fig.update_layout(
        title="Evolution du Risk Score Moyen",
        xaxis_title="Date",
        yaxis_title="Risk Score",
        height=400
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Volume et high risk
    fig2 = make_subplots(
        rows=2, cols=1,
        subplot_titles=('Volume de Prédictions', '% Prédictions High Risk'),
        vertical_spacing=0.15
    )
    
    fig2.add_trace(
        go.Bar(x=df_temporal['date'], y=df_temporal['predictions_count'], name='Volume'),
        row=1, col=1
    )
    
    fig2.add_trace(
        go.Scatter(x=df_temporal['date'], y=df_temporal['high_risk_pct'],
                  mode='lines', name='% High Risk', line=dict(color='red')),
        row=2, col=1
    )
    
    fig2.update_layout(height=600, showlegend=False)
    st.plotly_chart(fig2, use_container_width=True)
    
    # Statistiques période
    st.markdown("#### Statistiques de la Période")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Risk Moyen", f"{df_temporal['avg_risk_score'].mean():.2%}")
    col2.metric("Risk Max", f"{df_temporal['avg_risk_score'].max():.2%}")
    col3.metric("Total Prédictions", f"{df_temporal['predictions_count'].sum():,}")
    col4.metric("% Jours High Risk", f"{(df_temporal['avg_risk_score'] > 0.27).mean():.1%}")
    
    # Détection anomalies
    st.markdown("#### Détection d'Anomalies")
    threshold = df_temporal['avg_risk_score'].mean() + 2 * df_temporal['avg_risk_score'].std()
    anomalies = df_temporal[df_temporal['avg_risk_score'] > threshold]
    
    if len(anomalies) > 0:
        st.warning(f"⚠️ {len(anomalies)} jour(s) avec risque anormalement élevé détecté(s)")
        st.dataframe(anomalies[['date', 'avg_risk_score', 'high_risk_count']], use_container_width=True)
    else:
        st.success("✅ Aucune anomalie détectée dans la période")

with tab3:
    st.markdown("### Comparaison Carriers vs Airports")
    st.markdown("Comparez les performances entre carriers et airports")
    
    # Simuler données
    carriers = ['AA', 'UA', 'DL', 'WN', 'B6', 'AS', 'NK', 'F9']
    airports = ['ATL', 'ORD', 'DFW', 'LAX', 'JFK', 'DEN', 'SFO', 'SEA']
    
    np.random.seed(42)
    carrier_data = pd.DataFrame({
        'carrier': carriers,
        'avg_risk': np.random.uniform(0.15, 0.35, len(carriers)),
        'total_routes': np.random.randint(50, 200, len(carriers)),
        'high_risk_routes': np.random.randint(10, 60, len(carriers))
    })
    carrier_data['high_risk_pct'] = carrier_data['high_risk_routes'] / carrier_data['total_routes']
    
    airport_data = pd.DataFrame({
        'airport': airports,
        'avg_risk': np.random.uniform(0.15, 0.35, len(airports)),
        'total_routes': np.random.randint(80, 250, len(airports)),
        'high_risk_routes': np.random.randint(15, 70, len(airports))
    })
    airport_data['high_risk_pct'] = airport_data['high_risk_routes'] / airport_data['total_routes']
    
    # Comparaison side-by-side
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### Top/Bottom Carriers par Risk Score")
        
        carrier_sorted = carrier_data.sort_values('avg_risk', ascending=False)
        
        fig = go.Figure()
        
        colors = ['red' if x > 0.25 else 'orange' if x > 0.20 else 'green' 
                  for x in carrier_sorted['avg_risk']]
        
        fig.add_trace(go.Bar(
            y=carrier_sorted['carrier'],
            x=carrier_sorted['avg_risk'],
            orientation='h',
            marker_color=colors,
            text=[f"{x:.1%}" for x in carrier_sorted['avg_risk']],
            textposition='auto'
        ))
        
        fig.update_layout(
            title="Risk Score Moyen par Carrier",
            xaxis_title="Risk Score",
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.markdown("#### Top/Bottom Airports par Risk Score")
        
        airport_sorted = airport_data.sort_values('avg_risk', ascending=False)
        
        fig = go.Figure()
        
        colors = ['red' if x > 0.25 else 'orange' if x > 0.20 else 'green' 
                  for x in airport_sorted['avg_risk']]
        
        fig.add_trace(go.Bar(
            y=airport_sorted['airport'],
            x=airport_sorted['avg_risk'],
            orientation='h',
            marker_color=colors,
            text=[f"{x:.1%}" for x in airport_sorted['avg_risk']],
            textposition='auto'
        ))
        
        fig.update_layout(
            title="Risk Score Moyen par Airport",
            xaxis_title="Risk Score",
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    # Scatter plot: risk vs volume
    st.markdown("#### Risk Score vs Volume de Routes")
    
    # Combiner carriers et airports
    combined = pd.concat([
        carrier_data.assign(type='Carrier').rename(columns={'carrier': 'entity'}),
        airport_data.assign(type='Airport').rename(columns={'airport': 'entity'})
    ])
    
    fig = px.scatter(
        combined,
        x='total_routes',
        y='avg_risk',
        size='high_risk_routes',
        color='type',
        hover_data=['entity'],
        title="Correlation entre Volume et Risk Score",
        labels={
            'total_routes': 'Nombre de Routes',
            'avg_risk': 'Risk Score Moyen'
        }
    )
    
    fig.add_hline(y=0.25, line_dash="dash", line_color="red",
                 annotation_text="Seuil High Risk (25%)")
    
    fig.update_layout(height=500)
    st.plotly_chart(fig, use_container_width=True)
    
    # Heatmap carrier vs airport
    st.markdown("#### Heatmap Carrier × Airport Risk")
    
    # Créer matrice
    matrix = np.random.uniform(0.1, 0.4, (len(carriers[:5]), len(airports[:5])))
    
    fig = go.Figure(data=go.Heatmap(
        z=matrix,
        x=airports[:5],
        y=carriers[:5],
        colorscale='RdYlGn_r',
        text=[[f"{val:.1%}" for val in row] for row in matrix],
        texttemplate="%{text}",
        textfont={"size": 10}
    ))
    
    fig.update_layout(
        title="Risk Score par Paire Carrier-Airport",
        xaxis_title="Airport",
        yaxis_title="Carrier",
        height=400
    )
    
    st.plotly_chart(fig, use_container_width=True)

# Footer
st.markdown("---")
st.caption("📈 Comparative Analysis | 🔬 Model Comparison | ✈️ Carrier vs Airport")
