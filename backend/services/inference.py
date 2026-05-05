"""
AI Inference Service — LangChain + Google Gemini + Rufus 6-Stage Pipeline

Stage 2 — Query Planner: classify_query() runs first, determines RAG depth + output emphasis.
Stage 3 — COSMO/RAG + UGC: retrieve_rag_context() + detect_review_contradictions() run in parallel.
Stage 6 — Streaming Hydration: tokens stream first, then report_card, then market_estimate.

Message structure (per spec §4.1):
  [SystemMessage(system_prompt + qp_routing_emphasis)]
  [HumanMessage(persona_xml + ugc_contradictions + rag_chunks + query)]
"""
from __future__ import annotations

import json
import logging
from typing import AsyncIterator, Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

from config import settings
from models.request import PersonaContext, ProductData
from models.response import CompetitiveGap, ReportCard, ScoreSection
from services.rag_indexer import retrieve_rag_context
from services.ugc_analyzer import detect_review_contradictions, format_contradictions_for_context
from services.query_planner import classify_query, QueryType

logger = logging.getLogger(__name__)

# ── LLM (singleton, lazy) ─────────────────────────────────────────────────────
_llm: ChatGoogleGenerativeAI | None = None

def _get_llm() -> ChatGoogleGenerativeAI:
    global _llm
    if _llm is None:
        _llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=settings.google_api_key,
            max_tokens=4096,
            temperature=0.1,
        )
        logger.info("ChatGoogleGenerativeAI (gemini-2.5-flash) initialized via LangChain")
    return _llm


# ── System Prompt (exact from architecture spec §4.1) ─────────────────────────
SYSTEM_PROMPT = """You are a neutral AI shopping assistant that mirrors Amazon Rufus's evaluation logic.
You are given:
1. A structured PersonaContext describing the shopper's behavioral profile
2. Product data chunks for a target ASIN and up to 3 competitor ASINs, retrieved via semantic RAG
3. A natural language shopper query

## Your evaluation mandate

You MUST evaluate products using ONLY the provided product data. You never invent, infer, or hallucinate facts not present in the context.

## Persona adaptation rules

You receive a PersonaContext XML block. It changes HOW you evaluate — not WHAT the product is.

- budget_tier = "budget"      → weight price-to-value ratio 40%, penalize luxury positioning
- budget_tier = "premium"     → weight brand trust, material quality, longevity 40%
- budget_tier = "mid"         → balanced weighting across all factors

- quality_sensitivity = "high" → treat 1-star review clusters as hard disqualifiers
- quality_sensitivity = "low"  → treat review complaints as soft signals only

- deal_sensitivity = "deal-seeker" → highlight if competitors offer better value/$
- deal_sensitivity = "convenience" → deprioritize price gap; weight Prime, fast shipping, easy returns

- brand_loyalty = "loyal" → note if target ASIN is a repeat brand for user; boost familiarity score
- brand_loyalty = "exploratory" → treat all brands equally; highlight novelty of alternatives

- primary_concern = "price"   → score contextual_completeness harder on pricing transparency
- primary_concern = "quality" → score review_sentiment_alignment on material/durability mentions
- primary_concern = "speed"   → surface shipping, Prime eligibility, availability
- primary_concern = "eco"     → scan for sustainability, materials, certifications

## Regional & Currency Rules

- ALWAYS use the currency symbol from PersonaContext for all prices
- If region is India: reference BEE star ratings, Indian summer performance, voltage stability
- If is_fallback = true: use neutral shopper tone with no persona weighting

## Evaluation dimensions (all scored 0–100)

1. contextual_completeness — Does the listing explicitly address the query use-case?
   Check: title, bullets, description, structured attributes, Q&A answers

2. review_sentiment_alignment — Do real reviews validate the listing's claims for this query?
   Check: semantic clusters matching query intent in top 100 reviews

3. competitive_gap — What does the competitor provide that this listing does not?
   Check: feature presence, review coverage, Q&A depth per query dimension

## Output format

Use the provided tool schema. Always produce:
(a) A natural language recommendation paragraph (persona-adjusted tone)
(b) A structured AEO report card (JSON via tool_use)

If competitors are present: include a Head-to-Head Comparison Table in the recommendation.
MANDATORY: Use Github Flavored Markdown (GFM) pipes '|' for tables. NEVER use tabs.
MANDATORY: Add exactly TWO empty lines after every table to ensure following text renders correctly.
Never reveal internal scoring weights. Never reference the PersonaContext XML directly to the user."""


# ── AEO Report Tool Schema ────────────────────────────────────────────────────
AEO_REPORT_TOOL = {
    "type": "function",
    "function": {
        "name": "generate_aeo_report",
        "description": "Generate a Rufus-style shopping recommendation and AEO diagnostic report card.",
        "parameters": {
            "type": "object",
            "properties": {
                "recommendation": {
                    "type": "string",
                    "description": "Natural-language Rufus-style recommendation. 2-4 paragraphs, persona-adjusted tone, citing specific review evidence. Be honest about trade-offs.",
                },
                "report_card": {
                    "type": "object",
                    "properties": {
                        "target_asin": {"type": "string"},
                        "overall_aeo_score": {
                            "type": "number",
                            "description": "0–100. Probability the AI recommends this product for the query, weighted by PersonaContext.",
                        },
                        "contextual_completeness": {
                            "type": "object",
                            "properties": {
                                "score": {"type": "number"},
                                "notes": {"type": "string", "description": "Specific attributes or query-relevant details missing from the listing."},
                            },
                            "required": ["score", "notes"],
                        },
                        "sentiment_alignment": {
                            "type": "object",
                            "properties": {
                                "score": {"type": "number"},
                                "notes": {"type": "string", "description": "How well customer reviews validate the product's claims for this specific query."},
                            },
                            "required": ["score", "notes"],
                        },
                        "competitive_gap": {
                            "type": "object",
                            "properties": {
                                "missing_attributes": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Attributes in competitor listings not present in the target.",
                                },
                                "competitor_advantage": {
                                    "type": "string",
                                    "description": "Plain-English explanation of where competitors have an edge.",
                                },
                            },
                            "required": ["missing_attributes", "competitor_advantage"],
                        },
                        "recommended_actions": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "3–5 specific, implementable actions for the seller to improve AEO score.",
                        },
                    },
                    "required": [
                        "target_asin", "overall_aeo_score", "contextual_completeness",
                        "sentiment_alignment", "competitive_gap", "recommended_actions",
                    ],
                },
            },
            "required": ["recommendation", "report_card"],
        }
    }
}


# ── PersonaContext XML Serializer ─────────────────────────────────────────────
def _persona_to_xml(persona: PersonaContext) -> str:
    """
    Serialize PersonaContext into a compact XML block for injection into HumanMessage.
    Per spec: persona context goes in the human turn so it's part of retrieval context.
    """
    currency_symbol_map = {"USD": "$", "INR": "\u20b9", "GBP": "\u00a3", "EUR": "\u20ac"}
    symbol = currency_symbol_map.get(persona.currency, "$")

    mode = "Guest Mode (query-only, no persona weighting)" if persona.is_fallback else "Persona Mode"
    affinity_str = ", ".join(persona.category_affinity) if persona.category_affinity else "General"

    return f"""<PersonaContext mode="{mode}" confidence="{persona.confidence_score:.2f}">
  <region>{persona.region}</region>
  <currency code="{persona.currency}" symbol="{symbol}" />
  <budget_tier>{persona.budget_tier}</budget_tier>
  <category_affinity>{affinity_str}</category_affinity>
  <quality_sensitivity>{persona.quality_sensitivity}</quality_sensitivity>
  <brand_loyalty>{persona.brand_loyalty}</brand_loyalty>
  <deal_sensitivity>{persona.deal_sensitivity}</deal_sensitivity>
  <primary_concern>{persona.primary_concern}</primary_concern>
  <is_fallback>{str(persona.is_fallback).lower()}</is_fallback>
</PersonaContext>"""


# ── Result parsing ────────────────────────────────────────────────────────────
def _parse_report_card(tool_input: dict, target_asin: str) -> tuple[str, ReportCard]:
    recommendation = tool_input.get("recommendation", "")
    rc = tool_input.get("report_card", {})

    def clamp(val: float) -> float:
        return min(100.0, max(0.0, float(val)))

    report_card = ReportCard(
        target_asin=rc.get("target_asin", target_asin),
        overall_aeo_score=clamp(rc.get("overall_aeo_score", 50)),
        contextual_completeness=ScoreSection(
            score=clamp(rc["contextual_completeness"]["score"]),
            notes=rc["contextual_completeness"]["notes"],
        ),
        sentiment_alignment=ScoreSection(
            score=clamp(rc["sentiment_alignment"]["score"]),
            notes=rc["sentiment_alignment"]["notes"],
        ),
        competitive_gap=CompetitiveGap(
            missing_attributes=rc["competitive_gap"].get("missing_attributes", []),
            competitor_advantage=rc["competitive_gap"].get("competitor_advantage", ""),
        ),
        recommended_actions=rc.get("recommended_actions", []),
    )
    return recommendation, report_card


# ── Core inference ────────────────────────────────────────────────────────────
async def run_inference(
    target: ProductData,
    competitors: list[ProductData],
    query: str,
    persona: PersonaContext,
) -> tuple[str, ReportCard]:
    """
    Full Rufus 6-Stage pipeline:
      Stage 2: Query Planner classification → determines RAG depth + output format
      Stage 3: RAG retrieval + UGC contradiction detection (run concurrently)
      Stage 4: Gemini 2.5 Flash inference with persona-injected + UGC-augmented context
    Returns (recommendation_text, report_card).
    """
    import asyncio

    # ── Stage 2: Query Planner ─────────────────────────────────────────────────
    qp_task = asyncio.create_task(classify_query(query))

    # ── Stage 3a: RAG Retrieval ────────────────────────────────────────────────
    logger.info(f"Starting RAG retrieval for query: {query!r}")
    rag_context = retrieve_rag_context(target, competitors, query)
    logger.info(f"RAG context size: {len(rag_context)} chars")

    # ── Stage 3b: UGC Contradiction Detection ─────────────────────────────────
    # Runs against listing claims — UGC is ground truth per Rufus production spec
    contradictions = detect_review_contradictions(
        listing_bullet_points=target.bullet_points,
        reviews=target.reviews,
        description=target.description,
    )
    ugc_block = format_contradictions_for_context(contradictions)
    if ugc_block:
        logger.info(f"UGC override block injected ({len(contradictions)} contradictions)")

    # ── Await QP result ────────────────────────────────────────────────────────
    query_type, routing = await qp_task
    output_emphasis = routing["output_emphasis"]
    logger.info(f"QP routing: type={query_type} | emphasis={output_emphasis[:60]}...")

    llm = _get_llm()
    llm_with_tools = llm.bind_tools(
        [AEO_REPORT_TOOL],
        tool_choice="generate_aeo_report",
    )

    # Build persona XML block
    persona_xml = _persona_to_xml(persona)

    # ── Stage 4: Compose prompt (per spec message structure) ───────────────────
    # System prompt augmented with QP routing emphasis
    system_with_qp = (
        SYSTEM_PROMPT
        + f"\n\n## Query Planner Directive\nQuery type: {query_type.upper()}\n"
        f"Output emphasis: {output_emphasis}"
    )

    # Human turn: PersonaContext XML + UGC contradictions + RAG chunks + query
    human_parts = [persona_xml]
    if ugc_block:
        human_parts.append(ugc_block)
    human_parts.append(rag_context)
    human_parts.append(f"Shopper Query: {query}")
    human_content = "\n\n".join(human_parts)

    messages = [
        SystemMessage(content=system_with_qp),
        HumanMessage(content=human_content),
    ]

    for attempt in range(3):
        try:
            response = await llm_with_tools.ainvoke(messages)
            tool_calls = getattr(response, "tool_calls", [])
            if not tool_calls:
                raise ValueError("LLM did not invoke the required tool.")
            tool_input = tool_calls[0].get("args", {})
            recommendation, report_card = _parse_report_card(tool_input, target.asin)
            logger.info(
                f"Inference complete. AEO score: {report_card.overall_aeo_score:.1f} "
                f"for ASIN {target.asin} | Persona: {persona.budget_tier}/{persona.primary_concern}"
            )
            return recommendation, report_card
        except Exception as e:
            logger.warning(f"Inference attempt {attempt + 1} failed: {e}")
            if attempt == 2:
                raise RuntimeError(f"All 3 inference attempts failed for ASIN {target.asin}: {e}") from e

    raise RuntimeError("Inference failed after all retries.")


# ── SSE Streaming ─────────────────────────────────────────────────────────────
async def stream_inference(
    target: ProductData,
    competitors: list[ProductData],
    query: str,
    persona: PersonaContext,
) -> AsyncIterator[str]:
    """
    Streaming inference via SSE.

    Yields SSE-formatted strings:
      - data: {"type": "token", "content": "word "}\\n\\n      — per token (typewriter)
      - data: {"type": "report_card", "content": {...}}\\n\\n  — full AEO report
      - data: [DONE]\\n\\n                                      — terminal signal
    """
    recommendation, report_card = await run_inference(target, competitors, query, persona)

    words = recommendation.split(" ")
    for i, word in enumerate(words):
        chunk = word + (" " if i < len(words) - 1 else "")
        yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"

    yield f"data: {json.dumps({'type': 'report_card', 'content': report_card.model_dump()})}\n\n"
    # NOTE: [DONE] is NOT yielded here — the router's event_generator sends it
    # AFTER the market_estimate hydration event so the frontend sees all data.
