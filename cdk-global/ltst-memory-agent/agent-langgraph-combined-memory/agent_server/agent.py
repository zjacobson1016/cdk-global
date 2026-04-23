import logging
import os
from datetime import datetime
from typing import Any, AsyncGenerator, Optional, Sequence, TypedDict

import mlflow
from databricks.sdk import WorkspaceClient
from databricks_langchain import (
    AsyncCheckpointSaver,
    AsyncDatabricksStore,
    ChatDatabricks,
    DatabricksMCPServer,
    DatabricksMultiServerMCPClient,
)
from fastapi import HTTPException
from langchain.agents import create_agent
from langchain_core.messages import AnyMessage
from langchain_core.tools import tool
from langgraph.graph.message import add_messages
from langgraph.store.base import BaseStore
from mlflow.genai.agent_server import invoke, stream
from mlflow.types.responses import (
    ResponsesAgentRequest,
    ResponsesAgentResponse,
    ResponsesAgentStreamEvent,
    to_chat_completions_input,
)
from typing_extensions import Annotated

from agent_server.context_builder import (
    build_context,
    build_system_prompt,
    write_episodic_trajectory,
)
from agent_server.utils import (
    get_databricks_host_from_env,
    get_lakebase_access_error_message,
    get_or_create_thread_id,
    get_user_workspace_client,
    process_agent_astream_events,
)
from agent_server.utils_memory import (
    get_user_id,
    memory_tools,
    resolve_lakebase_instance_name,
)

logger = logging.getLogger(__name__)
logging.getLogger("mlflow.utils.autologging_utils").setLevel(logging.ERROR)
logging.getLogger("LiteLLM").setLevel(logging.WARNING)
mlflow.langchain.autolog()
sp_workspace_client = WorkspaceClient()


@tool
def get_current_time() -> str:
    """Get the current date and time."""
    return datetime.now().isoformat()


############################################
# Configuration
############################################
LLM_ENDPOINT_NAME = os.getenv("LLM_ENDPOINT_NAME", "databricks-claude-sonnet-4-5")
_LAKEBASE_INSTANCE_NAME_RAW = os.getenv("LAKEBASE_INSTANCE_NAME") or None
EMBEDDING_ENDPOINT = "databricks-gte-large-en"
EMBEDDING_DIMS = 1024
LAKEBASE_AUTOSCALING_PROJECT = os.getenv("LAKEBASE_AUTOSCALING_PROJECT") or None
LAKEBASE_AUTOSCALING_BRANCH = os.getenv("LAKEBASE_AUTOSCALING_BRANCH") or None

############################################

_has_autoscaling = LAKEBASE_AUTOSCALING_PROJECT and LAKEBASE_AUTOSCALING_BRANCH
if not _LAKEBASE_INSTANCE_NAME_RAW and not _has_autoscaling:
    raise ValueError(
        "Lakebase configuration is required but not set. "
        "Please set one of the following in your environment:\n"
        "  Option 1 (provisioned): LAKEBASE_INSTANCE_NAME=<your-instance-name>\n"
        "  Option 2 (autoscaling): LAKEBASE_AUTOSCALING_PROJECT=<project> and LAKEBASE_AUTOSCALING_BRANCH=<branch>\n"
    )

LAKEBASE_INSTANCE_NAME = resolve_lakebase_instance_name(_LAKEBASE_INSTANCE_NAME_RAW) if _LAKEBASE_INSTANCE_NAME_RAW else None


class StatefulAgentState(TypedDict, total=False):
    """State schema that enables short-term (checkpoint) memory."""
    messages: Annotated[Sequence[AnyMessage], add_messages]
    custom_inputs: dict[str, Any]
    custom_outputs: dict[str, Any]
    context: dict[str, Any]


def init_mcp_client(workspace_client: WorkspaceClient) -> DatabricksMultiServerMCPClient:
    host_name = get_databricks_host_from_env()
    return DatabricksMultiServerMCPClient(
        [
            DatabricksMCPServer(
                name="system-ai",
                url=f"{host_name}/api/2.0/mcp/functions/system/ai",
                workspace_client=workspace_client,
            ),
        ]
    )


async def init_agent(
    store: BaseStore,
    system_prompt: str,
    workspace_client: Optional[WorkspaceClient] = None,
    checkpointer: Optional[Any] = None,
):
    tools = [get_current_time] + memory_tools()

    return create_agent(
        model=ChatDatabricks(endpoint=LLM_ENDPOINT_NAME),
        tools=tools,
        system_prompt=system_prompt,
        store=store,
        checkpointer=checkpointer,
        state_schema=StatefulAgentState,
    )


@invoke()
async def invoke_handler(request: ResponsesAgentRequest) -> ResponsesAgentResponse:
    thread_id = get_or_create_thread_id(request)
    request.custom_inputs = dict(request.custom_inputs or {})
    request.custom_inputs["thread_id"] = thread_id

    outputs = [
        event.item
        async for event in stream_handler(request)
        if event.type == "response.output_item.done"
    ]

    user_id = get_user_id(request)
    custom_outputs: dict[str, Any] = {"thread_id": thread_id}
    if user_id:
        custom_outputs["user_id"] = user_id
    return ResponsesAgentResponse(output=outputs, custom_outputs=custom_outputs)


@stream()
async def stream_handler(
    request: ResponsesAgentRequest,
) -> AsyncGenerator[ResponsesAgentStreamEvent, None]:
    thread_id = get_or_create_thread_id(request)
    mlflow.update_current_trace(metadata={"mlflow.trace.session": thread_id})

    user_id = get_user_id(request)
    if not user_id:
        logger.warning("No user_id provided - long-term memory features will not be available")

    messages = to_chat_completions_input([i.model_dump() for i in request.input])
    user_query = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            user_query = msg.get("content", "")
            break

    input_state: dict[str, Any] = {
        "messages": messages,
        "custom_inputs": dict(request.custom_inputs or {}),
    }

    try:
        async with AsyncCheckpointSaver(
            instance_name=LAKEBASE_INSTANCE_NAME,
            project=LAKEBASE_AUTOSCALING_PROJECT,
            branch=LAKEBASE_AUTOSCALING_BRANCH,
        ) as checkpointer:
            await checkpointer.setup()

            async with AsyncDatabricksStore(
                instance_name=LAKEBASE_INSTANCE_NAME,
                project=LAKEBASE_AUTOSCALING_PROJECT,
                branch=LAKEBASE_AUTOSCALING_BRANCH,
                embedding_endpoint=EMBEDDING_ENDPOINT,
                embedding_dims=EMBEDDING_DIMS,
            ) as store:
                await store.setup()

                # Build context from Lakebase persistent stores
                ctx = await build_context(store, user_id, user_query)
                input_state["context"] = ctx

                # Dynamic system prompt from Skills + context
                system_prompt = build_system_prompt(
                    instructions=ctx["instructions"],
                    retrieved_docs=ctx["retrieved_docs"],
                    memories=ctx["memories"],
                )

                config: dict[str, Any] = {
                    "configurable": {
                        "thread_id": thread_id,
                        "store": store,
                    }
                }
                if user_id:
                    config["configurable"]["user_id"] = user_id

                agent = await init_agent(
                    workspace_client=sp_workspace_client,
                    store=store,
                    system_prompt=system_prompt,
                    checkpointer=checkpointer,
                )
                async for event in process_agent_astream_events(
                    agent.astream(
                        input_state,
                        config,
                        stream_mode=["updates", "messages"],
                    )
                ):
                    yield event

                # Post-interaction: write episodic trajectory for continuous improvement
                await write_episodic_trajectory(
                    store=store,
                    user_id=user_id,
                    thread_id=thread_id,
                    summary=f"User query: {user_query[:200]}",
                )
    except Exception as e:
        error_msg = str(e).lower()
        if any(keyword in error_msg for keyword in ["lakebase", "pg_hba", "postgres", "database instance"]):
            logger.error(f"Lakebase access error: {e}")
            lakebase_desc = LAKEBASE_INSTANCE_NAME or f"{LAKEBASE_AUTOSCALING_PROJECT}/{LAKEBASE_AUTOSCALING_BRANCH}"
            raise HTTPException(
                status_code=503, detail=get_lakebase_access_error_message(lakebase_desc)
            ) from e
        raise
