# Rufus Twin — Backend

FastAPI service orchestrating the Rufus 6-Stage inference pipeline.

## 🏗 Key Services

### Stage 1: Persona Synthesizer
`services/persona_synthesizer.py`
Synthesizes raw Amazon profile signals (scraped via Apify) into a `PersonaContext`. It determines:
- **Budget Tier**: (Budget, Mid, Premium)
- **Quality Sensitivity**: (High, Low)
- **Key Constraints**: (Price, Quality, Speed, Eco)

### Stage 2: Query Planner
`services/query_planner.py`
A high-speed keyword classifier that determines the `QueryType` (Factual, Comparison, Planning, Agentic). It decides the RAG depth and output emphasis.

### Stage 3: COSMO RAG + UGC Analyzer
- `services/rag_indexer.py`: Semantic retrieval using Voyage AI `voyage-3` embeddings and ChromaDB.
- `services/ugc_analyzer.py`: **The UGC Override rule.** Scans reviews for claims that contradict the listing. If >10% of reviews contradict a marketing claim, it injects a `<UGCContradictions>` block into the prompt.

### Stage 4: Inference Engine
`services/inference.py`
Uses Gemini 2.5 Flash via LangChain to generate the final recommendation. It injects the `PersonaContext` XML and `UGCContradictions` directly into the Human turn for maximum context adherence.

---

## 🛠 Setup

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Environment Variables**:
   See `.env.example`. Required:
   - `GOOGLE_API_KEY`: For Gemini 2.5 Flash.
   - `VOYAGE_API_KEY`: For embeddings.
   - `APIFY_API_TOKEN`: For Amazon scraping.

3. **Run Server**:
   ```bash
   uvicorn main:app --reload --port 8000
   ```

## 📡 API Overview

- `POST /analyze/stream`: The main SSE endpoint. Emits `persona`, `query_plan`, `token`, `report_card`, and `market_estimate` events.
- `POST /profile/extract`: Standalone endpoint to preview persona synthesis from an Amazon profile URL.
