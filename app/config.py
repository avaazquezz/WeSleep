"""
Configuration settings for WeSleep API.

Using Pydantic BaseSettings to manage environment variables.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    Application settings.

    Attributes:
        PROJECT_NAME: Name of the API project.
        API_V1_STR: Base prefix for API v1.
        SQLITE_URL: Database connection string.
    """
    PROJECT_NAME: str = "WeSleep API"
    API_V1_STR: str = "/api/v1"
    
    # Database
    SQLITE_URL: str = "sqlite+aiosqlite:///./wesleep.db"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        extra="ignore"
    )

settings = Settings()
