# Databricks notebook source
# MAGIC %md
# MAGIC # Trigger Deployment Job
# MAGIC Looks up the deployment job created by `03a_create_deployment_job` by name,
# MAGIC triggers it via `run_now`, and polls until completion.

# COMMAND ----------

import time
from databricks.sdk import WorkspaceClient
from databricks.sdk.service import jobs

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

# COMMAND ----------

# MAGIC %md
# MAGIC ## Trigger the deployment job and wait for completion

# COMMAND ----------

run = w.jobs.run_now(job_id=job_id)
print(f"Triggered run {run.run_id} for job '{deployment_job_name}' (ID: {job_id})")
print(f"Run URL: {w.config.host}#job/{job_id}/run/{run.run_id}")

run_result = w.jobs.get_run(run.run_id)
while run_result.state.life_cycle_state in ("PENDING", "RUNNING", "QUEUED"):
    print(f"  Run state: {run_result.state.life_cycle_state}...")
    time.sleep(30)
    run_result = w.jobs.get_run(run.run_id)

if run_result.state.result_state == jobs.RunResultState.SUCCESS:
    print(f"Deployment run {run.run_id} completed successfully.")
else:
    msg = f"Deployment run {run.run_id} finished with state: {run_result.state.result_state}"
    if run_result.state.state_message:
        msg += f" — {run_result.state.state_message}"
    raise RuntimeError(msg)
