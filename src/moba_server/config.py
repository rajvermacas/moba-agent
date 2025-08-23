"""
Configuration management for FastAPI server using Pydantic Settings.
"""

from typing import Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class FastAPIServerConfig(BaseSettings):
    """Configuration for the FastAPI server."""
    
    # LLM Provider Configuration
    llm_provider: str = Field(
        default="openrouter",
        description="LLM provider to use (openrouter, gemini)"
    )
    
    # OpenRouter API Configuration
    openrouter_api_key: Optional[str] = Field(
        default=None,
        description="OpenRouter API key for LLM access"
    )
    openrouter_model: str = Field(
        default="qwen/qwen3-coder:free",
        description="OpenRouter model to use"
    )
    
    # Google Gemini API Configuration
    gemini_api_key: Optional[str] = Field(
        default=None,
        description="Google Gemini API key for LLM access"
    )
    gemini_model: str = Field(
        default="gemini-pro",
        description="Google Gemini model to use"
    )
    
    # MCP Server Configuration
    mcp_server_url: str = Field(
        default="http://localhost:8000",
        description="URL of the MCP server"
    )
    mcp_transport: str = Field(
        default="sse",
        description="Transport protocol for MCP connection (stdio or http)"
    )
    
    # FastAPI Server Configuration
    fastapi_port: int = Field(
        default=8001,
        description="Port for FastAPI server"
    )
    fastapi_host: str = Field(
        default="0.0.0.0",
        description="Host for FastAPI server"
    )
    
    # Database Configuration (for MCP server reference)
    database_path: str = Field(
        default="test_data/sample.db",
        description="Path to SQLite database"
    )
    metadata_path: str = Field(
        default="resources/metadata.json",
        description="Path to metadata file"
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
    
    # Optional: Site information for OpenRouter
    site_url: Optional[str] = Field(
        default="http://localhost:8001",
        description="Site URL for OpenRouter rankings"
    )
    site_name: Optional[str] = Field(
        default="Talk2Tables FastAPI Server",
        description="Site name for OpenRouter rankings"
    )
    
    # OpenAI-compatible settings
    max_tokens: int = Field(
        default=2000,
        description="Maximum tokens for LLM responses"
    )
    temperature: float = Field(
        default=0.7,
        description="Temperature for LLM responses"
    )
    
    # Timeout Configuration
    agent_execution_timeout: int = Field(
        default=120,
        description="Maximum execution time in seconds for agent operations"
    )
    llm_request_timeout: int = Field(
        default=120,
        description="Timeout in seconds for LLM API requests"
    )
    api_request_timeout: int = Field(
        default=120,
        description="Timeout in seconds for general API requests"
    )
    
    # Retry and Rate Limiting Configuration
    max_retries: int = Field(
        default=3,
        description="Maximum number of retry attempts for API calls"
    )
    initial_retry_delay: float = Field(
        default=1.0,
        description="Initial delay in seconds before first retry"
    )
    max_retry_delay: float = Field(
        default=30.0,
        description="Maximum delay in seconds between retries"
    )
    retry_backoff_factor: float = Field(
        default=2.0,
        description="Exponential backoff factor for retry delays"
    )
    
    @field_validator("mcp_transport")
    @classmethod
    def validate_transport(cls, v: str) -> str:
        """Validate MCP transport protocol."""
        if v not in ["stdio", "http", "sse"]:
            raise ValueError("MCP transport must be 'stdio', 'http', or 'sse'")
        return v
    
    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate logging level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of: {valid_levels}")
        return v.upper()
    
    @field_validator("llm_provider")
    @classmethod
    def validate_llm_provider(cls, v: str) -> str:
        """Validate LLM provider is supported."""
        valid_providers = ["openrouter", "gemini"]
        if v not in valid_providers:
            raise ValueError(f"LLM provider must be one of: {valid_providers}")
        return v
    
    @field_validator("openrouter_api_key")
    @classmethod
    def validate_openrouter_api_key(cls, v: Optional[str], info) -> Optional[str]:
        """Validate OpenRouter API key is provided when using OpenRouter."""
        # Get the provider from data or environment
        provider = info.data.get("llm_provider")
        if provider is None:
            # Check environment variable if not in data
            import os
            provider = os.getenv("LLM_PROVIDER", "openrouter")
        
        if provider == "openrouter":
            if not v or v == "your_openrouter_api_key_here":
                raise ValueError("OpenRouter API key must be provided when using openrouter provider")
        return v
    
    @field_validator("gemini_api_key")
    @classmethod
    def validate_gemini_api_key(cls, v: Optional[str], info) -> Optional[str]:
        """Validate Gemini API key is provided when using Gemini."""
        # Get the provider from data or environment
        provider = info.data.get("llm_provider")
        if provider is None:
            # Check environment variable if not in data
            import os
            provider = os.getenv("LLM_PROVIDER", "openrouter")
        
        if provider == "gemini":
            if not v or v == "your_gemini_api_key_here":
                raise ValueError("Gemini API key must be provided when using gemini provider")
        return v
    
    @field_validator("max_retries")
    @classmethod
    def validate_max_retries(cls, v: int) -> int:
        """Validate max retries is reasonable."""
        if v < 0 or v > 10:
            raise ValueError("Max retries must be between 0 and 10")
        return v
    
    @field_validator("initial_retry_delay")
    @classmethod
    def validate_initial_retry_delay(cls, v: float) -> float:
        """Validate initial retry delay is positive."""
        if v <= 0:
            raise ValueError("Initial retry delay must be positive")
        return v
    
    @field_validator("max_retry_delay")
    @classmethod
    def validate_max_retry_delay(cls, v: float) -> float:
        """Validate max retry delay is reasonable."""
        if v <= 0 or v > 300:  # Max 5 minutes
            raise ValueError("Max retry delay must be between 0 and 300 seconds")
        return v
    
    @field_validator("retry_backoff_factor")
    @classmethod
    def validate_retry_backoff_factor(cls, v: float) -> float:
        """Validate backoff factor is reasonable."""
        if v < 1.0 or v > 5.0:
            raise ValueError("Retry backoff factor must be between 1.0 and 5.0")
        return v
    
    @field_validator("agent_execution_timeout", "llm_request_timeout", "api_request_timeout")
    @classmethod
    def validate_timeouts(cls, v: int) -> int:
        """Validate timeout values are reasonable."""
        if v < 10 or v > 600:  # Between 10 seconds and 10 minutes
            raise ValueError("Timeout must be between 10 and 600 seconds")
        return v
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields like TRANSPORT which is for MCP server


# Global configuration instance
config = FastAPIServerConfig()