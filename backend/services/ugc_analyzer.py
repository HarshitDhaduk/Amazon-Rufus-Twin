"""
UGC Contradiction Detector — Stage 3 enhancement.

Implements the critical Rufus production rule:
  UGC (reviews + Q&A) is treated as GROUND TRUTH and overrides marketing copy.
  If 15%+ of reviews contradict a listing claim, Rufus surfaces that cluster
  regardless of what the bullet points say.

How it works:
  1. Parse listing bullet points into individual claim phrases
  2. For each claim, scan review corpus for semantic contradictions
     using keyword + pattern matching (fast, no extra LLM call)
  3. Compute contradiction cluster size as % of total reviews
  4. Return contradiction list for injection into RAG context and AEO scoring

Contradiction signals it detects:
  - Battery/endurance claims vs "battery dies", "doesn't last", "discharge"
  - Build quality claims vs "broke", "cracked", "feels cheap", "flimsy"
  - Size/fit claims vs "runs small", "too big", "not as described"
  - Temperature/performance claims vs "overheats", "underperforms in heat"
  - Price/value claims vs "overpriced", "not worth it", "cheaper alternative"
  - Connectivity claims vs "disconnects", "lag", "pairing issues"
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ── Contradiction pattern library ─────────────────────────────────────────────
# Format: {claim_keyword: [contradiction_patterns]}
CONTRADICTION_PATTERNS: dict[str, list[str]] = {
    # Battery / Endurance
    "battery": [
        "battery dies", "battery dead", "doesn't last", "does not last",
        "poor battery", "bad battery", "drains fast", "drains quickly",
        "short battery", "only lasts", "charge frequently",
    ],
    "long battery": [
        "battery dies", "doesn't last", "only last", "short battery life",
    ],
    "all-day": [
        "battery dies", "need to charge", "doesn't last all day", "half day",
    ],
    # Build Quality
    "durable": [
        "broke", "broken", "cracked", "fell apart", "cheap plastic",
        "flimsy", "feels cheap", "poor quality", "bad quality", "cheaply made",
    ],
    "premium": [
        "feels cheap", "cheap quality", "not premium", "overpriced", "plastic",
    ],
    "sturdy": [
        "broke", "not sturdy", "flimsy", "bends", "cracked",
    ],
    # Fit / Size
    "true to size": [
        "runs small", "runs large", "too small", "too big", "size off",
        "not true to size", "sizing is off", "size up", "size down",
    ],
    "fits well": [
        "doesn't fit", "poor fit", "uncomfortable", "too tight", "too loose",
    ],
    # Thermal / Climate
    "energy efficient": [
        "uses a lot of electricity", "expensive electricity", "high power bill",
        "consumes more", "not efficient",
    ],
    "cooling": [
        "overheats", "doesn't cool", "not cooling", "warm in summer",
        "struggles in heat", "poor cooling",
    ],
    "inverter": [
        "high electricity", "power consumption", "bill increased",
    ],
    # Sound / Audio
    "clear sound": [
        "distorted", "crackling", "fuzzy", "muffled", "poor sound", "bad audio",
    ],
    "noise cancelling": [
        "doesn't cancel", "still hear noise", "poor anc", "anc not working",
    ],
    # Connectivity
    "stable connection": [
        "disconnects", "drops connection", "lag", "latency", "pairing issues",
        "bluetooth issues", "wifi issues",
    ],
    # Performance
    "fast": [
        "slow", "sluggish", "lags", "freezes", "performance issues",
    ],
    "powerful": [
        "underpowered", "struggles", "can't handle", "slow",
    ],
    # Value
    "value": [
        "overpriced", "not worth", "waste of money", "cheaper alternative",
        "too expensive",
    ],
    # Waterproofing
    "waterproof": [
        "not waterproof", "water damaged", "water got in", "not water resistant",
    ],
}


@dataclass
class Contradiction:
    claim: str              # The listing claim that's contradicted
    review_count: int       # Number of reviews in this cluster
    total_reviews: int      # Total reviews checked
    contradiction_pct: float  # % of reviews that contradict
    sample_phrases: list[str] = field(default_factory=list)  # Up to 3 example phrases
    severity: str = "low"   # "low" < 10%, "medium" 10-20%, "high" > 20%


def _extract_claims(bullet_points: list[str], description: str = "") -> list[str]:
    """Extract simple claim keywords from bullet points."""
    all_text = " ".join(bullet_points) + " " + description
    all_text_lower = all_text.lower()
    found_claims = []
    for claim_key in CONTRADICTION_PATTERNS:
        if claim_key in all_text_lower:
            found_claims.append(claim_key)
    return found_claims


def _find_contradictions_for_claim(
    claim: str,
    reviews: list[str],
    patterns: list[str],
) -> tuple[int, list[str]]:
    """Return (count_of_contradicting_reviews, sample_phrases)."""
    count = 0
    samples: list[str] = []
    for review in reviews:
        review_lower = review.lower()
        for pattern in patterns:
            if pattern in review_lower:
                count += 1
                if len(samples) < 3:
                    # Extract a short snippet around the match
                    idx = review_lower.find(pattern)
                    start = max(0, idx - 30)
                    end = min(len(review), idx + len(pattern) + 50)
                    snippet = review[start:end].strip()
                    if snippet not in samples:
                        samples.append(f"…{snippet}…")
                break  # Count each review once per claim
    return count, samples


def detect_review_contradictions(
    listing_bullet_points: list[str],
    reviews: list[str],
    description: str = "",
    threshold_pct: float = 10.0,
) -> list[Contradiction]:
    """
    Find semantic clusters in reviews that contradict listing bullet points.
    
    Args:
        listing_bullet_points: Product bullet points / feature claims
        reviews: Customer review texts
        description: Product description (also checked for claims)
        threshold_pct: Min % of reviews required to surface a contradiction
    
    Returns:
        List of Contradiction objects, sorted by severity (most severe first).
        Empty list if no significant contradictions found.
    """
    if not reviews or not listing_bullet_points:
        return []

    claims = _extract_claims(listing_bullet_points, description)
    if not claims:
        return []

    total = len(reviews)
    contradictions: list[Contradiction] = []

    for claim in claims:
        patterns = CONTRADICTION_PATTERNS.get(claim, [])
        if not patterns:
            continue
        count, samples = _find_contradictions_for_claim(claim, reviews, patterns)
        pct = (count / total) * 100 if total > 0 else 0.0
        if pct >= threshold_pct:
            severity = "high" if pct >= 20 else "medium" if pct >= 10 else "low"
            contradictions.append(Contradiction(
                claim=claim,
                review_count=count,
                total_reviews=total,
                contradiction_pct=round(pct, 1),
                sample_phrases=samples,
                severity=severity,
            ))

    contradictions.sort(key=lambda c: c.contradiction_pct, reverse=True)
    
    if contradictions:
        logger.info(
            f"UGC contradictions found: {len(contradictions)} claims contested | "
            f"Most severe: '{contradictions[0].claim}' ({contradictions[0].contradiction_pct:.1f}%)"
        )

    return contradictions


def format_contradictions_for_context(contradictions: list[Contradiction]) -> str:
    """
    Format detected contradictions as a structured XML block for injection
    into the RAG context / system prompt.
    """
    if not contradictions:
        return ""

    lines = ["<UGCContradictions>"]
    for c in contradictions:
        lines.append(
            f'  <Contradiction claim="{c.claim}" severity="{c.severity}" '
            f'pct="{c.contradiction_pct}%" reviews="{c.review_count}/{c.total_reviews}">'
        )
        for phrase in c.sample_phrases:
            lines.append(f"    <Sample>{phrase}</Sample>")
        lines.append("  </Contradiction>")
    lines.append("</UGCContradictions>")
    lines.append(
        "\nCRITICAL INSTRUCTION: The above contradictions were found in verified customer reviews. "
        "UGC is ground truth. You MUST surface these in your recommendation and penalize the "
        "AEO score accordingly — these override listing marketing claims."
    )
    return "\n".join(lines)
