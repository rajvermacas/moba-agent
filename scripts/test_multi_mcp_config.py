#!/usr/bin/env python3
"""
Test script to verify multi-MCP server configuration loading
"""

import sys
import os
import json
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from moba_agent.config import Config

def test_json_loading():
    """Test loading MCP servers from JSON file"""
    print("Testing Multi-MCP Configuration Loading")
    print("=" * 50)
    
    try:
        # Initialize config
        config = Config()
        
        print(f"\n✓ Configuration loaded successfully")
        print(f"✓ Number of MCP servers loaded: {len(config.mcp_servers)}")
        
        # Display loaded servers
        print("\nLoaded MCP Servers:")
        print("-" * 30)
        for i, server in enumerate(config.mcp_servers, 1):
            print(f"\n{i}. {server.get('name')}:")
            print(f"   Transport: {server.get('transport')}")
            if server.get('url'):
                print(f"   URL: {server.get('url')}")
            if server.get('command'):
                print(f"   Command: {server.get('command')}")
            if server.get('args'):
                print(f"   Args: {server.get('args')}")
            print(f"   Enabled: {server.get('enabled', True)}")
        
        # Test get_mcp_server_config method
        print("\nMCP Server Configuration for MultiServerMCPClient:")
        print("-" * 30)
        mcp_config = config.get_mcp_server_config()
        print(json.dumps(mcp_config, indent=2))
        
        print("\n✓ All tests passed!")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

def test_env_fallback():
    """Test fallback to environment variables when JSON doesn't exist"""
    print("\n\nTesting Environment Variable Fallback")
    print("=" * 50)
    
    # Temporarily rename the JSON file
    json_path = Path("mcp_servers.json")
    temp_path = Path("mcp_servers.json.bak")
    
    try:
        if json_path.exists():
            json_path.rename(temp_path)
        
        # Set environment variables
        os.environ["MCP_SERVER_URL"] = "http://test-server:8000/sse"
        os.environ["MCP_SERVER_NAME"] = "test_env_server"
        os.environ["MCP_TRANSPORT"] = "sse"
        
        # Initialize config
        config = Config()
        
        print(f"✓ Fallback to environment variables successful")
        print(f"✓ Number of MCP servers loaded: {len(config.mcp_servers)}")
        
        if config.mcp_servers:
            server = config.mcp_servers[0]
            print(f"\nLoaded server from env:")
            print(f"  Name: {server.get('name')}")
            print(f"  Transport: {server.get('transport')}")
            print(f"  URL: {server.get('url')}")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Restore the JSON file
        if temp_path.exists():
            temp_path.rename(json_path)
        
        # Clean up env vars
        os.environ.pop("MCP_SERVER_URL", None)
        os.environ.pop("MCP_SERVER_NAME", None)
        os.environ.pop("MCP_TRANSPORT", None)

if __name__ == "__main__":
    success = test_json_loading()
    if success:
        test_env_fallback()