"""
Market Size Estimation Service
Converts BSR → monthly sales → revenue using category-specific constants.
Methodology: per ChatGPT deep-research-report (top-10 sellers ≈ 20% of category revenue).
"""
from __future__ import annotations

import logging
from models.request import ProductData
from models.response import MarketEstimate, ProductBreakdown

logger = logging.getLogger(__name__)

# Category constants derived from BSR-to-sales empirical data.
CATEGORY_CONSTANTS: dict[str, int] = {
    "books": 150_000,
    "kindle store": 120_000,
    "music": 100_000,
    "movies & tv": 100_000,
    "video games": 80_000,
    "software": 70_000,
    "electronics": 60_000,
    "computers": 60_000,
    "camera & photo": 55_000,
    "cell phones & accessories": 55_000,
    "office products": 50_000,
    "toys & games": 50_000,
    "baby products": 45_000,
    "sports & outdoors": 45_000,
    "automotive": 40_000,
    "tools & home improvement": 40_000,
    "home & kitchen": 40_000,
    "garden & outdoor": 35_000,
    "beauty & personal care": 35_000,
    "health & household": 35_000,
    "grocery & gourmet food": 30_000,
    "pet supplies": 30_000,
    "arts, crafts & sewing": 25_000,
    "clothing, shoes & jewelry": 20_000,
    "industrial & scientific": 15_000,
    "default": 40_000,
}


def _get_constant(category: str) -> int:
    key = category.lower().strip()
    if key in CATEGORY_CONSTANTS:
        return CATEGORY_CONSTANTS[key]
    for cat_key, constant in CATEGORY_CONSTANTS.items():
        if cat_key in key or key in cat_key:
            return constant
    return CATEGORY_CONSTANTS["default"]


def estimate_market_size(products: list[ProductData], currency: str = "USD") -> MarketEstimate:
    """
    Estimate total monthly market revenue from a list of products.
    """
    # Use ASCII escapes to avoid encoding issues: \u20b9 = ₹, \u00a3 = £, \u20ac = €
    symbol_map = {"USD": "$", "INR": "\u20b9", "GBP": "\u00a3", "EUR": "\u20ac"}
    symbol = symbol_map.get(currency, "$")

    # Filter products with valid BSR and price
    valid = [p for p in products if p.bsr and p.bsr > 0 and p.price > 0]
    valid.sort(key=lambda p: p.bsr)
    top10 = valid[:10]

    breakdowns: list[ProductBreakdown] = []
    top10_revenue = 0.0

    for product in top10:
        constant = _get_constant(product.category)
        monthly_sales = constant / product.bsr if product.bsr else 0
        monthly_revenue = monthly_sales * product.price
        top10_revenue += monthly_revenue
        breakdowns.append(
            ProductBreakdown(
                asin=product.asin,
                title=product.title[:80],
                bsr=product.bsr,
                price=product.price,
                monthly_sales=round(monthly_sales, 1),
                monthly_revenue=round(monthly_revenue, 2),
                currency=currency,
                currency_symbol=symbol,
            )
        )

    scaling_factor = 5.0
    total_market = 0.0
    if breakdowns:
        anchor_revenue = max(b.monthly_revenue for b in breakdowns)
        total_market = anchor_revenue * 2.5 * scaling_factor
    elif products:
        median_price = sum(p.price for p in products) / len(products) if products else 100.0
        constant = _get_constant(products[0].category)
        total_market = constant * median_price * 0.1
    
    categories = [p.category for p in top10]
    dominant_category = max(set(categories), key=categories.count) if categories else "Unknown"

    return MarketEstimate(
        category=dominant_category,
        top10_revenue=round(top10_revenue, 2),
        total_market_revenue=round(total_market, 2),
        scaling_factor=scaling_factor,
        currency=currency,
        currency_symbol=symbol,
        products_breakdown=breakdowns,
    )
