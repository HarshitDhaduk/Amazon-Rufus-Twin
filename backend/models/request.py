from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, Field


# ── PersonaContext — Core Shopper Profile ─────────────────────────────────────

class PersonaContext(BaseModel):
    """
    Structured shopper persona synthesized from public Amazon profile signals.
    This is injected into every Gemini inference prompt to personalize scoring.
    Stateless — computed fresh per request, never stored.
    """
    budget_tier: Literal["budget", "mid", "premium"] = "mid"
    category_affinity: list[str] = Field(default_factory=list)
    quality_sensitivity: Literal["low", "medium", "high"] = "medium"
    brand_loyalty: Literal["loyal", "exploratory"] = "exploratory"
    deal_sensitivity: Literal["deal-seeker", "convenience"] = "convenience"
    primary_concern: Literal["price", "quality", "speed", "eco"] = "quality"
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    signals_used: list[str] = Field(default_factory=list)
    is_fallback: bool = True  # True when profile is private/not provided (Guest Mode)
    # Region/currency retained for routing convenience
    region: str = "Global"
    currency: str = "USD"
    detected_market: str = "amazon.com"


# ── Raw Profile Signals (intermediate, before synthesis) ──────────────────────

class PurchaseSignal(BaseModel):
    category: str
    brand: str = ""
    price_paid: float = 0.0
    repeat_purchase: bool = False


class WishlistSignal(BaseModel):
    category: str = ""
    listed_price: float = 0.0
    days_on_list: int = 0


class ReviewSignal(BaseModel):
    rating_given: float = 0.0
    review_text: str = ""
    sentiment_words: list[str] = Field(default_factory=list)


class ProfileSignals(BaseModel):
    """Raw signals scraped from a public Amazon profile. May contain Nones for private data."""
    purchase_history: list[PurchaseSignal] = Field(default_factory=list)
    wishlist_items: list[WishlistSignal] = Field(default_factory=list)
    review_history: list[ReviewSignal] = Field(default_factory=list)
    profile_badges: list[str] = Field(default_factory=list)
    scrape_success: bool = False


# ── Request Models ─────────────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    target_asin: str = Field(..., min_length=10, max_length=10, pattern=r"^[A-Z0-9]{10}$")
    competitor_asins: list[str] = Field(default_factory=list, max_length=3)
    query: str = Field(..., min_length=10, max_length=500)
    include_market_size: bool = True
    include_competitors: bool = False
    currency: str = "USD"
    amazon_profile_url: Optional[str] = None  # Optional — falls back to Guest Mode


class MarketSizeRequest(BaseModel):
    asins: list[str] = Field(..., min_length=1, max_length=10)
    category: Optional[str] = None


# ── Data Models ────────────────────────────────────────────────────────────────

class ProductData(BaseModel):
    asin: str
    title: str
    bullet_points: list[str] = Field(default_factory=list)
    description: str = ""
    reviews: list[str] = Field(default_factory=list)
    qa: list[dict] = Field(default_factory=list)
    bsr: Optional[int] = None
    category: str = "Unknown"
    price: float = 0.0
    rating: Optional[float] = None
    review_count: Optional[int] = None
