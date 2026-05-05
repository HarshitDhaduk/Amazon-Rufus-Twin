"""
/market router — standalone market size estimation.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from models.request import MarketSizeRequest, ProductData
from models.response import MarketEstimate
from services.extractor import extract_multiple
from services.market_model import estimate_market_size

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/market", tags=["market"])


@router.post("/size", response_model=MarketEstimate)
async def market_size(req: MarketSizeRequest) -> MarketEstimate:
    """
    Estimate total monthly market revenue for a set of ASINs (e.g., a category's top sellers).
    Uses BSR → sales → revenue model.
    """
    logger.info(f"Market size request: asins={req.asins}")

    products = await extract_multiple(req.asins)
    valid = [p for p in products if p.bsr is not None and p.price > 0]

    if not valid:
        raise HTTPException(
            status_code=422,
            detail="None of the provided ASINs returned valid BSR and price data.",
        )

    return estimate_market_size(valid)
