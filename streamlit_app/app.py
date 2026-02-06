"""
Streamlit Dashboard - Pipeline Temps Reel
==========================================
Visualisation du flux NiFi -> Kafka -> ClickHouse
avec les predictions ML integrees.
"""
import streamlit as st
import pandas as pd
import time
from datetime import datetime
import json

# Configuration de la page
st.set_page_config(
    page_title="Airline Delay Pipeline",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS personnalise
st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 10px;
        color: white;
        text-align: center;
    }
    .risk-critical { background-color: #ff4444; color: white; padding: 5px 10px; border-radius: 5px; }
    .risk-high { background-color: #ff8800; color: white; padding: 5px 10px; border-radius: 5px; }
    .risk-medium { background-color: #ffcc00; color: black; padding: 5px 10px; border-radius: 5px; }
    .risk-low { background-color: #00cc66; color: white; padding: 5px 10px; border-radius: 5px; }
    .kafka-message {
        background-color: #1a1a2e;
        color: #00ff88;
        padding: 10px;
        border-radius: 5px;
        font-family: monospace;
        font-size: 12px;
        max-height: 300px;
        overflow-y: auto;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# Fonctions utilitaires
# ============================================================================

def get_clickhouse_client():
    """Connexion a ClickHouse"""
    try:
        import clickhouse_connect
        import os
        return clickhouse_connect.get_client(
            host=os.getenv('CLICKHOUSE_HOST', 'localhost'),
            port=int(os.getenv('CLICKHOUSE_HTTP_PORT', '8123')),
            database='airline_data'
        )
    except Exception as e:
        st.error(f"Erreur connexion ClickHouse: {e}")
        return None

def get_kafka_consumer():
    """Connexion a Kafka"""
    try:
        from kafka import KafkaConsumer
        import os
        return KafkaConsumer(
            'airline-data-enriched',
            bootstrap_servers=os.getenv('KAFKA_BOOTSTRAP', 'localhost:9092'),
            auto_offset_reset='latest',
            enable_auto_commit=True,
            consumer_timeout_ms=1000,
            value_deserializer=lambda x: json.loads(x.decode('utf-8'))
        )
    except Exception as e:
        return None

# ============================================================================
# Sidebar
# ============================================================================

st.sidebar.title("⚙️ Configuration")

# Auto-refresh
auto_refresh = st.sidebar.checkbox("Auto-refresh", value=True)
refresh_interval = st.sidebar.slider("Intervalle (sec)", 3, 30, 5)

# Filtres
st.sidebar.markdown("---")
st.sidebar.subheader("🔍 Filtres")

# Mode
mode = st.sidebar.radio(
    "Vue",
    ["📊 Dashboard Pipeline", "🤖 Predictions ML", "📈 Kafka Messages"]
)

# ============================================================================
# Header
# ============================================================================

st.title("✈️ Airline Delay Pipeline - Temps Reel")
st.markdown(f"*Derniere MAJ: {datetime.now().strftime('%H:%M:%S')}*")

# ============================================================================
# Dashboard Pipeline
# ============================================================================

if mode == "📊 Dashboard Pipeline":
    
    # Connexion ClickHouse
    ch = get_clickhouse_client()
    
    if ch:
        # Metriques principales
        col1, col2, col3, col4 = st.columns(4)
        
        try:
            # Total records
            total = ch.query("SELECT count() FROM gold_ml_features").result_rows[0][0]
            col1.metric("📦 Records ClickHouse", f"{total:,}")
            
            # Predictions
            preds = ch.query("SELECT count() FROM ml_predictions WHERE year = 2026").result_rows[0][0]
            col2.metric("🔮 Predictions 2026", f"{preds:,}")
            
            # High Risk
            high_risk = ch.query("SELECT count() FROM ml_predictions WHERE risk_category IN ('critical', 'high')").result_rows[0][0]
            col3.metric("⚠️ Routes a Risque", f"{high_risk:,}")
            
            # Carriers
            carriers = ch.query("SELECT countDistinct(carrier) FROM gold_ml_features").result_rows[0][0]
            col4.metric("✈️ Compagnies", carriers)
            
        except Exception as e:
            st.error(f"Erreur requete: {e}")
        
        st.markdown("---")
        
        # Distribution des risques
        st.subheader("📊 Distribution des Risques (2026)")
        
        try:
            risk_df = ch.query_df("""
                SELECT risk_category, count() as count
                FROM ml_predictions
                WHERE year = 2026
                GROUP BY risk_category
                ORDER BY 
                    CASE risk_category
                        WHEN 'critical' THEN 1
                        WHEN 'high' THEN 2
                        WHEN 'medium' THEN 3
                        WHEN 'low' THEN 4
                    END
            """)
            
            if not risk_df.empty:
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.bar_chart(risk_df.set_index('risk_category'))
                
                with col2:
                    for _, row in risk_df.iterrows():
                        cat = row['risk_category']
                        count = row['count']
                        color = {
                            'critical': '🔴',
                            'high': '🟠',
                            'medium': '🟡',
                            'low': '🟢'
                        }.get(cat, '⚪')
                        st.write(f"{color} **{cat.upper()}**: {count:,}")
                        
        except Exception as e:
            st.warning(f"Pas de predictions: {e}")
        
        st.markdown("---")
        
        # Top Routes a Risque
        st.subheader("🚨 Top 10 Routes Critiques")
        
        try:
            top_risk = ch.query_df("""
                SELECT 
                    carrier,
                    origin_airport as airport,
                    month,
                    round(predicted_delay_rate * 100, 1) as risk_pct,
                    risk_category
                FROM ml_predictions
                WHERE year = 2026 AND risk_category = 'critical'
                ORDER BY predicted_delay_rate DESC
                LIMIT 10
            """)
            
            if not top_risk.empty:
                st.dataframe(top_risk, use_container_width=True)
            else:
                st.info("Aucune route critique")
                
        except Exception as e:
            st.warning(f"Erreur: {e}")
            
    else:
        st.warning("⚠️ ClickHouse non disponible. Demarrez Docker.")
        st.code("docker-compose up -d clickhouse")

# ============================================================================
# Predictions ML
# ============================================================================

elif mode == "🤖 Predictions ML":
    
    st.subheader("🤖 Predictions du Modele ML")
    
    ch = get_clickhouse_client()
    
    if ch:
        # Filtres
        col1, col2, col3 = st.columns(3)
        
        try:
            carriers = ch.query_df("SELECT DISTINCT carrier FROM ml_predictions ORDER BY carrier")
            airports = ch.query_df("SELECT DISTINCT origin_airport FROM ml_predictions ORDER BY origin_airport LIMIT 50")
            
            with col1:
                carrier_filter = st.selectbox("Compagnie", ["Toutes"] + carriers['carrier'].tolist())
            with col2:
                airport_filter = st.selectbox("Aeroport", ["Tous"] + airports['origin_airport'].tolist())
            with col3:
                risk_filter = st.selectbox("Risque", ["Tous", "critical", "high", "medium", "low"])
                
        except:
            carrier_filter = "Toutes"
            airport_filter = "Tous"
            risk_filter = "Tous"
        
        # Construction de la requete
        where_clauses = ["year = 2026"]
        if carrier_filter != "Toutes":
            where_clauses.append(f"carrier = '{carrier_filter}'")
        if airport_filter != "Tous":
            where_clauses.append(f"origin_airport = '{airport_filter}'")
        if risk_filter != "Tous":
            where_clauses.append(f"risk_category = '{risk_filter}'")
        
        where_sql = " AND ".join(where_clauses)
        
        try:
            df = ch.query_df(f"""
                SELECT 
                    carrier,
                    origin_airport as airport,
                    month,
                    round(predicted_delay_rate * 100, 1) as probability,
                    risk_category,
                    arr_flights
                FROM ml_predictions
                WHERE {where_sql}
                ORDER BY predicted_delay_rate DESC
                LIMIT 100
            """)
            
            st.dataframe(df, use_container_width=True)
            st.caption(f"{len(df)} resultats affiches")
            
        except Exception as e:
            st.error(f"Erreur: {e}")
    else:
        st.warning("⚠️ ClickHouse non disponible")

# ============================================================================
# Kafka Messages
# ============================================================================

elif mode == "📈 Kafka Messages":
    
    st.subheader("📨 Messages Kafka (Temps Reel)")
    
    # Buffer pour les messages
    if 'kafka_messages' not in st.session_state:
        st.session_state.kafka_messages = []
    
    # Placeholder pour les messages
    message_container = st.empty()
    stats_container = st.empty()
    
    # Bouton pour simuler des messages (si Kafka non disponible)
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Simuler Message"):
            import random
            carriers = ['AA', 'DL', 'UA', 'WN', 'B6']
            airports = ['JFK', 'LAX', 'ORD', 'ATL', 'DFW']
            
            msg = {
                "timestamp": datetime.now().isoformat(),
                "carrier": random.choice(carriers),
                "airport": random.choice(airports),
                "arr_flights": random.randint(50, 500),
                "arr_del15": random.randint(5, 100),
                "delay_rate": round(random.uniform(0.1, 0.4), 3)
            }
            st.session_state.kafka_messages.insert(0, msg)
            st.session_state.kafka_messages = st.session_state.kafka_messages[:50]  # Garder 50 max
    
    with col2:
        if st.button("🗑️ Vider Buffer"):
            st.session_state.kafka_messages = []
    
    # Afficher les messages
    if st.session_state.kafka_messages:
        st.markdown("**Derniers Messages:**")
        
        messages_html = '<div class="kafka-message">'
        for msg in st.session_state.kafka_messages[:20]:
            delay_rate = msg.get('delay_rate', 0)
            risk = '🔴' if delay_rate > 0.3 else ('🟠' if delay_rate > 0.2 else '🟢')
            messages_html += f"<div>{risk} [{msg.get('timestamp', '')[-8:]}] {msg.get('carrier', 'N/A')}-{msg.get('airport', 'N/A')} | Flights: {msg.get('arr_flights', 0)} | Delay: {delay_rate*100:.1f}%</div>"
        messages_html += '</div>'
        
        st.markdown(messages_html, unsafe_allow_html=True)
        
        # Stats
        st.markdown("---")
        st.metric("📊 Messages en buffer", len(st.session_state.kafka_messages))
    else:
        st.info("Aucun message. Cliquez sur 'Simuler Message' ou connectez Kafka.")

# ============================================================================
# Footer
# ============================================================================

st.markdown("---")

# Metriques du modele
with st.expander("ℹ️ Informations Modele ML"):
    col1, col2, col3 = st.columns(3)
    col1.metric("Accuracy", "79.0%")
    col2.metric("ROC-AUC", "0.810")
    col3.metric("Cutoff", "0.47")
    
    st.caption("Modele: XGBoost Classifier | 20 features | Entraine sur 318K echantillons")

# Auto-refresh
if auto_refresh:
    time.sleep(refresh_interval)
    st.rerun()
