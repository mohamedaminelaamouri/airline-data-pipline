from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from ml_api.utils.clickhouse_client import query_df

app = FastAPI(title="ML Dashboard API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/stats/summary")
def summary_stats():
    sql = """
    SELECT
        count() AS total_predictions,
        countIf(risk_category = 'critical') AS critical_risk_routes,
        countIf(risk_category = 'high') AS high_risk_routes,
        countIf(risk_category = 'medium') AS medium_risk_routes,
        countIf(risk_category = 'low') AS low_risk_routes,
        countDistinct(carrier) AS carriers_analyzed,
        countDistinct(origin_airport) AS airports_analyzed,
        avg(predicted_delay_rate) AS avg_predicted_delay,
        avg(risk_score) AS avg_risk_score
    FROM ml_predictions
    """
    df = query_df(sql)
    if df.empty:
        return {
            "total_predictions": 0,
            "critical_risk_routes": 0,
            "high_risk_routes": 0,
            "medium_risk_routes": 0,
            "low_risk_routes": 0,
            "carriers_analyzed": 0,
            "airports_analyzed": 0,
            "avg_predicted_delay": 0,
            "avg_risk_score": 0,
            "high_risk_percentage": 0,
            "critical_risk_percentage": 0,
        }
    row = df.iloc[0].to_dict()
    total = float(row.get("total_predictions") or 0)
    high = float(row.get("high_risk_routes") or 0)
    critical = float(row.get("critical_risk_routes") or 0)
    row["high_risk_percentage"] = (high / total * 100) if total else 0
    row["critical_risk_percentage"] = (critical / total * 100) if total else 0
    return row


@app.get("/predictions")
def predictions(
    carrier: Optional[str] = Query(default=None),
    airport: Optional[str] = Query(default=None),
    risk_category: Optional[str] = Query(default=None),
    month: Optional[int] = Query(default=None),
):
    where = []
    params = {}
    if carrier:
        where.append("carrier = %(carrier)s")
        params["carrier"] = carrier
    if airport:
        where.append("origin_airport = %(airport)s")
        params["airport"] = airport
    if risk_category:
        where.append("risk_category = %(risk_category)s")
        params["risk_category"] = risk_category
    if month:
        where.append("month = %(month)s")
        params["month"] = int(month)

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    sql = f"""
    SELECT
        carrier,
        origin_airport,
        year,
        month,
        predicted_delay_rate,
        risk_score,
        risk_category,
        arr_flights,
        model_version,
        confidence
    FROM ml_predictions
    {where_sql}
    ORDER BY year, month
    LIMIT 5000
    """
    df = query_df(sql, parameters=params)
    return df.to_dict(orient="records")


@app.get("/explainability/global")
def explainability_global():
    features_sql = """
    SELECT
        top_feature_1,
        AVG(top_feature_1_importance) AS avg_importance_1,
        top_feature_2,
        AVG(top_feature_2_importance) AS avg_importance_2,
        top_feature_3,
        AVG(top_feature_3_importance) AS avg_importance_3
    FROM ml_predictions
    GROUP BY top_feature_1, top_feature_2, top_feature_3
    LIMIT 1
    """
    features_df = query_df(features_sql)

    risk_sql = """
    SELECT risk_category, count() AS count
    FROM ml_predictions
    GROUP BY risk_category
    """
    risk_df = query_df(risk_sql)

    return {
        "features": features_df.to_dict(orient="records"),
        "risk_distribution": risk_df.to_dict(orient="records"),
    }


@app.get("/explainability/route")
def explainability_route(
    carrier: str = Query(...),
    airport: str = Query(...),
):
    sql = """
    SELECT
        carrier,
        origin_airport,
        year,
        month,
        predicted_delay_rate,
        risk_score,
        risk_category,
        arr_flights,
        model_version,
        top_feature_1,
        top_feature_1_importance,
        top_feature_2,
        top_feature_2_importance,
        top_feature_3,
        top_feature_3_importance
    FROM ml_predictions
    WHERE carrier = %(carrier)s AND origin_airport = %(airport)s
    ORDER BY month
    """
    df = query_df(sql, parameters={"carrier": carrier, "airport": airport})
    return df.to_dict(orient="records")


@app.get("/monitoring")
def monitoring():
    return summary_stats()


@app.get("/metadata")
def metadata():
    carriers_sql = """
    SELECT DISTINCT carrier
    FROM ml_predictions
    ORDER BY carrier
    """
    airports_sql = """
    SELECT DISTINCT origin_airport
    FROM ml_predictions
    ORDER BY origin_airport
    """
    carriers_df = query_df(carriers_sql)
    airports_df = query_df(airports_sql)
    return {
        "carriers": carriers_df["carrier"].dropna().tolist() if not carriers_df.empty else [],
        "airports": airports_df["origin_airport"].dropna().tolist() if not airports_df.empty else [],
    }


@app.get("/stats/monthly")
def monthly_stats():
    sql = """
    SELECT
        month,
        avg(predicted_delay_rate) AS avg_predicted_delay,
        avg(risk_score) AS avg_risk_score,
        sum(arr_flights) AS total_flights
    FROM ml_predictions
    WHERE year = 2026
    GROUP BY month
    ORDER BY month
    """
    df = query_df(sql)
    return df.to_dict(orient="records")


@app.get("/stats/classification")
def classification_stats():
    """
    Statistiques du modèle de classification.
    Expose les métriques ROC-AUC, cutoff, et distribution des risques.
    """
    # Distribution par catégorie de risque
    risk_sql = """
    SELECT 
        risk_category,
        count() as count,
        avg(predicted_delay_rate) as avg_probability,
        avg(risk_score) as avg_risk_score
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
    """
    risk_df = query_df(risk_sql)
    
    # Statistiques globales
    stats_sql = """
    SELECT
        count() as total_predictions,
        countIf(predicted_delay_rate >= 0.47) as above_cutoff,
        avg(predicted_delay_rate) as avg_probability,
        min(predicted_delay_rate) as min_probability,
        max(predicted_delay_rate) as max_probability,
        countDistinct(carrier) as unique_carriers,
        countDistinct(origin_airport) as unique_airports
    FROM ml_predictions
    WHERE year = 2026
    """
    stats_df = query_df(stats_sql)
    
    # Métriques du modèle production (mis à jour)
    model_metrics = {
        "model_type": "XGBoost Classifier",
        "accuracy": 0.790,
        "roc_auc_test": 0.810,
        "precision": 0.718,
        "recall": 0.421,
        "f1_score": 0.530,
        "cutoff": 0.47,
        "target_threshold": 0.20,  # delay_rate > 20% = risque
        "n_features": 20,
        "train_samples": 216019,
    }
    
    stats = stats_df.iloc[0].to_dict() if not stats_df.empty else {}
    total = float(stats.get("total_predictions", 0))
    above = float(stats.get("above_cutoff", 0))
    
    return {
        "model": model_metrics,
        "predictions": {
            "total": int(total),
            "above_cutoff": int(above),
            "above_cutoff_pct": round(above / total * 100, 2) if total > 0 else 0,
            "avg_probability": round(float(stats.get("avg_probability", 0)), 4),
            "unique_carriers": int(stats.get("unique_carriers", 0)),
            "unique_airports": int(stats.get("unique_airports", 0)),
        },
        "risk_distribution": risk_df.to_dict(orient="records"),
    }

