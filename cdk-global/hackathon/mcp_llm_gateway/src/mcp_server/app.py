"""
Databricks Foundation Model MCP Gateway

A FastMCP server that exposes all Databricks Foundation Model serving endpoints
as MCP tools. Users can list available models, pick one, and query it.
"""

import logging

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import ChatMessage, ChatMessageRole
from fastmcp import FastMCP
import os
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Complete model catalog — all pay-per-token endpoints from:
# https://docs.databricks.com/aws/en/machine-learning/foundation-model-apis/supported-models
# ---------------------------------------------------------------------------

MODEL_CATALOG: dict[str, dict] = {
    # --- Anthropic Claude ---
    "databricks-claude-opus-4-6": {
        "family": "Anthropic Claude",
        "type": "chat",
        "description": "Most capable hybrid reasoning model with adaptive thinking. 1M token context. Excels at complex reasoning, deep analysis, code generation, research, and multi-step workflows.",
    },
    "databricks-claude-opus-4-5": {
        "family": "Anthropic Claude",
        "type": "chat",
        "description": "Powerful hybrid reasoning model for complex tasks requiring deep analysis and extended thinking. 200K token context. Excels at code generation, research, and agentic workflows.",
    },
    "databricks-claude-opus-4-1": {
        "family": "Anthropic Claude",
        "type": "chat",
        "description": "General purpose hybrid reasoning model. 200K token context, 32K output. Excels at code generation, research, content creation, and multi-step agent workflows.",
    },
    "databricks-claude-sonnet-4-6": {
        "family": "Anthropic Claude",
        "type": "chat",
        "description": "Advanced hybrid reasoning model with instant and extended thinking modes. Ideal for customer-facing agents, production coding, and content generation at scale.",
    },
    "databricks-claude-sonnet-4-5": {
        "family": "Anthropic Claude",
        "type": "chat",
        "description": "Hybrid reasoning model balancing throughput and advanced thinking. Great for agents, coding workflows, and content generation.",
    },
    "databricks-claude-sonnet-4": {
        "family": "Anthropic Claude",
        "type": "chat",
        "description": "Hybrid reasoning model with instant and extended thinking modes. Optimized for code development, content analysis, and agent applications.",
    },
    "databricks-claude-3-7-sonnet": {
        "family": "Anthropic Claude",
        "type": "chat",
        "description": "Hybrid reasoning model with visible reasoning steps in extended thinking mode. Optimized for code generation, math, and instruction following. Retiring April 12, 2026.",
    },
    "databricks-claude-haiku-4-5": {
        "family": "Anthropic Claude",
        "type": "chat",
        "description": "Fastest and most cost-effective Claude model. Near-frontier coding quality with exceptional speed. Ideal for chat assistants, customer service, and rapid prototyping.",
    },
    # --- OpenAI GPT ---
    "databricks-gpt-5-4": {
        "family": "OpenAI GPT",
        "type": "chat",
        "description": "Latest flagship GPT model with enhanced accuracy and scaffolded reasoning. 400K context, 128K output. Multimodal inputs supported.",
    },
    "databricks-gpt-5-3-codex": {
        "family": "OpenAI GPT",
        "type": "chat",
        "description": "Most advanced agentic coding model. Handles complex, long-running tasks involving research, tool use, and execution. 25% faster than GPT-5.2 Codex. Not supported in AI Playground — use Responses API.",
    },
    "databricks-gpt-5-2-codex": {
        "family": "OpenAI GPT",
        "type": "chat",
        "description": "Code-specialized model excelling at code generation, refactoring, debugging, and software engineering. 400K context. Not supported in AI Playground — use Responses API.",
    },
    "databricks-gpt-5-2": {
        "family": "OpenAI GPT",
        "type": "chat",
        "description": "General purpose reasoning model. Higher accuracy and improved token efficiency over GPT-5.1. Excels at structured extraction and multi-step workflows. 400K context.",
    },
    "databricks-gpt-5-1": {
        "family": "OpenAI GPT",
        "type": "chat",
        "description": "General purpose model with Instant and Thinking modes. Automatically adjusts for simple or complex tasks. 400K context, 128K output.",
    },
    "databricks-gpt-5-1-codex-max": {
        "family": "OpenAI GPT",
        "type": "chat",
        "description": "High-performance code-specialized model for complex code generation, large-scale refactoring, and enterprise software engineering. Not supported in AI Playground — use Responses API.",
    },
    "databricks-gpt-5-1-codex-mini": {
        "family": "OpenAI GPT",
        "type": "chat",
        "description": "Cost-optimized code model for code completion, simple refactoring, and everyday coding tasks. Not supported in AI Playground — use Responses API.",
    },
    "databricks-gpt-5": {
        "family": "OpenAI GPT",
        "type": "chat",
        "description": "General purpose reasoning model for coding, chat, reasoning, and agent-driven tasks. 400K context, 128K output. Multimodal inputs supported.",
    },
    "databricks-gpt-5-mini": {
        "family": "OpenAI GPT",
        "type": "chat",
        "description": "Cost-optimized reasoning model. Excels at well-defined tasks requiring reliable reasoning, precise language, and rapid output. 400K context.",
    },
    "databricks-gpt-5-nano": {
        "family": "OpenAI GPT",
        "type": "chat",
        "description": "Smallest GPT model. Excels at high-throughput tasks like instruction-following, classification, and routine business processes. 400K context.",
    },
    # --- OpenAI GPT Open Source ---
    "databricks-gpt-oss-120b": {
        "family": "OpenAI GPT (Open Source)",
        "type": "chat",
        "description": "Flagship open-weight reasoning model with chain-of-thought and adjustable reasoning effort. 128K context. OpenAI's largest open-source model.",
    },
    "databricks-gpt-oss-20b": {
        "family": "OpenAI GPT (Open Source)",
        "type": "chat",
        "description": "Lightweight open-weight reasoning model. 128K context. Excels at real-time copilots and batch inference tasks.",
    },
    # --- Google Gemini ---
    "databricks-gemini-3-1-pro": {
        "family": "Google Gemini",
        "type": "chat",
        "description": "State-of-the-art hybrid reasoning model with 1M token context. Stronger reasoning and document intelligence than Gemini 3 Pro. Excels at complex reasoning and multimodal understanding.",
    },
    "databricks-gemini-3-pro": {
        "family": "Google Gemini",
        "type": "chat",
        "description": "Hybrid reasoning model with 1M token context. Advanced reasoning and multimodal capabilities. Retiring March 26, 2026 — will redirect to Gemini 3.1 Pro.",
    },
    "databricks-gemini-3-flash": {
        "family": "Google Gemini",
        "type": "chat",
        "description": "High-speed, cost-efficient multimodal model. Advanced capabilities for video analysis, data extraction, and visual Q&A in near real-time.",
    },
    "databricks-gemini-3-1-flash-lite": {
        "family": "Google Gemini",
        "type": "chat",
        "description": "Fastest and most cost-efficient Gemini model. Supports multimodal inputs, function calling, and structured output. Optimized for high-throughput deployments.",
    },
    "databricks-gemini-2-5-pro": {
        "family": "Google Gemini",
        "type": "chat",
        "description": "Hybrid reasoning model with Deep Think Mode and 1M token context. Excels at complex reasoning, deep analysis, and multimodal understanding.",
    },
    "databricks-gemini-2-5-flash": {
        "family": "Google Gemini",
        "type": "chat",
        "description": "First fully hybrid reasoning model from Google. 1M token context. Optimized for real-time and high-volume applications like chatbots, data extraction, and document parsing.",
    },
    # --- Google Gemma ---
    "databricks-gemma-3-12b": {
        "family": "Google Gemma",
        "type": "chat",
        "description": "12B parameter multimodal vision-language model. 128K context, 140+ languages. Handles text and image inputs. Optimized for dialogue, text generation, and image understanding.",
    },
    # --- Meta Llama ---
    "databricks-llama-4-maverick": {
        "family": "Meta Llama",
        "type": "chat",
        "description": "First Llama model using mixture-of-experts architecture. Optimized for image and text understanding (currently text-only on Databricks).",
    },
    "databricks-meta-llama-3-3-70b-instruct": {
        "family": "Meta Llama",
        "type": "chat",
        "description": "70B parameter model with 128K context. Multi-language support, optimized for dialogue. Replaced Llama 3.1 70B.",
    },
    "databricks-meta-llama-3-1-405b-instruct": {
        "family": "Meta Llama",
        "type": "chat",
        "description": "Largest openly available LLM (405B). 128K context, 10 languages. Competitive with GPT-4-Turbo. Retiring Feb 15, 2026 for pay-per-token.",
    },
    "databricks-meta-llama-3-1-8b-instruct": {
        "family": "Meta Llama",
        "type": "chat",
        "description": "Compact 8B parameter model with 128K context. Multi-language, optimized for dialogue. Fast and cost-effective.",
    },
    # --- Alibaba Cloud Qwen ---
    "databricks-qwen3-next-80b-a3b-instruct": {
        "family": "Alibaba Qwen",
        "type": "chat",
        "description": "Highly efficient model optimized for instruction-following. Excels at ultra-long contexts, multi-step workflows, RAG, and deterministic outputs at high throughput.",
    },
    # --- Embedding Models ---
    "databricks-qwen3-embedding-0-6b": {
        "family": "Alibaba Qwen",
        "type": "embedding",
        "description": "Compact text embedding model (~600M params). 100+ languages, up to 32K tokens. Configurable dimensionality up to 1024. For retrieval, similarity search, and clustering.",
    },
    "databricks-gte-large-en": {
        "family": "Embedding",
        "type": "embedding",
        "description": "Text embedding model mapping text to 1024-dim vectors. 8192 token window. For retrieval, classification, semantic search. English only, non-normalized.",
    },
    "databricks-bge-large-en": {
        "family": "Embedding",
        "type": "embedding",
        "description": "Text embedding model mapping text to 1024-dim vectors. 512 token window. For retrieval, classification, semantic search. English only, normalized.",
    },
}

CHAT_MODELS = {k: v for k, v in MODEL_CATALOG.items() if v["type"] == "chat"}
EMBEDDING_MODELS = {k: v for k, v in MODEL_CATALOG.items() if v["type"] == "embedding"}

# ---------------------------------------------------------------------------
# FastMCP Server
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "Databricks LLM Gateway",
    instructions=(
        "You are the Databricks Foundation Model Gateway. "
        "You help users list available models, pick one, and query it. "
        "Use `list_models` to show what's available, then `chat` to query a model."
    ),
)


def _get_workspace_client() -> WorkspaceClient:
    return WorkspaceClient(client_id=os.environ.get('DATABRICKS_CLIENT_ID'), client_secret=os.environ.get('DATABRICKS_CLIENT_SECRET'))


@mcp.tool()
def list_models(include_embeddings: bool = False) -> str:
    """List all available Databricks Foundation Models.

    Args:
        include_embeddings: If True, also show embedding models (default: False).
    """
    models = MODEL_CATALOG if include_embeddings else CHAT_MODELS
    by_family: dict[str, list] = {}
    for name, info in models.items():
        by_family.setdefault(info["family"], []).append((name, info))

    lines = ["# Available Databricks Foundation Models\n"]
    for family in sorted(by_family.keys()):
        lines.append(f"\n## {family}\n")
        for name, info in by_family[family]:
            tag = " [embedding]" if info["type"] == "embedding" else ""
            lines.append(f"- **{name}**{tag}\n  {info['description']}\n")

    chat_count = len(CHAT_MODELS)
    embed_count = len(EMBEDDING_MODELS)
    lines.append(f"\n**{chat_count} chat/completion models, {embed_count} embedding models**")
    lines.append('\nUse `chat(model="<endpoint_name>", message="...")` to query a model.')

    return "\n".join(lines)


@mcp.tool()
def get_model_info(model: str) -> str:
    """Get detailed information about a specific Foundation Model.

    Args:
        model: The model endpoint name (e.g. "databricks-claude-sonnet-4-6").
    """
    if model not in MODEL_CATALOG:
        available = ", ".join(sorted(MODEL_CATALOG.keys()))
        return f"Unknown model: `{model}`.\n\nAvailable models:\n{available}"

    info = MODEL_CATALOG[model]
    return (
        f"# {model}\n\n"
        f"**Family:** {info['family']}\n"
        f"**Type:** {info['type']}\n"
        f"**Description:** {info['description']}\n"
    )


@mcp.tool()
def chat(
    message: str,
    model: str = "databricks-claude-sonnet-4-6",
    system_prompt: str | None = None,
    max_tokens: int = 4096,
    temperature: float = 0.7,
) -> str:
    """Send a message to a Databricks Foundation Model and get a response.

    Call `list_models` first to see all available models.

    Args:
        message: The user message to send to the model.
        model: Foundation Model endpoint name. Call `list_models` to see options.
        system_prompt: Optional system prompt to guide the model's behavior.
        max_tokens: Maximum tokens in the response (default 4096).
        temperature: Sampling temperature 0.0-2.0 (default 0.7).
    """
    if model in EMBEDDING_MODELS:
        return (
            f"`{model}` is an embedding model and cannot be used for chat. "
            f"Use a chat model instead — call `list_models` to see options."
        )

    if model not in CHAT_MODELS:
        return (
            f"Unknown model: `{model}`.\n\n"
            f"Call `list_models` to see all available Foundation Models."
        )

    w = _get_workspace_client()
    messages = []
    if system_prompt:
        messages.append(ChatMessage(role=ChatMessageRole.SYSTEM, content=system_prompt))
    messages.append(ChatMessage(role=ChatMessageRole.USER, content=message))

    try:
        response = w.serving_endpoints.query(
            name=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        content = response.choices[0].message.content
        usage = response.usage

        result_lines = [content, "\n---", f"*Model: {model}*"]
        if usage:
            result_lines.append(
                f"*Tokens — prompt: {usage.prompt_tokens}, "
                f"completion: {usage.completion_tokens}, "
                f"total: {usage.total_tokens}*"
            )
        return "\n".join(result_lines)

    except Exception as e:
        logger.error("Error querying model %s: %s", model, e)
        return f"Error querying `{model}`: {e}"


# ---------------------------------------------------------------------------
# ASGI app for uvicorn — Streamable HTTP on /mcp
# ---------------------------------------------------------------------------

app = mcp.http_app(path="/mcp", stateless_http=True)
