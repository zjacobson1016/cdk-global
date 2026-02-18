# Databricks notebook source
# MAGIC %md
# MAGIC # Get Deployment Job ID
# MAGIC Looks up the deployment job created by `03a_create_deployment_job` by name
# MAGIC and passes its ID to downstream tasks via task values.

# COMMAND ----------

from databricks.sdk import WorkspaceClient

w = WorkspaceClient()

deployment_job_name = "Lender-Approval-Model-Deployment-Job"

existing_jobs = w.jobs.list(name=deployment_job_name)
job_id = None
for job in existing_jobs:
    if job.settings.name == deployment_job_name:
        job_id = job.job_id
        break

if job_id is None:
    raise ValueError(f"Deployment job '{deployment_job_name}' not found. Ensure 03a_create_deployment_job has been run.")

print(f"Found deployment job '{deployment_job_name}' with ID: {job_id}")
dbutils.jobs.taskValues.set(key="deployment_job_id", value=job_id)
