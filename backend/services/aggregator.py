"""
Context Aggregator Service
Builds a structured XML context payload from product data for the Claude inference call.
"""
from __future__ import annotations

from models.request import ProductData


def _truncate(text: str, max_chars: int = 2000) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "…"


def _reviews_block(reviews: list[str], max_reviews: int = 40) -> str:
    if not reviews:
        return "<reviews>No reviews available.</reviews>"
    lines = "\n".join(
        f'  <review index="{i + 1}">{_truncate(r, 500)}</review>'
        for i, r in enumerate(reviews[:max_reviews])
    )
    return f"<reviews>\n{lines}\n</reviews>"


def _qa_block(qa: list[dict], max_items: int = 20) -> str:
    if not qa:
        return "<qa>No Q&amp;A available.</qa>"
    lines = "\n".join(
        f'  <item><question>{item.get("question", "")}</question>'
        f'<answer>{_truncate(item.get("answer", ""), 300)}</answer></item>'
        for item in qa[:max_items]
    )
    return f"<qa>\n{lines}\n</qa>"


def _bullets_block(bullets: list[str]) -> str:
    if not bullets:
        return "<features>No features listed.</features>"
    lines = "\n".join(f"  <feature>{b}</feature>" for b in bullets)
    return f"<features>\n{lines}\n</features>"


def _product_xml(product: ProductData, role: str) -> str:
    return f"""<product asin="{product.asin}" role="{role}">
  <title>{product.title}</title>
  <price>${product.price:.2f}</price>
  <rating>{product.rating or "N/A"} ({product.review_count or 0} reviews)</rating>
  <category>{product.category}</category>
  {_bullets_block(product.bullet_points)}
  <description>{_truncate(product.description, 1000)}</description>
  {_reviews_block(product.reviews)}
  {_qa_block(product.qa)}
</product>"""


def build_context_payload(
    target: ProductData,
    competitors: list[ProductData],
    query: str,
) -> str:
    """Build the full XML context payload to feed into Claude."""
    product_blocks = [_product_xml(target, "target")]
    for i, comp in enumerate(competitors, start=1):
        product_blocks.append(_product_xml(comp, f"competitor_{i}"))

    products_xml = "\n\n".join(product_blocks)

    return f"""<context>
  <user_query>{query}</user_query>
  <instruction>
    Evaluate these products as if you are Amazon's Rufus AI shopping assistant.
    Base your evaluation ONLY on the data provided below.
    Do not hallucinate data, prices, or reviews that are not shown.
  </instruction>

{products_xml}
</context>"""
