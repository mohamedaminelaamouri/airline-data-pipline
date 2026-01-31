// MongoDB Initialization Script for ML Artifacts
// Collections optimized for ML predictions, model registry, and explainability

// Switch to ML database
db = db.getSiblingDB('airline_ml');

// ============================================================================
// Collection 1: ML Predictions (enriched with explainability)
// ============================================================================
db.createCollection('predictions', {
    validator: {
        $jsonSchema: {
            bsonType: "object",
            required: ["prediction", "model_info", "created_at"],
            properties: {
                prediction: {
                    bsonType: "object",
                    required: ["carrier", "airport", "month", "risk_score"],
                    properties: {
                        carrier: { bsonType: "string" },
                        airport: { bsonType: "string" },
                        month: { bsonType: "date" },
                        risk_score: { bsonType: "double", minimum: 0, maximum: 1 },
                        predicted_delay_rate: { bsonType: "double" },
                        confidence_interval: { bsonType: "array" }
                    }
                },
                model_info: {
                    bsonType: "object",
                    required: ["model_id", "trained_at"],
                    properties: {
                        model_id: { bsonType: "string" },
                        trained_at: { bsonType: "date" },
                        roc_auc: { bsonType: "double" },
                        features_used: { bsonType: "array" }
                    }
                },
                explainability: {
                    bsonType: "object",
                    properties: {
                        top_features: { bsonType: "array" },
                        baseline_score: { bsonType: "double" },
                        feature_contributions: { bsonType: "object" }
                    }
                },
                alerts: { bsonType: "array" },
                created_at: { bsonType: "date" }
            }
        }
    }
});

// Indexes for predictions
db.predictions.createIndex({ "prediction.carrier": 1, "prediction.airport": 1 });
db.predictions.createIndex({ "prediction.month": 1 });
db.predictions.createIndex({ "prediction.risk_score": -1 });
db.predictions.createIndex({ "model_info.model_id": 1 });
db.predictions.createIndex({ "created_at": -1 });

// Compound index for common queries
db.predictions.createIndex({ 
    "prediction.month": 1, 
    "prediction.risk_score": -1 
});

// TTL index (auto-delete predictions older than 6 months)
db.predictions.createIndex({ "created_at": 1 }, { expireAfterSeconds: 15552000 });

print("✅ Collection 'predictions' created with indexes");

// ============================================================================
// Collection 2: Model Registry (versioning and metadata)
// ============================================================================
db.createCollection('model_registry', {
    validator: {
        $jsonSchema: {
            bsonType: "object",
            required: ["model_id", "trained_at", "metrics", "status"],
            properties: {
                model_id: { bsonType: "string" },
                version: { bsonType: "string" },
                trained_at: { bsonType: "date" },
                status: { 
                    enum: ["training", "validated", "deployed", "deprecated", "failed"] 
                },
                metrics: {
                    bsonType: "object",
                    required: ["val_roc_auc", "test_roc_auc"],
                    properties: {
                        val_roc_auc: { bsonType: "double" },
                        test_roc_auc: { bsonType: "double" },
                        test_recall: { bsonType: "double" },
                        test_precision: { bsonType: "double" }
                    }
                },
                hyperparameters: { bsonType: "object" },
                feature_importance: { bsonType: "array" },
                artifacts: {
                    bsonType: "object",
                    properties: {
                        model_path: { bsonType: "string" },
                        encoders_path: { bsonType: "string" }
                    }
                },
                dataset_info: {
                    bsonType: "object",
                    properties: {
                        train_size: { bsonType: "int" },
                        val_size: { bsonType: "int" },
                        test_size: { bsonType: "int" },
                        date_range: { bsonType: "object" }
                    }
                }
            }
        }
    }
});

// Indexes for model registry
db.model_registry.createIndex({ "model_id": 1 }, { unique: true });
db.model_registry.createIndex({ "version": 1 });
db.model_registry.createIndex({ "status": 1 });
db.model_registry.createIndex({ "trained_at": -1 });
db.model_registry.createIndex({ "metrics.test_roc_auc": -1 });

print("✅ Collection 'model_registry' created with indexes");

// ============================================================================
// Collection 3: Model Performance Monitoring
// ============================================================================
db.createCollection('model_monitoring', {
    validator: {
        $jsonSchema: {
            bsonType: "object",
            required: ["model_id", "date", "predictions_count"],
            properties: {
                model_id: { bsonType: "string" },
                date: { bsonType: "date" },
                predictions_count: { bsonType: "int" },
                performance: {
                    bsonType: "object",
                    properties: {
                        accuracy: { bsonType: "double" },
                        mae: { bsonType: "double" },
                        rmse: { bsonType: "double" }
                    }
                },
                drift_metrics: {
                    bsonType: "object",
                    properties: {
                        feature_drift: { bsonType: "array" },
                        prediction_drift: { bsonType: "double" },
                        alerts: { bsonType: "array" }
                    }
                }
            }
        }
    }
});

// Indexes for monitoring
db.model_monitoring.createIndex({ "model_id": 1, "date": -1 });
db.model_monitoring.createIndex({ "date": -1 });
db.model_monitoring.createIndex({ "drift_metrics.alerts": 1 });

// TTL index (keep monitoring data for 1 year)
db.model_monitoring.createIndex({ "date": 1 }, { expireAfterSeconds: 31536000 });

print("✅ Collection 'model_monitoring' created with indexes");

// ============================================================================
// Collection 4: Feature Store (reusable engineered features)
// ============================================================================
db.createCollection('feature_store', {
    validator: {
        $jsonSchema: {
            bsonType: "object",
            required: ["carrier", "airport", "month", "features", "created_at"],
            properties: {
                carrier: { bsonType: "string" },
                airport: { bsonType: "string" },
                month: { bsonType: "date" },
                features: {
                    bsonType: "object",
                    properties: {
                        lag_features: { bsonType: "object" },
                        seasonality_features: { bsonType: "object" },
                        aggregation_features: { bsonType: "object" }
                    }
                },
                created_at: { bsonType: "date" }
            }
        }
    }
});

// Indexes for feature store
db.feature_store.createIndex({ "carrier": 1, "airport": 1, "month": 1 }, { unique: true });
db.feature_store.createIndex({ "created_at": -1 });

// TTL index (keep features for 3 months)
db.feature_store.createIndex({ "created_at": 1 }, { expireAfterSeconds: 7776000 });

print("✅ Collection 'feature_store' created with indexes");

// ============================================================================
// Collection 5: API Request Logs (for monitoring)
// ============================================================================
db.createCollection('api_logs', {
    capped: true,
    size: 104857600, // 100MB
    max: 100000
});

db.api_logs.createIndex({ "timestamp": -1 });
db.api_logs.createIndex({ "endpoint": 1, "status_code": 1 });

print("✅ Collection 'api_logs' created (capped collection)");

// ============================================================================
// Initial Data / Test Documents
// ============================================================================

// Insert a sample model
db.model_registry.insertOne({
    model_id: "xgb_v1.0_baseline",
    version: "1.0.0",
    trained_at: new Date(),
    status: "deployed",
    metrics: {
        val_roc_auc: 0.842,
        test_roc_auc: 0.738,
        test_recall: 0.917,
        test_precision: 0.522
    },
    hyperparameters: {
        n_estimators: 600,
        max_depth: 5,
        learning_rate: 0.05
    },
    feature_importance: [],
    artifacts: {
        model_path: "models/ml_runs/xgb_v1.0/model.pkl",
        encoders_path: "models/ml_runs/xgb_v1.0/"
    },
    dataset_info: {
        train_size: 243678,
        val_size: 69622,
        test_size: 34813,
        date_range: {
            start: "2003-01-01",
            end: "2025-12-31"
        }
    }
});

print("✅ Sample model inserted");

// ============================================================================
// Database Stats
// ============================================================================
print("\n📊 Database Summary:");
print("Database: " + db.getName());
print("Collections: " + db.getCollectionNames().length);
print("\nCollection Details:");
db.getCollectionNames().forEach(function(collName) {
    var coll = db.getCollection(collName);
    print("  • " + collName + ": " + coll.countDocuments() + " documents");
});

print("\n✅ MongoDB ML database initialized successfully!");
