"""
Intent Analysis Service
Uses a lightweight LLM call to extract user-centric shopping context, 
region, and budget parameters from the raw query.
"""
from __future__ import annotations

import logging
from typing import Optional
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field

from config import settings
from models.request import QueryIntent

logger = logging.getLogger(__name__)

INTENT_PROMPT = """Analyze the following Amazon shopper query and extract the specific context.

RULES:
1. Identify the 'region' (e.g., 'India', 'USA', 'Global').
2. Identify 'currency' (e.g., 'INR', 'USD'). If 'rupees' or 'lakh' is mentioned, it's INR.
3. Extract 'budget_constraint' (e.g., 'under 1 lakh', 'budget-friendly', 'premium').
4. List 'priority_features' (e.g., 'gaming', 'long battery', 'indian summer cooling').
5. Define a 'user_persona' (e.g., 'college student', 'family of 5', 'professional editor').
6. Provide a 'shopping_context' summary (e.g., 'Buying a gaming laptop for college in India').

Query: {query}

Return ONLY a JSON object matching the QueryIntent schema."""

def _get_intent_llm() -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=settings.google_api_key,
        temperature=0.0,
    )

async def extract_query_intent(query: str) -> QueryIntent:
    """Analyze query and return structured intent."""
    logger.info(f"Extracting intent for query: {query!r}")
    
    llm = _get_intent_llm()
    messages = [
        SystemMessage(content="You are a linguistic expert specializing in e-commerce intent parsing."),
        HumanMessage(content=INTENT_PROMPT.format(query=query))
    ]
    
    try:
        # Use structured output for reliability
        structured_llm = llm.with_structured_output(QueryIntent)
        intent = await structured_llm.ainvoke(messages)
        
        # Fallback market detection
        if intent.region.lower() == "india" or "inr" in intent.currency.upper():
            intent.detected_market = "amazon.in"
        else:
            intent.detected_market = "amazon.com"
            
        logger.info(f"Intent extracted: region={intent.region}, currency={intent.currency}")
        return intent
    except Exception as e:
        logger.error(f"Failed to extract intent: {e}")
        # Return default safe intent
        return QueryIntent(
            shopping_context=f"General search for: {query}",
            detected_market="amazon.in" if "rupee" in query.lower() or "india" in query.lower() else "amazon.com"
        )
