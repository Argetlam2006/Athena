"""
shared/config/settings.py — Production Configuration Loader.
"""

import os

from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()


class Settings:
    """Central configuration class."""

    # Environment
    ATHENA_ENV: str = os.getenv("ATHENA_ENV", "development")

    # Provider Settings
    ATHENA_PROVIDER: str = os.getenv("ATHENA_PROVIDER", "auto")

    # API Keys
    ANTHROPIC_API_KEY: str | None = os.getenv("ANTHROPIC_API_KEY")
    OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY")
    GEMINI_API_KEY: str | None = os.getenv("GEMINI_API_KEY")
    NVIDIA_API_KEY: str | None = os.getenv("NVIDIA_API_KEY")
    GEMINI_MODEL: str | None = os.getenv("GEMINI_MODEL")

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    @property
    def is_production(self) -> bool:
        return self.ATHENA_ENV.lower() == "production"

    @property
    def is_demo(self) -> bool:
        return self.ATHENA_ENV.lower() == "demo"


# Global settings instance
settings = Settings()
