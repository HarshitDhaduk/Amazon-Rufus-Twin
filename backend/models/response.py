from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


# ── Sub-models ─────────────────────────────────────────────────────────────────

class ScoreSection(BaseModel):
    score: float = Field(..., ge=0, le=100)
    notes: str


class CompetitiveGap(BaseModel):
    missing_attributes: list[str] = Field(default_factory=list)
    competitor_advantage: str


class ReportCard(BaseModel):
    target_asin: str
    overall_aeo_score: float = Field(..., ge=0, le=100)
    contextual_completeness: ScoreSection
    sentiment_alignment: ScoreSection
    competitive_gap: CompetitiveGap
    recommended_actions: list[str] = Field(default_factory=list)


class ProductBreakdown(BaseModel):
    asin: str
    title: str
    bsr: Optional[int]
    price: float
    monthly_sales: float
    monthly_revenue: float
    currency: str = "USD"
    currency_symbol: str = "$"


class MarketEstimate(BaseModel):
    category: str
    top10_revenue: float
    total_market_revenue: float
    scaling_factor: float = 5.0
    currency: str = "USD"
    currency_symbol: str = "$"
    products_breakdown: list[ProductBreakdown] = Field(default_factory=list)


# ── Response Models ────────────────────────────────────────────────────────────

class AnalyzeResponse(BaseModel):
    recommendation: str
    report_card: ReportCard
    market_estimate: Optional[MarketEstimate] = None


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"
