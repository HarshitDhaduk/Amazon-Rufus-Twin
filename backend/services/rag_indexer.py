"""
RAG Indexer Service — Real-World LangChain + ChromaDB + Voyage AI Pipeline

Architecture (using AI Research Skills: langchain + chroma):
  - Embeddings : Voyage AI voyage-3-large (Anthropic's embedding platform)
                 → 1024-dim, best-in-class for semantic search
                 → https://www.voyageai.com (50M free tokens/month)
  - Vector DB  : ChromaDB PersistentClient (local dev) → portable to cloud
  - Framework  : LangChain (langchain-chroma, langchain-voyageai)
  - Retrieval  : Metadata-filtered similarity search per product role

Chunking strategy (mirrors Rufus RAG retrieval logic):
  1. listing chunk  → title + category + bullets + description (1 doc)
  2. review chunks  → one Document per review (up to 100)
  3. qa chunks      → one Document per Q&A pair (up to 50)

Cache: each ASIN collection is persisted to disk with a 24h TTL.
       Re-indexing is skipped when the collection is fresh.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path

import chromadb
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_voyageai import VoyageAIEmbeddings

from config import settings
from models.request import ProductData

logger = logging.getLogger(__name__)

# ── Storage ────────────────────────────────────────────────────────────────────
CHROMA_DIR = Path(__file__).parent.parent / "data" / "chroma_db"
CHROMA_DIR.mkdir(parents=True, exist_ok=True)

_TTL_SECONDS = 86_400  # 24h cache per ASIN

# ── Embedding model (initialized once, shared) ─────────────────────────────────
# voyage-3-large: Anthropic's flagship embedding model
# → 1024 dimensions, MTEB SOTA for retrieval tasks
# → Handles long product descriptions + noisy review text perfectly
_VOYAGE_MODEL = "voyage-3-large"

def _get_embeddings() -> VoyageAIEmbeddings:
    """Lazy-init the Voyage AI embedding model (thread-safe singleton)."""
    return VoyageAIEmbeddings(
        voyage_api_key=settings.voyage_api_key,
        model=_VOYAGE_MODEL,
    )


# ── ChromaDB client (persistent, shared) ─────────────────────────────────────
_chroma_client: chromadb.PersistentClient | None = None

def _get_chroma_client() -> chromadb.PersistentClient:
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        logger.info(f"ChromaDB initialized at {CHROMA_DIR}")
    return _chroma_client


# ── Collection naming ──────────────────────────────────────────────────────────
def _collection_name(asin: str) -> str:
    """Stable, safe ChromaDB collection name."""
    return f"asin-v3-{asin.lower()}"


# ── Document chunking ──────────────────────────────────────────────────────────
def _build_documents(product: ProductData, role: str) -> list[Document]:
    """
    Convert ProductData into LangChain Documents for embedding.

    Metadata is rich enough to filter by role (target vs competitor)
    and by chunk_type (listing, review, qa) during retrieval.
    """
    base_meta = {
        "asin": product.asin,
        "role": role,
        "category": product.category,
        "price": float(product.price),
        "rating": float(product.rating or 0.0),
        "review_count": int(product.review_count or 0),
    }
    docs: list[Document] = []

    # 1. Listing chunk — single authoritative product representation
    listing_text = "\n".join(filter(None, [
        f"ASIN: {product.asin}",
        f"Title: {product.title}",
        f"Price: ${product.price:.2f}",
        f"Category: {product.category}",
        f"Rating: {product.rating or 'N/A'} stars ({product.review_count or 0} reviews)",
        "",
        "Key Features and Benefits:",
        *[f"  • {b}" for b in product.bullet_points],
        "",
        "Product Description:",
        product.description[:3000] if product.description else "",
    ]))
    docs.append(Document(
        page_content=listing_text,
        metadata={**base_meta, "chunk_type": "listing"},
    ))

    # 2. Review chunks — individual voice-of-customer signals
    for i, review in enumerate(product.reviews[:100]):
        text = review.strip()
        if not text:
            continue
        docs.append(Document(
            page_content=f"Customer Review #{i + 1}: {text[:1000]}",
            metadata={**base_meta, "chunk_type": "review", "review_index": i},
        ))

    # 3. Q&A chunks — explicit intent signals from shoppers
    for i, qa in enumerate(product.qa[:50]):
        q = qa.get("question", "").strip()
        a = qa.get("answer", "").strip()
        if q or a:
            docs.append(Document(
                page_content=f"Shopper Question: {q}\nSeller/Community Answer: {a[:600]}",
                metadata={**base_meta, "chunk_type": "qa", "qa_index": i},
            ))

    logger.info(
        f"Chunked ASIN {product.asin} ({role}) → {len(docs)} documents "
        f"({sum(1 for d in docs if d.metadata['chunk_type'] == 'listing')} listing, "
        f"{sum(1 for d in docs if d.metadata['chunk_type'] == 'review')} reviews, "
        f"{sum(1 for d in docs if d.metadata['chunk_type'] == 'qa')} Q&A)"
    )
    return docs


# ── Cache helpers ──────────────────────────────────────────────────────────────
def _collection_is_fresh(client: chromadb.PersistentClient, name: str) -> bool:
    """Return True if the collection exists, has data, and is within TTL."""
    try:
        col = client.get_collection(name)
        meta = col.metadata or {}
        indexed_at = float(meta.get("indexed_at", 0))
        return col.count() > 0 and (time.time() - indexed_at) < _TTL_SECONDS
    except Exception:
        return False


# ── Public API ────────────────────────────────────────────────────────────────

def build_or_load_store(product: ProductData, role: str) -> Chroma:
    """
    Build (or load from 24h cache) a LangChain Chroma vector store for one product.
    Uses Voyage AI voyage-3-large embeddings.
    """
    client = _get_chroma_client()
    embeddings = _get_embeddings()
    col_name = _collection_name(product.asin)

    if _collection_is_fresh(client, col_name):
        logger.info(f"Cache hit: loading existing index for {product.asin}")
        return Chroma(
            client=client,
            collection_name=col_name,
            embedding_function=embeddings,
        )

    # Delete stale collection if exists
    try:
        client.delete_collection(col_name)
        logger.info(f"Deleted stale collection: {col_name}")
    except Exception:
        pass

    # Build fresh documents and ingest into Chroma
    logger.info(f"Building new index for {product.asin} (role={role})…")
    documents = _build_documents(product, role)

    # Create collection with metadata for TTL tracking
    # Only set indexed_at if it's a real product, so stubs don't get cached for 24h
    meta = {"asin": product.asin, "role": role}
    if not product.title.startswith("[Extraction failed"):
        meta["indexed_at"] = str(time.time())

    client.create_collection(
        name=col_name,
        metadata=meta,
    )

    store = Chroma.from_documents(
        documents=documents,
        embedding=embeddings,
        client=client,
        collection_name=col_name,
    )
    logger.info(f"Indexed {len(documents)} chunks for ASIN {product.asin}")
    return store


def retrieve_rag_context(
    target: ProductData,
    competitors: list[ProductData],
    query: str,
    top_k: int = 8,
) -> str:
    """
    The core RAG retrieval step.

    For each product (target + competitors):
      1. Build/load a Chroma vector store (Voyage AI embeddings)
      2. Execute semantic similarity search for the shopper query
      3. Retrieve top_k most relevant chunks per product

    Returns a structured XML context string, where only the most query-relevant
    reviews and Q&A items are included — this is the key advantage over static
    aggregation: Claude sees high-signal context, not the full 10,000-token dump.
    """
    context_parts: list[str] = [
        "<context>",
        f"  <user_query>{query}</user_query>",
        "  <instruction>",
        "    You are Amazon's Rufus AI shopping assistant. Evaluate the target product",
        "    against competitors using ONLY the semantically retrieved evidence below.",
        "    Each chunk was selected because it is RELEVANT to the user's query.",
        "    Do not hallucinate facts not present in the context.",
        "  </instruction>",
        "",
    ]

    all_products = [("target", target)] + [
        (f"competitor_{i}", comp) for i, comp in enumerate(competitors, 1)
    ]

    for role, product in all_products:
        try:
            store = build_or_load_store(product, role)
            retriever = store.as_retriever(
                search_type="similarity",
                search_kwargs={"k": top_k},
            )
            docs = retriever.invoke(query)

            if not docs:
                logger.warning(f"No documents retrieved for {product.asin}")
                continue

            # Partition by chunk type
            listing = [d for d in docs if d.metadata.get("chunk_type") == "listing"]
            reviews = [d for d in docs if d.metadata.get("chunk_type") == "review"]
            qa_items = [d for d in docs if d.metadata.get("chunk_type") == "qa"]

            asin = product.asin
            context_parts.append(f'  <product asin="{asin}" role="{role}">')

            # Always include the listing if it was retrieved
            for d in listing:
                context_parts.append(f"    <listing>\n{d.page_content}\n    </listing>")

            # Semantically ranked reviews (most relevant to query first)
            if reviews:
                context_parts.append("    <reviews>")
                for d in reviews[:6]:
                    context_parts.append(f"      <review>{d.page_content}</review>")
                context_parts.append("    </reviews>")

            # Q&A relevant to query intent
            if qa_items:
                context_parts.append("    <qa>")
                for d in qa_items[:4]:
                    context_parts.append(f"      <item>{d.page_content}</item>")
                context_parts.append("    </qa>")

            context_parts.append("  </product>")
            context_parts.append("")

            logger.info(
                f"RAG retrieved for {asin}: {len(listing)} listing, "
                f"{len(reviews)} reviews, {len(qa_items)} Q&A chunks"
            )

        except Exception as e:
            logger.error(f"RAG retrieval failed for {product.asin}: {e}", exc_info=True)
            # Fallback: include raw listing only
            context_parts.append(f'  <product asin="{product.asin}" role="{role}">')
            context_parts.append(f"    <listing>\n{product.title}\n{product.description[:1000]}\n    </listing>")
            context_parts.append("  </product>")
            context_parts.append("")

    context_parts.append("</context>")
    return "\n".join(context_parts)
