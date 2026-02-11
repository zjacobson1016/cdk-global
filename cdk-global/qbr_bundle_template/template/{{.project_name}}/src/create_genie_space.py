import os
import requests
import json
from dotenv import load_dotenv
load_dotenv()
from pathlib import Path
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)
assert os.getenv("DATABRICKS_HOST")   # e.g. https://abc.cloud.databricks.com
assert os.getenv("DATABRICKS_TOKEN")    # PAT or configured token
assert os.getenv("DATABRICKS_WAREHOUSE_ID") # warehouse to attach
DATABRICKS_TOKEN = os.getenv("DATABRICKS_TOKEN")
DATABRICKS_HOST = os.getenv("DATABRICKS_HOST")
WAREHOUSE_ID = os.getenv("DATABRICKS_WAREHOUSE_ID")
HEADERS = {"Authorization": f"Bearer {DATABRICKS_TOKEN}"}
GENIE_SPACE_NAME = os.getenv("GENIE_SPACE_NAME")
def find_genie_space_by_name(title: str) -> str | None:
    """
    Find a Genie Space ID by its title/name.
    
    Args:
        title: The title/name of the Genie Space to find
        
    Returns:
        The space_id if found, None otherwise
    """
    url = f"{DATABRICKS_HOST}/api/2.0/genie/spaces"
    params = {}
    
    # Handle pagination if there are many spaces
    while True:
        resp = requests.get(url, headers=HEADERS, params=params)
        resp.raise_for_status()
        data = resp.json()
        
        # Search through spaces in current page
        spaces = data.get("spaces", [])
        for space in spaces:
            if space.get("title") == title:
                return space.get("space_id")
        
        # Check if there's another page
        next_page_token = data.get("next_page_token")
        if not next_page_token:
            break
        params["page_token"] = next_page_token
    
    # Not found
    return None

def get_genie_space(space_id: str) -> dict:
    url = f"{DATABRICKS_HOST}/api/2.0/genie/spaces/{space_id}"
    params = {"include_serialized_space": "true"}
    resp = requests.get(url, headers=HEADERS, params=params)
    resp.raise_for_status()
    return resp.json()

def create_genie_space(serialized_space: str,
                       parent_path: str,
                       warehouse_id: str,
                       title: str | None = None,
                       description: str | None = None) -> dict:
    url = f"{DATABRICKS_HOST}/api/2.0/genie/spaces"
    payload = {
        "serialized_space": serialized_space,
        "parent_path": parent_path,
        "warehouse_id": warehouse_id,
    }
    if title:
        payload["title"] = title
    if description:
        payload["description"] = description

    resp = requests.post(url, headers=HEADERS, json=payload)
    resp.raise_for_status()
    return resp.json()

# Example usage:
if __name__ == "__main__":
    print(f"Environment file: {env_path}")
    serialized_space_file = Path(__file__).resolve().parent / "serialized_space.json"
    
    # 1) Find a space by name
    space_name = GENIE_SPACE_NAME
    found_space_id = find_genie_space_by_name(space_name)
    
    if found_space_id:
        # Space exists - get its details
        print(f"✅ Found Genie Space '{space_name}' with ID: {found_space_id}")
        
        example_space = get_genie_space(found_space_id)
        print(f"\nExisting space details:")
        print(f"  Title: {example_space.get('title')}")
        print(f"  Space ID: {example_space.get('space_id')}")
        print(f"  Description: {example_space.get('description')}")
        print("\nSerialized space:\n", example_space.get("serialized_space", ""))
        
        # Write serialized_space to file for reference
        with open(serialized_space_file, "w") as f:
            json.dump(example_space.get("serialized_space", ""), f, indent=2)
        print(f"\n✅ Serialized space written to: {serialized_space_file}")
    else:
        # Space doesn't exist - create it from serialized_space.json
        print(f"❌ Genie Space '{space_name}' not found")
        print(f"📦 Creating new Genie Space from {serialized_space_file}...")
        
        # Read serialized_space from file
        if not serialized_space_file.exists():
            print(f"❌ Error: {serialized_space_file} not found. Cannot create space.")
            exit(1)
        
        with open(serialized_space_file, "r") as f:
            serialized_space_from_file = json.load(f)
        
        # Create the new space
        new_space = create_genie_space(
            serialized_space=serialized_space_from_file,
            parent_path="/Workspace/Users/zach.jacobson@databricks.com/",
            warehouse_id=WAREHOUSE_ID,
            title=space_name,
            description="Fraud Detection Genie Space - Created via API",
        )
        print(f"\n✅ Created new Genie Space:")
        print(f"  Title: {new_space.get('title')}")
        print(f"  Space ID: {new_space.get('space_id')}")
        print(f"  Description: {new_space.get('description')}")
