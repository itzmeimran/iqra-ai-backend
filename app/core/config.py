from pydantic_settings import BaseSettings
from typing import List
import os
from dotenv import load_dotenv
load_dotenv()

class Settings(BaseSettings):
    # MongoDB
    mongodb_uri: str = "mongodb://localhost:27017/iqra-ai"
    mongodb_db_name: str = "iqra-ai"

    # JWT
    jwt_access_secret: str = "change-me-access-secret"
    jwt_refresh_secret: str = "change-me-refresh-secret"
    jwt_access_expires_in: int = 15       # minutes
    jwt_refresh_expires_in: int = 10080   # minutes (7 days)

    # Google SSO
    google_client_id: str = ""
    google_client_secret: str = ""

    # LLM
    llm_provider: str = "ollama"
    llm_base_url: str = "http://localhost:11434"
    default_model: str = "gemma4:31b"

    # LangSmith
    langchain_tracing_v2: str = "false"
    langchain_endpoint: str = "https://api.smith.langchain.com"
    langchain_project: str = ""
    langchain_api_key: str = ""

    # App
    app_env: str = "development"
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
