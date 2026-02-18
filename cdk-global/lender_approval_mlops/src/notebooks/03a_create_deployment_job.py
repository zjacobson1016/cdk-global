# Databricks notebook source
# MAGIC %md
# MAGIC # Create MLflow 3.0 Model Deployment Job – Lender Approval
# MAGIC Creates (or updates) a Databricks Job templated as an MLflow 3.0 Deployment Job
# MAGIC for the **lender approval** model. The job has three tasks:
# MAGIC
# MAGIC | Task | Notebook | Purpose |
# MAGIC |------|----------|---------|
# MAGIC | **Evaluation** | `04a_challenger_validation` | Validate the Challenger model against the Champion |
# MAGIC | **Approval_Check** | `04b_challenger_approval` | Check UC approval tag; promote if approved |
# MAGIC | **Deployment** | `06_serve_features_and_model` | Deploy features to Online Store & model to Serving endpoint |
# MAGIC
# MAGIC After creation the job is linked to the UC Model so it appears in the Model UI.
# MAGIC
# MAGIC Adapted from the MLflow 3.0 Deployment Job template
# MAGIC ([AWS](https://docs.databricks.com/aws/mlflow/deployment-job#example-template-notebooks) |
# MAGIC [Azure](https://learn.microsoft.com/azure/databricks/mlflow/deployment-job#example-template-notebooks) |
# MAGIC [GCP](https://docs.databricks.com/gcp/mlflow/deployment-job#example-template-notebooks)).

# COMMAND ----------

# MAGIC %run ./_setup_lender

# COMMAND ----------

# MAGIC %md
# MAGIC ## Configuration

# COMMAND ----------

import os

current_directory = os.getcwd()
print(f"Current directory: {current_directory}")

# COMMAND ----------

# Model registered by 03b_from_notebook_to_models_in_uc
# model_name is already set by _setup_lender: {catalog}.{db}.lender_approval_model
model_version = "1"
job_name = "Lender-Approval-Model-Deployment-Job"

# Notebook paths for each task (relative to this notebook's directory)
evaluation_notebook_path = f"{current_directory}/04a_challenger_validation"
approval_notebook_path = f"{current_directory}/04b_challenger_approval"
deployment_notebook_path = f"{current_directory}/06_serve_features_and_model"

# COMMAND ----------

# MAGIC %md
# MAGIC ## Create / Update Lakeflow Deployment Job

# COMMAND ----------

from databricks.sdk import WorkspaceClient
from databricks.sdk.service import jobs
from databricks.sdk.service.compute import Environment

# Serverless environment — install deps from requirements.txt via pip -r
requirements_ws_path = f"{current_directory}/../requirements.txt"

serverless_env = jobs.JobEnvironment(
    environment_key="default",
    spec=Environment(client="4", dependencies=[f"-r {requirements_ws_path}"]),
)

job_settings = jobs.JobSettings(
    name=job_name,
    environments=[serverless_env],
    tasks=[
        jobs.Task(
            task_key="Evaluation",
            notebook_task=jobs.NotebookTask(notebook_path=evaluation_notebook_path),
            environment_key="default",
            max_retries=0,
        ),
        jobs.Task(
            task_key="Approval_Check",
            notebook_task=jobs.NotebookTask(
                notebook_path=approval_notebook_path,
                base_parameters={"approval_tag_name": "{{task.name}}"},
            ),
            depends_on=[jobs.TaskDependency(task_key="Evaluation")],
            environment_key="default",
            max_retries=0,
        ),
        jobs.Task(
            task_key="Deployment",
            notebook_task=jobs.NotebookTask(
                notebook_path=deployment_notebook_path,
                base_parameters={"smoke_test": "False"},
            ),
            depends_on=[jobs.TaskDependency(task_key="Approval_Check")],
            environment_key="default",
            max_retries=0,
        ),
    ],
    parameters=[
        jobs.JobParameter(name="model_name", default=model_name),
        jobs.JobParameter(name="model_version", default=model_version),
    ],
    queue=jobs.QueueSettings(enabled=True),
    max_concurrent_runs=1,
)

# COMMAND ----------

w = WorkspaceClient()
current_user = w.current_user.me().user_name

# Search for existing job by name (idempotent create-or-update)
existing_jobs = w.jobs.list(name=job_name)
job_id = None
for created_job in existing_jobs:
    if created_job.settings.name == job_name and created_job.creator_user_name == current_user:
        job_id = created_job.job_id
        break

if job_id:
    print(f"Updating existing job ({job_id})...")
    w.jobs.update(job_id=job_id, new_settings=job_settings)
else:
    print("Creating new deployment job...")
    created_job = w.jobs.create(**job_settings.__dict__)
    job_id = created_job.job_id

print(f"Deployment Job ID: {job_id}")

# Set task value so downstream tasks (e.g. run_job_task) can reference the ID
dbutils.jobs.taskValues.set(key="deployment_job_id", value=job_id)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Link Deployment Job to UC Model
# MAGIC Programmatically connect the job so it appears in the Unity Catalog Model UI.

# COMMAND ----------

import mlflow
from mlflow.tracking.client import MlflowClient


client = MlflowClient(registry_uri="databricks-uc")

try:
    model_info = client.get_registered_model(model_name)
    if model_info:
        if model_info.deployment_job_id == job_id:
            print(f"Model '{model_name}' already linked to job {job_id} — no change needed.")
        else:
            print(f"Updating model '{model_name}' deployment job to {job_id}...")
            client.update_registered_model(model_name, deployment_job_id="")       # unlink current
            client.update_registered_model(model_name, deployment_job_id=job_id)   # link new

except mlflow.exceptions.RestException as e:
    if "PERMISSION_DENIED" in str(e):
        print(f"Permission denied on model '{model_name}' — Deployment Job NOT linked.")
    else:
        print(f"Model '{model_name}' does not exist — creating placeholder and linking job...")
        client.create_registered_model(model_name, deployment_job_id=job_id)

# COMMAND ----------

print(f"Done. Deployment job '{job_name}' (ID: {job_id}) is linked to UC model '{model_name}'.")
print(f"\nDocumentation:")
print(f"  AWS:   https://docs.databricks.com/aws/mlflow/deployment-job#connect")
print(f"  Azure: https://learn.microsoft.com/azure/databricks/mlflow/deployment-job#connect")
print(f"  GCP:   https://docs.databricks.com/gcp/mlflow/deployment-job#connect")
