# Databricks notebook source
# MAGIC %md
# MAGIC # Lender approval – HPO training with Optuna & MLflow (MLOps advanced)
# MAGIC Feature lookups + optional feature function, create_training_set, preprocessors, Optuna HPO, fe.log_model, register to UC.

# COMMAND ----------

dbutils.widgets.text("catalog", "mfg_mc_se_sa", "Catalog")
dbutils.widgets.text("schema", "cdk", "Schema")
catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")

# COMMAND ----------

# MAGIC %run ./_setup_lender

# COMMAND ----------

from databricks.feature_store import FeatureLookup, FeatureFunction
from databricks.feature_engineering import FeatureEngineeringClient
from pyspark.sql.functions import col, last, max

fe = FeatureEngineeringClient()

feature_lookups_n_functions = [
    FeatureLookup(
        table_name=f"{catalog}.{db}.{feature_table_name}",
        lookup_key=["application_id"],
        timestamp_lookup_key="transaction_ts",
    ),
    FeatureFunction(
        udf_name=f"{catalog}.{db}.affordability_ratio",
        input_bindings={"income_in": "income", "loan_amount_in": "loan_amount"},
        output_name="affordability_ratio",
    ),
    # Deterministic rule: pay-stub income within 70-150% of self-reported
    FeatureFunction(
        udf_name=f"{catalog}.{db}.income_validation",
        input_bindings={"income_in": "income", "verified_period_income_in": "verified_period_income"},
        output_name="income_validated",
    ),
    # Deterministic rule: photo ID must not be expired
    FeatureFunction(
        udf_name=f"{catalog}.{db}.id_expiration_check",
        input_bindings={"id_expiration_date_in": "id_expiration_date"},
        output_name="id_not_expired",
    ),
]

labels_df = spark.read.table(f"{catalog}.{db}.{label_table_name}")
latest_df = labels_df.groupBy("application_id").agg(
    max("transaction_ts").alias("transaction_ts"),
    last("approved").alias(label_col),
    last("split").alias("split"),
)

training_set_specs = fe.create_training_set(
    df=latest_df,
    label=label_col,
    feature_lookups=feature_lookups_n_functions,
    exclude_columns=["application_id", "transaction_ts", "split"],
    exclude_null_labels=True,
)

# COMMAND ----------

import pandas as pd

training_pdf = training_set_specs.load_df().filter("split == 'train'").drop("split").toPandas()
test_pdf = training_set_specs.load_df().filter("split == 'test'").drop("split").toPandas()

X_train = training_pdf.drop(label_col, axis=1)
Y_train = training_pdf[label_col]
X_test = test_pdf.drop(label_col, axis=1)
Y_test = test_pdf[label_col]

# COMMAND ----------

from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler
from sklearn.preprocessing import OneHotEncoder as SklearnOneHotEncoder

num_cols = ["income", "credit_score", "employment_years", "debt_to_income", "loan_amount", "affordability_ratio", "income_validated", "id_not_expired"]
cat_cols = ["loan_purpose"]

num_pipeline = Pipeline(steps=[
    ("converter", FunctionTransformer(lambda df: df.apply(pd.to_numeric, errors="coerce"))),
    ("imputer", SimpleImputer(strategy="median")),
    ("scaler", StandardScaler()),
])
cat_pipeline = Pipeline(steps=[
    ("imputer", SimpleImputer(strategy="constant", fill_value="other")),
    ("onehot", SklearnOneHotEncoder(handle_unknown="ignore")),
])
preprocessor = ColumnTransformer(
    [("num", num_pipeline, num_cols), ("cat", cat_pipeline, cat_cols)],
    remainder="drop",
)

# COMMAND ----------

import optuna
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from sklearn.model_selection import train_test_split
from lightgbm import LGBMClassifier

class ObjectiveOptuna:
    def __init__(self, X_train_in, Y_train_in, preprocessor_in, rng_seed=42, pos_label_in=1):
        self.preprocessor = preprocessor_in
        self.rng_seed = rng_seed
        self.pos_label = pos_label_in
        X_t, X_v, Y_t, Y_v = train_test_split(X_train_in, Y_train_in, test_size=0.1, random_state=rng_seed)
        self.X_train, self.Y_train = X_t, Y_t
        self.X_val, self.Y_val = X_v, Y_v

    def __call__(self, trial):
        classifier_name = trial.suggest_categorical("classifier", ["LogisticRegression", "RandomForest", "LightGBM"])
        if classifier_name == "LogisticRegression":
            classifier_obj = LogisticRegression(
                C=trial.suggest_float("C", 1e-2, 1, log=True),
                random_state=self.rng_seed,
            )
        elif classifier_name == "RandomForest":
            classifier_obj = RandomForestClassifier(
                n_estimators=trial.suggest_int("n_estimators", 10, 150),
                max_depth=trial.suggest_int("max_depth", 3, 10),
                random_state=self.rng_seed,
            )
        else:
            classifier_obj = LGBMClassifier(
                force_row_wise=True, verbose=-1,
                n_estimators=trial.suggest_int("n_estimators", 10, 150),
                max_depth=trial.suggest_int("max_depth", 3, 10),
                learning_rate=trial.suggest_float("learning_rate", 1e-2, 0.3),
                random_state=self.rng_seed,
            )
        from sklearn.pipeline import Pipeline
        model = Pipeline(steps=[("preprocessor", self.preprocessor), ("classifier", classifier_obj)])
        model.fit(self.X_train, self.Y_train)
        y_pred = model.predict(self.X_val)
        return f1_score(self.Y_val, y_pred, average="binary", pos_label=self.pos_label)
# COMMAND ----------

import mlflow
from mlflow.optuna.storage import MlflowStorage
from mlflow.pyspark.optuna.study import MlflowSparkStudy
from mlflow.tracking.client import MlflowClient

mlflow.set_registry_uri("databricks-uc")
try:
    exp = mlflow.get_experiment_by_name(experiment_name)
    experiment_id = exp.experiment_id
except Exception:
    experiment_id = mlflow.create_experiment(name=experiment_name, tags={"lender_approval_mlops": "advanced"})

mlflow.set_experiment(experiment_name)
mlflow_storage = MlflowStorage(experiment_id=experiment_id)

class NoneValuePruner(optuna.pruners.BasePruner):
    def prune(self, study, trial):
        return trial.value is None

objective_fn = ObjectiveOptuna(X_train, Y_train, preprocessor, pos_label_in=pos_label)
optuna_sampler = optuna.samplers.TPESampler(seed=42)

mlflow_optuna_study = MlflowSparkStudy(
    pruner=NoneValuePruner(),
    sampler=optuna_sampler,
    study_name="lender_approval_hpo",
    storage=mlflow_storage,
)
mlflow_optuna_study._directions = ["maximize"]
mlflow_optuna_study.optimize(objective_fn, n_trials=12, n_jobs=2)

# COMMAND ----------

best_params = mlflow_optuna_study.best_params.copy()
best_params["random_state"] = 42
clf_type = best_params.pop("classifier")
if clf_type == "LogisticRegression":
    best_clf = LogisticRegression(**best_params)
elif clf_type == "RandomForest":
    best_clf = RandomForestClassifier(**best_params)
else:
    best_clf = LGBMClassifier(force_row_wise=True, verbose=-1, **best_params)

from sklearn.pipeline import Pipeline as SkPipeline
model_pipeline = SkPipeline(steps=[("preprocessor", preprocessor), ("classifier", best_clf)])
model_pipeline.fit(X_train, Y_train)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Custom pyfunc wrapper – ML prediction + deterministic business rules
# MAGIC The wrapper runs the sklearn pipeline, then applies two hard rules that
# MAGIC can override the model's prediction. Every response includes a
# MAGIC `decision_reason` so callers can see *why* a decision was made.

# COMMAND ----------

import mlflow
import numpy as np

class LenderApprovalWithRules(mlflow.pyfunc.PythonModel):
    """Wraps the sklearn pipeline with deterministic business rules.

    Returns structured predictions:
      prediction       – final decision (0/1) after rules
      ml_prediction    – raw ML model prediction (0/1)
      ml_probability   – ML model's P(approved)
      income_check     – PASS / FAIL / MISSING
      id_check         – PASS / FAIL / MISSING
      decision_reason  – human-readable explanation
    """

    def __init__(self, pipeline=None):
        self.pipeline = pipeline

    def predict(self, context, model_input, params=None):
        import pandas as _pd

        ml_pred = self.pipeline.predict(model_input)
        try:
            ml_proba = self.pipeline.predict_proba(model_input)[:, 1]
        except (AttributeError, IndexError):
            ml_proba = np.full(len(ml_pred), np.nan)

        # Rule inputs (computed by Feature Functions before predict is called)
        income_val = (
            model_input["income_validated"]
            if "income_validated" in model_input.columns
            else _pd.Series([-1] * len(model_input))
        ).fillna(-1).astype(int)

        id_val = (
            model_input["id_not_expired"]
            if "id_not_expired" in model_input.columns
            else _pd.Series([-1] * len(model_input))
        ).fillna(-1).astype(int)

        rows = []
        for i in range(len(model_input)):
            ml_p = int(ml_pred[i])
            prob = round(float(ml_proba[i]), 4) if not np.isnan(ml_proba[i]) else None
            inc = int(income_val.iloc[i])
            id_v = int(id_val.iloc[i])

            inc_s = "PASS" if inc == 1 else ("FAIL" if inc == 0 else "MISSING")
            id_s  = "PASS" if id_v == 1 else ("FAIL" if id_v == 0 else "MISSING")

            # ── Deterministic override logic ──
            overrides = []
            if inc == 0:
                overrides.append("Income mismatch (pay stub vs application)")
            if id_v == 0:
                overrides.append("Expired photo ID")

            if overrides:
                final = 0
                reason = "DENIED by rules: " + " + ".join(overrides)
            elif ml_p == 1:
                final = 1
                reason = (
                    "APPROVED by ML model (all checks passed)"
                    if inc_s != "MISSING" and id_s != "MISSING"
                    else "APPROVED by ML model (pending doc verification)"
                )
            else:
                final = 0
                reason = "DENIED by ML model"

            rows.append({
                "prediction": final,
                "ml_prediction": ml_p,
                "ml_probability": prob,
                "income_check": inc_s,
                "id_check": id_s,
                "decision_reason": reason,
            })

        return _pd.DataFrame(rows)

# COMMAND ----------

wrapped_model = LenderApprovalWithRules(pipeline=model_pipeline)

# Quick local sanity check
_sample = X_test.head(3)
print("Sample predictions with reasoning:")
print(wrapped_model.predict(context=None, model_input=_sample).to_string(index=False))

# COMMAND ----------

import mlflow.sklearn

mlflow.sklearn.autolog(log_input_examples=True, log_models=False, silent=True)
with mlflow.start_run(run_name="lender_approval_hpo_best") as run:
    test_f1 = f1_score(Y_test, model_pipeline.predict(X_test), average="binary", pos_label=pos_label)
    mlflow.log_metric("test_f1_score", test_f1)
    fe.log_model(
        model=wrapped_model,
        artifact_path="model",
        flavor=mlflow.pyfunc,
        training_set=training_set_specs,
    )
    run_id = run.info.run_id

print(f"Logged wrapped model with rules. Run ID: {run_id}. Register in 03b as Challenger.")
