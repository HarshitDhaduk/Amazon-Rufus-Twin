"""
Persona Synthesizer Service
Uses Gemini 2.5 Flash to classify raw Amazon profile signals into a structured
PersonaContext JSON using the PERSONA_SYNTHESIS_PROMPT from the architecture spec.

Stateless — computed fresh per request, never stored.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

from config import settings
from models.request import PersonaContext, ProfileSignals

logger = logging.getLogger(__name__)

# ── Persona Synthesis Prompt (exact from architecture spec §4.2) ──────────────
PERSONA_SYNTHESIS_PROMPT = """
You are analyzing Amazon behavioral data scraped from a public user profile.
Your job is to classify this shopper into a structured PersonaContext schema.

## Input data provided:
- purchase_history: list of {category, brand, price_paid, repeat_purchase}
- wishlist_items: list of {category, listed_price, days_on_list}
- review_history: list of {rating_given, review_text, sentiment_words}
- profile_badges: list of strings (e.g. "Prime member", "Vine Voice", "Top 500 Reviewer")

## Classification rules

budget_tier:
  - "budget"   → avg price paid < $30 OR wishlist items avg < $25
  - "premium"  → avg price paid > $80 OR repeated luxury brand purchases
  - "mid"      → everything else

quality_sensitivity:
  - Scan review_history. If >30% of reviews mention defects, materials, durability
    in complaints → "high". If mostly about price or delivery → "low". Else "medium".

deal_sensitivity:
  - "deal-seeker" → review mentions of "sale", "coupon", "cheaper", "overpriced" > 3
    OR wishlist items avg days_on_list > 30 (waiting for price drop)
  - "convenience" → Prime badge + avg days_on_list < 7 → impulse buyer

brand_loyalty:
  - "loyal" → >40% of purchases are repeat brands
  - "exploratory" → <20% repeat brands

category_affinity:
  - Top 3 categories by purchase volume

primary_concern:
  - Extract most frequent sentiment theme from review_history:
    price complaints → "price", material/build → "quality",
    shipping/late → "speed", green/sustainable → "eco"

## Output ONLY valid JSON. No prose. Schema:
{
  "budget_tier": "budget|mid|premium",
  "category_affinity": ["cat1", "cat2", "cat3"],
  "quality_sensitivity": "low|medium|high",
  "brand_loyalty": "loyal|exploratory",
  "deal_sensitivity": "deal-seeker|convenience",
  "primary_concern": "price|quality|speed|eco",
  "confidence_score": 0.0-1.0,
  "signals_used": ["signal1", "signal2"]
}
"""

_synth_llm: ChatGoogleGenerativeAI | None = None

def _get_synth_llm() -> ChatGoogleGenerativeAI:
    global _synth_llm
    if _synth_llm is None:
        _synth_llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=settings.google_api_key,
            temperature=0.0,
        )
    return _synth_llm


def _signals_to_text(signals: ProfileSignals) -> str:
    """Serialize ProfileSignals into a compact text block for the LLM."""
    lines = []

    if signals.profile_badges:
        lines.append(f"profile_badges: {signals.profile_badges}")

    if signals.review_history:
        review_summaries = []
        for r in signals.review_history[:20]:
            review_summaries.append({
                "rating_given": r.rating_given,
                "sentiment_words": r.sentiment_words,
                "review_text": r.review_text[:150],
            })
        lines.append(f"review_history: {json.dumps(review_summaries)}")

    if signals.wishlist_items:
        wishlist_summaries = [
            {"listed_price": w.listed_price, "days_on_list": w.days_on_list}
            for w in signals.wishlist_items[:10]
        ]
        lines.append(f"wishlist_items: {json.dumps(wishlist_summaries)}")

    if signals.purchase_history:
        purchase_summaries = [
            {"category": p.category, "brand": p.brand, "price_paid": p.price_paid, "repeat_purchase": p.repeat_purchase}
            for p in signals.purchase_history[:20]
        ]
        lines.append(f"purchase_history: {json.dumps(purchase_summaries)}")

    return "\n".join(lines) if lines else "No behavioral signals available."


def _build_guest_persona(currency: str = "USD") -> PersonaContext:
    """Return a neutral Guest Mode persona with all fields at neutral defaults."""
    symbol_to_market = {"INR": "amazon.in", "GBP": "amazon.co.uk", "EUR": "amazon.de"}
    market = symbol_to_market.get(currency, "amazon.com")
    region_map = {"INR": "India", "GBP": "United Kingdom", "EUR": "Europe"}
    region = region_map.get(currency, "Global")

    return PersonaContext(
        is_fallback=True,
        signals_used=["guest_mode"],
        confidence_score=0.0,
        currency=currency,
        region=region,
        detected_market=market,
    )


async def synthesize_persona(
    signals: ProfileSignals,
    currency: str = "USD",
) -> PersonaContext:
    """
    Classify raw profile signals into a PersonaContext using Gemini.
    Falls back to a neutral Guest Mode persona if signals are empty or synthesis fails.
    """
    symbol_to_market = {"INR": "amazon.in", "GBP": "amazon.co.uk", "EUR": "amazon.de"}
    market = symbol_to_market.get(currency, "amazon.com")
    region_map = {"INR": "India", "GBP": "United Kingdom", "EUR": "Europe"}
    region = region_map.get(currency, "Global")

    if not signals.scrape_success:
        logger.info("Profile scrape unsuccessful — using Guest Mode persona")
        return _build_guest_persona(currency)

    signals_text = _signals_to_text(signals)
    if signals_text == "No behavioral signals available.":
        logger.info("No signals available — using Guest Mode persona")
        return _build_guest_persona(currency)

    llm = _get_synth_llm()
    messages = [
        SystemMessage(content=PERSONA_SYNTHESIS_PROMPT),
        HumanMessage(content=f"Classify this shopper:\n\n{signals_text}"),
    ]

    try:
        response = await llm.ainvoke(messages)
        content = response.content.strip()

        # Strip markdown code fences if present
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        content = content.strip()

        data = json.loads(content)
        persona = PersonaContext(
            budget_tier=data.get("budget_tier", "mid"),
            category_affinity=data.get("category_affinity", []),
            quality_sensitivity=data.get("quality_sensitivity", "medium"),
            brand_loyalty=data.get("brand_loyalty", "exploratory"),
            deal_sensitivity=data.get("deal_sensitivity", "convenience"),
            primary_concern=data.get("primary_concern", "quality"),
            confidence_score=float(data.get("confidence_score", 0.5)),
            signals_used=data.get("signals_used", []),
            is_fallback=False,
            currency=currency,
            region=region,
            detected_market=market,
        )
        logger.info(f"Persona synthesized: budget={persona.budget_tier} concern={persona.primary_concern} confidence={persona.confidence_score:.2f}")
        return persona

    except Exception as e:
        logger.warning(f"Persona synthesis failed: {e} — falling back to Guest Mode")
        return _build_guest_persona(currency)
