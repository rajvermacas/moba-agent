"""
Tests for Multi-MCP Server Configuration
"""

import pytest
import json
import os
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
from src.langgraph_agent_mcp.config import Config


class TestMultiMCPConfig:
    """Test Multi-MCP Server Configuration"""
    
    @pytest.fixture
    def sample_json_config(self):
        """Sample JSON configuration with multiple MCP servers"""
        return {
            "mcp_servers": [
                {
                    "name": "server1",
                    "transport": "sse",
                    "url": "http://localhost:8000/sse",
                    "enabled": True
                },
                {
                    "name": "server2",
                    "transport": "stdio",
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-filesystem"],
                    "enabled": True
                },
                {
                    "name": "server3",
                    "transport": "http",
                    "url": "http://localhost:9000/api",
                    "enabled": False
                }
            ]
        }
    
    @pytest.fixture
    def json_config_file(self, tmp_path, sample_json_config):
        """Create a temporary JSON config file"""
        config_file = tmp_path / "mcp_servers.json"
        with open(config_file, 'w') as f:
            json.dump(sample_json_config, f)
        return str(config_file)
    
    def test_load_mcp_servers_from_json(self, json_config_file):
        """Test loading multiple MCP servers from JSON file"""
        with patch.dict('os.environ', {
            'GOOGLE_API_KEY': 'test-key',
            'MCP_CONFIG_FILE': json_config_file
        }):
            config = Config()
            
            # Should load 2 enabled servers (server3 is disabled)
            assert len(config.mcp_servers) == 2
            assert config.mcp_servers[0]['name'] == 'server1'
            assert config.mcp_servers[1]['name'] == 'server2'
    
    def test_get_mcp_server_config_multiple(self, json_config_file):
        """Test get_mcp_server_config returns all servers"""
        with patch.dict('os.environ', {
            'GOOGLE_API_KEY': 'test-key',
            'MCP_CONFIG_FILE': json_config_file
        }):
            config = Config()
            mcp_config = config.get_mcp_server_config()
            
            assert 'server1' in mcp_config
            assert 'server2' in mcp_config
            assert 'server3' not in mcp_config  # disabled
            
            # Check server1 (SSE)
            assert mcp_config['server1']['transport'] == 'sse'
            assert mcp_config['server1']['url'] == 'http://localhost:8000/sse'
            
            # Check server2 (stdio)
            assert mcp_config['server2']['transport'] == 'stdio'
            assert mcp_config['server2']['command'] == 'npx'
            assert mcp_config['server2']['args'] == ['-y', '@modelcontextprotocol/server-filesystem']
    
    def test_environment_variable_substitution(self, tmp_path):
        """Test environment variable substitution in JSON config"""
        config_data = {
            "mcp_servers": [
                {
                    "name": "github_server",
                    "transport": "stdio",
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-github"],
                    "env": {
                        "GITHUB_TOKEN": "${GITHUB_TOKEN}"
                    },
                    "enabled": True
                }
            ]
        }
        
        config_file = tmp_path / "mcp_servers.json"
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
        
        with patch.dict('os.environ', {
            'GOOGLE_API_KEY': 'test-key',
            'MCP_CONFIG_FILE': str(config_file),
            'GITHUB_TOKEN': 'ghp_test_token_123'
        }):
            config = Config()
            
            assert len(config.mcp_servers) == 1
            server = config.mcp_servers[0]
            assert server['env']['GITHUB_TOKEN'] == 'ghp_test_token_123'
    
    def test_fallback_to_env_vars_when_no_json(self):
        """Test fallback to environment variables when JSON doesn't exist"""
        with patch.dict('os.environ', {
            'GOOGLE_API_KEY': 'test-key',
            'MCP_CONFIG_FILE': 'non_existent_file.json',
            'MCP_SERVER_URL': 'http://test-server:8000/sse',
            'MCP_SERVER_NAME': 'env_server',
            'MCP_TRANSPORT': 'sse'
        }):
            config = Config()
            
            assert len(config.mcp_servers) == 1
            assert config.mcp_servers[0]['name'] == 'env_server'
            assert config.mcp_servers[0]['url'] == 'http://test-server:8000/sse'
            assert config.mcp_servers[0]['transport'] == 'sse'
    
    def test_validation_no_servers(self, tmp_path):
        """Test validation fails when no servers are configured"""
        # Point to a non-existent JSON file in a temp directory
        non_existent_file = str(tmp_path / "non_existent.json")
        
        with patch.dict('os.environ', {
            'GOOGLE_API_KEY': 'test-key',
            'MCP_CONFIG_FILE': non_existent_file
        }, clear=True):  # Clear all existing env vars
            with pytest.raises(ValueError, match="No MCP servers configured"):
                Config()
    
    def test_validation_missing_fields(self, tmp_path):
        """Test validation fails for servers with missing required fields"""
        config_data = {
            "mcp_servers": [
                {
                    "name": "invalid_server",
                    "enabled": True
                    # Missing transport field
                }
            ]
        }
        
        config_file = tmp_path / "mcp_servers.json"
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
        
        with patch.dict('os.environ', {
            'GOOGLE_API_KEY': 'test-key',
            'MCP_CONFIG_FILE': str(config_file)
        }):
            with pytest.raises(ValueError, match="missing 'transport' field"):
                Config()
    
    def test_validation_stdio_missing_command(self, tmp_path):
        """Test validation fails for stdio transport without command"""
        config_data = {
            "mcp_servers": [
                {
                    "name": "stdio_server",
                    "transport": "stdio",
                    "enabled": True
                    # Missing command field
                }
            ]
        }
        
        config_file = tmp_path / "mcp_servers.json"
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
        
        with patch.dict('os.environ', {
            'GOOGLE_API_KEY': 'test-key',
            'MCP_CONFIG_FILE': str(config_file)
        }):
            with pytest.raises(ValueError, match="requires 'command' field"):
                Config()
    
    def test_validation_http_missing_url(self, tmp_path):
        """Test validation fails for http transport without URL"""
        config_data = {
            "mcp_servers": [
                {
                    "name": "http_server",
                    "transport": "http",
                    "enabled": True
                    # Missing url field
                }
            ]
        }
        
        config_file = tmp_path / "mcp_servers.json"
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
        
        with patch.dict('os.environ', {
            'GOOGLE_API_KEY': 'test-key',
            'MCP_CONFIG_FILE': str(config_file)
        }):
            with pytest.raises(ValueError, match="requires 'url' field"):
                Config()