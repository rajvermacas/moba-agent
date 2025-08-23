"""
Configuration management for FastAPI server using Pydantic Settings.
"""

from pydantic import Field
from pydantic_settings import BaseSettings


class FastAPIServerConfig(BaseSettings):
    """Configuration for the FastAPI server."""
    
    # FastAPI Server Configuration
    fastapi_port: int = Field(
        default=8001,
        description="Port for FastAPI server"
    )
    fastapi_host: str = Field(
        default="0.0.0.0",
        description="Host for FastAPI server"
    )
    
    # Logging Configuration
    log_level: str = Field(
        default="INFO",
        description="Logging level"
    )
    
    # CORS Configuration
    allow_cors: bool = Field(
        default=True,
        description="Allow CORS for React frontend"
    )
    
    # OpenAI-compatible settings
    agent_model: str = Field(
        default="gemini-2.5-flash",
        description="Default model name for responses"
    )
    max_tokens: int = Field(
        default=2000,
        description="Maximum tokens for LLM responses"
    )
    temperature: float = Field(
        default=0.7,
        description="Temperature for LLM responses"
    )
    
    # Request timeout settings
    request_timeout: int = Field(
        default=120,
        description="Request timeout in seconds"
    )
    
    # Logging directory configuration
    log_dir: str = Field(
        default="./logs",
        description="Directory for log files"
    )
    
    class Config:
        """Pydantic configuration."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields in environment


# Global configuration instance
config = FastAPIServerConfig()