"""Deploy the Invoice Processing Agent to a Model Serving endpoint."""
import sys
from databricks import agents

model_name = sys.argv[1] if len(sys.argv) > 1 else "home_zach_jacobson.models.parts_invoice_agent"
version = sys.argv[2] if len(sys.argv) > 2 else "1"

print(f"Deploying {model_name} version {version}...")

deployment = agents.deploy(
    model_name,
    version,
    tags={"source": "mcp", "use_case": "parts_invoice_processing", "customer": "cdk"},
)

print(f"Deployment complete!")
print(f"Endpoint: {deployment.endpoint_name}")
print(f"Endpoint URL: {deployment.endpoint_url}")
