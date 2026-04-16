"""Test UC connections proxy endpoint with Airtable.

Reads the connection description, then lists bases and tables/fields.
"""

import json
import requests
from databricks.sdk import WorkspaceClient

PROFILE = "cdk"
CONNECTION = "fortellis_api"

w = WorkspaceClient(profile=PROFILE)
connections = w.connections.list()
for conn in connections:
    print(f"Connection: {conn.name}")
    print(f"Owner: {conn.owner}")
    print(f"Comment: {conn.comment}")
    print(f"Connection Type: {conn.connection_type}")

# 0) Show the connection description from Unity Catalog
conn = w.connections.get(CONNECTION)
print(f"=== Connection: {conn.name} ===")
print(f"Owner: {conn.owner}")
print(f"\n--- Description ---\n")
print(conn.comment or "(no description)")
print(f"\n--- End Description ---\n")


def proxy_get(path: str) -> dict | None:
    resp = requests.get(
        f"{w.config.host}/api/2.0/unity-catalog/connections/{CONNECTION}/proxy/{path.lstrip('/')}",
        headers={**w.config.authenticate(), "Accept-Encoding": "identity"},
    )
    if not resp.ok:
        print(f"  ERROR {resp.status_code}: {resp.text[:300]}")
        return None
    return resp.json()


