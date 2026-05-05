from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Data extraction APIs
    rainforest_api_key: str = ""
    amazon_domain: str = "amazon.com"
    apify_api_token: str = ""
    easyparser_api_key: str = ""

    # AI Inference - Google Gemini (Free Tier)
    # Get free key at: https://aistudio.google.com/
    google_api_key: str

    # Embeddings — Voyage AI (Anthropic's embedding platform)
    # Get free key at: https://www.voyageai.com/
    # Free tier: 50M tokens/month — sufficient for thousands of analyses
    voyage_api_key: str

    # Deployment
    allowed_origins: str = "http://localhost:3000"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()  # type: ignore[call-arg]
