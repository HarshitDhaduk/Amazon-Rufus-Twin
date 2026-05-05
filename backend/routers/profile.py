"""
/profile router — Standalone persona extraction endpoint.
Allows the frontend to preview a shopper's persona before running a full analysis.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from models.request import PersonaContext
from services.persona_synthesizer import synthesize_persona
from services.profile_scraper import scrape_amazon_profile

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/profile", tags=["profile"])


class ProfileExtractRequest(BaseModel):
    profile_url: str
    currency: str = "USD"


@router.post("/extract", response_model=PersonaContext)
async def extract_profile(req: ProfileExtractRequest) -> PersonaContext:
    """
    Extract and synthesize a shopper persona from a public Amazon profile URL.
    Returns a PersonaContext JSON. Sets is_fallback=True if profile is private or scraping fails.
    """
    logger.info(f"Profile extract request: url={req.profile_url[:60]}...")
    signals = await scrape_amazon_profile(req.profile_url)
    persona = await synthesize_persona(signals, currency=req.currency)
    return persona
