"""
Data Extraction Service
Pulls product data from Amazon via Apify (primary) or Easyparser (fallback).
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

import httpx

from config import settings
from models.request import ProductData

logger = logging.getLogger(__name__)

APIFY_BASE = "https://api.apify.com/v2"
ACTOR_ID = "pache~amazon-rufus-scraper"


async def _poll_apify_run(client: httpx.AsyncClient, run_id: str, token: str) -> dict:
    """Poll Apify run until it finishes and return the first dataset item."""
    for _ in range(60):  # max 5 minutes (5s × 60)
        await asyncio.sleep(5)
        resp = await client.get(
            f"{APIFY_BASE}/actor-runs/{run_id}",
            params={"token": token},
        )
        resp.raise_for_status()
        run = resp.json()["data"]
        status = run["status"]
        if status == "SUCCEEDED":
            dataset_id = run["defaultDatasetId"]
            items_resp = await client.get(
                f"{APIFY_BASE}/datasets/{dataset_id}/items",
                params={"token": token, "limit": 1},
            )
            items_resp.raise_for_status()
            items = items_resp.json()
            if not items:
                raise ValueError(f"Apify run {run_id} succeeded but returned 0 items. The ASIN may be invalid or scraping failed.")
            return items[0]
        if status in ("FAILED", "ABORTED", "TIMED-OUT"):
            raise RuntimeError(f"Apify run {run_id} ended with status: {status}")
    raise TimeoutError(f"Apify run {run_id} did not complete within 5 minutes")


def _parse_apify_item(raw: dict, asin: str) -> ProductData:
    """Map raw Apify JSON to our ProductData model."""
    logger.info(f"[_parse_apify_item] Parsing data for ASIN {asin}. Keys found: {list(raw.keys())}")
    
    if "error" in raw and raw["error"]:
        logger.error(f"Apify explicitly returned an error for {asin}: {raw['error']}")
        raise ValueError(f"Apify scraping failed for {asin}: {raw['error']}")

    # Check if the payload is nested inside baselineData
    if "baselineData" in raw and isinstance(raw["baselineData"], dict) and raw["baselineData"]:
        logger.info(f"[_parse_apify_item] Found nested baselineData for {asin}, extracting from it.")
        raw = raw["baselineData"]

    # Reviews: may be list of dicts or strings
    reviews_raw = raw.get("reviews", [])
    logger.info(f"[_parse_apify_item] Found {len(reviews_raw)} raw reviews for {asin}.")
    reviews: list[str] = []
    for r in reviews_raw[:100]:
        if isinstance(r, dict):
            reviews.append(r.get("text") or r.get("body") or str(r))
        else:
            reviews.append(str(r))

    # Q&A
    qa_raw = raw.get("qa", raw.get("questionsAndAnswers", []))
    qa: list[dict] = []
    for item in qa_raw:
        if isinstance(item, dict):
            qa.append({"question": item.get("question", ""), "answer": item.get("answer", "")})

    # Price
    price_raw = raw.get("price", raw.get("originalPrice", 0))
    try:
        price = float(str(price_raw).replace("$", "").replace(",", "").strip())
    except (ValueError, TypeError):
        price = 0.0

    # BSR
    bsr_raw = raw.get("bestSellersRank", raw.get("bsr", None))
    bsr: Optional[int] = None
    if bsr_raw is not None:
        try:
            bsr = int(str(bsr_raw).replace(",", "").strip())
        except (ValueError, TypeError):
            bsr = None

    return ProductData(
        asin=asin,
        title=raw.get("title", "Unknown Product"),
        bullet_points=raw.get("bulletPoints", raw.get("features", [])),
        description=raw.get("description", raw.get("productDescription", "")),
        reviews=reviews,
        qa=qa,
        bsr=bsr,
        category=raw.get("category", raw.get("breadCrumbs", "Unknown")),
        price=price,
        rating=raw.get("rating", raw.get("stars", None)),
        review_count=raw.get("reviewsCount", raw.get("ratingsTotal", None)),
    )


async def extract_asin_data(asin: str) -> ProductData:
    """Extract product data for a single ASIN using Rainforest API."""
    
    # ── MOCK DATA FOR DEMO PURPOSES ──
    if asin.upper() == "B09XS7JWHH" and not settings.rainforest_api_key:
        logger.info(f"Using rich mock data for target ASIN {asin} to bypass API requirement.")
        return ProductData(
            asin=asin,
            title="Beats Fit Pro - True Wireless Noise Cancelling Earbuds - Apple H1 Headphone Chip, Compatible with Apple & Android, Class 1 Bluetooth, Built-in Microphone, 6 Hours of Listening Time - Black",
            bullet_points=[
                "Flexible, secure-fit wingtips for all-day comfort and stability during workouts",
                "Custom acoustic platform delivers powerful, balanced sound",
                "Spatial Audio with dynamic head tracking for immersive music, movies, and games",
                "Three distinct listening modes: Active Noise Cancelling, Transparency Mode, and Adaptive EQ",
                "Enhanced by the Apple H1 chip for Automatic Switching, Audio Sharing (with another pair of Beats headphones or Apple AirPods), and 'Hey Siri'",
                "Sweat and water resistant (IPX4-rated) earbuds",
                "Up to 6 hours of listening time (up to 24 hours combined with pocket-sized charging case)",
            ],
            description="Equipped with comfortable, secure-fit wingtips that flex to fit your ear. The universal wingtip design was put to the ultimate test by athletes of all kinds so you can trust these earbuds will stay put through work days and workouts. Complete with pressure relieving vents, you can comfortably wear these earbuds all day long. Beats Fit Pro is engineered to deliver powerful, balanced sound via a custom acoustic platform that stays with you through your daily activities.",
            reviews=[
                "These are the absolute best earbuds for the gym! I run 5 miles a day and they never fall out thanks to the wingtips. The sweat resistance is legit.",
                "Sound quality is amazing with strong bass. ANC blocks out the gym music easily.",
                "Battery life is pretty good, but I wish the case had wireless charging. They stay in my ears during heavy lifts though.",
                "Love the integration with my iPhone. Siri works flawlessly while I'm on the treadmill.",
                "A bit uncomfortable after 3 hours, but for a 1-hour gym session they are perfect."
            ],
            qa=[
                {"question": "Are these good for sweaty gym workouts?", "answer": "Yes, they are IPX4 sweat and water resistant and the wingtips keep them secure."},
                {"question": "Do they work with Android?", "answer": "Yes, there is a Beats app for Android that lets you customize the controls and ANC."},
                {"question": "Can I run a marathon with these?", "answer": "Battery lasts 6 hours with ANC on, so yes they will last a marathon."}
            ],
            bsr=142,
            category="Electronics > Headphones > Earbuds",
            price=199.95,
            rating=4.5,
            review_count=12450,
        )

    if settings.rainforest_api_key:
        return await _extract_via_rainforest(asin, settings.rainforest_api_key)

    raise RuntimeError(
        f"No extraction API configured. Set RAINFOREST_API_KEY in .env"
    )


async def _extract_via_rainforest(asin: str, api_key: str) -> ProductData:
    """Extract product data using Rainforest API (Gold Standard Amazon Scraper)."""
    base_url = "https://api.rainforestapi.com/request"
    params_product = {
        "api_key": api_key,
        "type": "product",
        "amazon_domain": settings.amazon_domain,
        "asin": asin
    }
    params_reviews = {
        "api_key": api_key,
        "type": "reviews",
        "amazon_domain": settings.amazon_domain,
        "asin": asin,
        "max_page": "2"
    }
    
    async with httpx.AsyncClient(timeout=60) as client:
        logger.info(f"Fetching Rainforest API data for ASIN {asin}...")
        
        # Concurrent fetching of product details and rich reviews
        product_req = client.get(base_url, params=params_product)
        reviews_req = client.get(base_url, params=params_reviews)
        
        prod_resp, rev_resp = await asyncio.gather(product_req, reviews_req, return_exceptions=True)
        
        if isinstance(prod_resp, Exception):
            raise RuntimeError(f"Rainforest API product request failed: {prod_resp}")
        prod_resp.raise_for_status()
        prod_data = prod_resp.json()
        
        if "product" not in prod_data:
            raise ValueError(f"Rainforest API returned no product data for {asin}. Is it a valid ASIN? Response: {prod_data.get('request_info', {}).get('message', '')}")
            
        product = prod_data["product"]
        
        # Extract Reviews
        reviews = []
        if not isinstance(rev_resp, Exception) and rev_resp.status_code == 200:
            try:
                rev_data = rev_resp.json()
                for r in rev_data.get("reviews", []):
                    text = r.get("body") or r.get("title")
                    if text:
                        reviews.append(text)
            except Exception as e:
                logger.warning(f"Failed to parse Rainforest reviews payload: {e}")
        else:
            status = rev_resp.status_code if not isinstance(rev_resp, Exception) else str(rev_resp)
            logger.warning(f"Rainforest reviews endpoint failed or returned {status}. Falling back to top_reviews.")
            
        # Fallback to top_reviews from product endpoint if reviews endpoint failed/empty
        if not reviews:
            for r in product.get("top_reviews", []):
                text = r.get("body") or r.get("title")
                if text:
                    reviews.append(text)
                    
        # Extract QA
        qa = []
        for q in product.get("questions_and_answers", []):
            qa.append({"question": q.get("question", ""), "answer": q.get("answer", "")})
            
        # Parse Price
        price_raw = product.get("buybox_winner", {}).get("price", {}).get("value", 0.0)
        
        # Parse BSR
        bsr_list = product.get("bestsellers_rank", [])
        bsr = bsr_list[0].get("rank") if bsr_list else None
        
        # Categories
        cat_list = product.get("categories", [])
        category = " > ".join(c.get("name", "") for c in cat_list) if cat_list else "Unknown"
        
        logger.info(f"Successfully extracted {asin} via Rainforest API.")
        return ProductData(
            asin=asin,
            title=product.get("title", f"Unknown ASIN {asin}"),
            bullet_points=product.get("feature_bullets", []),
            description=product.get("description", ""),
            reviews=reviews[:100],
            qa=qa,
            bsr=bsr,
            category=category,
            price=float(price_raw) if price_raw else 0.0,
            rating=product.get("rating", 0.0),
            review_count=product.get("ratings_total", 0),
        )


async def search_competitors(query: str, amazon_domain: str) -> list[str]:
    """Search for the top competitor ASINs for a given query."""
    api_key = settings.rainforest_api_key
    if not api_key:
        return []
        
    base_url = "https://api.rainforestapi.com/request"
    params = {
        "api_key": api_key,
        "type": "search",
        "amazon_domain": amazon_domain,
        "search_term": query
    }
    
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(base_url, params=params)
            resp.raise_for_status()
            data = resp.json()
            results = data.get("search_results", [])
            # Return top 5 ASINs
            return [r["asin"] for r in results[:5] if "asin" in r]
    except Exception as e:
        logger.warning(f"Competitor discovery failed: {e}")
        return []


async def extract_multiple(asins: list[str]) -> list[ProductData]:
    """Extract data for multiple ASINs concurrently."""
    results = await asyncio.gather(
        *[extract_asin_data(asin) for asin in asins],
        return_exceptions=True,
    )
    products: list[ProductData] = []
    for asin, result in zip(asins, results):
        if isinstance(result, Exception):
            logger.error(f"Failed to extract ASIN {asin}: {result}")
            # Return a stub so the pipeline can continue
            products.append(ProductData(asin=asin, title=f"[Extraction failed for {asin}]"))
        else:
            products.append(result)  # type: ignore[arg-type]
    return products
