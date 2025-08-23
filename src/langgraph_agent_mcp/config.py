"""
Configuration module for LangGraph MCP Agent
"""

import os
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


@dataclass
class Config:
    """Configuration for MCP Agent with Gemini"""
    
    # Google Gemini Configuration
    google_api_key: str = field(default_factory=lambda: os.getenv("GOOGLE_API_KEY", ""))
    agent_model: str = field(default_factory=lambda: os.getenv("AGENT_MODEL", "gemini-2.5-flash"))
    agent_temperature: float = field(default_factory=lambda: float(os.getenv("AGENT_TEMPERATURE", "0.1")))
    agent_max_tokens: int = field(default_factory=lambda: int(os.getenv("AGENT_MAX_TOKENS", "4096")))
    
    # MCP Server Configuration
    mcp_server_url: str = field(default_factory=lambda: os.getenv("MCP_SERVER_URL", "http://localhost:8000/sse"))
    mcp_server_name: str = field(default_factory=lambda: os.getenv("MCP_SERVER_NAME", "mherb_mcp_server"))
    mcp_transport: str = field(default_factory=lambda: os.getenv("MCP_TRANSPORT", "sse"))
    
    # SSE Configuration
    sse_reconnect_enabled: bool = field(default_factory=lambda: os.getenv("SSE_RECONNECT_ENABLED", "true").lower() == "true")
    sse_reconnect_max_attempts: int = field(default_factory=lambda: int(os.getenv("SSE_RECONNECT_MAX_ATTEMPTS", "5")))
    sse_reconnect_delay_ms: int = field(default_factory=lambda: int(os.getenv("SSE_RECONNECT_DELAY_MS", "1000")))
    
    # Logging Configuration
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "DEBUG"))
    
    def __post_init__(self):
        """Validate configuration after initialization"""
        self._setup_logging()
        self._validate_config()
    
    def _setup_logging(self):
        """Setup logging configuration"""
        log_levels = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL
        }
        
        level = log_levels.get(self.log_level.upper(), logging.INFO)
        
        # Configure root logger
        logging.basicConfig(
            level=level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Create logger for this module
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(level)
    
    def _validate_config(self):
        """Validate required configuration values"""
        errors = []
        
        if not self.google_api_key:
            errors.append("GOOGLE_API_KEY is required but not set")
        
        if not self.mcp_server_url:
            errors.append("MCP_SERVER_URL is required but not set")
        
        if errors:
            error_msg = "Configuration validation failed:\n" + "\n".join(errors)
            self.logger.error(error_msg)
            raise ValueError(error_msg)
        
        self.logger.info("Configuration loaded successfully")
        self.logger.debug(f"MCP Server URL: {self.mcp_server_url}")
        self.logger.debug(f"Agent Model: {self.agent_model}")
        self.logger.debug(f"Transport: {self.mcp_transport}")
    
    def get_mcp_server_config(self) -> Dict[str, Any]:
        """Get MCP server configuration for MultiServerMCPClient"""
        config = {
            self.mcp_server_name: {
                "transport": self.mcp_transport,
                "url": self.mcp_server_url
            }
        }
        
        # Note: reconnect parameters are not supported by langchain_mcp_adapters for SSE/streamable_http
        # The library handles reconnection internally
        
        self.logger.debug(f"MCP Server config: {config}")
        return config
    
    def get_gemini_config(self) -> Dict[str, Any]:
        """Get Gemini model configuration"""
        return {
            "model": self.agent_model,
            "temperature": self.agent_temperature,
            "max_tokens": self.agent_max_tokens,
            "google_api_key": self.google_api_key
        }