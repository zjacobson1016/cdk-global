"""Seed Lakebase persistent stores with sample data.

Populates Skills, Knowledge, Episodic Memory, and Semantic Memory
namespaces so the agent has representative content for demos.

Usage:
    uv run seed-lakebase
    uv run seed-lakebase --clear   # wipe existing entries first
"""

import argparse
import asyncio
import logging
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Namespace constants (must match context_builder.py)
# ---------------------------------------------------------------------------
NS_SKILLS = ("skills", "org")
NS_KNOWLEDGE = ("knowledge", "org")
NS_EPISODIC_ORG = ("memory_episodic", "org")
NS_SEMANTIC_ORG = ("memory_semantic", "org")

SAMPLE_USER_ID = "demo-user"
NS_EPISODIC_USER = ("memory_episodic", SAMPLE_USER_ID)
NS_SEMANTIC_USER = ("memory_semantic", SAMPLE_USER_ID)

# ---------------------------------------------------------------------------
# Skills — loaded from markdown files in data/skills/
# ---------------------------------------------------------------------------
SKILLS_DIR = Path(__file__).resolve().parent.parent / "data" / "skills"


def _load_skills_from_markdown() -> dict[str, dict]:
    """Parse each .md file in the skills directory into a store entry.

    Each file uses YAML front-matter (between ``---`` fences) for metadata
    and the remainder of the file as the system_prompt.
    """
    skills: dict[str, dict] = {}
    if not SKILLS_DIR.is_dir():
        logger.warning("Skills directory not found: %s", SKILLS_DIR)
        return skills

    for md_path in sorted(SKILLS_DIR.glob("*.md")):
        text = md_path.read_text(encoding="utf-8")
        meta, body = _parse_frontmatter(text)
        key = md_path.stem  # filename without extension
        skills[key] = {
            "name": meta.get("name", key),
            "description": meta.get("description", ""),
            "system_prompt": body.strip(),
            "capabilities": meta.get("capabilities", []),
            "is_active": meta.get("is_active", True),
        }
        logger.info("  Loaded skill: %s (%s)", key, md_path.name)

    return skills


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Split a markdown file into YAML front-matter dict and body string."""
    if not text.startswith("---"):
        return {}, text

    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text

    try:
        meta = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        meta = {}

    body = parts[2]
    return meta, body


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

KNOWLEDGE: dict[str, dict] = {
    "company_overview": {
        "title": "Pella Corporation Overview",
        "content": (
            "Pella Corporation is a privately held window and door manufacturer "
            "headquartered in Pella, Iowa. Founded in 1925, Pella operates manufacturing "
            "facilities across the United States and serves residential and commercial "
            "markets. Key product lines include Pella Lifestyle Series, Pella Defender "
            "Series, Pella Reserve, and Pella Impervia (fiberglass). Pella employs "
            "approximately 10,000 associates and distributes through a network of "
            "Pella showrooms and authorized dealers."
        ),
        "category": "company_info",
        "content_type": "structured",
    },
    "return_policy": {
        "title": "Warranty and Return Policy",
        "content": (
            "Pella offers a Limited Lifetime Warranty on most products covering defects "
            "in materials and workmanship. Wood components are covered for 10 years, "
            "glass for 20 years, and non-glass/non-wood components for the lifetime of "
            "the original purchaser. Labour for warranty repairs is covered for 2 years "
            "from installation date. Returns of undamaged, uninstalled products are "
            "accepted within 30 days of delivery with original receipt. Custom orders "
            "are non-returnable. All claims must be submitted through an authorized "
            "Pella dealer or via pella.com/support."
        ),
        "category": "policy",
        "content_type": "unstructured",
    },
    "product_catalog_summary": {
        "title": "Product Catalog Summary",
        "content": (
            "Pella product tiers (ascending price): "
            "1) Pella 150 Series — vinyl, budget-friendly, new construction. "
            "2) Pella 250 Series — vinyl, energy-efficient, replacement & new. "
            "3) Pella Lifestyle Series — wood/fiberglass hybrid, mid-range. "
            "4) Pella Impervia — fiberglass, commercial-grade durability. "
            "5) Pella Reserve — premium architectural wood, custom sizes. "
            "Window types: double-hung, casement, awning, sliding, fixed, bay/bow. "
            "Door types: entry, patio (sliding/hinged), storm, bifold."
        ),
        "category": "product",
        "content_type": "structured",
    },
    "escalation_procedures": {
        "title": "Customer Issue Escalation Procedures",
        "content": (
            "Tier 1 (Agent): handle product questions, order status, simple warranty checks. "
            "Tier 2 (Specialist): installation defects, complex warranty claims, pricing disputes. "
            "Tier 3 (Manager): legal complaints, social-media escalations, claims >$5,000. "
            "Always collect: order number, product SKU, photos of the issue, and customer "
            "contact info before escalating. SLA: Tier 2 response within 4 business hours, "
            "Tier 3 within 1 business day."
        ),
        "category": "process",
        "content_type": "structured",
    },
    "parts_forecasting_overview": {
        "title": "Parts Forecasting Data Model",
        "content": (
            "The parts forecasting pipeline follows a demand-driven supply chain model: "
            "Demand Signals → Purchase Orders → Receivers → Invoices → Work Orders → "
            "Customer Quotes. Key tables: bronze_demand_signals, silver_purchase_orders, "
            "gold_fact_work_order_completion, gold_dim_parts_type1, gold_dim_parts_type2. "
            "The gold layer includes both SCD Type 1 (overwrite) and Type 2 (history-tracked) "
            "dimensions for parts and customers."
        ),
        "category": "data_model",
        "content_type": "structured",
    },
}

EPISODIC_ORG: dict[str, dict] = {
    "resolution_warranty_glass": {
        "summary": (
            "Customer reported fogged double-pane glass on a 15-year-old Lifestyle Series "
            "window. Agent confirmed the glass was still under the 20-year warranty, "
            "submitted a replacement glass order, and scheduled a technician visit. "
            "Resolution time: 6 days. Customer satisfaction: 5/5."
        ),
        "outcome": "successful_resolution",
        "category": "warranty_claim",
    },
    "failure_pattern_custom_order": {
        "summary": (
            "Customer attempted to return a custom-sized Reserve Series bay window. "
            "Agent initially approved the return, which was rejected by fulfillment. "
            "Root cause: agent did not check the non-returnable custom order policy. "
            "Corrective action: always verify custom vs. standard before approving returns."
        ),
        "outcome": "failed_resolution",
        "category": "return_request",
        "lesson": "Always check custom order flag before approving returns",
    },
    "resolution_parts_backorder": {
        "summary": (
            "Technician needed Impervia sash hardware for a commercial site. Part was "
            "backordered with a 3-week ETA. Agent proactively offered a temporary fix "
            "(adjustable shim kit) and set a calendar reminder for follow-up. "
            "Customer appreciated the proactive communication."
        ),
        "outcome": "successful_resolution",
        "category": "parts_availability",
    },
}

EPISODIC_USER: dict[str, dict] = {
    "session_onboarding_2025_03": {
        "thread_id": "thread-demo-001",
        "summary": (
            "User introduced themselves as a regional sales manager for the Midwest. "
            "Discussed Q1 sales targets and asked about Impervia product specs. "
            "Saved preference for concise bullet-point answers."
        ),
        "timestamp": "2025-03-15T10:30:00",
    },
    "session_pricing_2025_04": {
        "thread_id": "thread-demo-002",
        "summary": (
            "User asked for pricing comparisons between Lifestyle and Reserve series "
            "for a commercial project in Kansas City. Provided a side-by-side table. "
            "User corrected an outdated MSRP — feedback incorporated."
        ),
        "feedback": "Reserve Series MSRP was updated in Q1 2025; use latest price sheet",
        "timestamp": "2025-04-02T14:15:00",
    },
    "session_forecast_review_2025_04": {
        "thread_id": "thread-demo-003",
        "summary": (
            "User reviewed demand forecast dashboard and flagged that casement window "
            "demand in the Midwest spiked. Discussed root cause (new housing development). "
            "User asked to remember that the KC metro is their primary territory."
        ),
        "timestamp": "2025-04-10T09:00:00",
    },
}

SEMANTIC_ORG: dict[str, dict] = {
    "rule_warranty_before_quote": {
        "rule": "Always check warranty status before quoting repair costs to a customer.",
        "category": "policy",
        "confidence": 0.95,
    },
    "rule_premium_priority": {
        "rule": "Premium tier customers (Reserve Series owners) get priority routing to Tier 2.",
        "category": "routing",
        "confidence": 0.90,
    },
    "pattern_seasonal_demand": {
        "rule": (
            "Window replacement demand peaks in spring (March–May) and early fall "
            "(September–October). Plan inventory buffers 6 weeks ahead of these periods."
        ),
        "category": "forecasting",
        "confidence": 0.85,
    },
    "rule_uc_naming": {
        "rule": (
            "All Databricks tables follow Unity Catalog three-level naming: "
            "catalog.schema.table. The production catalog is 'mfg_mc_se_sa' "
            "and the schema for Pella data is 'pella'."
        ),
        "category": "data_standards",
        "confidence": 0.99,
    },
}

SEMANTIC_USER: dict[str, dict] = {
    "pref_concise_answers": {
        "content": "Prefers concise, bullet-point answers over long paragraphs.",
        "category": "communication_preference",
        "confidence": 0.95,
    },
    "pref_region_midwest": {
        "content": "Works in the Midwest region. Primary territory is the Kansas City metro area.",
        "category": "role_context",
        "confidence": 0.90,
    },
    "pref_commercial_focus": {
        "content": "Primary focus is commercial projects, especially multi-unit residential and office buildings.",
        "category": "role_context",
        "confidence": 0.90,
    },
    "pref_impervia_expert": {
        "content": "Has deep knowledge of the Impervia (fiberglass) product line. Often asks about specs and availability.",
        "category": "expertise",
        "confidence": 0.85,
    },
}


# ---------------------------------------------------------------------------
# Seed runner
# ---------------------------------------------------------------------------
async def _seed(clear: bool = False) -> None:
    from databricks_langchain import AsyncDatabricksStore

    instance_name_raw = os.getenv("LAKEBASE_INSTANCE_NAME") or None
    project = os.getenv("LAKEBASE_AUTOSCALING_PROJECT") or None
    branch = os.getenv("LAKEBASE_AUTOSCALING_BRANCH") or None
    embedding_endpoint = os.getenv("EMBEDDING_ENDPOINT", "databricks-gte-large-en")
    embedding_dims = int(os.getenv("EMBEDDING_DIMS", "1024"))

    if instance_name_raw:
        from agent_server.utils_memory import resolve_lakebase_instance_name
        instance_name = resolve_lakebase_instance_name(instance_name_raw)
    else:
        instance_name = None

    async with AsyncDatabricksStore(
        instance_name=instance_name,
        project=project,
        branch=branch,
        embedding_endpoint=embedding_endpoint,
        embedding_dims=embedding_dims,
    ) as store:
        await store.setup()

        logger.info("Loading skills from %s ...", SKILLS_DIR)
        skills = _load_skills_from_markdown()
        if not skills:
            logger.warning("No skill files found — skills namespace will be empty")

        all_namespaces: list[tuple[str, tuple[str, str], dict[str, dict]]] = [
            ("Skills", NS_SKILLS, skills),
            ("Knowledge", NS_KNOWLEDGE, KNOWLEDGE),
            ("Episodic (org)", NS_EPISODIC_ORG, EPISODIC_ORG),
            ("Episodic (user)", NS_EPISODIC_USER, EPISODIC_USER),
            ("Semantic (org)", NS_SEMANTIC_ORG, SEMANTIC_ORG),
            ("Semantic (user)", NS_SEMANTIC_USER, SEMANTIC_USER),
        ]

        for label, ns, data in all_namespaces:
            if clear:
                logger.info("Clearing %s namespace %s ...", label, ns)
                try:
                    existing = await store.asearch(ns, query="", limit=100)
                    for item in existing:
                        await store.adelete(ns, item.key)
                    logger.info("  Deleted %d existing entries", len(existing))
                except Exception:
                    logger.warning("  Could not clear namespace %s", ns)

            logger.info("Seeding %s (%d entries) ...", label, len(data))
            for key, value in data.items():
                await store.aput(ns, key, value)
            logger.info("  Done.")

    logger.info("Seed complete.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Lakebase persistent stores")
    parser.add_argument("--clear", action="store_true", help="Clear existing entries before seeding")
    args = parser.parse_args()
    asyncio.run(_seed(clear=args.clear))


if __name__ == "__main__":
    main()
