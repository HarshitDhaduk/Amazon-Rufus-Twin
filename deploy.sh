#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# deploy.sh — One-shot Google Cloud Run deployment for Rufus AI Twin
#
# Usage:
#   chmod +x deploy.sh
#   ./deploy.sh
#
# Prerequisites:
#   1. gcloud CLI installed and authenticated: gcloud auth login
#   2. Project set: gcloud config set project YOUR_PROJECT_ID
#   3. APIs enabled (script will enable them if missing)
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

# ── Configuration — Edit these ────────────────────────────────────────────────
PROJECT_ID="${GCP_PROJECT_ID:-amazon-rufus-clone}"
REGION="${GCP_REGION:-asia-south1}"   # Mumbai — closest to amazon.in users

BACKEND_SERVICE="rufus-backend"
FRONTEND_SERVICE="rufus-frontend"

BACKEND_IMAGE="gcr.io/${PROJECT_ID}/${BACKEND_SERVICE}"
FRONTEND_IMAGE="gcr.io/${PROJECT_ID}/${FRONTEND_SERVICE}"

# ── API Keys — Set these before running ───────────────────────────────────────
GOOGLE_API_KEY="${GOOGLE_API_KEY:-}"
VOYAGE_API_KEY="${VOYAGE_API_KEY:-}"
RAINFOREST_API_KEY="${RAINFOREST_API_KEY:-}"
APIFY_API_TOKEN="${APIFY_API_TOKEN:-}"
AMAZON_DOMAIN="${AMAZON_DOMAIN:-amazon.in}"

# ─────────────────────────────────────────────────────────────────────────────
echo "🚀 Rufus AI Twin — Cloud Run Deployment"
echo "   Project : ${PROJECT_ID}"
echo "   Region  : ${REGION}"
echo ""

# Validate required keys
if [[ -z "$GOOGLE_API_KEY" || -z "$VOYAGE_API_KEY" || -z "$RAINFOREST_API_KEY" ]]; then
  echo "❌ Error: Required environment variables not set."
  echo "   Export before running:"
  echo "   export GOOGLE_API_KEY=..."
  echo "   export VOYAGE_API_KEY=..."
  echo "   export RAINFOREST_API_KEY=..."
  exit 1
fi

# Enable required GCP APIs
echo "📦 Enabling GCP APIs..."
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  containerregistry.googleapis.com \
  --project="${PROJECT_ID}" --quiet

# ── Step 1: Build & Deploy Backend ───────────────────────────────────────────
echo ""
echo "🔨 [1/4] Building backend Docker image..."
gcloud builds submit ./backend \
  --tag "${BACKEND_IMAGE}" \
  --project="${PROJECT_ID}"

echo ""
echo "🚢 [2/4] Deploying backend to Cloud Run..."
gcloud run deploy "${BACKEND_SERVICE}" \
  --image "${BACKEND_IMAGE}" \
  --region "${REGION}" \
  --platform managed \
  --allow-unauthenticated \
  --min-instances 1 \
  --max-instances 3 \
  --memory 2Gi \
  --cpu 1 \
  --timeout 3600 \
  --concurrency 10 \
  --set-env-vars "\
GOOGLE_API_KEY=${GOOGLE_API_KEY},\
VOYAGE_API_KEY=${VOYAGE_API_KEY},\
RAINFOREST_API_KEY=${RAINFOREST_API_KEY},\
APIFY_API_TOKEN=${APIFY_API_TOKEN},\
AMAZON_DOMAIN=${AMAZON_DOMAIN},\
ALLOWED_ORIGINS=*" \
  --project="${PROJECT_ID}"

# Get the backend URL
BACKEND_URL=$(gcloud run services describe "${BACKEND_SERVICE}" \
  --region "${REGION}" \
  --project="${PROJECT_ID}" \
  --format="value(status.url)")
echo "✅ Backend deployed at: ${BACKEND_URL}"

# Update CORS to only allow the frontend origin (tightened after frontend deploy)
# For now, ALLOWED_ORIGINS=* is used. We'll update after getting frontend URL.

# ── Step 2: Build & Deploy Frontend ──────────────────────────────────────────
echo ""
echo "🔨 [3/4] Building frontend Docker image (injecting backend URL)..."
gcloud builds submit ./frontend \
  --tag "${FRONTEND_IMAGE}" \
  --substitutions "_NEXT_PUBLIC_API_URL=${BACKEND_URL}" \
  --project="${PROJECT_ID}"

echo ""
echo "🚢 [4/4] Deploying frontend to Cloud Run..."
gcloud run deploy "${FRONTEND_SERVICE}" \
  --image "${FRONTEND_IMAGE}" \
  --region "${REGION}" \
  --platform managed \
  --allow-unauthenticated \
  --min-instances 0 \
  --max-instances 5 \
  --memory 512Mi \
  --cpu 1 \
  --timeout 60 \
  --set-env-vars "NEXT_PUBLIC_API_URL=${BACKEND_URL}" \
  --project="${PROJECT_ID}"

FRONTEND_URL=$(gcloud run services describe "${FRONTEND_SERVICE}" \
  --region "${REGION}" \
  --project="${PROJECT_ID}" \
  --format="value(status.url)")
echo "✅ Frontend deployed at: ${FRONTEND_URL}"

# ── Step 3: Tighten CORS ─────────────────────────────────────────────────────
echo ""
echo "🔒 Tightening CORS to frontend origin only..."
gcloud run services update "${BACKEND_SERVICE}" \
  --region "${REGION}" \
  --update-env-vars "ALLOWED_ORIGINS=${FRONTEND_URL}" \
  --project="${PROJECT_ID}" --quiet

# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════"
echo "✅ Deployment complete!"
echo ""
echo "   Frontend : ${FRONTEND_URL}"
echo "   Backend  : ${BACKEND_URL}/docs"
echo ""
echo "⚠️  Note: First request after cold start will re-index ChromaDB."
echo "   Backend has min-instances=1 to keep it warm between requests."
echo "════════════════════════════════════════════"
