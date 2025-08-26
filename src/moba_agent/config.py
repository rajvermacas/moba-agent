"""
Configuration module for LangGraph MCP Agent
"""

import os
import json
import logging
from typing import Dict, Any, List
from dataclasses import dataclass, field
from pathlib import Path
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
    
    # Agent System Prompt
    system_prompt: str = field(
        default_factory=lambda: os.getenv(
            "AGENT_SYSTEM_PROMPT", 
            "You are a database expert who will help write sql query to execute to get the data in table format and then format it to show graph on UI"
        )
    )
    
    # MCP Configuration File Path
    mcp_config_file: str = field(default_factory=lambda: os.getenv("MCP_CONFIG_FILE", "mcp_servers.json"))
    
    # MCP Servers loaded from JSON
    mcp_servers: List[Dict[str, Any]] = field(default_factory=list)
    
    # Logging Configuration
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "DEBUG"))
    
    def __post_init__(self):
        """Validate configuration after initialization"""
        self._setup_logging()
        self._load_mcp_servers()
        self._validate_config()
    
    def _load_mcp_servers(self):
        """Load MCP server configurations from JSON file"""
        config_path = Path(self.mcp_config_file)
        
        # Check if it's an absolute path, otherwise look relative to project root
        if not config_path.is_absolute():
            # Try relative to current working directory first
            if not config_path.exists():
                # Try relative to the config.py file location
                config_path = Path(__file__).parent.parent.parent / self.mcp_config_file
        
        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    config_data = json.load(f)
                    
                # Load MCP servers, filtering only enabled ones
                all_servers = config_data.get('mcp_servers', [])
                self.mcp_servers = [
                    server for server in all_servers 
                    if server.get('enabled', True)
                ]
                
                # Process environment variable substitution
                self._substitute_env_vars()
                
                self.logger.info(f"Loaded {len(self.mcp_servers)} MCP server configurations from {config_path}")
                for server in self.mcp_servers:
                    self.logger.debug(f"Loaded MCP server: {server.get('name')}")
                    
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse JSON config file {config_path}: {e}")
                raise ValueError(f"Invalid JSON in MCP config file: {e}")
            except Exception as e:
                self.logger.error(f"Failed to load MCP config from {config_path}: {e}")
                raise
        else:
            # Fall back to environment variables for backward compatibility
            self.logger.warning(f"MCP config file not found at {config_path}, falling back to environment variables")
            self._load_from_env_vars()
    
    def _substitute_env_vars(self):
        """Substitute environment variables in MCP server configurations"""
        import re
        env_var_pattern = re.compile(r'\$\{([^}]+)\}')
        
        def substitute_in_value(value):
            if isinstance(value, str):
                # Replace ${VAR_NAME} with actual environment variable value
                def replacer(match):
                    var_name = match.group(1)
                    return os.getenv(var_name, match.group(0))
                return env_var_pattern.sub(replacer, value)
            elif isinstance(value, dict):
                return {k: substitute_in_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [substitute_in_value(item) for item in value]
            return value
        
        for server in self.mcp_servers:
            for key, value in server.items():
                server[key] = substitute_in_value(value)
    
    def _load_from_env_vars(self):
        """Load MCP server configuration from environment variables (backward compatibility)"""
        mcp_server_url = os.getenv("MCP_SERVER_URL")
        mcp_server_name = os.getenv("MCP_SERVER_NAME", "mherb_mcp_server")
        mcp_transport = os.getenv("MCP_TRANSPORT", "sse")
        
        if mcp_server_url:
            server_config = {
                "name": mcp_server_name,
                "transport": mcp_transport,
                "url": mcp_server_url,
                "enabled": True
            }
            
            # Add SSE reconnect settings if applicable
            if mcp_transport in ["sse", "streamable_http"]:
                server_config["reconnect"] = {
                    "enabled": os.getenv("SSE_RECONNECT_ENABLED", "true").lower() == "true",
                    "max_attempts": int(os.getenv("SSE_RECONNECT_MAX_ATTEMPTS", "5")),
                    "delay_ms": int(os.getenv("SSE_RECONNECT_DELAY_MS", "1000"))
                }
            
            self.mcp_servers = [server_config]
            self.logger.info("Loaded MCP server configuration from environment variables")
        else:
            # No MCP servers configured at all
            self.mcp_servers = []
            self.logger.warning("No MCP servers configured in environment variables")
    
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
        
        if not self.mcp_servers:
            errors.append("No MCP servers configured. Please check your mcp_servers.json file or environment variables")
        else:
            # Validate each MCP server configuration
            for i, server in enumerate(self.mcp_servers):
                server_name = server.get('name', f'server_{i}')
                
                if not server.get('name'):
                    errors.append(f"MCP server at index {i} is missing 'name' field")
                
                if not server.get('transport'):
                    errors.append(f"MCP server '{server_name}' is missing 'transport' field")
                
                transport = server.get('transport', '')
                if transport in ['sse', 'streamable_http', 'http']:
                    if not server.get('url'):
                        errors.append(f"MCP server '{server_name}' with transport '{transport}' requires 'url' field")
                elif transport == 'stdio':
                    if not server.get('command'):
                        errors.append(f"MCP server '{server_name}' with transport 'stdio' requires 'command' field")
        
        if errors:
            error_msg = "Configuration validation failed:\n" + "\n".join(errors)
            self.logger.error(error_msg)
            raise ValueError(error_msg)
        
        self.logger.info("Configuration loaded successfully")
        self.logger.debug(f"Loaded {len(self.mcp_servers)} MCP servers")
        self.logger.debug(f"Agent Model: {self.agent_model}")
    
    def get_mcp_server_config(self) -> Dict[str, Any]:
        """Get MCP server configuration for MultiServerMCPClient"""
        config = {}
        
        for server in self.mcp_servers:
            server_name = server['name']
            transport = server['transport']
            
            # Build server configuration based on transport type
            server_config = {
                "transport": transport
            }
            
            # Add transport-specific configuration
            if transport in ['sse', 'streamable_http', 'http']:
                server_config["url"] = server["url"]
            elif transport == 'stdio':
                server_config["command"] = server["command"]
                if "args" in server:
                    server_config["args"] = server["args"]
                if "env" in server:
                    server_config["env"] = server["env"]
            
            config[server_name] = server_config
        
        # Note: reconnect parameters are not directly supported by langchain_mcp_adapters
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