"""Builds agent State(Context) from Lakebase persistent stores.

Reads from four namespaced stores — Skills, Knowledge, Episodic Memory,
and Semantic Memory — then assembles the context dict that is injected
into the agent state before each LLM call.
"""

import json
import logging
from datetime import datetime
from typing import Any, Optional

from langgraph.store.base import BaseStore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Namespace constants
# ---------------------------------------------------------------------------
NS_SKILLS = ("skills", "org")
NS_KNOWLEDGE = ("knowledge", "org")
NS_EPISODIC_ORG = ("memory_episodic", "org")
NS_SEMANTIC_ORG = ("memory_semantic", "org")


def _ns_episodic_user(user_id: str) -> tuple[str, str]:
    return ("memory_episodic", user_id.replace(".", "-"))


def _ns_semantic_user(user_id: str) -> tuple[str, str]:
    return ("memory_semantic", user_id.replace(".", "-"))


# ---------------------------------------------------------------------------
# Context builder
# ---------------------------------------------------------------------------
async def build_context(
    store: BaseStore,
    user_id: Optional[str],
    user_query: str,
    *,
    skill_limit: int = 10,
    knowledge_limit: int = 5,
    memory_limit: int = 5,
) -> dict[str, Any]:
    """Assemble the full context dict from all Lakebase persistent stores.

    Returns ``{"instructions", "retrieved_docs", "memories"}`` ready for
    injection into the agent state / system prompt.
    """

    # 1. Instructions — load all active skills (not query-dependent)
    instructions = await _load_skills(store, limit=skill_limit)

    # 2. Retrieved documents — semantic search over Knowledge
    retrieved_docs = await _search_knowledge(store, user_query, limit=knowledge_limit)

    # 3. Relevant memories — search Episodic + Semantic (org & user)
    memories = await _search_memories(store, user_id, user_query, limit=memory_limit)

    return {
        "instructions": instructions,
        "retrieved_docs": retrieved_docs,
        "memories": memories,
    }


async def _load_skills(store: BaseStore, *, limit: int = 10) -> str:
    """Load all active skill entries and concatenate their prompts."""
    try:
        items = await store.asearch(NS_SKILLS, query="", limit=limit)
    except Exception:
        logger.warning("Failed to load skills from Lakebase — using empty instructions")
        return ""

    if not items:
        return ""

    parts: list[str] = []
    for item in items:
        val = item.value
        name = val.get("name", item.key)
        prompt = val.get("system_prompt", "")
        if prompt:
            parts.append(f"### {name}\n{prompt}")
    return "\n\n".join(parts)


async def _search_knowledge(
    store: BaseStore, query: str, *, limit: int = 5
) -> list[dict[str, Any]]:
    """Semantic search over the org-level Knowledge store."""
    if not query:
        return []
    try:
        items = await store.asearch(NS_KNOWLEDGE, query=query, limit=limit)
    except Exception:
        logger.warning("Failed to search knowledge store")
        return []

    return [
        {
            "key": item.key,
            "title": item.value.get("title", item.key),
            "content": item.value.get("content", ""),
            "category": item.value.get("category", "general"),
        }
        for item in items
    ]


async def _search_memories(
    store: BaseStore,
    user_id: Optional[str],
    query: str,
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Search Episodic + Semantic memory at both org and user level."""
    if not query:
        return []

    results: list[dict[str, Any]] = []

    namespaces = [
        ("episodic_org", NS_EPISODIC_ORG),
        ("semantic_org", NS_SEMANTIC_ORG),
    ]
    if user_id:
        namespaces.extend([
            ("episodic_user", _ns_episodic_user(user_id)),
            ("semantic_user", _ns_semantic_user(user_id)),
        ])

    for label, ns in namespaces:
        try:
            items = await store.asearch(ns, query=query, limit=limit)
            for item in items:
                results.append({
                    "source": label,
                    "key": item.key,
                    "value": item.value,
                })
        except Exception:
            logger.warning("Failed to search %s namespace", label)

    return results


# ---------------------------------------------------------------------------
# Build dynamic system prompt
# ---------------------------------------------------------------------------
def build_system_prompt(
    instructions: str,
    retrieved_docs: list[dict[str, Any]],
    memories: list[dict[str, Any]],
) -> str:
    """Assemble the full system prompt from context components."""

    sections: list[str] = []

    # Base behavioural rules (always present)
    sections.append(
        "You are a helpful assistant with access to persistent memory "
        "and enterprise knowledge. Use the available tools to answer questions."
    )

    # Skills / Instructions
    if instructions:
        sections.append(f"## Instructions\n{instructions}")

    # Retrieved documents
    if retrieved_docs:
        doc_lines = []
        for doc in retrieved_docs:
            doc_lines.append(f"- **{doc['title']}**: {doc['content']}")
        sections.append("## Retrieved Documents\n" + "\n".join(doc_lines))

    # Relevant memories
    if memories:
        mem_lines = []
        for mem in memories:
            mem_lines.append(f"- [{mem['source']}] {mem['key']}: {json.dumps(mem['value'])}")
        sections.append("## Relevant Memories\n" + "\n".join(mem_lines))

    # Memory management guidance
    sections.append(
        "## Memory Tools\n"
        "You have tools to manage persistent memory:\n"
        "- **search_semantic_memory** — find rules, preferences, and patterns\n"
        "- **save_semantic_memory** — persist new rules or user preferences\n"
        "- **delete_semantic_memory** — remove outdated memories\n"
        "- **search_knowledge** — look up enterprise documents and reference data\n"
        "- **search_episodic_memory** — find past interaction trajectories and feedback\n\n"
        "Proactively save semantic memories when the user shares durable preferences, "
        "roles, constraints, or explicit 'remember this' requests."
    )

    return "\n\n".join(sections)


# ---------------------------------------------------------------------------
# Trajectory write-back (continuous improvement)
# ---------------------------------------------------------------------------
async def write_episodic_trajectory(
    store: BaseStore,
    user_id: Optional[str],
    thread_id: str,
    summary: str,
    *,
    feedback: Optional[str] = None,
) -> None:
    """Write a conversation trajectory back to the episodic store."""
    value: dict[str, Any] = {
        "thread_id": thread_id,
        "summary": summary,
        "timestamp": datetime.now().isoformat(),
    }
    if feedback:
        value["feedback"] = feedback

    key = f"trajectory_{thread_id}"

    if user_id:
        ns = _ns_episodic_user(user_id)
    else:
        ns = NS_EPISODIC_ORG

    try:
        await store.aput(ns, key, value)
        logger.info("Wrote episodic trajectory %s", key)
    except Exception:
        logger.warning("Failed to write episodic trajectory %s", key, exc_info=True)
