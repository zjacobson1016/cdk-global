
# COMMAND ----------

# MAGIC %md
# MAGIC ## Machine Learning - Lead Time Prediction Model
# MAGIC 
# MAGIC Train a linear regression model to predict lead_time based on quote features.
# MAGIC Model is logged to MLflow and registered in Unity Catalog.

# COMMAND ----------

# COMMAND ----------
def train_lead_time_model():
    """
    Train a linear regression model to predict lead_time from bronze_automated_quotes.
    Uses MLflow for experiment tracking and Unity Catalog for model registry.
    
    Features used:
    - quantity: Number of units quoted
    - unit_price: Unit price of the product
    - total_price: Total price of the quote
    - priority: Quote priority (encoded)
    - status: Quote status (encoded)
    - product_id: Product identifier (encoded)
    
    Returns:
        MLflow run information and model metrics
    """
    import mlflow
    import mlflow.sklearn
    from sklearn.linear_model import LinearRegression
    from sklearn.model_selection import train_test_split
    from sklearn.preprocessing import LabelEncoder
    from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
    import pandas as pd
    import numpy as np
    
    # Set MLflow experiment
    import os
    from dotenv import load_dotenv
    env_path = "/Workspace/Users/zach.jacobson@databricks.com/.bundle/zach-demo-qbr/dev/files/.env"
    load_dotenv(dotenv_path=env_path, override=True)
    #env_path = "/Workspace/Users/zach.jacobson@databricks.com/.bundle/zach-demo-qbr/dev/files/.env"
    #load_dotenv(dotenv_path=env_path, override=True)
    experiment_name = f"/Users/{spark.sql('SELECT current_user()').collect()[0][0]}/quote_lead_time_prediction"
    mlflow.set_experiment(experiment_name)
    # catalog = os.getenv("CATALOG_NAME")
    # schema = os.getenv("SCHEMA_NAME")
    catalog = os.getenv("CATALOG_NAME")
    schema = os.getenv("SCHEMA_NAME")
    # Read data from bronze_automated_quotes table
    quotes_df = spark.table(f"{catalog}.{schema}.bronze_automated_quotes").toPandas()
    
    print(f"📊 Loaded {len(quotes_df)} quotes for training")
    print(f"📋 Columns: {quotes_df.columns.tolist()}")
    
    # Feature engineering and preparation
    df = quotes_df.copy()
    
    # Drop rows with missing target values
    df = df.dropna(subset=['lead_time'])
    
    # Select and prepare features
    feature_columns = ['quantity', 'unit_price', 'total_price', 'priority', 'status', 'product_id']
    
    # Remove rows with missing feature values
    df = df.dropna(subset=feature_columns)
    
    print(f"📊 Training dataset size after cleaning: {len(df)} rows")
    
    # Encode categorical variables
    le_priority = LabelEncoder()
    le_status = LabelEncoder()
    le_product = LabelEncoder()
    
    df['priority_encoded'] = le_priority.fit_transform(df['priority'])
    df['status_encoded'] = le_status.fit_transform(df['status'])
    df['product_encoded'] = le_product.fit_transform(df['product_id'])
    
    # Prepare feature matrix and target
    X = df[['quantity', 'unit_price', 'total_price', 'priority_encoded', 'status_encoded', 'product_encoded']]
    y = df['lead_time']
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    
    print(f"✅ Training set: {len(X_train)} rows")
    print(f"✅ Test set: {len(X_test)} rows")
    
    # Start MLflow run
    with mlflow.start_run(run_name="lead_time_linear_regression") as run:
        
        # Train the model
        model = LinearRegression()
        model.fit(X_train, y_train)
        
        # Make predictions
        y_pred_train = model.predict(X_train)
        y_pred_test = model.predict(X_test)
        
        # Calculate metrics
        train_rmse = np.sqrt(mean_squared_error(y_train, y_pred_train))
        test_rmse = np.sqrt(mean_squared_error(y_test, y_pred_test))
        train_mae = mean_absolute_error(y_train, y_pred_train)
        test_mae = mean_absolute_error(y_test, y_pred_test)
        train_r2 = r2_score(y_train, y_pred_train)
        test_r2 = r2_score(y_test, y_pred_test)
        
        # Log parameters
        mlflow.log_param("model_type", "LinearRegression")
        mlflow.log_param("features", feature_columns)
        mlflow.log_param("n_features", len(feature_columns))
        mlflow.log_param("train_size", len(X_train))
        mlflow.log_param("test_size", len(X_test))
        mlflow.log_param("random_state", 42)
        
        # Log metrics
        mlflow.log_metric("train_rmse", train_rmse)
        mlflow.log_metric("test_rmse", test_rmse)
        mlflow.log_metric("train_mae", train_mae)
        mlflow.log_metric("test_mae", test_mae)
        mlflow.log_metric("train_r2", train_r2)
        mlflow.log_metric("test_r2", test_r2)
        
        # Log feature importance (coefficients)
        feature_importance = pd.DataFrame({
            'feature': ['quantity', 'unit_price', 'total_price', 'priority', 'status', 'product_id'],
            'coefficient': model.coef_
        }).sort_values('coefficient', ascending=False)
        
        print("\n📊 Feature Importance (Coefficients):")
        print(feature_importance)
        
        # Log model with signature
        from mlflow.models.signature import infer_signature
        signature = infer_signature(X_train, y_pred_train)
        
        # Log the model
        mlflow.sklearn.log_model(
            model,
            artifact_path="model",
            signature=signature,
            registered_model_name=f"{catalog}.{schema}.lead_time_predictor"
        )
        
        
        print("\n✅ Model Training Complete!")
        print(f"📊 Test RMSE: {test_rmse:.2f} days")
        print(f"📊 Test MAE: {test_mae:.2f} days")
        print(f"📊 Test R²: {test_r2:.4f}")
        print(f"🔗 Run ID: {run.info.run_id}")
        print(f"🎯 Model registered as: {catalog}.{schema}.lead_time_predictor")
        
        # Create a summary table
        metrics_summary = {
            "metric": ["RMSE", "MAE", "R²"],
            "train": [train_rmse, train_mae, train_r2],
            "test": [test_rmse, test_mae, test_r2]
        }
        
        return {
            "run_id": run.info.run_id,
            "model_uri": f"models:/{catalog}.{schema}.lead_time_predictor/1",
            "metrics": metrics_summary,
            "feature_importance": feature_importance.to_dict()
        }
train_lead_time_model()

# COMMAND ----------

def predict_lead_time(quantity, unit_price, total_price, priority, status, product_id):
    """
    Use the trained model to predict lead time for a new quote.
    
    Args:
        quantity: Number of units
        unit_price: Unit price of the product
        total_price: Total price of quote
        priority: Quote priority (High, Medium, Low)
        status: Quote status (Pending, Approved, Denied)
        product_id: Product identifier
        
    Returns:
        Predicted lead time in days
    """
    import mlflow
    import pandas as pd
    
    # Load the latest model from Unity Catalog
    model_name = f"{catalog}.{schema}.lead_time_predictor"
    model = mlflow.sklearn.load_model(f"models:/{model_name}/latest")
    
    # Note: In production, you would also load the encoders and apply them
    # For now, this is a template showing the prediction structure
    
    print(f"✅ Model loaded: {model_name}")
    print(f"📊 Predicting lead time...")
    
    # In a real scenario, you'd encode the categorical variables here
    # using the saved encoders before prediction
    
    return None 

# COMMAND ----------

# MAGIC %md
# MAGIC ## Usage Instructions
# MAGIC 
# MAGIC To train the model, run:
# MAGIC ```python
# MAGIC result = train_lead_time_model()
# MAGIC print(result)
# MAGIC ```
# MAGIC 
# MAGIC To make predictions:
# MAGIC ```python
# MAGIC predicted_lead_time = predict_lead_time(
# MAGIC     quantity=5,
# MAGIC     unit_price=3250.00,
# MAGIC     total_price=16250.00,
# MAGIC     priority="High",
# MAGIC     status="Pending",
# MAGIC     product_id="3051S-CP"
# MAGIC )
# MAGIC ```

# Uncomment to train the model automatically when pipeline runs:
# train_lead_time_model()