"""
Fine-Tuning Dataset Generator for Rufus Twin

This script:
1. Extracts real data using Rainforest API
2. Processes it through our exact RAG pipeline (Voyage AI -> ChromaDB)
3. Uses gemini-1.5-pro to generate a "Golden" high-quality response
4. Saves the Input/Output pair as a JSONL line compatible with Google AI Studio fine-tuning.
"""

import asyncio
import json
import logging
import os
from pathlib import Path

# Add project root to python path to import services
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.extractor import extract_asin_data
from services.rag_indexer import retrieve_rag_context
from services.inference import SYSTEM_PROMPT
from config import settings
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
logger = logging.getLogger(__name__)

# List of ASINs to generate training data for
# Add your target ASINs here!
TRAINING_ASINS = [
    "B09XS7JWHH", # Beats Fit Pro
    "B086DKVNND", # Apple AirPods Pro
    "B08C1W5N87", # Sony WH-1000XM4 Headphones
    "B07VGRJDFY", # Nintendo Switch Lite
    "B09B8YG2YW", # Kindle Paperwhite
    "B08FBJ5Q7C", # Amazon Echo Dot
    "B0BX4FBVQB", # LG 655 L Refrigerator
]

USER_QUERY = "Give me a detailed breakdown of this product's features and whether it's a good buy."


async def generate_dataset():
    output_file = Path(__file__).parent.parent / "data" / "finetune_dataset.jsonl"
    output_file.parent.mkdir(exist_ok=True)
    
    # We use the PRO model to generate the "Golden" synthetic training data
    # (Since you mentioned "we will use pro model for this")
    pro_model = ChatGoogleGenerativeAI(
        model="gemini-2.5-pro",
        google_api_key=settings.google_api_key,
        temperature=0.2,
    )
    
    logger.info(f"Starting dataset generation for {len(TRAINING_ASINS)} ASINs...")
    
    with open(output_file, "a", encoding="utf-8") as f:
        for asin in TRAINING_ASINS:
            try:
                logger.info(f"--- Processing {asin} ---")
                
                # 1. Extract real data via Rainforest
                product = await extract_asin_data(asin)
                
                # 2. Get RAG Context (chunks, embeds, caches, and retrieves)
                context_xml = retrieve_rag_context(product, [], USER_QUERY)
                
                # 3. Construct the exact prompt the model will see in production
                full_input = f"{SYSTEM_PROMPT}\n\nContext:\n{context_xml}\n\nUser Query: {USER_QUERY}"
                
                # 4. Generate Golden Output using gemini-1.5-pro
                logger.info(f"Generating Golden response with gemini-1.5-pro...")
                response = await pro_model.ainvoke(full_input)
                golden_output = response.content
                
                # 5. Format for Google AI Studio JSONL
                # {"messages": [{"role": "user", "content": "..."}, {"role": "model", "content": "..."}]}
                row = {
                    "messages": [
                        {"role": "user", "content": full_input},
                        {"role": "model", "content": golden_output}
                    ]
                }
                
                f.write(json.dumps(row) + "\n")
                logger.info(f"Successfully appended {asin} to dataset.")
                
            except Exception as e:
                logger.error(f"Failed to process {asin}: {e}")
                
    logger.info(f"Dataset generation complete! Saved to {output_file}")


if __name__ == "__main__":
    asyncio.run(generate_dataset())
