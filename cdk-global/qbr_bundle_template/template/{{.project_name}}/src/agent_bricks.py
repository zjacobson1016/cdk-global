from databricks.sdk import WorkspaceClient
from openai import OpenAI
import os


# Get Databricks token from environment variable
# How to get your Databricks token: https://docs.databricks.com/en/dev-tools/auth/pat.html
DATABRICKS_TOKEN = os.getenv("DATABRICKS_TOKEN")
if not DATABRICKS_TOKEN:
    raise ValueError("DATABRICKS_TOKEN environment variable is not set")

# Alternatively in a Databricks notebook you can use this:
# DATABRICKS_TOKEN = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get()

endpoint = "ka-e698d7b0-endpoint"
w = WorkspaceClient(host="https://e2-demo-field-eng.cloud.databricks.com", token=DATABRICKS_TOKEN)

client = OpenAI(
    api_key=DATABRICKS_TOKEN,
    base_url="https://e2-demo-field-eng.cloud.databricks.com/serving-endpoints"
)

response = client.responses.create(
    model="ka-e698d7b0-endpoint",
    input=[
        {
            "role": "user",
            "content": "What is the weight of the rosemount 3051S pressure transmitter?"
        }
    ]
)

print(response.output[0].content[0].text)