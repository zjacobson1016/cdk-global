"""Log the Invoice Processing Agent to MLflow and register in Unity Catalog."""
import mlflow
from agent import AGENT, LLM_ENDPOINT, CATALOG, SCHEMA
from mlflow.models.resources import DatabricksServingEndpoint, DatabricksFunction
from unitycatalog.ai.langchain.toolkit import UnityCatalogTool

mlflow.set_registry_uri("databricks-uc")

# Collect resources for auto authentication passthrough
resources = [DatabricksServingEndpoint(endpoint_name=LLM_ENDPOINT)]

for tool in AGENT.tools:
    if isinstance(tool, UnityCatalogTool):
        resources.append(DatabricksFunction(function_name=tool.uc_function_name))

print(f"Resources: {[str(r) for r in resources]}")

input_example = {
    "input": [{"role": "user", "content": "Show me a summary of all invoices."}]
}

with mlflow.start_run():
    model_info = mlflow.pyfunc.log_model(
        name="agent",
        python_model="agent.py",
        input_example=input_example,
        resources=resources,
        pip_requirements=[
            "mlflow==3.6.0",
            "databricks-langchain",
            "langgraph==0.3.4",
            "pydantic",
            "databricks-agents",
        ],
    )
    print(f"Model URI: {model_info.model_uri}")

# Register to Unity Catalog
model_name = f"{CATALOG}.models.parts_invoice_agent"
uc_model_info = mlflow.register_model(
    model_uri=model_info.model_uri,
    name=model_name,
)
print(f"Registered: {uc_model_info.name} version {uc_model_info.version}")
