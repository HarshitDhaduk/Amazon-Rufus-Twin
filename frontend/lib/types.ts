// Type definitions shared across the frontend

export interface ScoreSection {
  score: number;
  notes: string;
}

export interface CompetitiveGap {
  missing_attributes: string[];
  competitor_advantage: string;
}

export interface ReportCard {
  target_asin: string;
  overall_aeo_score: number;
  contextual_completeness: ScoreSection;
  sentiment_alignment: ScoreSection;
  competitive_gap: CompetitiveGap;
  recommended_actions: string[];
}

export interface ProductBreakdown {
  asin: string;
  title: string;
  bsr: number | null;
  price: number;
  monthly_sales: number;
  monthly_revenue: number;
  currency: string;
  currency_symbol: string;
}

export interface MarketEstimate {
  category: string;
  top10_revenue: number;
  total_market_revenue: number;
  scaling_factor: number;
  currency: string;
  currency_symbol: string;
  products_breakdown: ProductBreakdown[];
}

export interface AnalyzeResponse {
  recommendation: string;
  report_card: ReportCard;
  market_estimate: MarketEstimate | null;
}

export interface AnalyzeRequest {
  target_asin: string;
  competitor_asins: string[];
  query: string;
  include_market_size: boolean;
  include_competitors: boolean;
  currency: string;
  amazon_profile_url?: string;
}

// ── PersonaContext — mirrors backend model ────────────────────────────────────
export interface PersonaContext {
  budget_tier: "budget" | "mid" | "premium";
  category_affinity: string[];
  quality_sensitivity: "low" | "medium" | "high";
  brand_loyalty: "loyal" | "exploratory";
  deal_sensitivity: "deal-seeker" | "convenience";
  primary_concern: "price" | "quality" | "speed" | "eco";
  confidence_score: number;
  signals_used: string[];
  is_fallback: boolean;
  region: string;
  currency: string;
  detected_market: string;
}

// ── SSE Event Types ───────────────────────────────────────────────────────────
export type SSEEvent =
  | { type: "persona";         content: PersonaContext }
  | { type: "query_plan";      content: { query_type: string; routing: Record<string, unknown> } }
  | { type: "token";           content: string }
  | { type: "report_card";     content: ReportCard }
  | { type: "market_estimate"; content: MarketEstimate }
  | { type: "error";           content: string };
