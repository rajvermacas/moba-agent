"""
Tests for configuration module
"""

import os
import pytest
from unittest.mock import patch, MagicMock
from src.langgraph_agent_mcp.config import Config


class TestConfig:
    """Test configuration class"""
    
    def test_config_initialization_with_env_vars(self):
        """Test config initialization with environment variables"""
        with patch.dict(os.environ, {
            'GOOGLE_API_KEY': 'test-api-key',
            'MCP_SERVER_URL': 'http://test:8000/mcp',
            'AGENT_MODEL': 'gemini-2.5-flash',
            'LOG_LEVEL': 'INFO'
        }):
            config = Config()
            
            assert config.google_api_key == 'test-api-key'
            assert config.mcp_server_url == 'http://test:8000/mcp'
            assert config.agent_model == 'gemini-2.5-flash'
            assert config.log_level == 'INFO'
    
    def test_config_validation_missing_api_key(self):
        """Test config validation fails with missing API key"""
        with patch.dict(os.environ, {
            'GOOGLE_API_KEY': '',
            'MCP_SERVER_URL': 'http://test:8000/mcp'
        }, clear=True):
            with pytest.raises(ValueError, match="GOOGLE_API_KEY is required"):
                Config()
    
    def test_config_validation_missing_server_url(self):
        """Test config validation fails with missing server URL"""
        with patch.dict(os.environ, {
            'GOOGLE_API_KEY': 'test-key',
            'MCP_SERVER_URL': ''
        }, clear=True):
            with pytest.raises(ValueError, match="MCP_SERVER_URL is required"):
                Config()
    
    def test_get_mcp_server_config(self):
        """Test MCP server configuration generation"""
        with patch.dict(os.environ, {
            'GOOGLE_API_KEY': 'test-key',
            'MCP_SERVER_URL': 'http://test:8000/mcp',
            'MCP_SERVER_NAME': 'test_server',
            'MCP_TRANSPORT': 'streamable_http',
            'SSE_RECONNECT_ENABLED': 'true',
            'SSE_RECONNECT_MAX_ATTEMPTS': '3',
            'SSE_RECONNECT_DELAY_MS': '2000'
        }):
            config = Config()
            server_config = config.get_mcp_server_config()
            
            assert 'test_server' in server_config
            assert server_config['test_server']['transport'] == 'streamable_http'
            assert server_config['test_server']['url'] == 'http://test:8000/mcp'
            assert server_config['test_server']['reconnect']['enabled'] == True
            assert server_config['test_server']['reconnect']['maxAttempts'] == 3
            assert server_config['test_server']['reconnect']['delayMs'] == 2000
    
    def test_get_mcp_server_config_no_reconnect(self):
        """Test MCP server config without reconnection"""
        with patch.dict(os.environ, {
            'GOOGLE_API_KEY': 'test-key',
            'MCP_SERVER_URL': 'http://test:8000/mcp',
            'MCP_TRANSPORT': 'stdio',
            'SSE_RECONNECT_ENABLED': 'false'
        }):
            config = Config()
            server_config = config.get_mcp_server_config()
            
            assert 'reconnect' not in server_config[config.mcp_server_name]
    
    def test_get_gemini_config(self):
        """Test Gemini configuration generation"""
        with patch.dict(os.environ, {
            'GOOGLE_API_KEY': 'test-key',
            'MCP_SERVER_URL': 'http://test:8000/mcp',
            'AGENT_MODEL': 'gemini-2.5-flash',
            'AGENT_TEMPERATURE': '0.5',
            'AGENT_MAX_TOKENS': '2048'
        }):
            config = Config()
            gemini_config = config.get_gemini_config()
            
            assert gemini_config['model'] == 'gemini-2.5-flash'
            assert gemini_config['temperature'] == 0.5
            assert gemini_config['max_tokens'] == 2048
            assert gemini_config['google_api_key'] == 'test-key'
    
    def test_logging_setup(self):
        """Test logging configuration"""
        with patch.dict(os.environ, {
            'GOOGLE_API_KEY': 'test-key',
            'MCP_SERVER_URL': 'http://test:8000/mcp',
            'LOG_LEVEL': 'DEBUG'
        }):
            config = Config()
            
            assert config.logger is not None
            assert config.log_level == 'DEBUG'