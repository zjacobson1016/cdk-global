from databricks_mcp import DatabricksMCPClient
from databricks.sdk import WorkspaceClient
import os
# from databricks.sdk.credentials_provider import ModelServingUserCredentials

# Replace with your deployed app URL
mcp_server_url = "https://mcp-ai-dev-kit-7474644652812129.aws.databricksapps.com/mcp"

workspace_client = WorkspaceClient(profile='group-demo')

mcp_client = DatabricksMCPClient(server_url=mcp_server_url, workspace_client=workspace_client)

# List available tools
tools = mcp_client.list_tools()
print(f"Available tools: {tools}")