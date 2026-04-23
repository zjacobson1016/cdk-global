import json
import logging
import os
from typing import Optional

from databricks.sdk import WorkspaceClient
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langgraph.store.base import BaseStore
from mlflow.types.responses import ResponsesAgentRequest


def _is_lakebase_hostname(value: str) -> bool:
    """Check if the value looks like a Lakebase hostname rather than an instance name."""
    # Hostname pattern: instance-{uuid}.database.{env}.cloud.databricks.com
    return ".database." in value and value.endswith(".com")


def resolve_lakebase_instance_name(
    instance_name: str, workspace_client: Optional[WorkspaceClient] = None
) -> str:
    """
    Resolve a Lakebase instance name from a hostname if needed.

    If the input is a hostname (e.g., from Databricks Apps value_from resolution),
    this will resolve it to the actual instance name by listing database instances.

    Args:
        instance_name: Either an instance name or a hostname
        workspace_client: Optional WorkspaceClient to use for resolution

    Returns:
        The resolved instance name

    Raises:
        ValueError: If the hostname cannot be resolved to an instance name
    """
    if not _is_lakebase_hostname(instance_name):
        # Input is already an instance name
        return instance_name

    # Input is a hostname - resolve to instance name
    client = workspace_client or WorkspaceClient()
    hostname = instance_name

    try:
        instances = list(client.database.list_database_instances())
    except Exception as exc:
        raise ValueError(
            f"Unable to list database instances to resolve hostname '{hostname}'. "
            "Ensure you have access to database instances."
        ) from exc

    # Find the instance that matches this hostname
    for instance in instances:
        rw_dns = getattr(instance, "read_write_dns", None)
        ro_dns = getattr(instance, "read_only_dns", None)

        if hostname in (rw_dns, ro_dns):
            resolved_name = getattr(instance, "name", None)
            if not resolved_name:
                raise ValueError(
                    f"Found matching instance for hostname '{hostname}' "
                    "but instance name is not available."
                )
            logging.info(f"Resolved Lakebase hostname '{hostname}' to instance name '{resolved_name}'")
            return resolved_name

    raise ValueError(
        f"Unable to find database instance matching hostname '{hostname}'. "
        "Ensure the hostname is correct and the instance exists."
    )


def get_user_id(request: ResponsesAgentRequest) -> Optional[str]:
    custom_inputs = dict(request.custom_inputs or {})
    if "user_id" in custom_inputs:
        return custom_inputs["user_id"]
    if request.context and getattr(request.context, "user_id", None):
        return request.context.user_id
    return None


def _is_databricks_app_env() -> bool:
    """Check if running in a Databricks App environment."""
    return bool(os.getenv("DATABRICKS_APP_NAME"))


def get_lakebase_access_error_message(lakebase_instance_name: str) -> str:
    """Generate a helpful error message for Lakebase access issues."""
    if _is_databricks_app_env():
        app_name = os.getenv("DATABRICKS_APP_NAME")
        return (
            f"Failed to connect to Lakebase instance '{lakebase_instance_name}'. "
            f"The App Service Principal for '{app_name}' may not have access.\n\n"
            "To fix this:\n"
            "1. Go to the Databricks UI and navigate to your app\n"
            "2. Click 'Edit' → 'App resources' → 'Add resource'\n"
            "3. Add your Lakebase instance as a resource\n"
            "4. Grant the necessary permissions on your Lakebase instance. "
            "See the README section 'Grant Lakebase permissions to your App's Service Principal' for the SQL commands."
        )
    else:
        return (
            f"Failed to connect to Lakebase instance '{lakebase_instance_name}'. "
            "Please verify:\n"
            "1. The instance name is correct\n"
            "2. You have the necessary permissions to access the instance\n"
            "3. Your Databricks authentication is configured correctly"
        )


def _get_store(config: RunnableConfig) -> Optional[BaseStore]:
    return config.get("configurable", {}).get("store")


def _get_user_id_from_config(config: RunnableConfig) -> Optional[str]:
    return config.get("configurable", {}).get("user_id")


def memory_tools():
    # ------------------------------------------------------------------
    # Semantic memory tools (user-scoped rules, preferences, patterns)
    # ------------------------------------------------------------------
    @tool
    async def search_semantic_memory(query: str, config: RunnableConfig) -> str:
        """Search for rules, preferences, and patterns in the user's semantic memory."""
        user_id = _get_user_id_from_config(config)
        if not user_id:
            return "Memory not available - no user_id provided."
        store = _get_store(config)
        if not store:
            return "Memory not available - store not configured."

        namespace = ("memory_semantic", user_id.replace(".", "-"))
        results = await store.asearch(namespace, query=query, limit=5)

        # Also search org-level semantic memory
        org_results = await store.asearch(("memory_semantic", "org"), query=query, limit=3)

        all_items = []
        for item in results:
            all_items.append(f"- [user/{item.key}]: {json.dumps(item.value)}")
        for item in org_results:
            all_items.append(f"- [org/{item.key}]: {json.dumps(item.value)}")

        if not all_items:
            return "No semantic memories found."

        return f"Found {len(all_items)} semantic memories:\n" + "\n".join(all_items)

    @tool
    async def save_semantic_memory(memory_key: str, memory_data_json: str, config: RunnableConfig) -> str:
        """Save a rule, preference, or pattern to the user's semantic memory."""
        user_id = _get_user_id_from_config(config)
        if not user_id:
            return "Cannot save memory - no user_id provided."
        store = _get_store(config)
        if not store:
            return "Cannot save memory - store not configured."

        namespace = ("memory_semantic", user_id.replace(".", "-"))
        try:
            memory_data = json.loads(memory_data_json)
            if not isinstance(memory_data, dict):
                return f"Failed: memory_data must be a JSON object, not {type(memory_data).__name__}"
            await store.aput(namespace, memory_key, memory_data)
            return f"Successfully saved semantic memory '{memory_key}'."
        except json.JSONDecodeError as e:
            return f"Failed to save memory: Invalid JSON - {e}"

    @tool
    async def delete_semantic_memory(memory_key: str, config: RunnableConfig) -> str:
        """Delete a specific entry from the user's semantic memory."""
        user_id = _get_user_id_from_config(config)
        if not user_id:
            return "Cannot delete memory - no user_id provided."
        store = _get_store(config)
        if not store:
            return "Cannot delete memory - store not configured."

        namespace = ("memory_semantic", user_id.replace(".", "-"))
        await store.adelete(namespace, memory_key)
        return f"Successfully deleted semantic memory '{memory_key}'."

    # ------------------------------------------------------------------
    # Knowledge tools (org-scoped documents and reference data)
    # ------------------------------------------------------------------
    @tool
    async def search_knowledge(query: str, config: RunnableConfig) -> str:
        """Search enterprise knowledge base for documents, policies, and reference data."""
        store = _get_store(config)
        if not store:
            return "Knowledge not available - store not configured."

        results = await store.asearch(("knowledge", "org"), query=query, limit=5)

        if not results:
            return "No knowledge documents found for this query."

        items = []
        for item in results:
            title = item.value.get("title", item.key)
            content = item.value.get("content", "")
            items.append(f"- **{title}**: {content}")

        return f"Found {len(results)} knowledge documents:\n" + "\n".join(items)

    # ------------------------------------------------------------------
    # Episodic memory tools (trajectories and feedback)
    # ------------------------------------------------------------------
    @tool
    async def search_episodic_memory(query: str, config: RunnableConfig) -> str:
        """Search past interaction trajectories and feedback from episodic memory."""
        user_id = _get_user_id_from_config(config)
        store = _get_store(config)
        if not store:
            return "Episodic memory not available - store not configured."

        all_items = []

        # Org-level episodic
        org_results = await store.asearch(("memory_episodic", "org"), query=query, limit=3)
        for item in org_results:
            all_items.append(f"- [org/{item.key}]: {json.dumps(item.value)}")

        # User-level episodic
        if user_id:
            user_results = await store.asearch(
                ("memory_episodic", user_id.replace(".", "-")), query=query, limit=3
            )
            for item in user_results:
                all_items.append(f"- [user/{item.key}]: {json.dumps(item.value)}")

        if not all_items:
            return "No episodic memories found."

        return f"Found {len(all_items)} episodic memories:\n" + "\n".join(all_items)

    return [
        search_semantic_memory,
        save_semantic_memory,
        delete_semantic_memory,
        search_knowledge,
        search_episodic_memory,
    ]
