# Rufus Twin — Amazon AEO Diagnostics Platform

> Reverse-engineer how Amazon Rufus AI evaluates your product listing. Get a full AEO report card, competitor gap analysis, and market size estimate — powered by Gemini 2.5 Flash + Persona-Driven Pipeline.

---

## 🚀 The Rufus 6-Stage Pipeline

This project implements a high-fidelity digital twin of the production Amazon Rufus architecture:

1.  **Stage 1: Input Assembly** — Synthesis of raw Amazon profile signals into a structured `PersonaContext`.
2.  **Stage 2: Query Planner** — Specialized keyword classifier determines retrieval strategy (<1ms latency).
3.  **Stage 3: COSMO/RAG + UGC** — Semantic retrieval combined with a UGC Contradiction Detector (Review Ground Truth).
4.  **Stage 4: Multi-Model Routing** — Gemini 2.5 Flash orchestrates persona-adjusted inference.
5.  **Stage 5: Speculative Decoding** — High-speed streaming via Gemini API.
6.  **Stage 6: Streaming Hydration** — Real-time SSE delivery: Tokens → Report Card → Market Estimate.

---

## 🛠 Quick Start

### Prerequisites
- Node.js 18+
- Python 3.11+
- **Google API Key** (Gemini 2.5 Flash)
- **Voyage AI API Key** (Embeddings — [free at voyageai.com](https://www.voyageai.com))
- **Apify API Token** (Amazon scraping)

### 1. Backend Setup

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate  # Mac/Linux

pip install -r requirements.txt

# Configure your keys
copy .env.example .env
# Edit .env and set GOOGLE_API_KEY, VOYAGE_API_KEY, APIFY_API_TOKEN

uvicorn main:app --reload --port 8000
```

### 2. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Open: [http://localhost:3000](http://localhost:3000)

---

## 📁 Project Structure

```
project/
├── backend/
│   ├── main.py               # FastAPI entry point
│   ├── services/
│   │   ├── query_planner.py  # Stage 2: Classifier
│   │   ├── ugc_analyzer.py   # Stage 3: Contradiction detection
│   │   ├── persona_synthesizer.py # Stage 1: Persona synthesis
│   │   └── inference.py      # Stage 4: Gemini inference logic
│   └── routers/              # API endpoints
└── frontend/
    ├── app/                  # Next.js App Router
    ├── components/           # UI Components (Glassmorphic)
    └── lib/                  # SSE & API clients
```

## ⚖️ License
MIT
