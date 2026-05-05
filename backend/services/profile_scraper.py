"""
Amazon Profile Scraper Service
Extracts public shopper signals from Amazon profile pages using Apify Playwright crawl.

Signals extracted:
  - Purchase history signals (from review cards: category, brand, price)
  - Wishlist signals (public wishlists: price ranges, days on list)
  - Review history (rating patterns, sentiment words)
  - Profile badges (Prime, Vine Voice, Top 500 Reviewer)

Fallback: Returns ProfileSignals(scrape_success=False) when:
  - No profile URL provided (Guest Mode)
  - Profile is private or scraping fails
  - Apify API key not configured
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Optional

import httpx

from config import settings
from models.request import ProfileSignals, PurchaseSignal, ReviewSignal, WishlistSignal

logger = logging.getLogger(__name__)

APIFY_BASE = "https://api.apify.com/v2"
# Apify web scraper actor — uses Playwright for JS-rendered pages
PROFILE_ACTOR_ID = "apify~web-scraper"


def _build_profile_page_function(profile_url: str) -> str:
    """Build the Apify page function that extracts signals from an Amazon profile."""
    return """
async function pageFunction(context) {
    const { $, request, log } = context;

    const badges = [];
    $('[data-hook="badge"]').each((i, el) => badges.push($(el).text().trim()));
    $('.a-badge-text').each((i, el) => badges.push($(el).text().trim()));

    const reviews = [];
    $('[data-hook="review"]').each((i, el) => {
        if (i >= 50) return false;
        const rating = parseFloat($(el).find('.review-rating').text()) || 0;
        const text = $(el).find('.review-text-content span').text().trim();
        const title = $(el).find('.review-title span').last().text().trim();
        if (text) reviews.push({ rating_given: rating, review_text: text.slice(0, 500), title });
    });

    const wishlist_items = [];
    $('[data-item-prime-info]').each((i, el) => {
        const priceText = $(el).find('.a-price-whole').text().replace(/[^0-9.]/g, '');
        const price = parseFloat(priceText) || 0;
        wishlist_items.push({ listed_price: price, category: '', days_on_list: 0 });
    });

    return { badges, reviews, wishlist_items, url: request.url };
}
"""


async def _run_apify_actor(start_urls: list[str]) -> Optional[dict]:
    """Run a lightweight Apify web-scraper and return the first result item."""
    token = settings.apify_api_token
    if not token:
        logger.warning("APIFY_API_TOKEN not configured — profile scraping unavailable")
        return None

    payload = {
        "startUrls": [{"url": url} for url in start_urls],
        "pageFunction": _build_profile_page_function(start_urls[0]),
        "maxRequestsPerCrawl": 5,
        "maxConcurrency": 1,
    }

    async with httpx.AsyncClient(timeout=60) as client:
        try:
            # Start the actor run
            run_resp = await client.post(
                f"{APIFY_BASE}/acts/{PROFILE_ACTOR_ID}/runs",
                params={"token": token},
                json=payload,
            )
            run_resp.raise_for_status()
            run_id = run_resp.json()["data"]["id"]
            logger.info(f"Apify profile scrape started: run_id={run_id}")

            # Poll for completion (max 30s for profile scraping)
            for _ in range(6):
                await asyncio.sleep(5)
                status_resp = await client.get(
                    f"{APIFY_BASE}/actor-runs/{run_id}",
                    params={"token": token},
                )
                status_resp.raise_for_status()
                run_data = status_resp.json()["data"]
                if run_data["status"] == "SUCCEEDED":
                    dataset_id = run_data["defaultDatasetId"]
                    items_resp = await client.get(
                        f"{APIFY_BASE}/datasets/{dataset_id}/items",
                        params={"token": token, "limit": 1},
                    )
                    items = items_resp.json()
                    return items[0] if items else None
                if run_data["status"] in ("FAILED", "ABORTED", "TIMED-OUT"):
                    logger.warning(f"Apify profile run {run_id} ended: {run_data['status']}")
                    return None
        except Exception as e:
            logger.warning(f"Apify profile scrape failed: {e}")
            return None


def _parse_profile_signals(raw: dict) -> ProfileSignals:
    """Parse raw Apify output into structured ProfileSignals."""
    badges: list[str] = [b for b in raw.get("badges", []) if b]

    reviews: list[ReviewSignal] = []
    for r in raw.get("reviews", [])[:50]:
        text = r.get("review_text", "") or r.get("text", "")
        # Extract simple sentiment words
        neg_words = [w for w in ["defect", "broke", "cheap", "quality", "poor", "bad", "waste", "overpriced"] if w in text.lower()]
        deal_words = [w for w in ["sale", "coupon", "cheaper", "deal", "discount", "overpriced"] if w in text.lower()]
        reviews.append(ReviewSignal(
            rating_given=float(r.get("rating_given", 0)),
            review_text=text[:300],
            sentiment_words=neg_words + deal_words,
        ))

    wishlist_items: list[WishlistSignal] = []
    for w in raw.get("wishlist_items", [])[:20]:
        wishlist_items.append(WishlistSignal(
            listed_price=float(w.get("listed_price", 0)),
            category=w.get("category", ""),
            days_on_list=int(w.get("days_on_list", 0)),
        ))

    return ProfileSignals(
        purchase_history=[],  # Not public — would need CSV upload (beta)
        wishlist_items=wishlist_items,
        review_history=reviews,
        profile_badges=badges,
        scrape_success=True,
    )


async def scrape_amazon_profile(profile_url: str) -> ProfileSignals:
    """
    Main entry point: scrape an Amazon profile URL and return structured signals.
    Returns ProfileSignals(scrape_success=False) on any failure.
    """
    if not profile_url or not profile_url.strip():
        logger.info("No profile URL provided — returning empty signals (Guest Mode)")
        return ProfileSignals(scrape_success=False)

    # Normalize URL
    url = profile_url.strip()
    if not url.startswith("http"):
        url = f"https://{url}"

    logger.info(f"Scraping Amazon profile: {url}")
    raw = await _run_apify_actor([url])

    if not raw:
        return ProfileSignals(scrape_success=False)

    try:
        return _parse_profile_signals(raw)
    except Exception as e:
        logger.warning(f"Failed to parse profile signals: {e}")
        return ProfileSignals(scrape_success=False)
