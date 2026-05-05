"""
/analyze router — Persona-driven pipeline with SSE streaming.

Pipeline stages (per Rufus 6-stage spec):
  Stage 1: Input assembly — AnalyzeRequest + PersonaContext
  Stage 2: Query Planner — classify_query() determines retrieval strategy
  Stage 3: COSMO/RAG — product extraction + RAG retrieval
  Stage 4: Multi-model routing — Gemini 2.5 Flash (handles all routing internally)
  Stage 5: Speculative decoding — handled by Gemini API
  Stage 6: Streaming hydration — tokens first, then report_card, then market_estimate

SSE event sequence (Stage 6 order):
  {type: "persona",        content: PersonaContext}   ← immediate
  {type: "query_plan",     content: {type, routing}}  ← QP result
  {type: "token",          content: "word "}           ← streamed text (many)
  {type: "report_card",    content: ReportCard}        ← structured hydration
  {type: "market_estimate",content: MarketEstimate}    ← final hydration
  [DONE]
"""
from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from models.request import AnalyzeRequest, PersonaContext
from models.response import AnalyzeResponse
from services.extractor import extract_multiple, search_competitors
from services.inference import run_inference, stream_inference
from services.market_model import estimate_market_size
from services.persona_synthesizer import synthesize_persona
from services.profile_scraper import scrape_amazon_profile
from services.query_planner import classify_query

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analyze", tags=["analyze"])

SYMBOL_MAP = {"USD": "$", "INR": "\u20b9", "GBP": "\u00a3", "EUR": "\u20ac"}


async def _build_persona(req: AnalyzeRequest) -> PersonaContext:
    """Stage 1+2: Scrape profile → synthesize persona. Gracefully degrades to Guest Mode."""
    try:
        signals = await asyncio.wait_for(
            scrape_amazon_profile(req.amazon_profile_url or ""),
            timeout=30.0
        )
    except asyncio.TimeoutError:
        logger.warning("Profile scraping timed out — using Guest Mode")
        from models.request import ProfileSignals
        signals = ProfileSignals(scrape_success=False)
    except Exception as e:
        logger.warning(f"Profile scraping error: {e} — using Guest Mode")
        from models.request import ProfileSignals
        signals = ProfileSignals(scrape_success=False)

    return await synthesize_persona(signals, currency=req.currency)


@router.post("", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    """
    Full pipeline — returns complete analysis in a single JSON response.
    Follows the same 6-stage order as analyze_stream.
    """
    logger.info(f"Analyze: target={req.target_asin}")

    # Stages 1+2: Persona synthesis + Query Planner run concurrently
    persona_task = asyncio.create_task(_build_persona(req))
    qp_task = asyncio.create_task(classify_query(req.query))
    persona, (query_type, routing) = await asyncio.gather(persona_task, qp_task)
    currency = persona.currency

    # Stage 3: Extract products — QP routing override for competitor discovery
    qp_needs_competitors = routing.get("require_competitors", False)
    all_asins = [req.target_asin] + req.competitor_asins
    if not req.competitor_asins and (req.include_competitors or qp_needs_competitors):
        logger.info(
            f"Auto-discovering competitors | reason={'QP:' + query_type if qp_needs_competitors else 'user flag'} | market={persona.detected_market}"
        )
        discovered = await search_competitors(req.query, persona.detected_market)
        discovered = [a for a in discovered if a != req.target_asin][:3]
        all_asins += discovered

    all_products = await extract_multiple(all_asins)
    target = all_products[0]
    competitors = all_products[1:]

    # Stage 4+5: Inference (must run before market estimation per spec)
    try:
        recommendation, report_card = await run_inference(target, competitors, req.query, persona)
    except Exception as e:
        logger.error(f"Inference failed: {e}")
        raise HTTPException(status_code=502, detail=f"AI inference failed: {str(e)}")

    # Stage 6 hydration: Market size runs AFTER inference (non-fatal)
    market_estimate = None
    if req.include_market_size:
        try:
            market_estimate = estimate_market_size(all_products, currency=currency)
        except Exception as e:
            logger.warning(f"Market size estimation failed (non-fatal): {e}")

    return AnalyzeResponse(
        recommendation=recommendation,
        report_card=report_card,
        market_estimate=market_estimate,
    )


@router.post("/stream")
async def analyze_stream(req: AnalyzeRequest) -> StreamingResponse:
    """
    Streaming pipeline — returns Server-Sent Events.

    SSE event sequence:
      {type: "persona",         content: PersonaContext}
      {type: "market_estimate", content: MarketEstimate}
      {type: "token",           content: "word "}        ← streamed words
      {type: "report_card",     content: ReportCard}
      [DONE]
    """
    logger.info(f"Stream analyze: target={req.target_asin}")

    # Stage 1+2: Persona synthesis + Query Planner run concurrently
    persona_task = asyncio.create_task(_build_persona(req))
    qp_task = asyncio.create_task(classify_query(req.query))
    persona, (query_type, routing) = await asyncio.gather(persona_task, qp_task)
    currency = persona.currency

    logger.info(f"Pipeline ready | persona={persona.budget_tier}/{persona.primary_concern} | qp={query_type}")

    # Stage 3: Extract products
    # QP routing override: if QP classifies as comparison/planning, competitors are mandatory.
    # Auto-discover them if none were provided — regardless of the frontend flag.
    qp_needs_competitors = routing.get("require_competitors", False)
    all_asins = [req.target_asin] + req.competitor_asins
    if not req.competitor_asins and (req.include_competitors or qp_needs_competitors):
        logger.info(
            f"Auto-discovering competitors | reason={'QP:' + query_type if qp_needs_competitors else 'user flag'} | market={persona.detected_market}"
        )
        discovered = await search_competitors(req.query, persona.detected_market)
        discovered = [a for a in discovered if a != req.target_asin][:3]
        all_asins += discovered
        logger.info(f"Discovered {len(discovered)} competitor(s): {discovered}")

    all_products = await extract_multiple(all_asins)
    target = all_products[0]
    competitors = all_products[1:]

    async def event_generator():
        # Stage 6 Hydration Event 0: Persona (immediate, before any inference)
        yield f"data: {json.dumps({'type': 'persona', 'content': persona.model_dump()})}\n\n"

        # Stage 6 Hydration Event 1: Query Plan
        yield f"data: {json.dumps({'type': 'query_plan', 'content': {'query_type': query_type, 'routing': routing}})}\n\n"

        # Stage 4: Market size (non-fatal, run before tokens start)
        market_estimate = None
        if req.include_market_size:
            try:
                market_estimate = estimate_market_size(all_products, currency=currency)
            except Exception as e:
                logger.warning(f"Market size estimation failed: {e}")

        # Abort if target extraction failed
        if target.title.startswith("[Extraction failed"):
            err_msg = (
                f"Data Extraction Failed: Could not retrieve product data for ASIN {target.asin}. "
                "The Rainforest API returned an error or the ASIN is invalid for the configured region."
            )
            logger.error(f"Aborting stream: {err_msg}")
            yield f"data: {json.dumps({'type': 'error', 'content': err_msg})}\n\n"
            yield "data: [DONE]\n\n"
            return

        # Stage 6: Stream tokens FIRST (text hydration)
        async for event in stream_inference(target, competitors, req.query, persona):
            yield event

        # Stage 6: Hydrate market_estimate AFTER tokens + report_card (structured hydration)
        if market_estimate:
            yield f"data: {json.dumps({'type': 'market_estimate', 'content': market_estimate.model_dump()})}\n\n"

        # [DONE] fires LAST — after all hydration events have been sent
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
